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

"""Tests for SER index functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from semantiva_studio_viewer.ser_index import SERIndex


@pytest.fixture
def sample_ser_data():
    """Sample SER records for testing."""
    return [
        {
            "type": "ser",
            "schema_version": 0,
            "ids": {
                "run_id": "run-test-123",
                "pipeline_id": "plid-test-456",
                "node_id": "node-1",
            },
            "labels": {
                "node_fqn": "TestProcessor",
                "declaration_index": 0,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": []},
            "action": {"op_ref": "TestProcessor", "params": {}, "param_source": {}},
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
                "run_id": "run-test-123",
                "pipeline_id": "plid-test-456",
                "node_id": "node-2",
            },
            "labels": {
                "node_fqn": "FailingProcessor",
                "declaration_index": 1,
                "declaration_subindex": 0,
            },
            "topology": {"upstream": ["node-1"]},
            "action": {"op_ref": "FailingProcessor", "params": {}, "param_source": {}},
            "io_delta": {
                "created": [],
                "read": ["output_data"],
                "updated": [],
                "summaries": {},
            },
            "checks": {
                "why_run": {
                    "trigger": "dependency",
                    "upstream_evidence": [{"node_id": "node-1", "state": "completed"}],
                    "pre": [],
                    "policy": [],
                },
                "why_ok": {"post": [], "invariants": [], "env": {}, "redaction": {}},
            },
            "timing": {
                "start": "2025-09-14T23:00:01.000Z",
                "end": "2025-09-14T23:00:01.500Z",
                "duration_ms": 500,
                "cpu_ms": 400,
            },
            "status": "error",
            "error": {"type": "ValueError", "message": "Test error message"},
        },
    ]


def test_ser_index_creation(sample_ser_data):
    """Test SERIndex creation from JSONL file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in sample_ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)

        # Check basic properties
        assert index.run_id == "run-test-123"
        assert index.pipeline_id == "plid-test-456"
        assert len(index.per_node) == 2
        assert "node-1" in index.per_node
        assert "node-2" in index.per_node

        # Check node mappings
        assert index.node_uuid_to_fqn["node-1"] == "TestProcessor"
        assert index.node_uuid_to_fqn["node-2"] == "FailingProcessor"
        assert index.fqn_to_node_uuid["TestProcessor"] == "node-1"
        assert index.fqn_to_node_uuid["FailingProcessor"] == "node-2"

        # Check canonical nodes
        assert len(index.canonical_nodes) == 2
        assert index.canonical_nodes["node-1"]["fqn"] == "TestProcessor"
        assert index.canonical_nodes["node-1"]["declaration_index"] == 0

    finally:
        Path(temp_path).unlink()


def test_ser_index_summary(sample_ser_data):
    """Test summary generation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in sample_ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)
        summary = index.summary()

        # Check structure
        assert "nodes" in summary
        assert len(summary["nodes"]) == 2

        # Check successful node
        node1_agg = summary["nodes"]["node-1"]
        assert node1_agg["count_before"] == 1
        assert node1_agg["count_after"] == 1
        assert node1_agg["count_error"] == 0
        assert node1_agg["t_wall_sum"] == 1.0  # 1000ms -> 1.0s

        # Check failed node
        node2_agg = summary["nodes"]["node-2"]
        assert node2_agg["count_before"] == 1
        assert node2_agg["count_after"] == 0
        assert node2_agg["count_error"] == 1
        assert node2_agg["last_error_type"] == "ValueError"
        assert node2_agg["last_error_msg"] == "Test error message"

    finally:
        Path(temp_path).unlink()


def test_ser_index_node_events(sample_ser_data):
    """Test node events retrieval."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in sample_ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)

        # Test successful node events
        events = index.node_events("node-1")
        assert events["total"] == 2  # before + after
        assert len(events["events"]) == 2

        # Check before event
        before_event = next(e for e in events["events"] if e["phase"] == "before")
        assert before_event["event_time_utc"] == "2025-09-14T23:00:00.000Z"

        # Check after event
        after_event = next(e for e in events["events"] if e["phase"] == "after")
        assert after_event["event_time_utc"] == "2025-09-14T23:00:01.000Z"
        assert after_event["t_wall"] == 1.0
        assert after_event["out_data_hash"] == "sha256-abc123"

        # Test failed node events
        events = index.node_events("node-2")
        assert events["total"] == 2  # before + error

        # Check error event
        error_event = next(e for e in events["events"] if e["phase"] == "error")
        assert error_event["error_type"] == "ValueError"
        assert error_event["error_msg"] == "Test error message"

    finally:
        Path(temp_path).unlink()


def test_ser_index_meta(sample_ser_data):
    """Test metadata generation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in sample_ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)
        meta = index.get_meta()

        # Check basic meta fields
        assert meta["run_id"] == "run-test-123"
        assert meta["pipeline_id"] == "plid-test-456"
        assert meta["ser_mode"] is True
        assert meta["node_count"] == 2
        assert meta["event_count"] == 2  # 2 SER records

        # Check node mappings
        assert "node_mappings" in meta
        mappings = meta["node_mappings"]
        assert "0:0" in mappings["index_to_uuid"]
        assert "1:0" in mappings["index_to_uuid"]
        assert mappings["index_to_uuid"]["0:0"] == "node-1"
        assert mappings["index_to_uuid"]["1:0"] == "node-2"

        # Check canonical nodes
        assert len(meta["canonical_nodes"]) == 2

    finally:
        Path(temp_path).unlink()


def test_ser_index_find_node_by_label(sample_ser_data):
    """Test node UUID lookup by label."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in sample_ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)

        # Test exact match
        assert index.find_node_uuid_by_label("TestProcessor") == "node-1"
        assert index.find_node_uuid_by_label("FailingProcessor") == "node-2"

        # Test partial match
        assert index.find_node_uuid_by_label("Test") == "node-1"

        # Test no match
        assert index.find_node_uuid_by_label("NonExistent") is None

    finally:
        Path(temp_path).unlink()


def test_ser_index_empty_file():
    """Test handling of empty file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)
        assert index.run_id is None
        assert index.pipeline_id is None
        assert len(index.per_node) == 0

    finally:
        Path(temp_path).unlink()


def test_ser_index_topology_reconstruction(sample_ser_data):
    """Test graph reconstruction from SER topology."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for record in sample_ser_data:
            f.write(json.dumps(record) + "\n")
        temp_path = f.name

    try:
        index = SERIndex.from_jsonl(temp_path)
        topology = index.get_ser_topology()

        # Check nodes
        assert len(topology["nodes"]) == 2
        node_ids = [node["node_id"] for node in topology["nodes"]]
        assert "node-1" in node_ids
        assert "node-2" in node_ids

        # Check edges
        assert len(topology["edges"]) == 1  # node-1 -> node-2
        edge = topology["edges"][0]
        assert edge["from"] == "node-1"
        assert edge["to"] == "node-2"

    finally:
        Path(temp_path).unlink()
