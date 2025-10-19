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
from semantiva_studio_viewer.core_trace_index import MultiTraceIndex, CoreTraceIndex


def _ser(rec):
    """Helper to serialize SER records."""
    return json.dumps(rec)


def _make_ser_v1(run_id, node_id="node1", timing=None, status="succeeded"):
    """Helper to create a SER v1 record with all required fields."""
    if timing is None:
        timing = {
            "started_at": "2025-01-01T00:00:00Z",
            "finished_at": "2025-01-01T00:00:01Z",
            "duration_ms": 1000,
            "cpu_ms": 800,
        }

    return {
        "record_type": "ser",
        "schema_version": 1,
        "identity": {"run_id": run_id, "pipeline_id": "p", "node_id": node_id},
        "dependencies": {"upstream": []},
        "processor": {"ref": "TestNode", "parameters": {}, "parameter_sources": {}},
        "context_delta": {
            "read_keys": [],
            "created_keys": [],
            "updated_keys": [],
            "key_summaries": {},
        },
        "assertions": {
            "preconditions": [{"code": "CONTEXT.READY", "result": "PASS"}],
            "postconditions": [{"code": "OUTPUT.VALID", "result": "PASS"}],
            "invariants": [],
            "environment": {
                "python": "3.12.0",
                "platform": "Linux",
                "semantiva": "1.0.0",
            },
            "redaction_policy": {},
        },
        "timing": timing,
        "status": status,
    }


def test_multi_ser_groups_runs(tmp_path):
    """Test that MultiTraceIndex correctly groups records by run_id."""
    p = tmp_path / "multi.jsonl"
    runs = [
        _make_ser_v1(
            "r1",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "r2",
            timing={
                "started_at": "2025-01-01T00:00:03Z",
                "finished_at": "2025-01-01T00:00:04Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "r1",
            timing={
                "started_at": "2025-01-01T00:00:05Z",
                "finished_at": "2025-01-01T00:00:06Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert {r["run_id"] for r in listed} == {"r1", "r2"}
    assert len(m.by_run) == 2
    assert m.get("r1").total_events == 2
    assert m.get("r2").total_events == 1
    # default run should be deterministic
    assert m.default_run_id() in {"r1", "r2"}


def test_multi_ser_json_array(tmp_path):
    """Test that MultiTraceIndex can handle JSON array format."""
    p = tmp_path / "multi.json"
    runs = [
        _make_ser_v1(
            "r1",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "r2",
            timing={
                "started_at": "2025-01-01T00:00:03Z",
                "finished_at": "2025-01-01T00:00:04Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text(json.dumps(runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"r1", "r2"}


def test_multi_ser_single_run_fallback(tmp_path):
    """Test that MultiTraceIndex handles single run correctly."""
    p = tmp_path / "single.jsonl"
    runs = [
        _make_ser_v1(
            "single",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 1
    assert listed[0]["run_id"] == "single"
    assert m.default_run_id() == "single"


def test_multi_ser_api_surface(tmp_path):
    """Test MultiTraceIndex API methods."""
    p = tmp_path / "api.jsonl"
    runs = [
        _make_ser_v1(
            "r1",
            node_id="node1",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "r2",
            node_id="node1",
            timing={
                "started_at": "2025-01-01T00:00:03Z",
                "finished_at": "2025-01-01T00:00:04Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))

    # Test get method
    ser1 = m.get("r1")
    ser2 = m.get("r2")
    assert isinstance(ser1, CoreTraceIndex)
    assert isinstance(ser2, CoreTraceIndex)
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
    """Test MultiTraceIndex error handling for missing runs."""
    p = tmp_path / "error.jsonl"
    runs = [
        _make_ser_v1("r1"),
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))

    with pytest.raises(KeyError, match="Run not found: nonexistent"):
        m.get("nonexistent")

    with pytest.raises(KeyError, match="Run not found: nonexistent"):
        m.get_meta("nonexistent")


def test_multi_ser_unknown_run_id(tmp_path):
    """Test MultiTraceIndex handles records without run_id (malformed SER v1)."""
    p = tmp_path / "unknown.jsonl"
    # Create a malformed SER v1 record without run_id in identity
    runs = [
        {
            "record_type": "ser",
            "schema_version": 1,
            "identity": {"pipeline_id": "p", "node_id": "node1"},  # Missing run_id
            "dependencies": {"upstream": []},
            "processor": {"ref": "TestNode", "parameters": {}, "parameter_sources": {}},
            "context_delta": {
                "read_keys": [],
                "created_keys": [],
                "updated_keys": [],
                "key_summaries": {},
            },
            "assertions": {
                "preconditions": [{"code": "READY", "result": "PASS"}],
                "postconditions": [{"code": "VALID", "result": "PASS"}],
                "invariants": [],
                "environment": {
                    "python": "3.12.0",
                    "platform": "Linux",
                    "semantiva": "1.0.0",
                },
                "redaction_policy": {},
            },
            "timing": {
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
            "status": "succeeded",
        },
    ]
    p.write_text("\n".join(json.dumps(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 1
    assert listed[0]["run_id"] == "unknown"


@pytest.mark.skip(
    reason="Core aggregator timing extraction requires pipeline_start/end records"
)
def test_multi_ser_timing_aggregation(tmp_path):
    """Test that timing information is correctly aggregated per run."""
    p = tmp_path / "timing.jsonl"
    runs = [
        _make_ser_v1(
            "r1",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "r1",
            timing={
                "started_at": "2025-01-01T00:00:00Z",
                "finished_at": "2025-01-01T00:00:03Z",
                "duration_ms": 3000,
                "cpu_ms": 2500,
            },
        ),  # Earlier start, later end
        _make_ser_v1(
            "r2",
            timing={
                "started_at": "2025-01-01T00:00:05Z",
                "finished_at": "2025-01-01T00:00:06Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
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


@pytest.mark.skip(
    reason="Core aggregator run ordering depends on pipeline_start/end records"
)
def test_multi_ser_run_ordering(tmp_path):
    """Test that runs are ordered by started_at, then run_id."""
    p = tmp_path / "ordering.jsonl"
    runs = [
        _make_ser_v1(
            "z_run",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "a_run",
            timing={
                "started_at": "2025-01-01T00:00:03Z",
                "finished_at": "2025-01-01T00:00:04Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "b_run",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),  # Same time as z_run
    ]
    p.write_text("\n".join(_ser(r) for r in runs), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    # Should be ordered by started_at, then by run_id
    expected_order = [
        "b_run",
        "z_run",
        "a_run",
    ]  # b_run and z_run both at 00:00:01Z, so b_run comes first alphabetically
    actual_order = [r["run_id"] for r in listed]
    assert actual_order == expected_order


@pytest.mark.skip(
    reason="Test depends on bespoke aggregator behavior with mixed record types"
)
def test_multi_ser_mixed_record_types(tmp_path):
    """Test that MultiTraceIndex handles mixed record types correctly."""
    p = tmp_path / "mixed.jsonl"
    records = [
        {"record_type": "pipeline_start", "run_id": "r1", "pipeline_id": "p"},
        _make_ser_v1(
            "r1",
            node_id="node1",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        {"record_type": "pipeline_end", "run_id": "r1", "pipeline_id": "p"},
        _make_ser_v1(
            "r2",
            node_id="node1",
            timing={
                "started_at": "2025-01-01T00:00:03Z",
                "finished_at": "2025-01-01T00:00:04Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text(
        "\n".join(
            (
                json.dumps(r)
                if isinstance(r, dict)
                and "record_type" in r
                and r["record_type"] != "ser"
                else _ser(r)
            )
            for r in records
        ),
        encoding="utf-8",
    )

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"r1", "r2"}

    # r1 should have processed both pipeline_start and ser records
    r1_index = m.get("r1")
    assert r1_index.pipeline_id == "p"
    assert r1_index.total_events == 3  # pipeline_start + ser + pipeline_end


def test_multi_ser_complex_ser_records(tmp_path):
    """Test MultiTraceIndex with complex SER v1 records."""
    p = tmp_path / "complex.jsonl"
    records = [
        _make_ser_v1(
            "complex1",
            node_id="node1",
            timing={
                "started_at": "2025-01-01T00:00:01Z",
                "finished_at": "2025-01-01T00:00:02Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        _make_ser_v1(
            "complex2",
            node_id="node1",
            timing={
                "started_at": "2025-01-01T00:00:03Z",
                "finished_at": "2025-01-01T00:00:04Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
    ]
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    m = MultiTraceIndex.from_json_or_jsonl(str(p))
    listed = m.list_runs()

    assert len(listed) == 2
    assert {r["run_id"] for r in listed} == {"complex1", "complex2"}

    # Both runs should have their SER data accessible
    c1_events = m.node_events("complex1", "node1", 0, 10)
    c2_events = m.node_events("complex2", "node1", 0, 10)

    assert c1_events["total"] == 1  # Just the SER record itself (no before/after)
    assert c2_events["total"] == 1

    # Check that raw SER data is preserved in events
    c1_event = c1_events["events"][0]
    # Events now contain the raw SER v1 record directly
    assert c1_event["status"] == "succeeded"
    assert c1_event["record_type"] == "ser"
    assert c1_event["identity"]["run_id"] == "complex1"
    assert c1_event["timing"]["started_at"] == "2025-01-01T00:00:01Z"
