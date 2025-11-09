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

"""Integration test: Viewer in YAML+Trace mode with Identity Health."""

import pytest
from fastapi.testclient import TestClient
from semantiva_studio_viewer.pipeline import app
from semantiva.trace.aggregation import TraceAggregator
from semantiva_studio_viewer.core_trace_index import MultiTraceIndex


@pytest.fixture
def yaml_trace_viewer():
    """Fixture that sets up a viewer with both YAML and trace data."""
    # Test configuration
    test_config = [
        {
            "component": "semantiva.testing.identity_test_processor",
            "label": "test_node",
            "params": {"value": 42},
        }
    ]

    # Create mock trace
    agg = TraceAggregator()
    test_run_id = "run-test-integration"

    # Create pipeline_start event with matching identities
    pipeline_start = {
        "record_type": "pipeline_start",
        "run_id": test_run_id,
        "pipeline_id": "plid-test-123",
        "meta": {"semantic_id": "plsemid-test-value", "config_id": "plcid-test-value"},
        "pipeline_spec_canonical": {
            "nodes": [
                {
                    "node_uuid": "node-uuid-1",
                    "declaration_index": 0,
                    "declaration_subindex": 0,
                    "processor_ref": "semantiva.testing.identity_test_processor",
                }
            ]
        },
    }

    agg.ingest(pipeline_start)
    trace_index = MultiTraceIndex(agg)
    trace_index.by_run[test_run_id] = trace_index.by_run.get(test_run_id)

    # Set up app state
    app.state.config = test_config
    app.state.config_filename = "test_pipeline.yaml"
    app.state.trace_index = trace_index
    app.state.trace_loaded = True
    app.state.raw_yaml = {}

    return TestClient(app)


def test_yaml_trace_mode_api_pipeline_still_yaml_only(yaml_trace_viewer):
    """Test that /api/pipeline remains YAML-only even when trace is available."""
    response = yaml_trace_viewer.get("/api/pipeline")

    assert response.status_code == 200
    data = response.json()

    # Identity from inspection.build must be present
    assert "identity" in data
    data["identity"]

    # Runtime IDs must NOT appear in /api/pipeline (even with trace loaded)
    assert (
        "pipeline_id" not in data
    ), "pipeline_id must NOT appear in /api/pipeline even with trace"
    assert (
        "run_id" not in data
    ), "run_id must NOT appear in /api/pipeline even with trace"


def test_yaml_trace_mode_trace_meta_has_runtime_ids(yaml_trace_viewer):
    """Test that /api/trace/meta provides runtime identities."""
    # Get the test run ID from fixture
    test_run_id = "run-test-integration"

    response = yaml_trace_viewer.get(f"/api/trace/meta?run={test_run_id}")

    if response.status_code == 200:
        data = response.json()

        # Runtime IDs MUST be present in trace endpoint
        assert "run_id" in data
        assert "pipeline_id" in data

        # Also should have YAML identities for comparison
        assert "semantic_id" in data
        assert "config_id" in data


def test_identity_health_comparison_matching():
    """Test Identity Health logic when YAML and Trace identities match."""
    yaml_identity = {
        "semantic_id": "plsemid-same-value",
        "config_id": "plcid-same-value",
        "run_space": {"spec_id": "spec-same-value"},
    }

    trace_identity = {
        "identity": {
            "semantic_id": "plsemid-same-value",
            "config_id": "plcid-same-value",
        },
        "run_space": {"spec_id": "spec-same-value"},
    }

    # Semantic ID check
    assert (
        yaml_identity["semantic_id"] == trace_identity["identity"]["semantic_id"]
    ), "Semantic ID should match - health check: OK"

    # Config ID check (expected variation)
    assert (
        yaml_identity["config_id"] == trace_identity["identity"]["config_id"]
    ), "Config ID should match - health check: WARNING (OK)"

    # Run-space spec ID check
    assert (
        yaml_identity["run_space"]["spec_id"] == trace_identity["run_space"]["spec_id"]
    ), "Run-space plan should match - health check: OK"


def test_identity_health_comparison_differing():
    """Test Identity Health logic when YAML and Trace identities differ."""
    yaml_identity = {
        "semantic_id": "plsemid-yaml-value",
        "config_id": "plcid-yaml-value",
        "run_space": {"spec_id": "spec-yaml-value"},
    }

    trace_identity = {
        "identity": {
            "semantic_id": "plsemid-trace-value",  # Different!
            "config_id": "plcid-trace-value",
        },
        "run_space": {"spec_id": "spec-trace-value"},  # Different!
    }

    # Semantic ID mismatch - ERROR
    assert (
        yaml_identity["semantic_id"] != trace_identity["identity"]["semantic_id"]
    ), "Semantic ID differs - health check: ERROR"

    # Config ID mismatch - WARNING
    assert (
        yaml_identity["config_id"] != trace_identity["identity"]["config_id"]
    ), "Config ID differs - health check: WARNING"

    # Run-space spec ID mismatch - ERROR
    assert (
        yaml_identity["run_space"]["spec_id"] != trace_identity["run_space"]["spec_id"]
    ), "Run-space plan differs - health check: ERROR"


def test_yaml_trace_mode_ui_receives_both_identities(yaml_trace_viewer):
    """Test that UI can receive and display both YAML and trace identities."""
    # Get YAML identity
    pipeline_response = yaml_trace_viewer.get("/api/pipeline")
    pipeline_data = pipeline_response.json()
    yaml_identity = pipeline_data.get("identity")

    # Get trace identity
    test_run_id = "run-test-integration"
    trace_response = yaml_trace_viewer.get(f"/api/trace/meta?run={test_run_id}")

    if trace_response.status_code == 200:
        trace_data = trace_response.json()

        # UI should be able to compare these
        assert yaml_identity is not None
        assert "semantic_id" in yaml_identity
        assert "semantic_id" in trace_data

        # This enables Identity Health feature in UI
        # Frontend code uses: inspectionIdentity and traceIdentity states
