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

"""Test trace meta adapter identity mapping with correct fallbacks."""

from semantiva_studio_viewer.core_trace_index import CoreTraceIndex
from semantiva.trace.aggregation import TraceAggregator


def test_trace_adapter_config_id_alias_fallback():
    """Test that config_id correctly falls back to pipeline_config_id alias."""
    # Create a mock trace aggregator with metadata
    agg = TraceAggregator()

    # Simulate a trace with only pipeline_config_id (legacy field)
    test_run_id = "run-test-123"

    # Create a minimal pipeline_start event to set up the run
    pipeline_start = {
        "record_type": "pipeline_start",
        "run_id": test_run_id,
        "pipeline_id": "plid-test",
        "meta": {
            "pipeline_config_id": "plcid-legacy-value"  # Only legacy field present
        },
        "pipeline_spec_canonical": {"nodes": []},
    }

    agg.ingest(pipeline_start)

    # Create trace index
    trace_index = CoreTraceIndex(test_run_id, agg)
    meta = trace_index.get_meta()

    # config_id should get the value from pipeline_config_id (alias)
    assert (
        meta["config_id"] == "plcid-legacy-value"
    ), "config_id should use pipeline_config_id as fallback"

    # semantic_id should be None (no fallback)
    assert (
        meta["semantic_id"] is None
    ), "semantic_id must NOT fall back to pipeline_config_id"


def test_trace_adapter_semantic_id_no_fallback():
    """Test that semantic_id does NOT fall back to config_id or pipeline_config_id."""
    agg = TraceAggregator()
    test_run_id = "run-test-456"

    # Create event with config_id but NO semantic_id
    pipeline_start = {
        "record_type": "pipeline_start",
        "run_id": test_run_id,
        "pipeline_id": "plid-test",
        "meta": {
            "config_id": "plcid-some-value",
            "pipeline_config_id": "plcid-legacy-value",
            # Note: NO semantic_id field
        },
        "pipeline_spec_canonical": {"nodes": []},
    }

    agg.ingest(pipeline_start)
    trace_index = CoreTraceIndex(test_run_id, agg)
    meta = trace_index.get_meta()

    # semantic_id must be None (not substituted)
    assert (
        meta["semantic_id"] is None
    ), "semantic_id must NOT be substituted with config_id"

    # config_id should still be present
    assert meta["config_id"] == "plcid-some-value", "config_id should be correct"


def test_trace_adapter_both_fields_present():
    """Test that when both semantic_id and config_id are present, both are used."""
    agg = TraceAggregator()
    test_run_id = "run-test-789"

    pipeline_start = {
        "record_type": "pipeline_start",
        "run_id": test_run_id,
        "pipeline_id": "plid-test",
        "meta": {
            "semantic_id": "plsemid-explicit-value",
            "config_id": "plcid-explicit-value",
            "pipeline_config_id": "plcid-legacy-ignored",  # Should be ignored when config_id present
        },
        "pipeline_spec_canonical": {"nodes": []},
    }

    agg.ingest(pipeline_start)
    trace_index = CoreTraceIndex(test_run_id, agg)
    meta = trace_index.get_meta()

    # Both should use explicit values
    assert (
        meta["semantic_id"] == "plsemid-explicit-value"
    ), "semantic_id should use explicit value"
    assert (
        meta["config_id"] == "plcid-explicit-value"
    ), "config_id should prefer explicit value over alias"


def test_trace_adapter_config_id_prefers_new_field():
    """Test that config_id prefers the new field over the alias."""
    agg = TraceAggregator()
    test_run_id = "run-test-abc"

    pipeline_start = {
        "record_type": "pipeline_start",
        "run_id": test_run_id,
        "pipeline_id": "plid-test",
        "meta": {
            "config_id": "plcid-new-field",
            "pipeline_config_id": "plcid-old-field",  # Should be ignored
        },
        "pipeline_spec_canonical": {"nodes": []},
    }

    agg.ingest(pipeline_start)
    trace_index = CoreTraceIndex(test_run_id, agg)
    meta = trace_index.get_meta()

    # Should prefer the new field
    assert (
        meta["config_id"] == "plcid-new-field"
    ), "config_id should prefer explicit field over alias"


def test_trace_adapter_no_identity_fields():
    """Test behavior when no identity fields are present."""
    agg = TraceAggregator()
    test_run_id = "run-test-xyz"

    pipeline_start = {
        "record_type": "pipeline_start",
        "run_id": test_run_id,
        "pipeline_id": "plid-test",
        "meta": {},  # No identity fields
        "pipeline_spec_canonical": {"nodes": []},
    }

    agg.ingest(pipeline_start)
    trace_index = CoreTraceIndex(test_run_id, agg)
    meta = trace_index.get_meta()

    # Both should be None
    assert meta["semantic_id"] is None, "semantic_id should be None when not present"
    assert (
        meta["config_id"] is None
    ), "config_id should be None when neither field present"

    # Run ID and Pipeline ID should still be present
    assert meta["run_id"] == test_run_id
    assert meta["pipeline_id"] == "plid-test"
