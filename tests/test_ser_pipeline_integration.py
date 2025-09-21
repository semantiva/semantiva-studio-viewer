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

"""Tests for SER integration with pipeline server."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from semantiva_studio_viewer.pipeline import app


@pytest.fixture
def sample_pipeline_config():
    """Sample pipeline configuration."""
    return [
        {"processor": "FloatValueDataSource", "params": {"value": 42.0}},
        {"processor": "FloatMultiplyOperation", "params": {"factor": 2.0}},
    ]


@pytest.fixture
def sample_ser_file():
    """Create a temporary SER file."""
    ser_data = [
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-test-456",
                "pipeline_id": "plid-test-789",
                "node_id": "node-uuid-1",
            },
            "labels": {
                "node_fqn": "FloatValueDataSource",
                "declaration_index": 0,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": []},
            "action": {
                "op_ref": "FloatValueDataSource",
                "params": {"value": 42.0},
                "param_source": {},
            },
            "io_delta": {
                "created": ["output_data"],
                "read": [],
                "updated": [],
                "summaries": {},
            },
            "checks": {
                "why_run": {
                    "trigger": "dependency",
                    "upstream_evidence": [],
                    "pre": [{"code": "CONTEXT.REQKEYS", "result": "PASS"}],
                    "policy": [{"rule": "RUN.ALLOW", "result": "PASS"}],
                },
                "why_ok": {
                    "post": [{"code": "TYPE.OUT.MATCH", "result": "PASS"}],
                    "invariants": [{"code": "NONEMPTY", "result": "PASS"}],
                    "env": {},
                    "redaction": {},
                },
            },
            "timing": {
                "start": "2025-09-14T23:00:00.000Z",
                "end": "2025-09-14T23:00:01.000Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
            "status": "completed",
            "summaries": {
                "output_data": {
                    "dtype": "FloatDataType",
                    "sha256": "sha256-abc123",
                    "repr": "FloatData(42.0)",
                }
            },
        },
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-test-456",
                "pipeline_id": "plid-test-789",
                "node_id": "node-uuid-2",
            },
            "labels": {
                "node_fqn": "FloatMultiplyOperation",
                "declaration_index": 1,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": ["node-uuid-1"]},
            "action": {
                "op_ref": "FloatMultiplyOperation",
                "params": {"factor": 2.0},
                "param_source": {},
            },
            "io_delta": {
                "created": ["output_data"],
                "read": ["output_data"],
                "updated": [],
                "summaries": {},
            },
            "checks": {
                "why_run": {
                    "trigger": "dependency",
                    "upstream_evidence": [
                        {"node_id": "node-uuid-1", "state": "completed"}
                    ],
                    "pre": [],
                    "policy": [],
                },
                "why_ok": {
                    "post": [{"code": "TYPE.OUT.MATCH", "result": "PASS"}],
                    "invariants": [],
                    "env": {},
                    "redaction": {},
                },
            },
            "timing": {
                "start": "2025-09-14T23:00:01.000Z",
                "end": "2025-09-14T23:00:02.000Z",
                "duration_ms": 1000,
                "cpu_ms": 900,
            },
            "status": "completed",
            "summaries": {
                "output_data": {
                    "dtype": "FloatDataType",
                    "sha256": "sha256-def456",
                    "repr": "FloatData(84.0)",
                }
            },
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ser.jsonl", delete=False) as f:
        for record in ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    yield temp_path
    Path(temp_path).unlink()


def test_ser_file_detection(sample_ser_file):
    """Test SER file detection function."""
    from semantiva_studio_viewer.pipeline import _detect_ser_file

    assert _detect_ser_file(sample_ser_file) is True

    # Test with legacy trace file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"type": "pipeline_start", "schema_version": 0}\n')
        f.write('{"type": "node", "phase": "before"}\n')
        legacy_path = f.name

    try:
        assert _detect_ser_file(legacy_path) is False
    finally:
        Path(legacy_path).unlink()


def test_pipeline_with_ser_trace(sample_pipeline_config, sample_ser_file):
    """Test pipeline API endpoints work with SER trace."""
    # Set up app state
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_ser_file
    app.state.trace_index = None  # Force lazy loading
    app.state.trace_loaded = False  # Force lazy loading

    client = TestClient(app)

    # Test trace meta endpoint
    response = client.get("/api/trace/meta")
    assert response.status_code == 200
    meta = response.json()
    assert meta["run_id"] == "run-test-456"
    assert meta["pipeline_id"] == "plid-test-789"
    assert meta["ser_mode"] is True
    assert len(meta["canonical_nodes"]) == 2

    # Test trace summary endpoint
    response = client.get("/api/trace/summary")
    assert response.status_code == 200
    summary = response.json()
    assert "nodes" in summary
    assert len(summary["nodes"]) == 2

    # Check node aggregates
    nodes = summary["nodes"]
    node1 = nodes["node-uuid-1"]
    assert node1["count_before"] == 1
    assert node1["count_after"] == 1
    assert node1["count_error"] == 0

    node2 = nodes["node-uuid-2"]
    assert node2["count_before"] == 1
    assert node2["count_after"] == 1
    assert node2["count_error"] == 0

    # Test node events endpoint
    response = client.get("/api/trace/node/node-uuid-1")
    assert response.status_code == 200
    events = response.json()
    assert events["total"] == 2  # before + after
    assert len(events["events"]) == 2

    # Check event details
    before_event = next(e for e in events["events"] if e["phase"] == "before")
    assert before_event["event_time_utc"] == "2025-09-14T23:00:00.000Z"

    after_event = next(e for e in events["events"] if e["phase"] == "after")
    assert after_event["event_time_utc"] == "2025-09-14T23:00:01.000Z"
    assert after_event["t_wall"] == 1.0
    assert after_event["out_data_hash"] == "sha256-abc123"

    # Check SER-specific data in raw event
    assert after_event["_raw"]["type"] == "ser"
    assert "checks" in after_event["_raw"]
    assert "io_delta" in after_event["_raw"]

    # Test trace mapping endpoint
    response = client.get("/api/trace/mapping")
    assert response.status_code == 200
    mapping = response.json()
    assert "label_to_uuid" in mapping
    assert "node_mappings" in mapping

    # Test that node events include SER data
    response = client.get("/api/trace/node/node-uuid-2")
    assert response.status_code == 200
    events = response.json()
    after_event = next(e for e in events["events"] if e["phase"] == "after")

    # Verify SER checks are present
    checks = after_event["_raw"]["checks"]
    assert "why_run" in checks
    assert "why_ok" in checks
    assert checks["why_ok"]["post"][0]["code"] == "TYPE.OUT.MATCH"
    assert checks["why_ok"]["post"][0]["result"] == "PASS"

    # Verify IO delta is present
    io_delta = after_event["_raw"]["io_delta"]
    assert "created" in io_delta
    assert "read" in io_delta
    assert io_delta["created"] == ["output_data"]
    assert io_delta["read"] == ["output_data"]


def test_pipeline_without_trace():
    """Test pipeline API endpoints work without trace."""
    app.state.config = [
        {"processor": "FloatValueDataSource", "params": {"value": 42.0}}
    ]
    app.state.trace_jsonl = None
    app.state.trace_index = None

    client = TestClient(app)

    # Trace endpoints should return 404
    response = client.get("/api/trace/meta")
    assert response.status_code == 404

    response = client.get("/api/trace/summary")
    assert response.status_code == 404

    response = client.get("/api/trace/node/some-uuid")
    assert response.status_code == 404

    response = client.get("/api/trace/mapping")
    assert response.status_code == 404


@pytest.fixture
def sample_multi_run_ser_file():
    """Create a temporary multi-run SER file."""
    ser_data = [
        # Run 1 - node 1
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-multi-1",
                "pipeline_id": "plid-multi",
                "node_id": "node-uuid-1",
            },
            "labels": {
                "node_fqn": "FloatValueDataSource",
                "declaration_index": 0,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": []},
            "checks": {
                "why_ok": {
                    "args": {"value": 42.0, "fanout.index": 0},
                    "env": {
                        "python": "3.12.0",
                        "platform": "Linux",
                        "semantiva": "1.0.0",
                        "registry": {"fingerprint": "fingerprint-run1"},
                    },
                }
            },
            "timing": {
                "start": "2025-09-14T23:00:00.000Z",
                "end": "2025-09-14T23:00:01.000Z",
                "duration_ms": 1000,
            },
            "status": "completed",
        },
        # Run 1 - node 2
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-multi-1",
                "pipeline_id": "plid-multi",
                "node_id": "node-uuid-2",
            },
            "labels": {
                "node_fqn": "FloatMultiplyOperation",
                "declaration_index": 1,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": ["node-uuid-1"]},
            "timing": {
                "start": "2025-09-14T23:00:01.000Z",
                "end": "2025-09-14T23:00:02.000Z",
                "duration_ms": 1000,
            },
            "status": "completed",
        },
        # Run 2 - node 1
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-multi-2",
                "pipeline_id": "plid-multi",
                "node_id": "node-uuid-1",
            },
            "labels": {
                "node_fqn": "FloatValueDataSource",
                "declaration_index": 0,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": []},
            "checks": {
                "why_ok": {
                    "args": {"value": 84.0, "fanout.index": 1},
                    "env": {
                        "python": "3.11.5",
                        "platform": "Darwin",
                        "semantiva": "1.0.0",
                        "registry": {"fingerprint": "fingerprint-run2"},
                    },
                }
            },
            "timing": {
                "start": "2025-09-14T23:00:10.000Z",
                "end": "2025-09-14T23:00:11.000Z",
                "duration_ms": 1000,
            },
            "status": "completed",
        },
        # Run 2 - node 2
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-multi-2",
                "pipeline_id": "plid-multi",
                "node_id": "node-uuid-2",
            },
            "labels": {
                "node_fqn": "FloatMultiplyOperation",
                "declaration_index": 1,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": ["node-uuid-1"]},
            "timing": {
                "start": "2025-09-14T23:00:11.000Z",
                "end": "2025-09-14T23:00:12.000Z",
                "duration_ms": 1000,
            },
            "status": "completed",
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in ser_data:
            f.write(json.dumps(record) + "\n")
        return f.name


def test_multi_run_api_runs_endpoint(sample_pipeline_config, sample_multi_run_ser_file):
    """Test /api/runs endpoint returns multiple runs."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_multi_run_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # Test runs endpoint
    response = client.get("/api/runs")
    assert response.status_code == 200
    runs = response.json()

    assert len(runs) == 2
    run_ids = {r["run_id"] for r in runs}
    assert run_ids == {"run-multi-1", "run-multi-2"}

    # Check run metadata
    run1 = next(r for r in runs if r["run_id"] == "run-multi-1")
    run2 = next(r for r in runs if r["run_id"] == "run-multi-2")

    assert run1["pipeline_id"] == "plid-multi"
    assert run2["pipeline_id"] == "plid-multi"
    assert run1["total_events"] == 2
    assert run2["total_events"] == 2


def test_multi_run_per_run_endpoints(sample_pipeline_config, sample_multi_run_ser_file):
    """Test trace endpoints with run parameter."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_multi_run_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # Test meta endpoint for specific run
    response = client.get("/api/trace/meta?run=run-multi-1")
    assert response.status_code == 200
    meta = response.json()
    assert meta["run_id"] == "run-multi-1"

    response = client.get("/api/trace/meta?run=run-multi-2")
    assert response.status_code == 200
    meta = response.json()
    assert meta["run_id"] == "run-multi-2"

    # Test summary endpoint for specific run
    response = client.get("/api/trace/summary?run=run-multi-1")
    assert response.status_code == 200
    summary = response.json()
    assert "nodes" in summary

    # Test mapping endpoint for specific run
    response = client.get("/api/trace/mapping?run=run-multi-1")
    assert response.status_code == 200
    mapping = response.json()
    assert "label_to_uuid" in mapping

    # Test node events for specific run
    response = client.get("/api/trace/node/node-uuid-1?run=run-multi-1")
    assert response.status_code == 200
    events = response.json()
    assert events["total"] > 0


def test_multi_run_default_behavior(sample_pipeline_config, sample_multi_run_ser_file):
    """Test that endpoints work without run parameter (use default run)."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_multi_run_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # Test that endpoints work without run parameter
    response = client.get("/api/trace/meta")
    assert response.status_code == 200
    meta = response.json()
    assert meta["run_id"] in ["run-multi-1", "run-multi-2"]

    response = client.get("/api/trace/summary")
    assert response.status_code == 200
    summary = response.json()
    assert "nodes" in summary


def test_multi_run_invalid_run_id(sample_pipeline_config, sample_multi_run_ser_file):
    """Test error handling for invalid run IDs."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_multi_run_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # Test invalid run ID
    response = client.get("/api/trace/meta?run=nonexistent")
    assert response.status_code == 404
    assert "Run not found" in response.json()["detail"]

    response = client.get("/api/trace/summary?run=nonexistent")
    assert response.status_code == 404

    response = client.get("/api/trace/node/node-uuid-1?run=nonexistent")
    assert response.status_code == 404


def test_multi_run_args_and_env_in_events(
    sample_pipeline_config, sample_multi_run_ser_file
):
    """Test that run args and environment data are accessible in events."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_multi_run_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # Get events for run 1
    response = client.get("/api/trace/node/node-uuid-1?run=run-multi-1")
    assert response.status_code == 200
    events = response.json()

    # Find the before or after event with raw SER data
    ser_event = None
    for event in events["events"]:
        if event.get("_raw") and event["_raw"].get("checks"):
            ser_event = event
            break

    assert ser_event is not None

    # Check that run args are present
    checks = ser_event["_raw"]["checks"]
    assert "why_ok" in checks
    assert "args" in checks["why_ok"]
    assert checks["why_ok"]["args"]["value"] == 42.0
    assert checks["why_ok"]["args"]["fanout.index"] == 0

    # Check that environment is present
    assert "env" in checks["why_ok"]
    env = checks["why_ok"]["env"]
    assert env["python"] == "3.12.0"
    assert env["platform"] == "Linux"
    assert env["semantiva"] == "1.0.0"
    assert env["registry"]["fingerprint"] == "fingerprint-run1"

    # Get events for run 2 and verify different data
    response = client.get("/api/trace/node/node-uuid-1?run=run-multi-2")
    assert response.status_code == 200
    events = response.json()

    ser_event = None
    for event in events["events"]:
        if event.get("_raw") and event["_raw"].get("checks"):
            ser_event = event
            break

    assert ser_event is not None
    checks = ser_event["_raw"]["checks"]

    # Verify different run args and environment
    assert checks["why_ok"]["args"]["value"] == 84.0
    assert checks["why_ok"]["args"]["fanout.index"] == 1
    assert checks["why_ok"]["env"]["python"] == "3.11.5"
    assert checks["why_ok"]["env"]["platform"] == "Darwin"
    assert checks["why_ok"]["env"]["registry"]["fingerprint"] == "fingerprint-run2"


def test_single_run_backward_compatibility(sample_pipeline_config, sample_ser_file):
    """Test that single-run files still work correctly."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # /api/runs should return single run
    response = client.get("/api/runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-test-456"

    # Endpoints should work without run parameter
    response = client.get("/api/trace/meta")
    assert response.status_code == 200
    meta = response.json()
    assert meta["run_id"] == "run-test-456"

    # Endpoints should also work with explicit run parameter
    response = client.get("/api/trace/meta?run=run-test-456")
    assert response.status_code == 200
    meta = response.json()
    assert meta["run_id"] == "run-test-456"
