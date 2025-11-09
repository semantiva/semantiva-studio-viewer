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

"""Integration test: Viewer in YAML-only mode (inspection)."""

import pytest
from fastapi.testclient import TestClient
from semantiva_studio_viewer.pipeline import app


@pytest.fixture
def yaml_only_viewer():
    """Fixture that sets up a viewer with YAML configuration only (no trace)."""
    # Simple test configuration
    test_config = [
        {
            "component": "semantiva.testing.identity_test_processor",
            "label": "test_node",
            "params": {"value": 42},
        }
    ]

    # Set up app state
    app.state.config = test_config
    app.state.config_filename = "test_pipeline.yaml"
    app.state.trace_index = None
    app.state.trace_loaded = True
    app.state.raw_yaml = {}

    return TestClient(app)


def test_yaml_only_mode_api_pipeline_response(yaml_only_viewer):
    """Test /api/pipeline response in YAML-only mode."""
    response = yaml_only_viewer.get("/api/pipeline")

    assert response.status_code == 200
    data = response.json()

    # Must have identity from inspection.build
    assert "identity" in data
    identity = data["identity"]

    # YAML identities must be present
    assert "semantic_id" in identity
    assert "config_id" in identity
    assert "run_space" in identity

    # Runtime IDs must NOT be present
    assert "pipeline_id" not in data, "pipeline_id must NOT appear in inspection mode"
    assert "run_id" not in data, "run_id must NOT appear in inspection mode"
    assert "pipeline_id" not in identity
    assert "run_id" not in identity

    # run_space.inputs_id must be None
    assert identity["run_space"]["inputs_id"] is None


def test_yaml_only_mode_ui_shows_correct_fields(yaml_only_viewer):
    """Test that UI receives correct identity structure for YAML-only mode."""
    response = yaml_only_viewer.get("/api/pipeline")
    data = response.json()

    identity = data["identity"]

    # Fields that SHOULD be present in UI (YAML identities)
    expected_yaml_fields = ["semantic_id", "config_id"]
    for field in expected_yaml_fields:
        assert field in identity, f"{field} should be available for UI"

    # Fields that should NOT be present (runtime IDs)
    forbidden_fields = ["pipeline_id", "run_id"]
    for field in forbidden_fields:
        assert field not in data, f"{field} must not be in response"
        assert field not in identity, f"{field} must not be in identity"


def test_yaml_only_mode_identity_deterministic(yaml_only_viewer):
    """Test that identity is deterministic across multiple requests."""
    response1 = yaml_only_viewer.get("/api/pipeline")
    response2 = yaml_only_viewer.get("/api/pipeline")

    data1 = response1.json()
    data2 = response2.json()

    # Same configuration must produce same identities
    assert data1["identity"]["semantic_id"] == data2["identity"]["semantic_id"]
    assert data1["identity"]["config_id"] == data2["identity"]["config_id"]


def test_yaml_only_mode_no_trace_endpoints():
    """Test that trace endpoints return 404 or empty when no trace is loaded."""
    # This test verifies that in YAML-only mode, trace endpoints handle missing data gracefully
    # Implementation depends on existing trace endpoint behavior
    pass  # Placeholder - extend based on actual trace endpoint implementation
