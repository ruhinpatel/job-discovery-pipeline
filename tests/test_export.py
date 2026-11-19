"""Export tests: shape and reconciliation only, no hard-coded demo counts."""

import json

from pipeline import export_demo
from pipeline.export_demo import build_export

TOP_KEYS = {"disclaimer", "summary", "queue", "gated", "sources", "routing_tiers"}
ROW_TYPES = {"rank": int, "score": float, "company": str, "title": str,
             "matched_skills": list, "min_years_experience": int, "url": str,
             "lane": int, "lane_name": str, "lane_reason": str}


def test_top_level_keys():
    assert set(build_export()) == TOP_KEYS


def test_summary_reconciles():
    s = build_export()["summary"]
    assert (s["resolved_suppressed"] + s["gated"] + s["in_batch_duplicates"]
            + s["in_queue"]) == s["total"]
    assert s["in_queue"] == len(build_export()["queue"])


def test_sources_sum_to_total():
    data = build_export()
    assert sum(s["count"] for s in data["sources"]) == data["summary"]["total"]


def test_queue_sorted_desc_and_ranked():
    q = build_export()["queue"]
    assert [r["score"] for r in q] == sorted((r["score"] for r in q), reverse=True)
    assert [r["rank"] for r in q] == list(range(1, len(q) + 1))


def test_queue_row_shape():
    for row in build_export()["queue"]:
        assert set(row) == set(ROW_TYPES)
        for key, typ in ROW_TYPES.items():
            assert isinstance(row[key], typ), key
        assert all(isinstance(s, str) for s in row["matched_skills"])


def test_sources_and_routing():
    data = build_export()
    assert len(data["sources"]) == 4
    assert all(isinstance(s["name"], str) and isinstance(s["count"], int) for s in data["sources"])
    assert data["routing_tiers"]
    assert all({"task", "model_tier", "note"} == set(t) for t in data["routing_tiers"])


def test_main_writes_js_global(tmp_path, monkeypatch):
    out = tmp_path / "docs" / "demo_data.js"
    monkeypatch.setattr(export_demo, "OUTPUT_PATH", out)
    export_demo.main()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("window.DEMO_DATA = ") and text.rstrip().endswith(";")
    assert json.loads(text[len("window.DEMO_DATA = "):].rstrip().rstrip(";")) == build_export()


def test_gated_section_shape_and_reconciliation():
    data = build_export()
    gated = data["gated"]
    assert gated["count"] == len(gated["rows"]) == data["summary"]["gated"]
    assert gated["count"] > 0
    for row in gated["rows"]:
        assert set(row) == {"company", "title", "url", "failed_gate", "reason"}
        assert row["failed_gate"] in {"min_yoe", "work_authorization", "clearance", "location"}
        assert row["reason"]


def test_queue_rows_carry_lane_reason():
    for row in build_export()["queue"]:
        assert row["lane_reason"]


def test_queue_lanes_are_valid_and_spread():
    q = build_export()["queue"]
    assert {r["lane"] for r in q} <= {0, 1, 2}
    assert all(r["lane_name"] for r in q)
    assert len({r["lane"] for r in q}) > 1  # demo shows more than one recommendation
