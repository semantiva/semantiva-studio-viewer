# Copyright 2025 Semantiva authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for multi-run SER support in studio viewer."""

import json
import pytest
from semantiva_studio_viewer.ser_index import MultiSERIndex, SERIndex


def _ser(rec):
    """Helper to serialize SER records."""
    return json.dumps(rec)


def test_multi_ser_groups_runs(tmp_path):
    """Test that MultiSERIndex correctly groups records by run_id."""
    p = tmp_path / "multi.jsonl"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z", "end": "2025-01-01T00:00:02Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "r2", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:03Z", "end": "2025-01-01T00:00:04Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:05Z", "end": "2025-01-01T00:00:06Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert {r["run_id"] for r in listed} == {"r1", "r2"}
    assert len(m.by_run) == 2
    assert m.get("r1").total_events == 2
    assert m.get("r2").total_events == 1
    # default run should be deterministic
    assert m.default_run_id() in {"r1", "r2"}


def test_multi_ser_json_array(tmp_path):
    """Test that MultiSERIndex can handle JSON array format."""
    p = tmp_path / "multi.json"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "r2", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:03Z"},
            "status": "completed",
        },
    ]
    p.write_text(json.dumps(runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"r1", "r2"}


def test_multi_ser_legacy_run_id(tmp_path):
    """Test that MultiSERIndex handles legacy run_id format."""
    p = tmp_path / "legacy.jsonl"
    runs = [
        {
            "type": "ser",
            "run_id": "legacy1",
            "pipeline_id": "p",
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "run_id": "legacy2",
            "pipeline_id": "p",
            "timing": {"start": "2025-01-01T00:00:03Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"legacy1", "legacy2"}


def test_multi_ser_single_run_fallback(tmp_path):
    """Test that MultiSERIndex handles single run correctly."""
    p = tmp_path / "single.jsonl"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "single", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 1
    assert listed[0]["run_id"] == "single"
    assert m.default_run_id() == "single"


def test_multi_ser_api_surface(tmp_path):
    """Test MultiSERIndex API methods."""
    p = tmp_path / "api.jsonl"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p", "node_id": "node1"},
            "timing": {"start": "2025-01-01T00:00:01Z", "end": "2025-01-01T00:00:02Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "r2", "pipeline_id": "p", "node_id": "node1"},
            "timing": {"start": "2025-01-01T00:00:03Z", "end": "2025-01-01T00:00:04Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))

    # Test get method
    ser1 = m.get("r1")
    ser2 = m.get("r2")
    assert isinstance(ser1, SERIndex)
    assert isinstance(ser2, SERIndex)
    assert ser1.run_id == "r1"
    assert ser2.run_id == "r2"

    # Test get_meta method
    meta1 = m.get_meta("r1")
    meta2 = m.get_meta("r2")
    assert meta1["run_id"] == "r1"
    assert meta2["run_id"] == "r2"

    # Test summary method
    summary1 = m.summary("r1")
    summary2 = m.summary("r2")
    assert "nodes" in summary1
    assert "nodes" in summary2

    # Test node_events method
    events1 = m.node_events("r1", "node1", 0, 10)
    events2 = m.node_events("r2", "node1", 0, 10)
    assert "events" in events1
    assert "events" in events2


def test_multi_ser_run_not_found(tmp_path):
    """Test MultiSERIndex error handling for missing runs."""
    p = tmp_path / "error.jsonl"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))

    with pytest.raises(KeyError, match="Run not found: nonexistent"):
        m.get("nonexistent")

    with pytest.raises(KeyError, match="Run not found: nonexistent"):
        m.get_meta("nonexistent")


def test_multi_ser_unknown_run_id(tmp_path):
    """Test MultiSERIndex handles records without run_id."""
    p = tmp_path / "unknown.jsonl"
    runs = [
        {
            "type": "ser",
            "pipeline_id": "p",
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 1
    assert listed[0]["run_id"] == "unknown"


def test_multi_ser_timing_aggregation(tmp_path):
    """Test that timing information is correctly aggregated per run."""
    p = tmp_path / "timing.jsonl"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z", "end": "2025-01-01T00:00:02Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:00Z", "end": "2025-01-01T00:00:03Z"},
            "status": "completed",
        },  # Earlier start, later end
        {
            "type": "ser",
            "ids": {"run_id": "r2", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:05Z", "end": "2025-01-01T00:00:06Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    r1_meta = next(r for r in listed if r["run_id"] == "r1")
    r2_meta = next(r for r in listed if r["run_id"] == "r2")

    # r1 should have earliest start and latest end
    assert r1_meta["started_at"] == "2025-01-01T00:00:00Z"
    assert r1_meta["ended_at"] == "2025-01-01T00:00:03Z"
    assert r1_meta["total_events"] == 2

    # r2 should have its own timing
    assert r2_meta["started_at"] == "2025-01-01T00:00:05Z"
    assert r2_meta["ended_at"] == "2025-01-01T00:00:06Z"
    assert r2_meta["total_events"] == 1


def test_multi_ser_run_ordering(tmp_path):
    """Test that runs are ordered by started_at then run_id."""
    p = tmp_path / "ordering.jsonl"
    runs = [
        {
            "type": "ser",
            "ids": {"run_id": "z_run", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "a_run", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:03Z"},
            "status": "completed",
        },
        {
            "type": "ser",
            "ids": {"run_id": "b_run", "pipeline_id": "p"},
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },  # Same time as z_run
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    # Should be ordered by started_at, then by run_id
    expected_order = [
        "b_run",
        "z_run",
        "a_run",
    ]  # b_run and z_run both at 00:00:01Z, so b_run comes first alphabetically
    actual_order = [r["run_id"] for r in listed]
    assert actual_order == expected_order


def test_multi_ser_mixed_record_types(tmp_path):
    """Test that MultiSERIndex handles mixed record types correctly."""
    p = tmp_path / "mixed.jsonl"
    records = [
        {"type": "pipeline_start", "run_id": "r1", "pipeline_id": "p"},
        {
            "type": "ser",
            "ids": {"run_id": "r1", "pipeline_id": "p", "node_id": "node1"},
            "timing": {"start": "2025-01-01T00:00:01Z"},
            "status": "completed",
        },
        {"type": "pipeline_end", "run_id": "r1", "pipeline_id": "p"},
        {
            "type": "ser",
            "ids": {"run_id": "r2", "pipeline_id": "p", "node_id": "node1"},
            "timing": {"start": "2025-01-01T00:00:03Z"},
            "status": "completed",
        },
    ]
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"r1", "r2"}

    # r1 should have processed both pipeline_start and ser records
    r1_index = m.get("r1")
    assert r1_index.pipeline_id == "p"
    assert r1_index.total_events == 3  # pipeline_start + ser + pipeline_end


def test_multi_ser_complex_ser_records(tmp_path):
    """Test MultiSERIndex with complex SER records including checks and args."""
    p = tmp_path / "complex.jsonl"
    records = [
        {
            "type": "ser",
            "ids": {"run_id": "complex1", "pipeline_id": "p", "node_id": "node1"},
            "timing": {"start": "2025-01-01T00:00:01Z", "end": "2025-01-01T00:00:02Z"},
            "status": "completed",
            "checks": {
                "why_ok": {
                    "args": {
                        "fanout.index": 0,
                        "fanout.values": [1, 2, 3],
                        "values_file_sha256": "abc123",
                    },
                    "env": {
                        "python": "3.12.0",
                        "platform": "Linux",
                        "semantiva": "1.0.0",
                        "registry": {"fingerprint": "def456"},
                    },
                }
            },
            "summaries": {
                "output_data": {"dtype": "float64", "rows": 100, "sha256": "sha123"}
            },
        },
        {
            "type": "ser",
            "ids": {"run_id": "complex2", "pipeline_id": "p", "node_id": "node1"},
            "timing": {"start": "2025-01-01T00:00:03Z", "end": "2025-01-01T00:00:04Z"},
            "status": "completed",
            "checks": {
                "why_ok": {
                    "args": {"fanout.index": 1, "fanout.values": [4, 5, 6]},
                    "env": {
                        "python": "3.11.0",
                        "platform": "Darwin",
                        "semantiva": "1.0.0",
                    },
                }
            },
        },
    ]
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    m = MultiSERIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"complex1", "complex2"}

    # Both runs should have their SER data accessible
    c1_events = m.node_events("complex1", "node1", 0, 10)
    c2_events = m.node_events("complex2", "node1", 0, 10)

    assert c1_events["total"] == 2  # before + after
    assert c2_events["total"] == 2  # before + after

    # Check that raw SER data is preserved in events
    c1_after_event = next(
        (e for e in c1_events["events"] if e["phase"] == "after"), None
    )
    assert c1_after_event is not None
    assert c1_after_event["_raw"]["checks"]["why_ok"]["args"]["fanout.index"] == 0
    assert c1_after_event["_raw"]["checks"]["why_ok"]["env"]["python"] == "3.12.0"
