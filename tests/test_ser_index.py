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
    """Sample SER v1 records for testing."""
    return [
        {
            "record_type": "ser",
            "schema_version": 1,
            "identity": {
                "run_id": "run-test-123",
                "pipeline_id": "plid-test-456",
                "node_id": "node-1",
            },
            "dependencies": {
                "upstream": [],
            },
            "processor": {
                "ref": "TestProcessor",
                "params": {},
                "param_source": {},
            },
            "context_delta": {
                "created_keys": ["output_data"],
                "read_keys": [],
                "updated_keys": [],
                "key_summaries": {},
            },
            "assertions": {
                "checks": [{"code": "TYPE.OUT.MATCH", "result": "PASS"}],
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
                "run_id": "run-test-123",
                "pipeline_id": "plid-test-456",
                "node_id": "node-2",
            },
            "dependencies": {
                "upstream": ["node-1"],
            },
            "processor": {
                "ref": "FailingProcessor",
                "params": {},
                "param_source": {},
            },
            "context_delta": {
                "created_keys": [],
                "read_keys": ["output_data"],
                "updated_keys": [],
                "key_summaries": {},
            },
            "assertions": {
                "checks": [],
            },
            "timing": {
                "started_at": "2025-09-14T23:00:00.000Z",
                "finished_at": "2025-09-14T23:00:02.000Z",
                "duration_ms": 2000,
                "cpu_ms": 1500,
            },
            "status": "error",
            "tags": {
                "declaration_index": 1,
                "declaration_subindex": 0,
            },
            "error": {
                "type": "ValueError",
                "msg": "Test error message",
                "traceback": "Traceback (most recent call last):\n  ...",
            },
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

        # Check successful node (SER v1: status, timing, error fields)
        node1_agg = summary["nodes"]["node-1"]
        assert node1_agg["status"] == "succeeded"  # SER v1 status value
        assert node1_agg["timing"]["duration_ms"] == 1000
        assert node1_agg["timing"]["cpu_ms"] == 800
        assert node1_agg["error"] is None  # No error for succeeded node

        # Check failed node (SER v1: status, timing, error fields)
        node2_agg = summary["nodes"]["node-2"]
        assert node2_agg["status"] == "error"  # SER v1 status field
        assert node2_agg["error"] is not None
        assert node2_agg["error"]["type"] == "ValueError"
        assert node2_agg["error"]["msg"] == "Test error message"

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

        # Test successful node events (SER v1: one record per execution)
        events = index.node_events("node-1")
        assert events["total"] == 1
        assert len(events["events"]) == 1

        # Check event (SER v1 structure)
        event = events["events"][0]
        assert event["status"] == "succeeded"
        assert event["timing"]["started_at"] == "2025-09-14T23:00:00.000Z"
        assert event["timing"]["finished_at"] == "2025-09-14T23:00:01.000Z"
        assert event["timing"]["duration_ms"] == 1000

        # Test failed node events (SER v1: one record per execution)
        events = index.node_events("node-2")
        assert events["total"] == 1

        # Check error event (SER v1 structure)
        event = events["events"][0]
        assert event["status"] == "error"
        assert event["error"]["type"] == "ValueError"
        assert event["error"]["msg"] == "Test error message"

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
