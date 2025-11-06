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

"""Run-space aware trace index adapter for viewer."""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import json


class RunRecord:
    """Metadata for a single run with optional run-space decoration."""

    __slots__ = (
        "run_id",
        "run_space_launch_id",
        "run_space_attempt",
        "run_space_index",
        "position",
        "started_at",
        "finished_at",
        "status",
    )

    run_id: str
    run_space_launch_id: Optional[str]
    run_space_attempt: Optional[int]
    run_space_index: Optional[int]
    position: int
    started_at: Optional[str]
    finished_at: Optional[str]
    status: str

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class TraceIndexWithRunSpace:
    """
    Thin wrapper around existing trace loading. It must precompute:
      - launches: {(launch_id, attempt): {"mode": str, "total": int}}
      - runs_by_launch: {(launch_id, attempt): [RunRecord,...]}
      - runs_none: [RunRecord,...]
    """

    def __init__(self, base_index: Any, trace_path: Optional[str] = None) -> None:
        self._base = base_index
        self._trace_path = trace_path
        self._launches: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self._runs_by_launch: Dict[Tuple[str, int], List[RunRecord]] = defaultdict(list)
        self._runs_none: List[RunRecord] = []
        self._run_space_metadata: Dict[str, Dict[str, Any]] = {}  # run_id -> metadata
        self._hydrate()

    def _load_run_space_metadata(self) -> None:
        """Scan trace file for run-space metadata not stored in aggregator."""
        if not self._trace_path:
            return

        try:
            if self._trace_path.endswith(".jsonl"):
                with open(self._trace_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if rec.get("record_type") == "pipeline_start":
                            run_id = rec.get("run_id")
                            if run_id and "run_space_index" in rec:
                                self._run_space_metadata[run_id] = {
                                    "run_space_index": rec.get("run_space_index"),
                                    "run_space_combine_mode": rec.get(
                                        "run_space_combine_mode", "?"
                                    ),
                                }
            else:
                with open(self._trace_path, "r", encoding="utf-8") as fh:
                    try:
                        arr = json.load(fh)
                    except Exception:
                        arr = []
                if isinstance(arr, list):
                    for rec in arr:
                        if (
                            isinstance(rec, dict)
                            and rec.get("record_type") == "pipeline_start"
                        ):
                            run_id = rec.get("run_id")
                            if run_id and "run_space_index" in rec:
                                self._run_space_metadata[run_id] = {
                                    "run_space_index": rec.get("run_space_index"),
                                    "run_space_combine_mode": rec.get(
                                        "run_space_combine_mode", "?"
                                    ),
                                }
        except Exception as e:
            print(f"Warning: Failed to load run-space metadata: {e}")

    def _hydrate(self) -> None:
        # Load additional run-space metadata from trace file
        self._load_run_space_metadata()

        # Access the underlying TraceAggregator to get run-space metadata
        position = 0
        for run_agg in self._base._agg.iter_runs():
            position += 1

            # Extract run-space fields directly from RunAggregate
            launch_id = getattr(run_agg, "run_space_launch_id", None)
            attempt = getattr(run_agg, "run_space_attempt", None)

            # Get additional metadata from trace file scan
            run_metadata = self._run_space_metadata.get(run_agg.run_id, {})
            index = run_metadata.get("run_space_index")
            combine_mode = run_metadata.get("run_space_combine_mode", "?")

            # Determine status
            status = "unknown"
            if run_agg.saw_end:
                status = "finished"
            elif run_agg.saw_start:
                status = "running"

            rr = RunRecord(
                run_id=run_agg.run_id,
                run_space_launch_id=launch_id,
                run_space_attempt=attempt,
                run_space_index=index,
                position=position,
                started_at=run_agg.start_timestamp,
                finished_at=run_agg.end_timestamp,
                status=status,
            )
            if rr.run_space_launch_id and rr.run_space_attempt is not None:
                key = (rr.run_space_launch_id, rr.run_space_attempt)
                self._runs_by_launch[key].append(rr)
                if key not in self._launches:
                    self._launches[key] = {
                        "mode": combine_mode,
                        "total": 0,
                    }
            else:
                self._runs_none.append(rr)

        for key in self._runs_by_launch:
            self._launches[key]["total"] = len(self._runs_by_launch[key])

    def _get_launch_metadata_from_trace(
        self, launch_id: str, attempt: int
    ) -> Optional[Dict[str, Any]]:
        """Scan trace file for run_space_start event to get full metadata."""
        if not self._trace_path:
            return None

        try:
            if self._trace_path.endswith(".jsonl"):
                with open(self._trace_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if (
                            rec.get("record_type") == "run_space_start"
                            and rec.get("run_space_launch_id") == launch_id
                            and rec.get("run_space_attempt") == attempt
                        ):
                            result: Dict[str, Any] = rec
                            return result
            else:
                with open(self._trace_path, "r", encoding="utf-8") as fh:
                    try:
                        arr = json.load(fh)
                    except Exception:
                        return None
                if isinstance(arr, list):
                    for rec in arr:
                        if (
                            isinstance(rec, dict)
                            and rec.get("record_type") == "run_space_start"
                            and rec.get("run_space_launch_id") == launch_id
                            and rec.get("run_space_attempt") == attempt
                        ):
                            result_dict: Dict[str, Any] = rec
                            return result_dict
        except Exception as e:
            print(f"Warning: Failed to scan for launch metadata: {e}")
        return None

    # ---- API consumed by runspace_api.py ----
    def get_runspace_launches(
        self,
    ) -> Tuple[List[Tuple[str, int, str, int]], bool]:
        launches = [
            (lid, attempt, str(meta["mode"]), int(meta["total"]))
            for (lid, attempt), meta in sorted(self._launches.items())
        ]
        return launches, bool(self._runs_none)

    def get_runs_for_runspace(self, launch_id: str, attempt: int) -> List[RunRecord]:
        return list(self._runs_by_launch.get((launch_id, attempt), []))

    def get_runs_without_runspace(self) -> List[RunRecord]:
        return list(self._runs_none)

    def get_all_runs(self) -> List[RunRecord]:
        # Flatten preserving original position order
        out = list(self._runs_none)
        for key in sorted(self._runs_by_launch):
            out.extend(self._runs_by_launch[key])
        # Keep stable order by .position
        return sorted(out, key=lambda r: r.position)

    def get_launch_details(
        self, launch_id: str, attempt: int
    ) -> Optional[Dict[str, Any]]:
        """Get detailed metadata for a specific run-space launch.

        Returns dict with spec_id, combine_mode, fingerprints, planner_meta, etc.
        Returns None if launch not found.
        """
        # Check if launch exists
        key = (launch_id, attempt)
        if key not in self._launches:
            return None

        # Get launch aggregate from base aggregator
        launch_agg = self._base._agg.get_launch(launch_id, attempt)
        if not launch_agg:
            return None

        # Get additional metadata from raw trace (combine_mode, max_runs_limit, summary)
        trace_meta = self._get_launch_metadata_from_trace(launch_id, attempt)

        # Get total runs from our index
        total_runs = self._launches[key]["total"]

        result: Dict[str, Any] = {
            "launch_id": launch_id,
            "attempt": attempt,
            "spec_id": launch_agg.run_space_spec_id,
            "combine_mode": (
                trace_meta.get("run_space_combine_mode") if trace_meta else None
            ),
            "total_runs": int(total_runs),
            "planned_run_count": launch_agg.planned_run_count,
            "max_runs_limit": (
                trace_meta.get("run_space_max_runs_limit") if trace_meta else None
            ),
            "inputs_id": launch_agg.run_space_inputs_id,
            "fingerprints": launch_agg.input_fingerprints or [],
            "planner_meta": (
                trace_meta.get("summary", {}).get("planner_meta")
                if trace_meta
                else None
            ),
        }
        return result
