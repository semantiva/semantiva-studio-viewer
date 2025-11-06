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

"""Tests for run-space launch details API endpoint."""

import pytest
from fastapi.testclient import TestClient
from semantiva_studio_viewer.pipeline import app
from semantiva_studio_viewer.core_trace_index import MultiTraceIndex
from semantiva_studio_viewer.trace_index_with_runspace import TraceIndexWithRunSpace
import json
import tempfile
import os


def _create_trace_with_runspace(
    launch_id, attempt, spec_id="rss-test", combine_mode="product"
):
    """Create a temporary trace file with run-space data."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)

    lines = [
        # Run-space start
        {
            "record_type": "run_space_start",
            "run_space_launch_id": launch_id,
            "run_space_attempt": attempt,
            "run_space_spec_id": spec_id,
            "run_space_combine_mode": combine_mode,
            "run_space_planned_run_count": 2,
            "run_space_max_runs_limit": 10,
            "run_space_inputs_id": "rsi-inputs-123",
            "run_space_input_fingerprints": [
                {
                    "uri": "s3://bucket/file1.csv",
                    "digest": "sha256:abc123",
                    "size": 1024,
                },
                {
                    "uri": "s3://bucket/file2.csv",
                    "digest": "sha256:def456",
                    "size": 2048,
                },
            ],
            "summary": {
                "planner_meta": {
                    "blocks": [
                        {
                            "source": {"format": "csv", "path": "file1.csv"},
                            "count": 100,
                        },
                        {
                            "source": {"format": "csv", "path": "file2.csv"},
                            "count": 200,
                        },
                    ]
                }
            },
        },
        # Pipeline runs
        {
            "record_type": "pipeline_start",
            "run_id": "run-1",
            "pipeline_id": "test-pipeline",
            "run_space_launch_id": launch_id,
            "run_space_attempt": attempt,
            "run_space_index": 0,
            "run_space_combine_mode": combine_mode,
            "pipeline_spec_canonical": {"nodes": []},
        },
        {"record_type": "pipeline_end", "run_id": "run-1"},
        {
            "record_type": "pipeline_start",
            "run_id": "run-2",
            "pipeline_id": "test-pipeline",
            "run_space_launch_id": launch_id,
            "run_space_attempt": attempt,
            "run_space_index": 1,
            "run_space_combine_mode": combine_mode,
            "pipeline_spec_canonical": {"nodes": []},
        },
        {"record_type": "pipeline_end", "run_id": "run-2"},
        # Run-space end
        {
            "record_type": "run_space_end",
            "run_space_launch_id": launch_id,
            "run_space_attempt": attempt,
        },
    ]

    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    return path


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


def test_launch_details_success(test_client):
    """Test getting launch details for a valid launch."""
    path = _create_trace_with_runspace("rsl-alpha", 1, "rss-spec-abc", "product")

    try:
        mti = MultiTraceIndex.from_json_or_jsonl(path)
        runspace_index = TraceIndexWithRunSpace(mti, path)
        app.state.runspace_index = runspace_index

        response = test_client.get(
            "/api/runspace/launch_details?launch_id=rsl-alpha&attempt=1"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["launch_id"] == "rsl-alpha"
        assert data["attempt"] == 1
        assert data["spec_id"] == "rss-spec-abc"
        assert data["combine_mode"] == "product"
        assert data["total_runs"] == 2
        assert data["planned_run_count"] == 2
        assert data["max_runs_limit"] == 10
        assert data["inputs_id"] == "rsi-inputs-123"
        assert len(data["fingerprints"]) == 2
        assert data["fingerprints"][0]["uri"] == "s3://bucket/file1.csv"
        assert data["fingerprints"][0]["digest"] == "sha256:abc123"
        assert data["fingerprints"][0]["size"] == 1024
        assert data["planner_meta"] is not None
        assert "blocks" in data["planner_meta"]
        assert len(data["planner_meta"]["blocks"]) == 2
    finally:
        os.unlink(path)
        if hasattr(app.state, "runspace_index"):
            delattr(app.state, "runspace_index")


def test_launch_details_not_found(test_client):
    """Test 404 for non-existent launch."""
    path = _create_trace_with_runspace("rsl-alpha", 1)

    try:
        mti = MultiTraceIndex.from_json_or_jsonl(path)
        runspace_index = TraceIndexWithRunSpace(mti, path)
        app.state.runspace_index = runspace_index

        response = test_client.get(
            "/api/runspace/launch_details?launch_id=unknown&attempt=999"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        os.unlink(path)
        if hasattr(app.state, "runspace_index"):
            delattr(app.state, "runspace_index")


def test_launch_details_missing_params(test_client):
    """Test that missing parameters are validated."""
    path = _create_trace_with_runspace("rsl-alpha", 1)

    try:
        mti = MultiTraceIndex.from_json_or_jsonl(path)
        runspace_index = TraceIndexWithRunSpace(mti, path)
        app.state.runspace_index = runspace_index

        # Missing launch_id
        response = test_client.get("/api/runspace/launch_details?attempt=1")
        assert response.status_code == 422  # FastAPI validation error

        # Missing attempt
        response = test_client.get("/api/runspace/launch_details?launch_id=rsl-alpha")
        assert response.status_code == 422
    finally:
        os.unlink(path)
        if hasattr(app.state, "runspace_index"):
            delattr(app.state, "runspace_index")


def test_launch_details_no_index(test_client):
    """Test graceful handling when runspace_index is not loaded."""
    if hasattr(app.state, "runspace_index"):
        delattr(app.state, "runspace_index")

    response = test_client.get(
        "/api/runspace/launch_details?launch_id=rsl-alpha&attempt=1"
    )
    # When no index is loaded, the endpoint will throw an error trying to access it
    # FastAPI will return 500
    assert response.status_code in [404, 500]  # Either not found or internal error


def test_launch_details_multiple_attempts(test_client):
    """Test that different attempts of same launch are distinct."""
    path1 = _create_trace_with_runspace("rsl-alpha", 1, "rss-v1", "product")
    path2 = _create_trace_with_runspace("rsl-alpha", 2, "rss-v2", "zip")

    try:
        # Load first trace
        mti1 = MultiTraceIndex.from_json_or_jsonl(path1)
        runspace_index1 = TraceIndexWithRunSpace(mti1, path1)
        app.state.runspace_index = runspace_index1

        response = test_client.get(
            "/api/runspace/launch_details?launch_id=rsl-alpha&attempt=1"
        )
        assert response.status_code == 200
        data1 = response.json()
        assert data1["spec_id"] == "rss-v1"
        assert data1["combine_mode"] == "product"

        # Attempt 2 should not exist in this trace
        response = test_client.get(
            "/api/runspace/launch_details?launch_id=rsl-alpha&attempt=2"
        )
        assert response.status_code == 404

        # Load second trace
        mti2 = MultiTraceIndex.from_json_or_jsonl(path2)
        runspace_index2 = TraceIndexWithRunSpace(mti2, path2)
        app.state.runspace_index = runspace_index2

        response = test_client.get(
            "/api/runspace/launch_details?launch_id=rsl-alpha&attempt=2"
        )
        assert response.status_code == 200
        data2 = response.json()
        assert data2["spec_id"] == "rss-v2"
        assert data2["combine_mode"] == "zip"
    finally:
        os.unlink(path1)
        os.unlink(path2)
        if hasattr(app.state, "runspace_index"):
            delattr(app.state, "runspace_index")


def test_launch_details_without_optional_fields(test_client):
    """Test launch details when optional fields are missing."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)

    # Minimal run-space start (no max_runs_limit, no planner_meta)
    lines = [
        {
            "record_type": "run_space_start",
            "run_space_launch_id": "rsl-minimal",
            "run_space_attempt": 1,
            "run_space_spec_id": "rss-min",
            "run_space_planned_run_count": 1,
            "run_space_inputs_id": "rsi-min",
            "run_space_input_fingerprints": [],
        },
        {
            "record_type": "pipeline_start",
            "run_id": "run-1",
            "pipeline_id": "test-pipeline",
            "run_space_launch_id": "rsl-minimal",
            "run_space_attempt": 1,
            "pipeline_spec_canonical": {"nodes": []},
        },
        {"record_type": "pipeline_end", "run_id": "run-1"},
    ]

    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    try:
        mti = MultiTraceIndex.from_json_or_jsonl(path)
        runspace_index = TraceIndexWithRunSpace(mti, path)
        app.state.runspace_index = runspace_index

        response = test_client.get(
            "/api/runspace/launch_details?launch_id=rsl-minimal&attempt=1"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["launch_id"] == "rsl-minimal"
        assert data["max_runs_limit"] is None
        assert data["planner_meta"] is None
        assert data["fingerprints"] == []
        assert data["combine_mode"] is None  # Not in minimal start event
    finally:
        os.unlink(path)
        if hasattr(app.state, "runspace_index"):
            delattr(app.state, "runspace_index")
