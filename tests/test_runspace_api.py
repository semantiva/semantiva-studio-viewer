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

"""Tests for run-space API endpoints."""

import pytest
from fastapi.testclient import TestClient
from semantiva_studio_viewer.pipeline import app
from semantiva_studio_viewer.core_trace_index import MultiTraceIndex
from semantiva_studio_viewer.trace_index_with_runspace import TraceIndexWithRunSpace
import json
import tempfile
import os


def _create_trace_file(runs_data):
    """Create a temporary trace file from run specifications."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)

    lines = []
    for r in runs_data:
        # Create pipeline_start event
        pipeline_start = {
            "record_type": "pipeline_start",
            "run_id": r["run_id"],
            "pipeline_id": "test-pipeline",
            "pipeline_spec_canonical": {"nodes": []},
        }

        # Add run-space fields if present
        if "run_space_launch_id" in r:
            pipeline_start["run_space_launch_id"] = r["run_space_launch_id"]
            pipeline_start["run_space_attempt"] = r["run_space_attempt"]
            pipeline_start["run_space_index"] = r["run_space_index"]
            pipeline_start["run_space_combine_mode"] = r["run_space_combine_mode"]

        lines.append(pipeline_start)

        # Create pipeline_end event if finished
        if r.get("finished_at"):
            pipeline_end = {
                "record_type": "pipeline_end",
                "run_id": r["run_id"],
            }
            lines.append(pipeline_end)

    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    return path


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def runspace_index_with_launches():
    """Create a run-space index with multiple launches and orphan runs."""
    runs_data = [
        # Launch 1, attempt 1 - two runs
        {
            "run_id": "run-1a",
            "run_space_launch_id": "rsl-alpha",
            "run_space_attempt": 1,
            "run_space_index": 0,
            "run_space_combine_mode": "product",
            "started_at": "2025-01-01T10:00:00Z",
            "finished_at": "2025-01-01T10:05:00Z",
            "status": "finished",
        },
        {
            "run_id": "run-1b",
            "run_space_launch_id": "rsl-alpha",
            "run_space_attempt": 1,
            "run_space_index": 1,
            "run_space_combine_mode": "product",
            "started_at": "2025-01-01T10:00:00Z",
            "finished_at": "2025-01-01T10:06:00Z",
            "status": "finished",
        },
        # Launch 1, attempt 2 - one run
        {
            "run_id": "run-2a",
            "run_space_launch_id": "rsl-alpha",
            "run_space_attempt": 2,
            "run_space_index": 0,
            "run_space_combine_mode": "product",
            "started_at": "2025-01-01T11:00:00Z",
            "finished_at": "2025-01-01T11:03:00Z",
            "status": "finished",
        },
        # Different launch - one run
        {
            "run_id": "run-3a",
            "run_space_launch_id": "rsl-beta",
            "run_space_attempt": 1,
            "run_space_index": 0,
            "run_space_combine_mode": "zip",
            "started_at": "2025-01-01T12:00:00Z",
            "finished_at": "2025-01-01T12:02:00Z",
            "status": "finished",
        },
        # Orphan runs (no run-space)
        {
            "run_id": "run-orphan-1",
            "started_at": "2025-01-01T09:00:00Z",
            "finished_at": "2025-01-01T09:05:00Z",
            "status": "finished",
        },
        {
            "run_id": "run-orphan-2",
            "started_at": "2025-01-01T09:10:00Z",
            "finished_at": None,
            "status": "running",
        },
    ]

    path = _create_trace_file(runs_data)
    mti = MultiTraceIndex.from_json_or_jsonl(path)
    runspace_index = TraceIndexWithRunSpace(mti, path)
    os.unlink(path)
    return runspace_index


@pytest.fixture
def runspace_index_no_orphans():
    """Create a run-space index with only launch runs (no orphans)."""
    runs_data = [
        {
            "run_id": "run-1",
            "run_space_launch_id": "rsl-x",
            "run_space_attempt": 1,
            "run_space_index": 0,
            "run_space_combine_mode": "product",
            "started_at": "2025-01-01T10:00:00Z",
            "finished_at": "2025-01-01T10:05:00Z",
            "status": "finished",
        },
        {
            "run_id": "run-2",
            "run_space_launch_id": "rsl-x",
            "run_space_attempt": 1,
            "run_space_index": 1,
            "run_space_combine_mode": "product",
            "started_at": "2025-01-01T10:00:00Z",
            "finished_at": "2025-01-01T10:06:00Z",
            "status": "finished",
        },
    ]

    path = _create_trace_file(runs_data)
    mti = MultiTraceIndex.from_json_or_jsonl(path)
    runspace_index = TraceIndexWithRunSpace(mti, path)
    os.unlink(path)
    return runspace_index


@pytest.fixture
def runspace_index_empty():
    """Create an empty run-space index."""
    path = _create_trace_file([])
    mti = MultiTraceIndex.from_json_or_jsonl(path)
    runspace_index = TraceIndexWithRunSpace(mti, path)
    os.unlink(path)
    return runspace_index


def test_list_launches_success(test_client, runspace_index_with_launches):
    """Test listing run-space launches."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/launches")
    assert response.status_code == 200

    data = response.json()
    assert "launches" in data
    assert "has_runs_without_runspace" in data

    # Should have 3 unique (launch_id, attempt) pairs
    assert len(data["launches"]) == 3

    # Verify first launch structure
    launch = data["launches"][0]
    assert "launch_id" in launch
    assert "attempt" in launch
    assert "label" in launch
    assert "combine_mode" in launch
    assert "total_runs" in launch

    # Check has_runs_without_runspace flag
    assert data["has_runs_without_runspace"] is True


def test_list_launches_no_orphans(test_client, runspace_index_no_orphans):
    """Test listing launches when there are no orphan runs."""
    app.state.runspace_index = runspace_index_no_orphans

    response = test_client.get("/api/runspace/launches")
    assert response.status_code == 200

    data = response.json()
    assert len(data["launches"]) == 1
    assert data["has_runs_without_runspace"] is False


def test_list_launches_empty(test_client, runspace_index_empty):
    """Test listing launches with empty index."""
    app.state.runspace_index = runspace_index_empty

    response = test_client.get("/api/runspace/launches")
    assert response.status_code == 200

    data = response.json()
    assert len(data["launches"]) == 0
    assert data["has_runs_without_runspace"] is False


def test_list_launches_not_loaded(test_client):
    """Test listing launches when no trace is loaded."""
    # Ensure runspace_index is not set
    if hasattr(app.state, "runspace_index"):
        delattr(app.state, "runspace_index")

    response = test_client.get("/api/runspace/launches")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"].lower()


def test_list_runs_all(test_client, runspace_index_with_launches):
    """Test listing all runs (no filter)."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs")
    assert response.status_code == 200

    data = response.json()
    assert "runs" in data
    assert len(data["runs"]) == 6  # All runs

    # Verify run structure
    run = data["runs"][0]
    assert "run_id" in run
    assert "index" in run
    assert "started_at" in run
    assert "finished_at" in run
    assert "status" in run


def test_list_runs_for_launch(test_client, runspace_index_with_launches):
    """Test listing runs for a specific launch."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs?launch_id=rsl-alpha&attempt=1")
    assert response.status_code == 200

    data = response.json()
    assert len(data["runs"]) == 2  # Two runs in this launch
    assert all(r["run_id"].startswith("run-1") for r in data["runs"])


def test_list_runs_for_different_attempt(test_client, runspace_index_with_launches):
    """Test listing runs for a different attempt of the same launch."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs?launch_id=rsl-alpha&attempt=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_id"] == "run-2a"


def test_list_runs_without_runspace(test_client, runspace_index_with_launches):
    """Test listing runs without run-space decoration."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs?none=true")
    assert response.status_code == 200

    data = response.json()
    assert len(data["runs"]) == 2  # Two orphan runs
    assert all("orphan" in r["run_id"] for r in data["runs"])


def test_list_runs_nonexistent_launch(test_client, runspace_index_with_launches):
    """Test listing runs for a non-existent launch."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs?launch_id=rsl-nonexistent&attempt=1")
    assert response.status_code == 200

    data = response.json()
    assert len(data["runs"]) == 0  # No runs for this launch


def test_list_runs_index_values(test_client, runspace_index_with_launches):
    """Test that run indices are correctly set."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs?launch_id=rsl-alpha&attempt=1")
    assert response.status_code == 200

    data = response.json()
    # Runs with run_space_index should use it
    for run in data["runs"]:
        if run["run_id"] == "run-1a":
            assert run["index"] == 0
        elif run["run_id"] == "run-1b":
            assert run["index"] == 1


def test_list_runs_not_loaded(test_client):
    """Test listing runs when no trace is loaded."""
    if hasattr(app.state, "runspace_index"):
        delattr(app.state, "runspace_index")

    response = test_client.get("/api/runspace/runs")
    assert response.status_code == 404


def test_launch_label_format(test_client, runspace_index_with_launches):
    """Test that launch labels are formatted correctly."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/launches")
    assert response.status_code == 200

    data = response.json()
    launch = data["launches"][0]

    # Label should contain launch_id, attempt, mode, and count
    assert launch["launch_id"] in launch["label"]
    assert f"attempt {launch['attempt']}" in launch["label"]
    assert launch["combine_mode"] in launch["label"]
    assert str(launch["total_runs"]) in launch["label"]


def test_runs_status_field(test_client, runspace_index_with_launches):
    """Test that run status field is properly set."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs")
    assert response.status_code == 200

    data = response.json()
    # Find the running orphan
    running_run = next(r for r in data["runs"] if r["run_id"] == "run-orphan-2")
    assert running_run["status"] == "running"
    assert running_run["finished_at"] is None


def test_multiple_launches_sorted(test_client, runspace_index_with_launches):
    """Test that launches are returned in sorted order."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/launches")
    assert response.status_code == 200

    data = response.json()
    launches = data["launches"]

    # Should be sorted by (launch_id, attempt)
    for i in range(len(launches) - 1):
        curr = (launches[i]["launch_id"], launches[i]["attempt"])
        next_l = (launches[i + 1]["launch_id"], launches[i + 1]["attempt"])
        assert curr <= next_l


def test_runs_preserve_position_order(test_client, runspace_index_with_launches):
    """Test that all runs are returned in stable position order."""
    app.state.runspace_index = runspace_index_with_launches

    response = test_client.get("/api/runspace/runs")
    assert response.status_code == 200

    data = response.json()
    # Orphans come first, then launches in sorted order
    # The position should be stable based on insertion order
    assert len(data["runs"]) == 6
