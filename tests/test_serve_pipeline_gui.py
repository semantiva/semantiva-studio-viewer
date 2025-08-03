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

import pytest
from fastapi.testclient import TestClient

from semantiva import Pipeline
from semantiva_studio_viewer.pipeline import app, build_pipeline_json
from semantiva.examples.test_utils import FloatMultiplyOperation, FloatCollectValueProbe


@pytest.fixture
def test_pipeline():
    """Generate a pipeline for testing."""
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]

    return Pipeline(node_configuration)


@pytest.fixture
def test_client(test_pipeline):
    """Create a FastAPI test client with the test pipeline."""
    # Set the configuration data for testing
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]
    app.state.config = node_configuration

    # Also set the pipeline for backward compatibility
    app.state.pipeline = test_pipeline

    # Return the test client
    return TestClient(app)


def test_build_pipeline_json(test_pipeline):
    """Test the build_pipeline_json function using Semantiva's inspection system."""
    # Get the pipeline JSON (now generated via inspection system)
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]
    pipeline_json = build_pipeline_json(node_configuration)

    # Check basic structure
    assert "nodes" in pipeline_json
    assert "edges" in pipeline_json

    # Check nodes
    assert len(pipeline_json["nodes"]) == 4  # Four nodes in our test pipeline

    # Check first node
    first_node = pipeline_json["nodes"][0]
    assert first_node["label"] == "FloatCollectValueProbe"
    assert "parameters" in first_node
    assert "parameter_resolution" in first_node

    # Check edges
    assert len(pipeline_json["edges"]) == 3  # Three edges connecting four nodes
    assert pipeline_json["edges"][0]["source"] == 1
    assert pipeline_json["edges"][0]["target"] == 2


def test_get_pipeline_endpoint(test_client):
    """Test the /api/pipeline endpoint."""
    # Call the endpoint
    response = test_client.get("/api/pipeline")

    # Check response
    assert response.status_code == 200

    # Parse JSON response
    data = response.json()

    # Check structure
    assert "nodes" in data
    assert "edges" in data

    # Check that nodes have expected data
    assert len(data["nodes"]) == 4
    assert data["nodes"][0]["label"] == "FloatCollectValueProbe"
    assert data["nodes"][1]["label"] == "FloatMultiplyOperation"


def test_index_endpoint(test_client):
    """Test the / endpoint."""
    response = test_client.get("/")
    assert (
        response.status_code == 200 or response.status_code == 404
    )  # 404 is acceptable if the file doesn't exist in test


def test_pipeline_json_has_parameter_resolution(test_pipeline):
    """Test that the pipeline JSON includes parameter resolution data."""
    # Get the pipeline JSON
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]
    pipeline_json = build_pipeline_json(node_configuration)

    # Check that each node has parameter resolution data
    for node in pipeline_json["nodes"]:
        assert "parameter_resolution" in node
        if node["label"] == "FloatMultiplyOperation":
            # factor should appear in parameter resolution from config or context
            param_res = node["parameter_resolution"]
            assert "factor" in param_res.get(
                "from_pipeline_config", {}
            ) or "factor" in param_res.get("from_context", {})


def test_pipeline_json_includes_pipeline_config_params(test_pipeline):
    """Nodes should include pipelineConfigParams list."""
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]
    pipeline_json = build_pipeline_json(node_configuration)
    for node in pipeline_json["nodes"]:
        assert "pipelineConfigParams" in node
    multiply_node = next(
        n for n in pipeline_json["nodes"] if n["label"] == "FloatMultiplyOperation"
    )
    assert multiply_node["pipelineConfigParams"] == ["factor"]


def test_pipeline_json_includes_context_params(test_pipeline):
    """Nodes should include contextParams list with context-sourced params."""
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]
    pipeline_json = build_pipeline_json(node_configuration)
    for node in pipeline_json["nodes"]:
        assert "contextParams" in node
    rename_node = next(n for n in pipeline_json["nodes"] if "Rename" in n["label"])
    delete_node = next(n for n in pipeline_json["nodes"] if "Delete" in n["label"])
    assert rename_node["contextParams"] == ["factor"]
    assert delete_node["contextParams"] == ["renamed_key"]


def test_pipeline_json_node_ids_start_from_one(test_pipeline):
    """Node IDs should start from 1 instead of 0."""
    node_configuration = [
        {"processor": FloatCollectValueProbe, "context_keyword": "factor"},
        {"processor": FloatMultiplyOperation, "parameters": {"factor": 2}},
        {"processor": "rename:factor:renamed_key"},
        {"processor": "delete:renamed_key"},
    ]
    pipeline_json = build_pipeline_json(node_configuration)
    node_ids = [node["id"] for node in pipeline_json["nodes"]]
    assert node_ids == list(range(1, len(node_ids) + 1))


def test_index_html_references_static_assets(test_client):
    """Index HTML should reference compiled static assets."""
    resp = test_client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "/static/pipeline.js" in html
    assert "/static/pipeline.css" in html
