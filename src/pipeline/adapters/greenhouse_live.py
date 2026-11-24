"""Live Greenhouse public-board adapter (opt-in).

Unlike the other adapters, `fetch_raw` here makes a real network call to the
public, no-auth Greenhouse board API:

    https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

That payload is already the shape `JobBoardsAdapter.normalize` consumes, so
this subclass only overrides `fetch_raw`: it fetches each board and reshapes
the real fields that differ from the synthetic fixture. `normalize` is
inherited unchanged.

This adapter is deliberately NOT in `ingest.ALL_ADAPTERS`, so the committed
demo (`data/postings.csv`) stays reproducible from the synthetic fixtures.

Real boards expose no sponsorship, clearance, or referral flag, so every live
row gets the safe defaults (sponsorship_offered=True, requires_clearance=False,
referral=False). That means sponsorship is UNKNOWN for live rows: the human
review step is where that call gets made, not this adapter.
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from typing import Any, Callable

from pipeline.adapters.job_boards import JobBoardsAdapter

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/{token}"
USER_AGENT ="job-discovery-pipeline/0.1"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_content(raw: str) -> str:
    """Real `content` is HTML-escaped HTML: unescape, strip tags, collapse space."""
    text = html.unescape(raw or "")  # pass 1: "&lt;p&gt;" -> "<p>"
    text = _TAG_RE.sub(" ", text)
    # pass 2: entities in the text itself ("&amp;amp;" -> "&amp;" -> "&")
    return _WS_RE.sub(" ", html.unescape(text)).strip()


class GreenhouseLiveAdapter(JobBoardsAdapter):
    source_name = "greenhouse_live"

    def __init__(
        self,
        board_tokens: list[str],
        display_names: dict[str, str] | None = None,
        timeout: float = 10,
        get: Callable[[str], str] | None = None,
    ) -> None:
        """board_tokens: Greenhouse board slugs (e.g. "stripe").
        display_names: optional {token: "Company Name"}; falls back to the token.
        get: injectable fetch seam (url -> response text) so tests stay offline.
        """
        super().__init__()
        self.board_tokens = list(board_tokens)
        self.display_names = display_names or {}
        self.timeout = timeout
        self._get_override = get

    def build_request(self, url: str) -> urllib.request.Request:
        # Generic UA only: no personal details in any request header or URL.
        return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    def _get(self, url: str) -> str:
        if self._get_override is not None:
            return self._get_override(url)
        with urllib.request.urlopen(self.build_request(url), timeout=self.timeout) as resp:
            return resp.read().decode("utf-8")

    def _company_name(self, token: str) -> str:
        """Explicit display_names override > board metadata `name` > the token.

        The real name matters beyond looks: the ledger fingerprint does not join
        words, so token "tidewatersoftware" would never match "Tidewater Software".
        """
        if token in self.display_names:
            return self.display_names[token]
        try:
            name = json.loads(self._get(BOARD_URL.format(token=token))).get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except Exception:
            pass  # metadata is best-effort; fall back to the token
        return token

    def _reshape(self, job: dict, company: str) -> dict:
        # Reconcile real-vs-fixture differences here, not in normalize():
        #  - company is not on the job; the board metadata (or token) supplies it
        #  - location is nested {"name": ...} on real boards, flat in the fixture
        #  - content is escaped HTML
        loc = job.get("location")
        location = loc.get("name", "") if isinstance(loc, dict) else (loc or "")
        return {
            "title": job.get("title") or "",
            "company": {"name": company},
            "absolute_url": job.get("absolute_url") or "",
            "content": clean_content(job.get("content", "")),
            "location": location,
        }

    def fetch_raw(self) -> list[Any]:
        out: list[dict] = []
        for token in self.board_tokens:
            try:
                payload = json.loads(self._get(API_URL.format(token=token)))
                jobs = payload.get("jobs") or []
            except Exception:
                # A live source being down must not take the pipeline down.
                continue
            company = self._company_name(token)
            out.extend(self._reshape(j, company) for j in jobs)
        return out
