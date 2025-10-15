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

"""SER (Step Evidence Record) indexing and analysis for execution overlay visualization."""

import json
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict

from .trace_index import TraceEvent, TraceAgg


class SERIndex:
    """In-memory index of SER records for fast querying.

    Provides same API as TraceIndex to maintain compatibility with existing Studio code.
    """

    def __init__(self) -> None:
        # Unique identifiers
        self.pipeline_id: Optional[str] = None
        self.run_id: Optional[str] = None

        # Raw and derived metadata
        self.meta: Dict[str, Any] = {}

        # Per-node aggregates and events
        self.per_node: Dict[str, TraceAgg] = {}
        self.events_by_node: Dict[str, List[TraceEvent]] = {}

        # Diagnostics
        self.warnings: List[str] = []
        self.total_events: int = 0

        # File info
        self.file_path: Optional[str] = None
        self.file_size: Optional[int] = None

        # Store mapping from node_uuid to FQN for easier node matching
        self.node_uuid_to_fqn: Dict[str, str] = {}
        self.fqn_to_node_uuid: Dict[str, str] = {}

        # Canonical nodes from SER labels
        self.canonical_nodes: Dict[str, Dict[str, Any]] = {}

        # Graph reconstruction from SER topology
        self._nodes_by_id: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, str]] = []

    @classmethod
    def from_jsonl(cls, path: str) -> "SERIndex":
        """Create SERIndex from SER JSONL file.

        Args:
            path: Path to SER JSONL file

        Returns:
            SERIndex instance with parsed data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        ser_file = Path(path)
        if not ser_file.exists():
            raise FileNotFoundError(f"SER file not found: {path}")

        if not ser_file.is_file():
            raise ValueError(f"Path is not a file: {path}")

        index = cls()
        index.file_path = str(ser_file.absolute())
        index.file_size = ser_file.stat().st_size

        # Bounded event storage per node (prevent memory blowup)
        MAX_EVENTS_PER_NODE = 500

        try:
            with open(ser_file, "r", encoding="utf-8") as f:
                line_num = 0
                for raw_line in f:
                    line_num += 1
                    line = raw_line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        index.total_events += 1
                        record_type = record.get("record_type")

                        # Handle trace records
                        if record_type == "pipeline_start":
                            index._process_pipeline_start(record)
                        elif record_type == "pipeline_end":
                            index._process_pipeline_end(record)
                        elif record_type == "ser":
                            index._process_ser_record(record, MAX_EVENTS_PER_NODE)
                        # ignore other record types
                    except json.JSONDecodeError as e:
                        index.warnings.append(f"Line {line_num}: Invalid JSON - {e}")
                    except Exception as e:
                        index.warnings.append(
                            f"Line {line_num}: Processing error - {e}"
                        )

        except Exception as e:
            raise ValueError(f"Failed to read SER file: {e}")

        # Compute averages for all nodes
        for node_uuid, agg in index.per_node.items():
            total_executions = agg.count_after + agg.count_error
            if total_executions > 0 and agg.t_wall_sum > 0:
                agg.t_wall_avg = agg.t_wall_sum / total_executions

        # Build graph from topology if no pipeline_start was found
        if not index.canonical_nodes:
            index._build_graph_from_topology()

        return index

    def _process_pipeline_start(self, record: Dict[str, Any]) -> None:
        """Process legacy pipeline_start record for backward compatibility."""
        self.run_id = record.get("run_id")
        self.pipeline_id = record.get("pipeline_id")
        self.meta = record.copy()

        # Extract canonical nodes if available
        canonical_spec = record.get("canonical_spec", {})
        if isinstance(canonical_spec, dict):
            nodes = canonical_spec.get("nodes", [])
            for node in nodes:
                node_uuid = node.get("node_uuid")
                processor_ref = node.get("processor_ref")
                if node_uuid:
                    self.canonical_nodes[node_uuid] = {
                        "node_uuid": node_uuid,
                        "fqn": processor_ref,
                        "declaration_index": node.get("declaration_index"),
                        "declaration_subindex": node.get("declaration_subindex"),
                        "role": node.get("role"),
                    }
                if node_uuid and processor_ref:
                    self.node_uuid_to_fqn[node_uuid] = processor_ref
                    self.fqn_to_node_uuid[processor_ref] = node_uuid

    def _process_pipeline_end(self, record: Dict[str, Any]) -> None:
        """Process legacy pipeline_end record for backward compatibility."""
        if "summary" in record:
            self.meta["end_summary"] = record["summary"]

    def _process_ser_record(
        self, record: Dict[str, Any], max_events_per_node: int
    ) -> None:
        """Process SER record and synthesize trace events."""
        try:
            identity = record.get("identity", {})
            node_id = identity.get("node_id")

            if not node_id:
                self.warnings.append("SER record missing node_id")
                return

            # Set run/pipeline IDs from first SER record
            if not self.run_id:
                self.run_id = identity.get("run_id")
            if not self.pipeline_id:
                self.pipeline_id = identity.get("pipeline_id")

            # Store node info for graph reconstruction
            tags = record.get("tags", {})
            node_fqn = tags.get("node_ref")
            if not node_fqn:
                # Fall back to processor.ref if no FQN in tags
                processor = record.get("processor", {})
                node_fqn = processor.get("ref", node_id[:8])

            # Update mappings
            if node_fqn:
                self.node_uuid_to_fqn[node_id] = node_fqn
                self.fqn_to_node_uuid[node_fqn] = node_id

            # Store canonical node info with tags, preserving existing data if available
            existing_canonical = self.canonical_nodes.get(node_id, {})

            # Preserve declaration_index and declaration_subindex from pipeline_start if available
            preserved_di = existing_canonical.get("declaration_index")
            preserved_dsub = existing_canonical.get("declaration_subindex", 0)

            # Only use tags data if we don't have preserved values
            final_di = (
                preserved_di
                if preserved_di is not None
                else tags.get("declaration_index")
            )
            final_dsub = (
                preserved_dsub
                if preserved_dsub is not None
                else tags.get("declaration_subindex", 0)
            )

            self.canonical_nodes[node_id] = {
                "node_uuid": node_id,
                "fqn": node_fqn,
                "declaration_index": final_di,
                "declaration_subindex": final_dsub,
                "role": existing_canonical.get("role") or tags.get("role"),
            }

            # Store dependencies for graph reconstruction
            dependencies = record.get("dependencies", {})
            upstream = dependencies.get("upstream", [])
            self._nodes_by_id[node_id] = {
                "node_id": node_id,
                "fqn": node_fqn,
                "upstream": upstream,
                "tags": tags,
                "processor": record.get("processor", {}),
            }

            # Add edges
            for parent_id in upstream:
                self._edges.append({"from": parent_id, "to": node_id})

            # Initialize node data if needed
            if node_id not in self.per_node:
                self.per_node[node_id] = TraceAgg()
                self.events_by_node[node_id] = []

            agg = self.per_node[node_id]
            timing = record.get("timing", {})
            status = record.get("status", "succeeded")

            # Extract timing info
            start_time = timing.get("started_at", "")
            end_time = timing.get("finished_at", "")
            duration_ms = timing.get("duration_ms", 0)
            t_wall = duration_ms / 1000.0 if duration_ms else 0.0

            # SER v1: Create single event per execution (not before/after)
            # Extract data summaries
            summaries = record.get("summaries", {})
            context_delta = record.get("context_delta", {})
            
            out_data_hash = self._extract_data_hash(
                summaries, context_delta, "output_data", "created_keys"
            )
            out_data_repr = self._extract_data_repr(summaries, "output_data")
            post_context_hash = self._extract_context_hash(summaries)
            post_context_repr = self._extract_context_repr(summaries)

            # Extract CPU time (ms -> seconds) when available
            t_cpu = (
                (timing.get("cpu_ms") / 1000.0)
                if timing.get("cpu_ms") is not None
                else None
            )

            # Create single event with complete execution data
            if status == "error":
                error_info = record.get("error", {})
                event = TraceEvent(
                    phase="error",
                    event_time_utc=end_time,
                    t_wall=t_wall,
                    t_cpu=t_cpu,
                    error_type=error_info.get("type", "Error"),
                    error_msg=error_info.get("message", ""),
                    out_data_hash=out_data_hash,
                    out_data_repr=out_data_repr,
                    post_context_hash=post_context_hash,
                    post_context_repr=post_context_repr,
                    _raw=record,
                )
                agg.count_error += 1
                agg.last_error_type = error_info.get("type")
                agg.last_error_msg = error_info.get("message")
                agg.last_phase = "error"
            else:
                event = TraceEvent(
                    phase="completed",
                    event_time_utc=end_time,
                    t_wall=t_wall,
                    t_cpu=t_cpu,
                    out_data_hash=out_data_hash,
                    out_data_repr=out_data_repr,
                    post_context_hash=post_context_hash,
                    post_context_repr=post_context_repr,
                    _raw=record,
                )
                agg.count_after += 1
                if t_wall:
                    agg.t_wall_sum += t_wall
                agg.last_phase = "completed"

            self._add_event(node_id, event, max_events_per_node)
            agg.last_event_time_utc = end_time

        except Exception as e:
            self.warnings.append(f"Error processing SER record: {e}")

    def _add_event(
        self, node_id: str, event: TraceEvent, max_events_per_node: int
    ) -> None:
        """Add event to node with size limit."""
        events_list = self.events_by_node[node_id]
        if len(events_list) >= max_events_per_node:
            events_list.pop(0)  # Remove oldest
        events_list.append(event)

    def _extract_data_hash(
        self, summaries: Dict, context_delta: Dict, summary_key: str, delta_key: str
    ) -> Optional[str]:
        """Extract data hash from summaries or compute from created keys."""
        # Try direct summary
        if summary_key in summaries:
            summary = summaries[summary_key]
            if isinstance(summary, dict) and "sha256" in summary:
                return summary["sha256"]

        # Try first created key from context_delta
        created = context_delta.get(delta_key, [])
            
        if created and len(created) > 0:
            first_key = created[0]
            # Look for summary of first created key
            for key, summary in summaries.items():
                if key == first_key and isinstance(summary, dict):
                    return summary.get("sha256")

        return None

    def _extract_data_repr(self, summaries: Dict, summary_key: str) -> Optional[str]:
        """Extract data repr from summaries."""
        if summary_key in summaries:
            summary = summaries[summary_key]
            if isinstance(summary, dict):
                if "repr" in summary:
                    return summary["repr"]
                # Build compact repr from available fields
                parts = []
                if "dtype" in summary:
                    parts.append(f"dtype={summary['dtype']}")
                if "rows" in summary:
                    parts.append(f"rows={summary['rows']}")
                if parts:
                    return f"{{{', '.join(parts)}}}"
        return None

    def _extract_context_hash(self, summaries: Dict) -> Optional[str]:
        """Extract or compute context hash from summaries."""
        # Look for post_context summary
        if "post_context" in summaries:
            summary = summaries["post_context"]
            if isinstance(summary, dict) and "sha256" in summary:
                return summary["sha256"]

        # Synthesize from created/updated keys
        created_updated = []
        for key, summary in summaries.items():
            if key.startswith(("created_", "updated_")) or key in ("output_data",):
                if isinstance(summary, dict) and "sha256" in summary:
                    created_updated.append((key, summary["sha256"]))

        if created_updated:
            # Create deterministic hash from all created/updated keys
            context_str = json.dumps(sorted(created_updated))
            return "sha256-" + hashlib.sha256(context_str.encode()).hexdigest()

        return None

    def _extract_context_repr(self, summaries: Dict) -> Optional[str]:
        """Extract or build context repr from summaries."""
        if "post_context" in summaries:
            summary = summaries["post_context"]
            if isinstance(summary, dict) and "repr" in summary:
                return summary["repr"]

        # Build context repr from created/updated summaries
        context_parts = []
        for key, summary in summaries.items():
            if key != "input_data" and isinstance(summary, dict):
                if "dtype" in summary:
                    context_parts.append(f"{key}={summary['dtype']}")

        if context_parts:
            return "{" + ", ".join(context_parts) + "}"

        return None

    def _build_graph_from_topology(self) -> None:
        """Build graph nodes and edges from SER topology information (SER-only mode)."""
        if not self._nodes_by_id:
            return

        # All nodes were already collected during SER processing
        # Edges were already collected as well

        # Update meta to indicate SER-only mode
        self.meta["ser_mode"] = True
        self.meta["graph_source"] = "ser_topology"

    def summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all nodes for API."""
        result = {}
        for node_uuid, agg in self.per_node.items():
            result[node_uuid] = asdict(agg)
        return {"nodes": result}

    def node_events(
        self, node_uuid: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """Get events for specific node with paging."""
        if node_uuid not in self.events_by_node:
            return {"events": [], "total": 0}

        events = self.events_by_node[node_uuid]
        total = len(events)

        # Apply paging
        start = min(offset, total)
        end = min(start + limit, total)
        page_events = events[start:end]

        # Convert to dict format for JSON serialization
        events_data = [asdict(event) for event in page_events]

        return {"events": events_data, "total": total, "offset": offset, "limit": limit}

    def get_meta(self) -> Dict[str, Any]:
        """Get SER metadata for API."""
        # Build positional mappings from canonical nodes if available
        index_to_uuid: Dict[str, str] = {}
        uuid_to_index: Dict[str, Dict[str, int]] = {}
        try:
            for uuid, ninfo in self.canonical_nodes.items():
                di = ninfo.get("declaration_index")
                dsub = ninfo.get("declaration_subindex", 0)
                if di is None:
                    continue
                key = f"{int(di)}:{int(dsub)}"
                index_to_uuid[key] = uuid
                uuid_to_index[uuid] = {
                    "declaration_index": int(di),
                    "declaration_subindex": int(dsub),
                }
        except Exception as e:
            self.warnings.append(f"Failed building positional node mappings: {e}")

        meta = {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "file": {"path": self.file_path, "size": self.file_size},
            "node_count": len(self.per_node),
            "event_count": self.total_events,
            "warnings": self.warnings,
            "ser_mode": True,  # Indicate this is SER data
            "node_mappings": {
                "fqn_to_uuid": self.fqn_to_node_uuid,
                "uuid_to_fqn": self.node_uuid_to_fqn,
                "index_to_uuid": index_to_uuid,
                "uuid_to_index": uuid_to_index,
            },
            "canonical_nodes": list(self.canonical_nodes.values()),
            **self.meta,
        }

        return meta

    def find_node_uuid_by_label(self, label: str) -> Optional[str]:
        """Find node UUID by matching against FQN patterns.

        Args:
            label: Node label from pipeline inspection

        Returns:
            Node UUID if a match is found, None otherwise
        """
        # Try exact match first
        for fqn, node_uuid in self.fqn_to_node_uuid.items():
            if fqn == label:
                return node_uuid

        # Try component matching for complex FQNs
        for fqn, node_uuid in self.fqn_to_node_uuid.items():
            parts = fqn.split(":")
            if len(parts) >= 2:
                component_name = parts[1]
                if component_name in label:
                    return node_uuid
            elif len(parts) == 1:
                if fqn in label:
                    return node_uuid

        # Try partial matches
        for fqn, node_uuid in self.fqn_to_node_uuid.items():
            if label in fqn:
                return node_uuid

        return None

    def get_ser_topology(self) -> Dict[str, Any]:
        """Get topology information for SER-only graph reconstruction."""
        return {
            "nodes": list(self._nodes_by_id.values()),
            "edges": self._edges,
        }


@dataclass
class RunMeta:
    """Metadata for a single run in a multi-run SER file."""

    run_id: str
    pipeline_id: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    total_events: int = 0


class MultiSERIndex:
    """Holds one SERIndex per run_id and routes queries by ?run= param."""

    def __init__(self) -> None:
        self.by_run: Dict[str, SERIndex] = {}
        self.meta_by_run: Dict[str, RunMeta] = {}
        self.file_path: Optional[str] = None
        self.file_size: int = 0
        self._default_run: Optional[str] = None

    @classmethod
    def from_json_or_jsonl(cls, path: str) -> "MultiSERIndex":
        """Create MultiSERIndex from JSON/JSONL file containing multiple SER runs.

        Args:
            path: Path to SER JSON/JSONL file

        Returns:
            MultiSERIndex instance with parsed data grouped by run_id

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"SER file not found: {path}")

        inst = cls()
        inst.file_path = str(p.absolute())
        inst.file_size = p.stat().st_size

        def _get_or_make(run_id: str) -> SERIndex:
            if run_id not in inst.by_run:
                inst.by_run[run_id] = SERIndex()
                inst.meta_by_run[run_id] = RunMeta(
                    run_id=run_id,
                    pipeline_id=None,
                    started_at=None,
                    ended_at=None,
                    total_events=0,
                )
                if inst._default_run is None:
                    inst._default_run = run_id
            return inst.by_run[run_id]

        def _touch_meta(run_id: str, record: Dict[str, Any]) -> None:
            meta = inst.meta_by_run[run_id]
            # pipeline_id
            pid = (
                # SER v1: record.identity.pipeline_id
                (record.get("identity") or {}).get("pipeline_id")
                # SER v0: record.ids.pipeline_id
                or (record.get("ids") or {}).get("pipeline_id") 
                # pipeline_start/end: record.pipeline_id
                or record.get("pipeline_id")
            )
            if pid and not meta.pipeline_id:
                meta.pipeline_id = pid
            # started_at / ended_at from timing if present
            timing = record.get("timing") or {}
            # SER v1: timing.started_at, timing.finished_at
            st = timing.get("started_at") or timing.get("start")
            en = timing.get("finished_at") or timing.get("end")
            if st and (not meta.started_at or st < meta.started_at):
                meta.started_at = st
            if en and (not meta.ended_at or en > meta.ended_at):
                meta.ended_at = en
            meta.total_events += 1

        def _route_record(index: SERIndex, record: Dict[str, Any]) -> None:
            rtype = record.get("record_type")
            if rtype == "ser":
                index._process_ser_record(record, max_events_per_node=500)
            elif rtype == "pipeline_start":
                index._process_pipeline_start(record)
            elif rtype == "pipeline_end":
                index._process_pipeline_end(record)
            # ignore others

        def _consume_block(txt: str) -> None:
            try:
                record = json.loads(txt)
                _dispatch(record)
            except json.JSONDecodeError:
                # Try line-by-line
                for ln in txt.splitlines():
                    if not ln.strip():
                        continue
                    try:
                        record = json.loads(ln)
                        _dispatch(record)
                    except json.JSONDecodeError:
                        continue

        def _dispatch(record: Dict[str, Any]) -> None:
            run_id = (
                # SER v1: record.identity.run_id
                (record.get("identity") or {}).get("run_id")
                # SER v0: record.ids.run_id  
                or (record.get("ids") or {}).get("run_id")
                # pipeline_start/end: record.run_id
                or record.get("run_id")
                or "unknown"
            )
            idx = _get_or_make(run_id)
            _route_record(idx, record)
            _touch_meta(run_id, record)

        # Read JSON array or JSON(L)
        try:
            with p.open("r", encoding="utf-8") as f:
                first_char = f.read(1)
                f.seek(0)

                if first_char == "[":
                    # JSON array
                    content = f.read()
                    data = json.loads(content)
                    if not isinstance(data, list):
                        raise ValueError("SER JSON must be an array of records")
                    for record in data:
                        _dispatch(record)
                else:
                    # JSONL (supports pretty records separated by blank lines, same as SERIndex)
                    buf: List[str] = []
                    for raw in f:
                        line = raw.strip()
                        if not line:
                            if buf:
                                _consume_block("\n".join(buf))
                                buf = []
                            continue
                        buf.append(raw)
                    if buf:
                        _consume_block("\n".join(buf))
        except Exception as e:
            raise ValueError(f"Failed to read SER file: {e}")

        # post-process: compute averages and topology for each run
        for run_id, idx in inst.by_run.items():
            # Copy metadata to individual SERIndex objects
            meta = inst.meta_by_run[run_id]
            idx.total_events = meta.total_events
            idx.pipeline_id = meta.pipeline_id
            idx.run_id = meta.run_id

            for _, agg in idx.per_node.items():
                total = agg.count_after + agg.count_error
                if total > 0 and agg.t_wall_sum > 0:
                    agg.t_wall_avg = agg.t_wall_sum / total
            if not idx.canonical_nodes:
                idx._build_graph_from_topology()

        return inst

    # ---- API ----
    def list_runs(self) -> List[Dict[str, Any]]:
        """Get list of all runs with metadata."""
        out = []
        for rm in self.meta_by_run.values():
            out.append(
                {
                    "run_id": rm.run_id,
                    "pipeline_id": rm.pipeline_id,
                    "started_at": rm.started_at,
                    "ended_at": rm.ended_at,
                    "total_events": rm.total_events,
                }
            )
        # stable order by started_at then run_id
        out.sort(key=lambda r: ((r["started_at"] or ""), r["run_id"]))
        return out

    def default_run_id(self) -> Optional[str]:
        """Get the default run ID (first encountered or earliest started)."""
        return self._default_run or (
            self.list_runs()[0]["run_id"] if self.by_run else None
        )

    def get(self, run_id: Optional[str]) -> SERIndex:
        """Get SERIndex for specific run."""
        rid = run_id or self.default_run_id()
        if not rid or rid not in self.by_run:
            raise KeyError(f"Run not found: {run_id}")
        return self.by_run[rid]

    def get_meta(self, run_id: Optional[str]) -> Dict[str, Any]:
        """Get metadata for specific run."""
        return self.get(run_id).get_meta()

    def summary(self, run_id: Optional[str]) -> Dict[str, Any]:
        """Get summary for specific run."""
        return self.get(run_id).summary()

    def node_events(
        self, run_id: Optional[str], node_uuid: str, offset: int, limit: int
    ) -> Dict[str, Any]:
        """Get node events for specific run."""
        return self.get(run_id).node_events(node_uuid, offset, limit)
