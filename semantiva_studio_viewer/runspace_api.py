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

"""Run-space filtering API endpoints for viewer."""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/runspace")


def _get_runspace_index(request: Request) -> Any:
    """Get run-space aware trace index from app state."""
    if not hasattr(request.app.state, "runspace_index"):
        raise HTTPException(
            status_code=404, detail="Run-space data not available (no trace loaded)"
        )
    return request.app.state.runspace_index


@router.get("/launches")
def list_launches(request: Request) -> Dict[str, Any]:
    """Get list of run-space launches and whether runs without run-space exist.

    Returns:
        Dict containing launches array and has_runs_without_runspace flag
    """
    idx = _get_runspace_index(request)
    # Expected to return:
    #   launches: List[Tuple[str, int, str, int]]  -> (launch_id, attempt, combine_mode, total_runs)
    #   has_none: bool
    launches, has_none = idx.get_runspace_launches()
    payload = {
        "launches": [
            {
                "launch_id": lid,
                "attempt": attempt,
                "label": f"{lid} · attempt {attempt} · {mode} · {total}",
                "combine_mode": mode,
                "total_runs": total,
            }
            for (lid, attempt, mode, total) in launches
        ],
        "has_runs_without_runspace": bool(has_none),
    }
    return payload


@router.get("/runs")
def list_runs_for_launch(
    request: Request,
    launch_id: Optional[str] = None,
    attempt: Optional[int] = None,
    none: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Get runs filtered by run-space launch or none flag.

    Args:
        launch_id: Optional run-space launch ID
        attempt: Optional run-space attempt number
        none: If "true", return only runs without run-space decoration

    Returns:
        Dict containing runs array with run metadata
    """
    idx = _get_runspace_index(request)

    if none and none.lower() == "true":
        runs = idx.get_runs_without_runspace()
    elif launch_id and attempt is not None:
        runs = idx.get_runs_for_runspace(launch_id, attempt)
    else:
        runs = idx.get_all_runs()

    return {
        "runs": [
            {
                "run_id": r.run_id,
                "index": (
                    r.run_space_index if r.run_space_index is not None else r.position
                ),
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "status": r.status,
            }
            for r in runs
        ]
    }


@router.get("/launch_details")
def get_launch_details(
    request: Request,
    launch_id: str,
    attempt: int,
) -> Dict[str, Any]:
    """Get detailed metadata for a specific run-space launch.

    Args:
        launch_id: Run-space launch ID
        attempt: Run-space attempt number

    Returns:
        Dict containing launch details (spec_id, combine_mode, fingerprints, etc.)

    Raises:
        HTTPException: 404 if launch not found
    """
    idx = _get_runspace_index(request)

    details = idx.get_launch_details(launch_id, attempt)
    if not details:
        raise HTTPException(status_code=404, detail="Run-space launch not found")

    # Explicit type assertion to satisfy mypy
    result: Dict[str, Any] = details
    return result
