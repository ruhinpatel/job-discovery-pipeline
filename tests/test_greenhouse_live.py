import json
from unittest import mock

from pipeline.adapters.base import CANONICAL_KEYS
from pipeline.adapters.greenhouse_live import API_URL, USER_AGENT, GreenhouseLiveAdapter
from pipeline.adapters.ingest import ALL_ADAPTERS

# Trimmed real-shape payload: HTML-escaped content, nested location, no yoe
# metadata, no sponsorship/clearance/referral flags. Fake company + .test URLs.
SAMPLE = {
    "jobs": [
        {
            "title": "Backend Engineer, New Grad",
            "absolute_url": "https://boards.example.test/acme/jobs/1",
            "location": {"name": "Remote - US"},
            "content": "&lt;p&gt;Build APIs &amp;amp; services.&lt;/p&gt;"
                       "&lt;ul&gt;&lt;li&gt;0-2 years of experience&lt;/li&gt;&lt;/ul&gt;",
        },
        {
            "title": "Platform Engineer",
            "absolute_url": "https://boards.example.test/acme/jobs/2",
            "location": {"name": "New York, NY"},
            "content": "&lt;p&gt;3+ years required, 5+ years preferred.&lt;/p&gt;",
        },
    ]
}


def _adapter(**kw):
    return GreenhouseLiveAdapter(["acme"], get=lambda url: json.dumps(SAMPLE), **kw)


def test_run_yields_canonical_rows():
    rows = _adapter(display_names={"acme": "Acme Corp"}).run()
    assert len(rows) == 2
    for row in rows:
        assert set(row) == set(CANONICAL_KEYS)
    first = rows[0]
    assert first["company"] == "Acme Corp"
    assert first["location"] == "Remote - US"
    assert "<" not in first["description"] and "&lt;" not in first["description"]
    assert "Build APIs & services." in first["description"]
    assert first["min_years_experience"] == 0   # "0-2 years" -> floor 0
    assert rows[1]["min_years_experience"] == 3  # smallest of 3+/5+


def test_safe_boolean_defaults_and_company_fallback():
    rows = _adapter().run()
    assert rows[0]["company"] == "acme"  # no display name -> token
    for r in rows:
        assert r["sponsorship_offered"] is True
        assert r["requires_clearance"] is False
        assert r["referral"] is False


def test_get_builds_url_and_generic_user_agent():
    adapter = GreenhouseLiveAdapter(["acme"])
    url = API_URL.format(token="acme")
    assert url == "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"
    req = adapter.build_request(url)
    assert req.full_url == url
    assert req.get_header("User-agent") == USER_AGENT
    # _get opens that request with the configured timeout; no real socket.
    fake = mock.MagicMock()
    fake.__enter__.return_value.read.return_value = b"{}"
    with mock.patch("urllib.request.urlopen", return_value=fake) as op:
        assert adapter._get(url) == "{}"
    assert op.call_args.kwargs["timeout"] == adapter.timeout


def test_failing_board_is_skipped_others_still_return():
    def get(url):
        if "/bad/" in url:
            raise OSError("boom")
        return json.dumps(SAMPLE)

    rows = GreenhouseLiveAdapter(["bad", "acme"], get=get).run()
    assert len(rows) == 2


def test_not_registered_in_default_adapters():
    assert GreenhouseLiveAdapter not in ALL_ADAPTERS
