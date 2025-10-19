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

"""Core-backed trace index adapter for per-run visualization (no run-space)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from semantiva.trace.aggregation import TraceAggregator, RunAggregate

_MAX_EVENTS_PER_NODE = 500  # UI-only buffer


def _expected_positional_maps(spec: Optional[Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, Dict[str, int]], Dict[str, Dict[str, Any]]]:
    idx_to_uuid: Dict[str, str] = {}
    uuid_to_idx: Dict[str, Dict[str, int]] = {}
    canonical_nodes: Dict[str, Dict[str, Any]] = {}
    if not spec:
        return idx_to_uuid, uuid_to_idx, canonical_nodes
    nodes = spec.get("nodes") or []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        uuid = n.get("node_uuid")
        di = n.get("declaration_index")
        dsub = n.get("declaration_subindex", 0)
        if uuid is None or di is None:
            continue
        key = f"{int(di)}:{int(dsub)}"
        idx_to_uuid[key] = uuid
        uuid_to_idx[uuid] = {
            "declaration_index": int(di),
            "declaration_subindex": int(dsub),
        }
        canonical_nodes[key] = {
            "node_uuid": uuid,
            "declaration_index": int(di),
            "declaration_subindex": int(dsub),
        }
    return idx_to_uuid, uuid_to_idx, canonical_nodes


@dataclass
class CoreTraceIndex:
    """Per-run viewer adapter backed by Semantiva Core TraceAggregator (no run-space)."""

    run_id: str
    _agg: TraceAggregator
    _events_by_node: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    canonical_nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # ----- public API used by pipeline.py endpoints -----
    def get_meta(self) -> Dict[str, Any]:
        run: Optional[RunAggregate] = self._agg.get_run(self.run_id)
        if not run:
            return {
                "run_id": self.run_id,
                "node_mappings": {"index_to_uuid": {}, "uuid_to_index": {}},
            }
        idx_to_uuid, uuid_to_idx, canonical_nodes = _expected_positional_maps(
            run.pipeline_spec_canonical
        )
        # expose canonical_nodes for `/api/trace/meta` optional field
        self.canonical_nodes = canonical_nodes
        return {
            "run_id": run.run_id,
            "pipeline_id": run.pipeline_id,
            "started_at": run.start_ts,
            "ended_at": run.end_ts,
            "node_mappings": {
                "index_to_uuid": idx_to_uuid,
                "uuid_to_index": uuid_to_idx,
            },
        }

    def summary(self) -> Dict[str, Any]:
        run = self._agg.get_run(self.run_id)
        per_node = {}
        if run:
            for nid, na in run.nodes.items():
                timing = na.timing or {}
                # normalize wall_ms first for UI consumers (fallbacks remain for legacy traces)
                wall_ms = timing.get("wall_ms")
                if wall_ms is None:
                    wall_ms = timing.get("duration_ms")
                    if wall_ms is None and "duration" in timing:
                        try:
                            wall_ms = round(float(timing.get("duration", 0.0)) * 1000)
                        except Exception:
                            wall_ms = None
                    if wall_ms is not None:
                        timing["wall_ms"] = wall_ms
                per_node[nid] = {
                    "status": na.last_status or "unknown",
                    "timing": timing,
                    "error": na.last_error,
                    "counts": na.counts,
                }
        return {"nodes": per_node}

    def node_events(
        self, node_uuid: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        events = self._events_by_node.get(node_uuid, [])
        total = len(events)
        start = min(max(offset, 0), total)
        end = min(start + max(min(limit, 1000), 1), total)
        return {
            "events": events[start:end],
            "total": total,
            "offset": start,
            "limit": end - start,
        }

    @property
    def total_events(self) -> int:
        """Total number of events buffered for this run."""
        return sum(len(events) for events in self._events_by_node.values())

    @property
    def pipeline_id(self) -> Optional[str]:
        """Get pipeline_id for this run."""
        run = self._agg.get_run(self.run_id)
        return run.pipeline_id if run else None

    @property
    def fqn_to_node_uuid(self) -> Dict[str, str]:
        """Build FQN to node UUID mapping from canonical spec."""
        run = self._agg.get_run(self.run_id)
        if not run or not run.pipeline_spec_canonical:
            return {}
        nodes = run.pipeline_spec_canonical.get("nodes", [])
        mapping = {}
        for n in nodes:
            if not isinstance(n, dict):
                continue
            uuid = n.get("node_uuid")
            fqn = n.get("processor_ref")
            if uuid and fqn:
                mapping[fqn] = uuid
        return mapping

    def find_node_uuid_by_label(self, label: str) -> Optional[str]:
        """Find node UUID by matching against FQN patterns in canonical spec."""
        run = self._agg.get_run(self.run_id)
        if not run or not run.pipeline_spec_canonical:
            return None
        nodes = run.pipeline_spec_canonical.get("nodes", [])
        # Build FQN mapping
        fqn_to_uuid = {}
        for n in nodes:
            if not isinstance(n, dict):
                continue
            uuid = n.get("node_uuid")
            fqn = n.get("processor_ref")
            if uuid and fqn:
                fqn_to_uuid[fqn] = uuid
        # Try exact match first
        if label in fqn_to_uuid:
            return fqn_to_uuid[label]
        # Try component matching for complex FQNs
        for fqn, uuid in fqn_to_uuid.items():
            parts = fqn.split(":")
            if len(parts) >= 2:
                component_name = parts[1]
                if component_name in label:
                    return uuid
            elif len(parts) == 1:
                if fqn in label:
                    return uuid
        # Try partial matches
        for fqn, uuid in fqn_to_uuid.items():
            if label in fqn:
                return uuid
        return None


class MultiTraceIndex:
    """Multi-run viewer facade; holds a single TraceAggregator and per-run adapters.
    NOTE: This remains per-run only; no run-space APIs are exposed/used.
    """

    def __init__(self, agg: TraceAggregator):
        self._agg = agg
        self.by_run: Dict[str, CoreTraceIndex] = {}

    @classmethod
    def from_json_or_jsonl(cls, path: str) -> "MultiTraceIndex":
        import json

        agg = TraceAggregator()
        mti = cls(agg)
        # Local tolerant loader (viewer-only IO; core remains IO-agnostic)
        if path.endswith(".jsonl"):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    _ingest_and_buffer(agg, mti, rec)
        else:
            with open(path, "r", encoding="utf-8") as fh:
                try:
                    arr = json.load(fh)
                except Exception:
                    arr = []
            if isinstance(arr, list):
                for rec in arr:
                    if isinstance(rec, dict):
                        _ingest_and_buffer(agg, mti, rec)
        # build per-run adapters
        for run in agg.iter_runs():
            if run.run_id not in mti.by_run:
                mti.by_run[run.run_id] = CoreTraceIndex(run.run_id, agg)
        return mti

    def get(self, run_id: Optional[str]) -> CoreTraceIndex:
        if not self.by_run:
            raise KeyError("No runs available")
        if run_id is None:
            run_id = sorted(self.by_run.keys())[0]
        if run_id not in self.by_run:
            raise KeyError(f"Run not found: {run_id}")
        return self.by_run[run_id]

    def list_runs(self) -> List[Dict[str, Any]]:
        """Get list of all runs with metadata."""
        out = []
        for run in self._agg.iter_runs():
            out.append(
                {
                    "run_id": run.run_id,
                    "pipeline_id": run.pipeline_id,
                    "started_at": run.start_ts,
                    "ended_at": run.end_ts,
                    "total_events": sum(
                        (na.counts or {}).get("total_records", 0)
                        for na in run.nodes.values()
                    ),
                }
            )
        # stable order by started_at then run_id
        out.sort(key=lambda r: ((r["started_at"] or ""), r["run_id"]))
        return out

    def default_run_id(self) -> Optional[str]:
        """Get the default run ID (first encountered or earliest started)."""
        runs = self.list_runs()
        return runs[0]["run_id"] if runs else None

    # --- Legacy API surface for compatibility with old tests ---
    def get_meta(self, run_id: Optional[str]) -> Dict[str, Any]:
        """Get metadata for specific run (legacy API)."""
        return self.get(run_id).get_meta()

    def summary(self, run_id: Optional[str]) -> Dict[str, Any]:
        """Get summary for specific run (legacy API)."""
        return self.get(run_id).summary()

    def node_events(
        self, run_id: Optional[str], node_uuid: str, offset: int, limit: int
    ) -> Dict[str, Any]:
        """Get node events for specific run (legacy API)."""
        return self.get(run_id).node_events(node_uuid, offset, limit)


# ---------------- private helpers (viewer-only) ----------------
def _ingest_and_buffer(
    agg: TraceAggregator, mti: MultiTraceIndex, rec: Dict[str, Any]
) -> None:
    # For malformed records without run_id, use "unknown" as fallback for viewer compatibility
    if rec.get("record_type") == "ser":
        ident = rec.get("identity") or {}
        rid = ident.get("run_id") or "unknown"  # fallback for malformed records
        nid = ident.get("node_id")
        if not nid:
            return
        # Inject run_id for Core aggregator (requires it)
        if "run_id" not in ident:
            ident["run_id"] = rid
            rec["identity"] = ident
        agg.ingest(rec)
        if rid not in mti.by_run:
            mti.by_run[rid] = CoreTraceIndex(rid, agg)
        buf = mti.by_run[rid]._events_by_node.setdefault(nid, [])
        buf.append(rec)
        if len(buf) > _MAX_EVENTS_PER_NODE:
            del buf[0 : len(buf) - _MAX_EVENTS_PER_NODE]
    else:
        # Non-SER records (pipeline_start, pipeline_end, etc.)
        agg.ingest(rec)
