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
        {
            "processor": "FloatValueDataSource",
            "params": {"value": 42.0}
        },
        {
            "processor": "FloatMultiplyOperation",
            "params": {"factor": 2.0}
        }
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
                "node_id": "node-uuid-1"
            },
            "labels": {
                "node_fqn": "FloatValueDataSource",
                "declaration_index": 0,
                "declaration_subindex": 0
            },
            "topology": {
                "upstream": []
            },
            "action": {
                "op_ref": "FloatValueDataSource",
                "params": {"value": 42.0},
                "param_source": {}
            },
            "io_delta": {
                "created": ["output_data"],
                "read": [],
                "updated": [],
                "summaries": {}
            },
            "checks": {
                "why_run": {
                    "trigger": "dependency",
                    "upstream_evidence": [],
                    "pre": [{"code": "CONTEXT.REQKEYS", "result": "PASS"}],
                    "policy": [{"rule": "RUN.ALLOW", "result": "PASS"}]
                },
                "why_ok": {
                    "post": [{"code": "TYPE.OUT.MATCH", "result": "PASS"}],
                    "invariants": [{"code": "NONEMPTY", "result": "PASS"}],
                    "env": {},
                    "redaction": {}
                }
            },
            "timing": {
                "start": "2025-09-14T23:00:00.000Z",
                "end": "2025-09-14T23:00:01.000Z",
                "duration_ms": 1000,
                "cpu_ms": 800
            },
            "status": "completed",
            "summaries": {
                "output_data": {
                    "dtype": "FloatDataType",
                    "sha256": "sha256-abc123",
                    "repr": "FloatData(42.0)"
                }
            }
        },
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-test-456",
                "pipeline_id": "plid-test-789",
                "node_id": "node-uuid-2"
            },
            "labels": {
                "node_fqn": "FloatMultiplyOperation",
                "declaration_index": 1,
                "declaration_subindex": 0
            },
            "topology": {
                "upstream": ["node-uuid-1"]
            },
            "action": {
                "op_ref": "FloatMultiplyOperation",
                "params": {"factor": 2.0},
                "param_source": {}
            },
            "io_delta": {
                "created": ["output_data"],
                "read": ["output_data"],
                "updated": [],
                "summaries": {}
            },
            "checks": {
                "why_run": {
                    "trigger": "dependency",
                    "upstream_evidence": [{"node_id": "node-uuid-1", "state": "completed"}],
                    "pre": [],
                    "policy": []
                },
                "why_ok": {
                    "post": [{"code": "TYPE.OUT.MATCH", "result": "PASS"}],
                    "invariants": [],
                    "env": {},
                    "redaction": {}
                }
            },
            "timing": {
                "start": "2025-09-14T23:00:01.000Z",
                "end": "2025-09-14T23:00:02.000Z",
                "duration_ms": 1000,
                "cpu_ms": 900
            },
            "status": "completed",
            "summaries": {
                "output_data": {
                    "dtype": "FloatDataType",
                    "sha256": "sha256-def456",
                    "repr": "FloatData(84.0)"
                }
            }
        }
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ser.jsonl', delete=False) as f:
        for record in ser_data:
            f.write(json.dumps(record) + '\n')
        temp_path = f.name
    
    yield temp_path
    Path(temp_path).unlink()


def test_ser_file_detection(sample_ser_file):
    """Test SER file detection function."""
    from semantiva_studio_viewer.pipeline import _detect_ser_file
    
    assert _detect_ser_file(sample_ser_file) is True
    
    # Test with legacy trace file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
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
    app.state.config = [{"processor": "FloatValueDataSource", "params": {"value": 42.0}}]
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
