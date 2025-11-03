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

"""Test that CoreTraceIndex exposes semantic_id and config_id from meta."""

from semantiva.trace.aggregation import TraceAggregator
from semantiva_studio_viewer.core_trace_index import CoreTraceIndex


def test_core_trace_index_exposes_meta_fields():
    """Verify that CoreTraceIndex.get_meta() exposes semantic_id and config_id."""
    agg = TraceAggregator()

    pipeline_start_record = {
        "record_type": "pipeline_start",
        "schema_version": 1,
        "timestamp": "2025-11-02T10:00:00.000Z",
        "seq": 1,
        "run_id": "run-meta-test",
        "pipeline_id": "plid-meta-test",
        "pipeline_spec_canonical": {
            "version": 1,
            "nodes": [
                {
                    "node_uuid": "node-uuid-meta",
                    "declaration_index": 0,
                    "declaration_subindex": 0,
                    "processor_ref": "TestProcessor",
                    "role": "processor",
                    "params": {},
                    "ports": {},
                }
            ],
            "edges": [],
        },
        "meta": {
            "num_nodes": 1,
            "pipeline_config_id": "cfg-meta-xyz",
            "node_semantic_ids": {
                "node-uuid-meta": "sem-id-meta-abc",
            },
        },
    }

    agg.ingest(pipeline_start_record)

    # Create CoreTraceIndex
    trace_idx = CoreTraceIndex("run-meta-test", agg)

    # Get metadata
    meta = trace_idx.get_meta()

    # Verify semantic_id and config_id are exposed
    assert meta["run_id"] == "run-meta-test"
    assert meta["pipeline_id"] == "plid-meta-test"
    assert meta["semantic_id"] == "cfg-meta-xyz"
    assert meta["config_id"] == "cfg-meta-xyz"
    assert meta["node_semantic_ids"] == {"node-uuid-meta": "sem-id-meta-abc"}


def test_core_trace_index_handles_missing_meta():
    """Verify that CoreTraceIndex gracefully handles missing meta field."""
    agg = TraceAggregator()

    # Pipeline start without meta field (old trace format)
    pipeline_start_record = {
        "record_type": "pipeline_start",
        "schema_version": 1,
        "timestamp": "2025-11-02T10:00:00.000Z",
        "seq": 1,
        "run_id": "run-no-meta",
        "pipeline_id": "plid-no-meta",
        "pipeline_spec_canonical": {
            "version": 1,
            "nodes": [],
            "edges": [],
        },
    }

    agg.ingest(pipeline_start_record)

    trace_idx = CoreTraceIndex("run-no-meta", agg)
    meta = trace_idx.get_meta()

    # Should return None for missing fields, not crash
    assert meta["run_id"] == "run-no-meta"
    assert meta["semantic_id"] is None
    assert meta["config_id"] is None
    assert meta["node_semantic_ids"] == {}
