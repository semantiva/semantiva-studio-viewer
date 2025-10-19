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


def _make_ser_v1(
    run_id,
    pipeline_id,
    node_id,
    processor_ref,
    parameters=None,
    upstream=None,
    timing=None,
):
    """Helper to create a SER v1 record for integration tests."""
    if parameters is None:
        parameters = {}
    if upstream is None:
        upstream = []
    if timing is None:
        timing = {
            "started_at": "2025-09-14T23:00:00.000Z",
            "finished_at": "2025-09-14T23:00:01.000Z",
            "duration_ms": 1000,
            "cpu_ms": 800,
        }

    return {
        "record_type": "ser",
        "schema_version": 1,
        "identity": {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "node_id": node_id,
        },
        "dependencies": {"upstream": upstream},
        "processor": {
            "ref": processor_ref,
            "parameters": parameters,
            "parameter_sources": {},
        },
        "context_delta": {
            "read_keys": [],
            "created_keys": ["output_data"],
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
        "status": "succeeded",
    }


@pytest.fixture
def sample_pipeline_config():
    """Sample pipeline configuration."""
    return [
        {"processor": "FloatValueDataSource", "params": {"value": 42.0}},
        {"processor": "FloatMultiplyOperation", "params": {"factor": 2.0}},
    ]


@pytest.fixture
def sample_ser_file():
    """Create a temporary SER file with SER v1 records."""
    ser_data = [
        {
            "record_type": "ser",
            "schema_version": 1,
            "identity": {
                "run_id": "run-test-456",
                "pipeline_id": "plid-test-789",
                "node_id": "node-uuid-1",
            },
            "dependencies": {"upstream": []},
            "processor": {
                "ref": "FloatValueDataSource",
                "parameters": {"value": 42.0},
                "parameter_sources": {},
            },
            "context_delta": {
                "created_keys": ["output_data"],
                "read_keys": [],
                "updated_keys": [],
                "key_summaries": {},
            },
            "assertions": {
                "preconditions": [{"code": "CONTEXT.REQKEYS", "result": "PASS"}],
                "postconditions": [
                    {"code": "TYPE.OUT.MATCH", "result": "PASS"},
                    {"code": "NONEMPTY", "result": "PASS"},
                ],
                "invariants": [],
                "environment": {
                    "python": "3.12.0",
                    "platform": "Linux",
                    "semantiva": "1.0.0",
                },
                "redaction_policy": {},
            },
            "timing": {
                "started_at": "2025-09-14T23:00:00.000Z",
                "finished_at": "2025-09-14T23:00:01.000Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
            "status": "succeeded",
            "tags": {
                "declaration_index": 0,
                "declaration_subindex": 0,
            },
            "summaries": {
                "output_data": {
                    "dtype": "FloatDataType",
                    "sha256": "sha256-abc123",
                    "repr": "FloatData(42.0)",
                }
            },
        },
        {
            "record_type": "ser",
            "schema_version": 1,
            "identity": {
                "run_id": "run-test-456",
                "pipeline_id": "plid-test-789",
                "node_id": "node-uuid-2",
            },
            "dependencies": {"upstream": ["node-uuid-1"]},
            "processor": {
                "ref": "FloatMultiplyOperation",
                "parameters": {"factor": 2.0},
                "parameter_sources": {},
            },
            "context_delta": {
                "created_keys": ["output_data"],
                "read_keys": ["output_data"],
                "updated_keys": [],
                "key_summaries": {},
            },
            "assertions": {
                "preconditions": [],
                "postconditions": [{"code": "TYPE.OUT.MATCH", "result": "PASS"}],
                "invariants": [],
                "environment": {
                    "python": "3.12.0",
                    "platform": "Linux",
                    "semantiva": "1.0.0",
                },
                "redaction_policy": {},
            },
            "timing": {
                "started_at": "2025-09-14T23:00:01.000Z",
                "finished_at": "2025-09-14T23:00:02.000Z",
                "duration_ms": 1000,
                "cpu_ms": 900,
            },
            "status": "succeeded",
            "tags": {
                "declaration_index": 1,
                "declaration_subindex": 0,
            },
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


@pytest.mark.skip(
    reason="Core aggregator requires pipeline_start record for pipeline_id extraction"
)
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

    # Check node aggregates (SER v1: status, timing, error)
    nodes = summary["nodes"]
    node1 = nodes["node-uuid-1"]
    assert node1["status"] == "succeeded"  # SER v1 status value
    assert node1["timing"]["duration_ms"] > 0
    assert node1["error"] is None

    node2 = nodes["node-uuid-2"]
    assert node2["status"] == "succeeded"  # SER v1 status value
    assert node2["timing"]["duration_ms"] > 0
    assert node2["error"] is None

    # Test node events endpoint
    response = client.get("/api/trace/node/node-uuid-1")
    assert response.status_code == 200
    events = response.json()
    assert events["total"] == 1  # One SER record per execution (not before+after)
    assert len(events["events"]) == 1

    # Check event details (SER v1 structure)
    event = events["events"][0]
    assert event["status"] == "succeeded"
    assert event["timing"]["finished_at"] is not None
    assert event["timing"]["duration_ms"] > 0

    # Check SER v1 structure
    assert event["record_type"] == "ser"  # SER v1 uses record_type
    assert event["schema_version"] == 1  # SER v1
    assert "identity" in event  # SER v1 uses identity instead of ids
    assert "context_delta" in event  # SER v1 uses context_delta instead of io_delta
    assert "processor" in event  # SER v1 uses processor instead of action

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
    # Events are raw SER v1 records (no before/after wrapping)
    assert len(events["events"]) == 1
    event = events["events"][0]
    assert event["status"] == "succeeded"
    assert event["record_type"] == "ser"
    assert event["identity"]["node_id"] == "node-uuid-2"

    # Verify SER v1 assertions are present
    assertions = event["assertions"]
    assert "postconditions" in assertions
    assert len(assertions["postconditions"]) > 0
    assert assertions["postconditions"][0]["code"] == "TYPE.OUT.MATCH"
    assert assertions["postconditions"][0]["result"] == "PASS"

    # Verify context_delta is present (SER v1)
    context_delta = event["context_delta"]
    assert "created_keys" in context_delta
    assert "read_keys" in context_delta
    assert "output_data" in context_delta["created_keys"]
    assert "output_data" in context_delta["read_keys"]


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
    """Create a temporary multi-run SER v1 file."""
    ser_data = [
        # Run 1 - node 1
        _make_ser_v1(
            "run-multi-1",
            "plid-multi",
            "node-uuid-1",
            "FloatValueDataSource",
            parameters={"value": 42.0},
            upstream=[],
            timing={
                "started_at": "2025-09-14T23:00:00.000Z",
                "finished_at": "2025-09-14T23:00:01.000Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        # Run 1 - node 2
        _make_ser_v1(
            "run-multi-1",
            "plid-multi",
            "node-uuid-2",
            "FloatMultiplyOperation",
            parameters={"factor": 2.0},
            upstream=["node-uuid-1"],
            timing={
                "started_at": "2025-09-14T23:00:01.000Z",
                "finished_at": "2025-09-14T23:00:02.000Z",
                "duration_ms": 1000,
                "cpu_ms": 900,
            },
        ),
        # Run 2 - node 1
        _make_ser_v1(
            "run-multi-2",
            "plid-multi",
            "node-uuid-1",
            "FloatValueDataSource",
            parameters={"value": 84.0},
            upstream=[],
            timing={
                "started_at": "2025-09-14T23:00:10.000Z",
                "finished_at": "2025-09-14T23:00:11.000Z",
                "duration_ms": 1000,
                "cpu_ms": 800,
            },
        ),
        # Run 2 - node 2
        _make_ser_v1(
            "run-multi-2",
            "plid-multi",
            "node-uuid-2",
            "FloatMultiplyOperation",
            parameters={"factor": 2.0},
            upstream=["node-uuid-1"],
            timing={
                "started_at": "2025-09-14T23:00:11.000Z",
                "finished_at": "2025-09-14T23:00:12.000Z",
                "duration_ms": 1000,
                "cpu_ms": 900,
            },
        ),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in ser_data:
            f.write(json.dumps(record) + "\n")
        return f.name


@pytest.mark.skip(
    reason="Core aggregator requires pipeline_start/end records for proper metadata"
)
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
    """Test that run parameters and environment data are accessible in SER v1 events."""
    app.state.config = sample_pipeline_config
    app.state.trace_jsonl = sample_multi_run_ser_file
    app.state.trace_index = None
    app.state.trace_loaded = False

    client = TestClient(app)

    # Get events for run 1
    response = client.get("/api/trace/node/node-uuid-1?run=run-multi-1")
    assert response.status_code == 200
    events = response.json()

    # Events are raw SER v1 records
    assert len(events["events"]) == 1
    event = events["events"][0]

    # Check SER v1 structure
    assert event["record_type"] == "ser"
    assert event["identity"]["run_id"] == "run-multi-1"

    # Check that processor parameters are present (SER v1)
    assert event["processor"]["parameters"]["value"] == 42.0

    # Check that environment is present in assertions (SER v1)
    assert "environment" in event["assertions"]
    env = event["assertions"]["environment"]
    assert env["python"] == "3.12.0"
    assert env["platform"] == "Linux"
    assert env["semantiva"] == "1.0.0"

    # Get events for run 2 and verify different data
    response = client.get("/api/trace/node/node-uuid-1?run=run-multi-2")
    assert response.status_code == 200
    events = response.json()

    assert len(events["events"]) == 1
    event = events["events"][0]

    # Verify different run parameters
    assert event["processor"]["parameters"]["value"] == 84.0
    assert event["identity"]["run_id"] == "run-multi-2"


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
