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

"""Trace indexing and analysis for execution overlay visualization."""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class TraceEvent:
    """Individual trace event for a node execution."""

    phase: str  # "before", "after", "error"
    event_time_utc: str
    t_wall: Optional[float] = None
    t_cpu: Optional[float] = None
    error_type: Optional[str] = None
    error_msg: Optional[str] = None
    params_sig: Optional[str] = None
    out_data_repr: Optional[str] = None
    out_data_hash: Optional[str] = None
    post_context_repr: Optional[str] = None
    post_context_hash: Optional[str] = None
    # Keep full raw record for future use/debugging
    _raw: Optional[dict] = None


@dataclass
class TraceAgg:
    """Aggregated trace data for a single node."""

    last_phase: Optional[str] = None
    count_before: int = 0
    count_after: int = 0
    count_error: int = 0
    t_wall_sum: float = 0.0
    t_wall_avg: float = 0.0
    last_error_type: Optional[str] = None
    last_error_msg: Optional[str] = None
    last_event_time_utc: Optional[str] = None


class TraceIndex:
    """In-memory index of trace events for fast querying."""

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

        # canonical nodes from pipeline_start (node_uuid -> node info)
        self.canonical_nodes: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def from_jsonl(cls, path: str) -> "TraceIndex":
        """Create TraceIndex from JSONL file.

        Args:
            path: Path to JSONL trace file

        Returns:
            TraceIndex instance with parsed data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        trace_file = Path(path)
        if not trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {path}")

        if not trace_file.is_file():
            raise ValueError(f"Path is not a file: {path}")

        index = cls()
        index.file_path = str(trace_file.absolute())
        index.file_size = trace_file.stat().st_size

        # Bounded event storage per node (prevent memory blowup)
        MAX_EVENTS_PER_NODE = 500

        try:
            # Read file and split into JSON blocks separated by blank lines.
            # This supports "pretty" multi-line JSON records.
            with open(trace_file, "r", encoding="utf-8") as f:
                buffer_lines: List[str] = []
                line_num = 0
                for raw_line in f:
                    line_num += 1
                    # Keep original line endings for nicer error messages if needed
                    if raw_line.strip() == "":
                        # End of a block
                        if not buffer_lines:
                            continue
                        block_text = "\n".join(buffer_lines)
                        buffer_lines = []
                        try:
                            record = json.loads(block_text)
                            index.total_events += 1
                            record_type = record.get("type")

                            if record_type == "pipeline_start":
                                index._process_pipeline_start(record)
                            elif record_type == "node":
                                index._process_node_event(record, MAX_EVENTS_PER_NODE)
                            elif record_type == "pipeline_end":
                                index._process_pipeline_end(record)
                            # ignore other record types
                        except json.JSONDecodeError as e:
                            index.warnings.append(
                                f"Block ending at line {line_num}: Invalid JSON - {e}"
                            )
                        except Exception as e:
                            index.warnings.append(
                                f"Block ending at line {line_num}: Processing error - {e}"
                            )
                        continue

                    buffer_lines.append(raw_line.rstrip("\n"))

                # If there's remaining buffered content at EOF, parse it
                if buffer_lines:
                    block_text = "\n".join(buffer_lines)
                    try:
                        record = json.loads(block_text)
                        index.total_events += 1
                        record_type = record.get("type")
                        if record_type == "pipeline_start":
                            index._process_pipeline_start(record)
                        elif record_type == "node":
                            index._process_node_event(record, MAX_EVENTS_PER_NODE)
                        elif record_type == "pipeline_end":
                            index._process_pipeline_end(record)
                    except json.JSONDecodeError as e:
                        index.warnings.append(f"EOF block: Invalid JSON - {e}")
                    except Exception as e:
                        index.warnings.append(f"EOF block: Processing error - {e}")

        except Exception as e:
            raise ValueError(f"Failed to read trace file: {e}")

        # Compute averages for all nodes
        for node_uuid, agg in index.per_node.items():
            total_executions = agg.count_after + agg.count_error
            if total_executions > 0 and agg.t_wall_sum > 0:
                agg.t_wall_avg = agg.t_wall_sum / total_executions

        return index

    def _process_pipeline_start(self, record: Dict[str, Any]) -> None:
        """Process pipeline_start record."""
        self.run_id = record.get("run_id")
        self.pipeline_id = record.get("pipeline_id")

        # Store meta and keep canonical_spec (but keep a lightweight representation)
        meta = record.copy()
        canonical_spec = meta.get("canonical_spec")
        if isinstance(canonical_spec, dict):
            # Keep the canonical_spec summary and a node-level index for UI usage
            meta["canonical_summary"] = {
                "version": canonical_spec.get("version"),
                "node_count": len(canonical_spec.get("nodes", [])),
                "edge_count": len(canonical_spec.get("edges", [])),
            }

            nodes = canonical_spec.get("nodes", [])
            for node in nodes:
                node_uuid = node.get("node_uuid")
                fqn = node.get("fqn")
                if node_uuid:
                    self.canonical_nodes[node_uuid] = {
                        "node_uuid": node_uuid,
                        "fqn": fqn,
                        "declaration_index": node.get("declaration_index"),
                        "declaration_subindex": node.get("declaration_subindex"),
                        "role": node.get("role"),
                    }
                if node_uuid and fqn:
                    self.node_uuid_to_fqn[node_uuid] = fqn
                    self.fqn_to_node_uuid[fqn] = node_uuid

            # Remove bulky canonical_spec from meta to avoid duplication but keep a copy under key 'canonical_spec_meta'
            meta["canonical_spec_meta"] = {
                "version": canonical_spec.get("version"),
                "nodes": [
                    {
                        k: node.get(k)
                        for k in (
                            "node_uuid",
                            "fqn",
                            "declaration_index",
                            "declaration_subindex",
                            "role",
                        )
                    }
                    for node in nodes
                ],
                "edges": canonical_spec.get("edges", []),
            }

        # Keep the rest of the pipeline_start record as meta
        self.meta = meta

    def _process_pipeline_end(self, record: Dict[str, Any]) -> None:
        """Process pipeline_end record."""
        if "summary" in record:
            self.meta["end_summary"] = record["summary"]

    def _process_node_event(
        self, record: Dict[str, Any], max_events_per_node: int
    ) -> None:
        """Process node execution event."""
        try:
            address = record.get("address", {})
            node_uuid = address.get("node_uuid")

            if not node_uuid:
                self.warnings.append("Node event missing node_uuid")
                return

            # Optionally filter by pipeline_run_id to the same run as pipeline_start
            addr_run_id = address.get("pipeline_run_id")
            if self.run_id and addr_run_id and addr_run_id != self.run_id:
                # ignore events for other runs
                return

            phase = record.get("phase")
            if not phase:
                self.warnings.append(f"Node {node_uuid}: missing phase")
                return

            # Initialize node data if needed
            if node_uuid not in self.per_node:
                self.per_node[node_uuid] = TraceAgg()
                self.events_by_node[node_uuid] = []

            agg = self.per_node[node_uuid]

            # Update aggregates
            agg.last_phase = phase
            agg.last_event_time_utc = record.get("event_time_utc")

            if phase == "before":
                agg.count_before += 1
            elif phase == "after":
                agg.count_after += 1
                # Accumulate wall time for successful executions
                t_wall = record.get("t_wall")
                if t_wall is not None:
                    try:
                        agg.t_wall_sum += float(t_wall)
                    except Exception:
                        pass
            elif phase == "error":
                agg.count_error += 1
                agg.last_error_type = record.get("error_type")
                agg.last_error_msg = record.get("error_msg")

            # Store bounded events
            events_list = self.events_by_node[node_uuid]
            if len(events_list) >= max_events_per_node:
                # Remove oldest event
                events_list.pop(0)

            # Create event record
            event = TraceEvent(
                phase=phase,
                event_time_utc=record.get("event_time_utc", ""),
                t_wall=record.get("t_wall"),
                t_cpu=record.get("t_cpu"),
                error_type=record.get("error_type"),
                error_msg=record.get("error_msg"),
                out_data_repr=record.get("out_data_repr"),
                out_data_hash=record.get("out_data_hash"),
                post_context_repr=record.get("post_context_repr"),
                post_context_hash=record.get("post_context_hash"),
                _raw=record,
            )

            events_list.append(event)

        except Exception as e:
            self.warnings.append(f"Error processing node event: {e}")

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
        """Get trace metadata for API."""
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
            # Non-fatal; expose a warning and continue
            self.warnings.append(f"Failed building positional node mappings: {e}")

        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "file": {"path": self.file_path, "size": self.file_size},
            "node_count": len(self.per_node),
            "event_count": self.total_events,
            "warnings": self.warnings,
            "node_mappings": {
                "fqn_to_uuid": self.fqn_to_node_uuid,
                "uuid_to_fqn": self.node_uuid_to_fqn,
                "index_to_uuid": index_to_uuid,
                "uuid_to_index": uuid_to_index,
            },
            **self.meta,
        }

    def find_node_uuid_by_label(self, label: str) -> Optional[str]:
        """Find node UUID by matching against FQN patterns.

        Args:
            label: Node label from pipeline inspection (e.g., "FloatMockDataSourceParametricSweep")

        Returns:
            Node UUID if a match is found, None otherwise
        """
        # Try exact match first
        for fqn, node_uuid in self.fqn_to_node_uuid.items():
            if fqn == label:
                return node_uuid

        # For complex FQNs like "sweep:FloatMockDataSource:FloatDataCollection", try component matching
        for fqn, node_uuid in self.fqn_to_node_uuid.items():
            parts = fqn.split(":")
            if len(parts) >= 2:
                # For sweep/slicer style FQNs, try matching against the middle component
                component_name = parts[1]
                # Check if the component name is contained in the label
                if component_name in label:
                    return node_uuid
            elif len(parts) == 1:
                # For simple FQNs, check if they're contained in the label
                if fqn in label:
                    return node_uuid

        # Try partial matches (label contained in FQN)
        for fqn, node_uuid in self.fqn_to_node_uuid.items():
            if label in fqn:
                return node_uuid

        return None
