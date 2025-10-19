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

"""Tests for core-backed trace adapter (per-run only, no run-space)."""

import json
import tempfile
import os
from semantiva_studio_viewer.core_trace_index import MultiTraceIndex


def test_adapter_per_run_only_ignores_run_space():
    """Test that adapter processes per-run data and ignores run-space records."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    lines = [
        {
            "record_type": "run_space_start",
            "run_space_launch_id": "L1",
            "run_space_attempt": 1,
        },
        {
            "record_type": "pipeline_start",
            "run_id": "R1",
            "pipeline_id": "P",
            "pipeline_spec_canonical": {
                "nodes": [
                    {
                        "node_uuid": "n1",
                        "declaration_index": 0,
                        "declaration_subindex": 0,
                    }
                ]
            },
        },
        {
            "record_type": "ser",
            "identity": {"run_id": "R1", "pipeline_id": "P", "node_id": "n1"},
            "status": "succeeded",
            "timing": {"wall_ms": 7},
            "processor": {"ref": "TestOp", "parameters": {}},
            "context_delta": {
                "created_keys": [],
                "updated_keys": [],
                "read_keys": [],
                "key_summaries": {},
            },
            "dependencies": {"upstream": []},
            "assertions": {},
        },
        {"record_type": "pipeline_end", "run_id": "R1"},
        {
            "record_type": "run_space_end",
            "run_space_launch_id": "L1",
            "run_space_attempt": 1,
        },
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    m = MultiTraceIndex.from_json_or_jsonl(path)
    idx = m.get("R1")
    meta = idx.get_meta()
    assert meta["run_id"] == "R1"
    s = idx.summary()
    assert s["nodes"]["n1"]["timing"]["wall_ms"] == 7
    # Verify run-space records are NOT exposed in UI data
    assert "run_space_launch_id" not in meta
    # Clean up
    os.unlink(path)


def test_adapter_wall_ms_backfill():
    """Test that adapter backfills wall_ms from duration_ms or duration."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    lines = [
        {
            "record_type": "pipeline_start",
            "run_id": "R2",
            "pipeline_id": "P",
            "pipeline_spec_canonical": {
                "nodes": [
                    {
                        "node_uuid": "n2",
                        "declaration_index": 0,
                        "declaration_subindex": 0,
                    }
                ]
            },
        },
        {
            "record_type": "ser",
            "identity": {"run_id": "R2", "pipeline_id": "P", "node_id": "n2"},
            "status": "succeeded",
            "timing": {"duration_ms": 42},  # No wall_ms
            "processor": {"ref": "TestOp2", "parameters": {}},
            "context_delta": {
                "created_keys": [],
                "updated_keys": [],
                "read_keys": [],
                "key_summaries": {},
            },
            "dependencies": {"upstream": []},
            "assertions": {},
        },
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    m = MultiTraceIndex.from_json_or_jsonl(path)
    idx = m.get("R2")
    s = idx.summary()
    # Should backfill wall_ms from duration_ms
    assert s["nodes"]["n2"]["timing"]["wall_ms"] == 42
    os.unlink(path)


def test_adapter_multiple_runs():
    """Test adapter handles multiple runs correctly."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    lines = [
        {
            "record_type": "pipeline_start",
            "run_id": "R_A",
            "pipeline_id": "P",
            "pipeline_spec_canonical": {
                "nodes": [
                    {
                        "node_uuid": "nA",
                        "declaration_index": 0,
                        "declaration_subindex": 0,
                    }
                ]
            },
        },
        {
            "record_type": "ser",
            "identity": {"run_id": "R_A", "pipeline_id": "P", "node_id": "nA"},
            "status": "succeeded",
            "timing": {"wall_ms": 10},
            "processor": {"ref": "OpA", "parameters": {}},
            "context_delta": {
                "created_keys": [],
                "updated_keys": [],
                "read_keys": [],
                "key_summaries": {},
            },
            "dependencies": {"upstream": []},
            "assertions": {},
        },
        {
            "record_type": "pipeline_start",
            "run_id": "R_B",
            "pipeline_id": "P",
            "pipeline_spec_canonical": {
                "nodes": [
                    {
                        "node_uuid": "nB",
                        "declaration_index": 0,
                        "declaration_subindex": 0,
                    }
                ]
            },
        },
        {
            "record_type": "ser",
            "identity": {"run_id": "R_B", "pipeline_id": "P", "node_id": "nB"},
            "status": "error",
            "timing": {"wall_ms": 20},
            "processor": {"ref": "OpB", "parameters": {}},
            "context_delta": {
                "created_keys": [],
                "updated_keys": [],
                "read_keys": [],
                "key_summaries": {},
            },
            "dependencies": {"upstream": []},
            "assertions": {},
        },
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    m = MultiTraceIndex.from_json_or_jsonl(path)
    runs = m.list_runs()
    assert len(runs) == 2
    run_ids = {r["run_id"] for r in runs}
    assert run_ids == {"R_A", "R_B"}

    # Verify per-run data
    idx_a = m.get("R_A")
    s_a = idx_a.summary()
    assert s_a["nodes"]["nA"]["status"] == "succeeded"

    idx_b = m.get("R_B")
    s_b = idx_b.summary()
    assert s_b["nodes"]["nB"]["status"] == "error"
    os.unlink(path)


def test_adapter_node_events_buffering():
    """Test that adapter buffers node events with size limit."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    lines = [
        {
            "record_type": "pipeline_start",
            "run_id": "R3",
            "pipeline_id": "P",
            "pipeline_spec_canonical": {
                "nodes": [
                    {
                        "node_uuid": "n3",
                        "declaration_index": 0,
                        "declaration_subindex": 0,
                    }
                ]
            },
        }
    ]
    # Add multiple SER records for same node (more than buffer limit)
    for i in range(10):
        lines.append(
            {
                "record_type": "ser",
                "identity": {"run_id": "R3", "pipeline_id": "P", "node_id": "n3"},
                "status": "succeeded",
                "timing": {"wall_ms": i},
                "processor": {"ref": "TestOp3", "parameters": {}},
                "context_delta": {
                    "created_keys": [],
                    "updated_keys": [],
                    "read_keys": [],
                    "key_summaries": {},
                },
                "dependencies": {"upstream": []},
                "assertions": {},
            }
        )

    with open(path, "w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    m = MultiTraceIndex.from_json_or_jsonl(path)
    idx = m.get("R3")
    events = idx.node_events("n3", offset=0, limit=100)
    # Should have all 10 events (under buffer limit)
    assert events["total"] == 10
    assert len(events["events"]) == 10
    os.unlink(path)


def test_adapter_empty_trace():
    """Test adapter handles empty or missing traces gracefully."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write("")  # Empty file
    m = MultiTraceIndex.from_json_or_jsonl(path)
    runs = m.list_runs()
    assert len(runs) == 0
    os.unlink(path)
