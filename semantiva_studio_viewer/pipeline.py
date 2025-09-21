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

"""Pipeline visualization web server and export functionality."""

import argparse
import json
from typing import Any
from fastapi.encoders import jsonable_encoder
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from semantiva import Pipeline, load_pipeline_from_yaml
from semantiva.inspection import (
    build_pipeline_inspection,
    json_report,
    summary_report,
    extended_report,
)

app = FastAPI()


# Legacy trace detection removed - only SER format is supported


def _ensure_trace_loaded():
    """Try to lazily load trace file if app.state.trace_index is not present and a path was provided."""
    if hasattr(app.state, "trace_loaded") and app.state.trace_loaded:
        return
    trace_path = getattr(app.state, "trace_jsonl", None)
    if not trace_path:
        app.state.trace_loaded = True
        return
    try:
        trace_file = Path(trace_path)
        if trace_file.exists() and trace_file.is_file():
            # Only SER format is supported
            from .ser_index import MultiSERIndex

            app.state.trace_index = MultiSERIndex.from_json_or_jsonl(trace_path)
            print(f"Lazy-loaded SER file: {trace_path}")
        app.state.trace_loaded = True
    except Exception as e:
        print(f"Warning: Failed to lazy-load trace file {trace_path}: {e}")
        app.state.trace_index = None
        app.state.trace_loaded = True


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def build_pipeline_json(config: list[dict]) -> dict:
    """Generate JSON representation of pipeline using the inspection system.

    Args:
        config: Raw configuration data (List[Dict]).

    Returns:
        Dictionary containing nodes and edges data for web visualization

    Note:
        This function replaces the previous direct pipeline analysis with
        a call to the inspection system's json_report() function, ensuring
        consistency across all pipeline introspection tools. It can handle
        invalid configurations that would fail during Pipeline construction.
    """
    # Use the Semantiva's inspection system for consistent data generation
    inspection = build_pipeline_inspection(config)

    # Run validation to populate errors in the inspection (but don't raise exceptions here)
    try:
        from semantiva.inspection.validator import validate_pipeline

        validate_pipeline(inspection)
    except Exception:
        # Validation failed, but errors are now populated in the inspection data
        pass

    # Convert inspection data to JSON format suitable for web visualization
    # and normalize via jsonable_encoder to ensure full JSON-serializability
    return jsonable_encoder(json_report(inspection))


@app.get("/api/pipeline")
def get_pipeline_api():
    """Get pipeline data as JSON.

    Returns:
        Dict containing nodes and edges for pipeline visualization

    Raises:
        HTTPException: If pipeline is not loaded or processing fails
    """
    try:
        # Only configuration data is supported now
        if hasattr(app.state, "config") and app.state.config is not None:
            # app.state.config must be a list of dictionaries
            data = build_pipeline_json(app.state.config)

            # Enrich nodes with node_uuid when trace is loaded by positional identity
            _ensure_trace_loaded()
            trace_index = getattr(app.state, "trace_index", None)
            if trace_index and getattr(trace_index, "canonical_nodes", None):
                # Build index_to_uuid map from trace meta
                idx_map = {}
                try:
                    # Prefer meta builder to avoid duplication
                    meta = trace_index.get_meta()
                    idx_map = meta.get("node_mappings", {}).get("index_to_uuid", {})
                except Exception:
                    idx_map = {}

                for node in data.get("nodes", []):
                    # Our inspection nodes are 1-based ids; declaration_index should be 0-based order
                    di = node.get("declaration_index")
                    dsub = node.get("declaration_subindex", 0)
                    # If inspection doesn't provide declaration indices, fall back to position by order
                    if di is None:
                        # Node ids are 1-based, convert to 0-based index
                        try:
                            di = int(node.get("id", 0)) - 1
                        except Exception:
                            di = None
                    if di is not None:
                        key = f"{int(di)}:{int(dsub)}"
                        uuid = idx_map.get(key)
                        if uuid:
                            node["node_uuid"] = uuid

            return data

        # Neither configuration nor pipeline available
        raise HTTPException(
            status_code=404,
            detail="Pipeline configuration not found. Please load a pipeline first.",
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Convert other exceptions to HTTP 500
        raise HTTPException(
            status_code=500, detail=f"Failed to process pipeline data: {str(e)}"
        )


def _get_trace_index_for_run(run: str | None):
    """Get trace index for specific run, handling both single and multi-run cases."""
    _ensure_trace_loaded()
    ti = getattr(app.state, "trace_index", None)
    if ti is None:
        raise HTTPException(status_code=404, detail="No trace data available.")
    # ti is always MultiSERIndex now
    try:
        return ti.get(run)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/runs")
def list_runs():
    """Get list of available runs.

    Returns:
        List of run metadata with run_id, pipeline_id, started_at, ended_at, total_events
    """
    _ensure_trace_loaded()
    ti = getattr(app.state, "trace_index", None)
    if ti is None:
        return []
    # ti is always MultiSERIndex now
    return ti.list_runs()


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "web_gui" / "index.html")


@app.get("/api/trace/meta")
def get_trace_meta(run: str | None = None):
    """Get trace metadata.

    Args:
        run: Optional run ID to get metadata for specific run

    Returns:
        Dict containing run_id, pipeline_id, file info, counts, warnings

    Raises:
        HTTPException: If no trace is loaded or run not found
    """
    ti = _get_trace_index_for_run(run)
    meta = ti.get_meta()
    # Also expose canonical nodes (if available) for UI to show declaration_index/subindex
    if hasattr(ti, "canonical_nodes") and ti.canonical_nodes:
        meta["canonical_nodes"] = list(ti.canonical_nodes.values())
    return meta


@app.get("/api/trace/summary")
def get_trace_summary(run: str | None = None):
    """Get aggregated trace data for all nodes.

    Args:
        run: Optional run ID to get summary for specific run

    Returns:
        Dict with "nodes" key containing per-node aggregates

    Raises:
        HTTPException: If no trace is loaded or run not found
    """
    ti = _get_trace_index_for_run(run)
    return ti.summary()


@app.get("/api/trace/node/{node_uuid}")
def get_trace_node_events(
    node_uuid: str, run: str | None = None, offset: int = 0, limit: int = 100
):
    """Get detailed events for a specific node.

    Args:
        node_uuid: UUID of the node to get events for
        run: Optional run ID to get events for specific run
        offset: Number of events to skip (for paging)
        limit: Maximum number of events to return

    Returns:
        Dict containing events list, total count, and paging info

    Raises:
        HTTPException: If no trace is loaded, invalid parameters, or run not found
    """
    # Validate parameters
    if offset < 0:
        raise HTTPException(status_code=400, detail="Offset must be non-negative")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")

    ti = _get_trace_index_for_run(run)
    return ti.node_events(node_uuid, offset, limit)


@app.get("/api/trace/mapping")
def get_trace_label_mapping(run: str | None = None):
    """Get mapping from pipeline node labels to trace UUIDs.

    Args:
        run: Optional run ID to get mapping for specific run

    Returns:
        Dict mapping pipeline node labels to trace node UUIDs

    Raises:
        HTTPException: If no trace is loaded or run not found
    """
    ti = _get_trace_index_for_run(run)

    # Get pipeline nodes using the same logic as get_pipeline_api
    try:
        if hasattr(app.state, "config") and app.state.config is not None:
            pipeline_data = build_pipeline_json(app.state.config)
            nodes = pipeline_data["nodes"]
        else:
            raise HTTPException(
                status_code=404, detail="Pipeline configuration not found."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load pipeline data: {e}"
        )

    # Build positional mapping first, then optional legacy heuristics
    meta = ti.get_meta()
    index_to_uuid = meta.get("node_mappings", {}).get("index_to_uuid", {})

    label_to_uuid = {}
    for i, node in enumerate(nodes):
        # Prefer declaration_index/subindex if present, else derive by order (0-based)
        di = node.get("declaration_index")
        dsub = node.get("declaration_subindex", 0)
        if di is None:
            di = i  # nodes list is in declaration order
        key = f"{int(di)}:{int(dsub)}"
        uuid = index_to_uuid.get(key)
        if uuid:
            label_to_uuid[node["label"]] = uuid
        else:
            # Last resort: legacy heuristic
            legacy_uuid = ti.find_node_uuid_by_label(node["label"])
            if legacy_uuid:
                label_to_uuid[node["label"]] = legacy_uuid

    return {
        "label_to_uuid": label_to_uuid,
        "available_labels": [node["label"] for node in nodes],
        "available_fqns": list(ti.fqn_to_node_uuid.keys()),
        "node_mappings": {
            "index_to_uuid": index_to_uuid,
            "uuid_to_index": meta.get("node_mappings", {}).get("uuid_to_index", {}),
        },
    }


def serve_pipeline(
    yaml_path: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    trace_jsonl: str | None = None,
):
    """Serve pipeline visualization web interface.

    Args:
        yaml_path: Path to pipeline YAML configuration file
        host: Host address to bind to
        port: Port number to listen on
        trace_jsonl: Optional path to trace JSONL file for execution overlay

    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        ValueError: If port is not in valid range
        OSError: If host/port combination is invalid
    """
    # Input validation
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        raise FileNotFoundError(f"Pipeline YAML file not found: {yaml_path}")

    if not yaml_file.is_file():
        raise ValueError(f"Path is not a file: {yaml_path}")

    if not 1 <= port <= 65535:
        raise ValueError(f"Port must be between 1 and 65535, got: {port}")

    # Validate host format (basic check)
    if not host or not isinstance(host, str):
        raise ValueError("Host must be a non-empty string")

    # Initialize core Semantiva components before loading configuration
    # This ensures that built-in processors like FloatMultiplyOperation are registered
    from semantiva.registry.class_registry import ClassRegistry

    ClassRegistry.initialize_default_modules()

    try:
        # Load the pipeline configuration (doesn't create Pipeline object)
        config = load_pipeline_from_yaml(yaml_path)
    except Exception as e:
        raise ValueError(f"Failed to load pipeline configuration: {e}")

    app.state.config = config
    app.state.trace_index = None
    app.state.trace_loaded = False
    # Keep the trace path so endpoints can attempt lazy-loading if needed
    app.state.trace_jsonl = trace_jsonl

    # Initialize trace index if trace file is provided
    if trace_jsonl:
        try:
            trace_file = Path(trace_jsonl)
            if not trace_file.exists():
                print(f"Warning: Trace file not found: {trace_jsonl}")
            elif not trace_file.is_file():
                print(f"Warning: Trace path is not a file: {trace_jsonl}")
            else:
                # Only SER format is supported
                print(f"Loading SER file: {trace_jsonl}")
                from .ser_index import MultiSERIndex

                app.state.trace_index = MultiSERIndex.from_json_or_jsonl(trace_jsonl)
                runs = app.state.trace_index.list_runs()
                if len(runs) > 1:
                    print(
                        f"Multi-run SER data loaded: {len(runs)} runs ({len(app.state.trace_index.by_run)} indices)"
                    )
                else:
                    print(
                        f"Single-run SER data loaded: {runs[0]['run_id'] if runs else 'unknown'}"
                    )
                app.state.trace_loaded = True
        except ImportError:
            print("Warning: Trace indexing not available, trace file will be ignored")
        except Exception as e:
            print(f"Warning: Failed to load trace file: {e}")
            print("Continuing without trace overlay")

    # Print inspection information using the raw configuration
    # This works even for invalid configurations that would fail Pipeline construction
    inspection = build_pipeline_inspection(config)

    # Run validation to populate errors in the inspection (but don't raise exceptions here)
    try:
        from semantiva.inspection.validator import validate_pipeline

        validate_pipeline(inspection)
    except Exception:
        # Validation failed, but errors are now populated in the inspection data
        pass

    print("Pipeline Inspector:", summary_report(inspection))
    print("-" * 40)
    print("Extended Pipeline Inspection:", extended_report(inspection))

    # Also try to create a Pipeline object for backward compatibility, but don't fail if it doesn't work
    app.state.pipeline = None
    try:
        app.state.pipeline = Pipeline(config)
        print("-" * 40)
        print("Pipeline object created successfully - configuration is valid")
    except Exception as e:
        print("-" * 40)
        print(f"Pipeline object creation failed: {e}")
        print("Continuing with inspection-only mode for invalid configuration")

    static_dir = Path(__file__).parent / "web_gui" / "static"
    if not static_dir.exists():
        raise FileNotFoundError(f"Static files directory not found: {static_dir}")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    import uvicorn

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        raise OSError(f"Failed to start server on {host}:{port}: {e}")


def export_pipeline(yaml_path: str, output_path: str, trace_jsonl: str | None = None):
    """Export pipeline visualization to standalone HTML file.

    Args:
        yaml_path: Path to pipeline YAML configuration file
        output_path: Path for output HTML file
        trace_jsonl: Optional path to trace JSONL file for execution overlay

    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        ValueError: If paths are invalid
        PermissionError: If output path is not writable
    """
    # Input validation
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        raise FileNotFoundError(f"Pipeline YAML file not found: {yaml_path}")

    if not yaml_file.is_file():
        raise ValueError(f"Path is not a file: {yaml_path}")

    # Validate and resolve output path
    output_file = Path(output_path)

    # Ensure parent directory exists and is writable
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PermissionError(f"Cannot create output directory: {e}")

    # Check if we can write to the output location
    if output_file.exists() and not output_file.is_file():
        raise ValueError(f"Output path exists but is not a file: {output_path}")

    # Initialize core Semantiva components before loading configuration
    # This ensures that built-in processors are available during export
    from semantiva.registry.class_registry import ClassRegistry

    ClassRegistry.initialize_default_modules()

    try:
        config = load_pipeline_from_yaml(yaml_path)
    except Exception as e:
        raise ValueError(f"Failed to load pipeline configuration: {e}")

    # Load trace data if provided
    trace_data: dict[str, Any] = {}
    if trace_jsonl:
        try:
            # Only SER format is supported
            print(f"Loading SER file for export: {trace_jsonl}")
            from .ser_index import MultiSERIndex

            trace_index = MultiSERIndex.from_json_or_jsonl(trace_jsonl)

            # Build trace data for injection
            runs_list = trace_index.list_runs()
            print(f"Found {len(runs_list)} runs for export")

            # Get default run metadata and mappings
            if runs_list:
                # Use default run
                default_run_id = trace_index.default_run_id()
                default_ser_index = trace_index.get(default_run_id)
                trace_meta = default_ser_index.get_meta()
                trace_summary = default_ser_index.summary()
            else:
                # Empty MultiSERIndex - use empty data
                trace_meta = {}
                trace_summary = {}

            # Build positional label to UUID mapping using index_to_uuid
            pipeline_data = build_pipeline_json(config)
            index_to_uuid = trace_meta.get("node_mappings", {}).get("index_to_uuid", {})
            label_to_uuid = {}
            for i, node in enumerate(pipeline_data["nodes"]):
                di = node.get("declaration_index")
                dsub = node.get("declaration_subindex", 0)
                if di is None:
                    di = i
                key = f"{int(di)}:{int(dsub)}"
                uuid = index_to_uuid.get(key)
                if uuid:
                    label_to_uuid[node["label"]] = uuid

            # Get available FQNs safely
            available_fqns = []
            if runs_list:
                # Use default run's SERIndex
                if hasattr(default_ser_index, "fqn_to_node_uuid"):
                    available_fqns = list(default_ser_index.fqn_to_node_uuid.keys())
            # If no runs, available_fqns stays empty list

            trace_mapping = {
                "label_to_uuid": label_to_uuid,
                "available_labels": [node["label"] for node in pipeline_data["nodes"]],
                "available_fqns": available_fqns,
                "node_mappings": {
                    "index_to_uuid": index_to_uuid,
                    "uuid_to_index": (
                        trace_meta.get("node_mappings", {}).get("uuid_to_index", {})
                        if isinstance(trace_meta, dict)
                        else {}
                    ),
                },
            }

            # Store all trace data with per-run metadata/summary/mapping
            trace_data = {
                "meta": trace_meta,  # Default run metadata
                "summary": trace_summary,  # Default run summary
                "mapping": trace_mapping,  # Default run mapping
                "node_events": {},  # Will be populated with individual node events
                "runs": runs_list,  # Include runs list for multi-run support
                "per_run": {},  # Per-run metadata, summary, and mapping
            }

            # Pre-compute metadata, summary, and mapping for each run
            if runs_list:
                # MultiSERIndex case
                for run_info in runs_list:
                    run_id = run_info["run_id"]
                    try:
                        run_ser_index = trace_index.get(run_id)
                        run_meta = run_ser_index.get_meta()
                        run_summary = run_ser_index.summary()

                        # Build run-specific mapping (should be same structure as default)
                        run_available_fqns = []
                        if hasattr(run_ser_index, "fqn_to_node_uuid"):
                            run_available_fqns = list(
                                run_ser_index.fqn_to_node_uuid.keys()
                            )

                        run_mapping = {
                            "label_to_uuid": label_to_uuid,  # Same for all runs
                            "available_labels": [
                                node["label"] for node in pipeline_data["nodes"]
                            ],
                            "available_fqns": run_available_fqns,
                            "node_mappings": {
                                "index_to_uuid": index_to_uuid,
                                "uuid_to_index": (
                                    run_meta.get("node_mappings", {}).get(
                                        "uuid_to_index", {}
                                    )
                                    if isinstance(run_meta, dict)
                                    else {}
                                ),
                            },
                        }

                        trace_data["per_run"][run_id] = {
                            "meta": run_meta,
                            "summary": run_summary,
                            "mapping": run_mapping,
                        }
                    except Exception as e:
                        print(
                            f"Warning: Failed to compute per-run data for {run_id}: {e}"
                        )

            # Pre-load events for all mapped nodes across all runs
            # Structure: trace_data["node_events"][run_id][uuid] = events

            if runs_list:
                # MultiSERIndex case: load events for each run
                for run_info in runs_list:
                    run_id = run_info["run_id"]
                    trace_data["node_events"][run_id] = {}

                    # Get the SERIndex for this specific run
                    try:
                        run_ser_index = trace_index.get(run_id)
                        for label, uuid in label_to_uuid.items():
                            try:
                                events_response = run_ser_index.node_events(
                                    uuid, offset=0, limit=100
                                )
                                trace_data["node_events"][run_id][
                                    uuid
                                ] = events_response
                            except Exception as e:
                                print(
                                    f"Warning: Failed to load events for {label} ({uuid}) in run {run_id}: {e}"
                                )
                    except Exception as e:
                        print(f"Warning: Failed to get SERIndex for run {run_id}: {e}")
            else:
                # Empty MultiSERIndex: no runs to load events from
                pass

            data_source = "SER"
            run_id_str = (
                trace_meta.get("run_id", "unknown")
                if isinstance(trace_meta, dict)
                else "unknown"
            )
            print(
                f"Trace data loaded from {data_source}: {run_id_str} ({len(label_to_uuid)} nodes mapped)"
            )

        except Exception as e:
            print(f"Warning: Failed to load trace data: {e}")
            trace_data = {}

    # Only use configuration for build_pipeline_json
    data = build_pipeline_json(config)

    # If we have trace positional mapping, inject node_uuid into exported nodes too
    if trace_data and "meta" in trace_data:
        try:
            idx_map = (
                trace_data["meta"].get("node_mappings", {}).get("index_to_uuid", {})
            )
            for i, node in enumerate(data.get("nodes", [])):
                di = node.get("declaration_index")
                dsub = node.get("declaration_subindex", 0)
                if di is None:
                    di = i
                key = f"{int(di)}:{int(dsub)}"
                uuid = idx_map.get(key)
                if uuid:
                    node["node_uuid"] = uuid
        except Exception:
            pass

    template_dir = Path(__file__).parent / "web_gui"
    template_path = template_dir / "index.html"
    css_path = template_dir / "static" / "pipeline.css"
    js_path = template_dir / "static" / "pipeline.js"

    # Validate template files exist
    for file_path in [template_path, css_path, js_path]:
        if not file_path.exists():
            raise FileNotFoundError(f"Template file not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

    try:
        html = template_path.read_text(encoding="utf-8")
        css = css_path.read_text(encoding="utf-8")
        js = js_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Failed to read template files: {e}")
    except OSError as e:
        raise PermissionError(f"Failed to read template files: {e}")

    html = html.replace(
        '<link rel="stylesheet" href="/static/pipeline.css" />',
        f"<style>\n{css}\n</style>",
    )
    html = html.replace(
        '<script type="text/babel" src="/static/pipeline.js"></script>',
        f'<script type="text/babel">\n{js}\n</script>',
    )

    # Create data injection - encode objects consistently with FastAPI responses
    encoded_data = jsonable_encoder(data)
    encoded_trace = jsonable_encoder(trace_data)
    data_json = json.dumps(encoded_data)
    trace_data_json = json.dumps(encoded_trace)

    # Build trace endpoint mocks if trace data is available
    trace_endpoints = ""
    runs_endpoint = ""
    if trace_data:
        # Add runs endpoint mock if we have runs data
        if trace_data.get("runs"):
            runs_endpoint = """
  if (url === '/api/runs') {
    return Promise.resolve({ok: true, json: () => Promise.resolve(window.TRACE_DATA.runs)});
  }"""

        trace_endpoints = (
            runs_endpoint
            + """
  if (url === '/api/trace/meta' || url.startsWith('/api/trace/meta?')) {
    const urlObj = new URL(url, 'http://localhost');
    const runParam = urlObj.searchParams.get('run');
    const data = runParam && window.TRACE_DATA.per_run[runParam] 
      ? window.TRACE_DATA.per_run[runParam].meta 
      : window.TRACE_DATA.meta;
    return Promise.resolve({ok: true, json: () => Promise.resolve(data)});
  }
  if (url === '/api/trace/summary' || url.startsWith('/api/trace/summary?')) {
    const urlObj = new URL(url, 'http://localhost');
    const runParam = urlObj.searchParams.get('run');
    const data = runParam && window.TRACE_DATA.per_run[runParam] 
      ? window.TRACE_DATA.per_run[runParam].summary 
      : window.TRACE_DATA.summary;
    return Promise.resolve({ok: true, json: () => Promise.resolve(data)});
  }
  if (url === '/api/trace/mapping' || url.startsWith('/api/trace/mapping?')) {
    const urlObj = new URL(url, 'http://localhost');
    const runParam = urlObj.searchParams.get('run');
    const data = runParam && window.TRACE_DATA.per_run[runParam] 
      ? window.TRACE_DATA.per_run[runParam].mapping 
      : window.TRACE_DATA.mapping;
    return Promise.resolve({ok: true, json: () => Promise.resolve(data)});
  }
  if (url.startsWith('/api/trace/node/')) {
    const nodeUuid = url.split('/api/trace/node/')[1].split('?')[0];
    const urlObj = new URL(url, 'http://localhost');
    const runParam = urlObj.searchParams.get('run');
    
    let events;
    if (runParam && window.TRACE_DATA.node_events[runParam]) {
      // Multi-run structure: node_events[run_id][uuid]
      events = window.TRACE_DATA.node_events[runParam][nodeUuid];
    } else if (!runParam && window.TRACE_DATA.node_events[nodeUuid]) {
      // Legacy single-run structure: node_events[uuid]
      events = window.TRACE_DATA.node_events[nodeUuid];
    }
    
    if (events) {
      return Promise.resolve({ok: true, json: () => Promise.resolve(events)});
    }
    return Promise.resolve({ok: false, status: 404});
  }"""
        )

    # Inject as parseable JSON strings to avoid embedding raw JSON directly in HTML
    injection = (
        "<script>\n"
        f"window.PIPELINE_DATA = JSON.parse({json.dumps(data_json)});\n"
        f"window.TRACE_DATA = JSON.parse({json.dumps(trace_data_json)});\n"
        "window.fetch = ((orig) => (url, options) => {\n"
        "  if (url === '/api/pipeline') {\n"
        "    return Promise.resolve({ok: true, json: () => Promise.resolve(window.PIPELINE_DATA)});\n"
        "  }\n"
        f"{trace_endpoints}\n"
        "  return orig(url, options);\n"
        "})(window.fetch);\n"
        "</script>"
    )

    html = html.replace("<body>", f"<body>\n{injection}", 1)

    try:
        output_file.write_text(html, encoding="utf-8")
        print(f"Standalone GUI written to {output_path}")
    except OSError as e:
        raise PermissionError(f"Failed to write output file: {e}")


def main():
    """Command line interface for pipeline visualization."""
    parser = argparse.ArgumentParser(description="Semantiva Pipeline GUI server")
    parser.add_argument("yaml", help="Path to pipeline YAML")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    serve_pipeline(args.yaml, args.host, args.port)


if __name__ == "__main__":
    main()
