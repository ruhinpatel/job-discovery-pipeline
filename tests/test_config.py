import json
import shutil
from pathlib import Path

from pipeline import config
from pipeline.candidate_queue import build_queue, main as queue_main

DATA = Path(__file__).parent.parent / "data"


def test_data_dir_precedence(monkeypatch, tmp_path):
    monkeypatch.delenv(config.ENV_DATA_DIR, raising=False)
    assert config.resolve_data_dir() == config.DEFAULT_DATA_DIR
    monkeypatch.setenv(config.ENV_DATA_DIR, str(tmp_path / "env"))
    assert config.resolve_data_dir() == tmp_path / "env"
    assert config.resolve_data_dir(str(tmp_path / "cli")) == tmp_path / "cli"


def test_profile_precedence(monkeypatch, tmp_path):
    monkeypatch.delenv(config.ENV_PROFILE, raising=False)
    assert config.profile_path(tmp_path) == tmp_path / "profile.json"
    monkeypatch.setenv(config.ENV_PROFILE, str(tmp_path / "env.json"))
    assert config.profile_path(tmp_path) == tmp_path / "env.json"
    assert config.profile_path(tmp_path, str(tmp_path / "cli.json")) == tmp_path / "cli.json"


def test_defaults_are_repo_anchored_not_cwd_relative():
    from pipeline.ledger import DEFAULT_LEDGER_PATH
    from pipeline.scorer import DEFAULT_POSTINGS_PATH, DEFAULT_PROFILE_PATH
    for p in (DEFAULT_LEDGER_PATH, DEFAULT_POSTINGS_PATH, DEFAULT_PROFILE_PATH):
        assert p.is_absolute()
        assert p.parent == config.DEFAULT_DATA_DIR


def test_queue_reads_from_resolved_dir_not_hardcoded(tmp_path):
    copy = tmp_path / "mydata"
    shutil.copytree(DATA, copy)
    default = build_queue()
    moved = build_queue(config.postings_path(copy), config.profile_path(copy),
                        config.ledger_path(copy))
    assert [r["url"] for r in moved["queue"]] == [r["url"] for r in default["queue"]]
    # Prove it really reads the copy: emptying the copied ledger changes the result.
    config.ledger_path(copy).write_text("fingerprint,company,title,status,resolved_date,url\n")
    assert build_queue(config.postings_path(copy), config.profile_path(copy),
                       config.ledger_path(copy))["suppressed_count"] == 0


def test_cli_data_dir_flag_end_to_end(tmp_path, capsys):
    copy = tmp_path / "mydata"
    shutil.copytree(DATA, copy)
    queue_main(["--data-dir", str(copy)])
    out = capsys.readouterr().out
    assert "in queue" in out


def test_profile_example_matches_profile_schema():
    example = json.loads((DATA / "profile.example.json").read_text(encoding="utf-8"))
    real = json.loads((DATA / "profile.json").read_text(encoding="utf-8"))
    assert set(example) == set(real)


def test_live_greenhouse_flag_writes_separate_file_and_leaves_demo(tmp_path, capsys, monkeypatch):
    from pipeline.adapters.greenhouse_live import GreenhouseLiveAdapter
    payload = {"jobs": [{"title": "Backend Engineer", "absolute_url": "https://x.test/1",
                         "location": {"name": "Remote - US"},
                         "content": "&lt;p&gt;Python and Go, 0-2 years&lt;/p&gt;"}]}
    monkeypatch.setattr(GreenhouseLiveAdapter, "_get", lambda self, url: json.dumps(payload))
    copy = tmp_path / "d"
    shutil.copytree(DATA, copy)
    before = (copy / "postings.csv").read_text(encoding="utf-8")
    queue_main(["--data-dir", str(copy), "--live-greenhouse", "acme"])
    assert "1 postings" in capsys.readouterr().out
    assert (copy / "postings_live.csv").exists()
    assert (copy / "postings.csv").read_text(encoding="utf-8") == before


def test_missing_inputs_give_clear_message_not_traceback(tmp_path):
    import pytest
    with pytest.raises(SystemExit) as exc:
        queue_main(["--data-dir", str(tmp_path)])
    msg = str(exc.value)
    assert "Missing input" in msg and "--live-greenhouse" in msg
