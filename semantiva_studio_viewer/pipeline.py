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


def _ensure_trace_loaded():
    """Try to lazily load trace file if app.state.trace_index is not present and a path was provided."""
    if hasattr(app.state, "trace_index") and app.state.trace_index:
        return
    trace_path = getattr(app.state, "trace_jsonl", None)
    if not trace_path:
        return
    try:
        from .trace_index import TraceIndex

        trace_file = Path(trace_path)
        if trace_file.exists() and trace_file.is_file():
            app.state.trace_index = TraceIndex.from_jsonl(trace_path)
            print(f"Lazy-loaded trace file: {trace_path}")
    except Exception as e:
        print(f"Warning: Failed to lazy-load trace file {trace_path}: {e}")
        app.state.trace_index = None


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
    return json_report(inspection)


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


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "web_gui" / "index.html")


@app.get("/api/trace/meta")
def get_trace_meta():
    """Get trace metadata.

    Returns:
        Dict containing run_id, pipeline_id, file info, counts, warnings

    Raises:
        HTTPException: If no trace is loaded
    """
    # Ensure trace is loaded (lazy load if --trace-jsonl was provided but loading deferred)
    _ensure_trace_loaded()
    if not hasattr(app.state, "trace_index") or app.state.trace_index is None:
        raise HTTPException(
            status_code=404,
            detail="No trace data available. Load a trace file with --trace-jsonl.",
        )
    meta = app.state.trace_index.get_meta()
    # Also expose canonical nodes (if available) for UI to show declaration_index/subindex
    if (
        hasattr(app.state.trace_index, "canonical_nodes")
        and app.state.trace_index.canonical_nodes
    ):
        meta["canonical_nodes"] = list(app.state.trace_index.canonical_nodes.values())
    return meta


@app.get("/api/trace/summary")
def get_trace_summary():
    """Get aggregated trace data for all nodes.

    Returns:
        Dict with "nodes" key containing per-node aggregates

    Raises:
        HTTPException: If no trace is loaded
    """
    _ensure_trace_loaded()
    if not hasattr(app.state, "trace_index") or app.state.trace_index is None:
        raise HTTPException(
            status_code=404,
            detail="No trace data available. Load a trace file with --trace-jsonl.",
        )

    return app.state.trace_index.summary()


@app.get("/api/trace/node/{node_uuid}")
def get_trace_node_events(node_uuid: str, offset: int = 0, limit: int = 100):
    """Get detailed events for a specific node.

    Args:
        node_uuid: UUID of the node to get events for
        offset: Number of events to skip (for paging)
        limit: Maximum number of events to return

    Returns:
        Dict containing events list, total count, and paging info

    Raises:
        HTTPException: If no trace is loaded or invalid parameters
    """
    _ensure_trace_loaded()
    if not hasattr(app.state, "trace_index") or app.state.trace_index is None:
        raise HTTPException(
            status_code=404,
            detail="No trace data available. Load a trace file with --trace-jsonl.",
        )

    # Validate parameters
    if offset < 0:
        raise HTTPException(status_code=400, detail="Offset must be non-negative")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")

    return app.state.trace_index.node_events(node_uuid, offset, limit)


@app.get("/api/trace/mapping")
def get_trace_label_mapping():
    """Get mapping from pipeline node labels to trace UUIDs.

    Returns:
        Dict mapping pipeline node labels to trace node UUIDs

    Raises:
        HTTPException: If no trace is loaded
    """
    _ensure_trace_loaded()
    if not hasattr(app.state, "trace_index") or app.state.trace_index is None:
        raise HTTPException(
            status_code=404,
            detail="No trace data available. Load a trace file with --trace-jsonl.",
        )

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
    meta = app.state.trace_index.get_meta()
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
            legacy_uuid = app.state.trace_index.find_node_uuid_by_label(node["label"])
            if legacy_uuid:
                label_to_uuid[node["label"]] = legacy_uuid

    return {
        "label_to_uuid": label_to_uuid,
        "available_labels": [node["label"] for node in nodes],
        "available_fqns": list(app.state.trace_index.fqn_to_node_uuid.keys()),
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

    try:
        # Load the pipeline configuration (doesn't create Pipeline object)
        config = load_pipeline_from_yaml(yaml_path)
    except Exception as e:
        raise ValueError(f"Failed to load pipeline configuration: {e}")

    app.state.config = config
    app.state.trace_index = None
    # Keep the trace path so endpoints can attempt lazy-loading if needed
    app.state.trace_jsonl = trace_jsonl

    # Initialize trace index if trace file is provided
    if trace_jsonl:
        try:
            from .trace_index import TraceIndex

            trace_file = Path(trace_jsonl)
            if not trace_file.exists():
                print(f"Warning: Trace file not found: {trace_jsonl}")
            elif not trace_file.is_file():
                print(f"Warning: Trace path is not a file: {trace_jsonl}")
            else:
                print(f"Loading trace file: {trace_jsonl}")
                app.state.trace_index = TraceIndex.from_jsonl(trace_jsonl)
                print(
                    f"Trace loaded: {app.state.trace_index.run_id} ({len(app.state.trace_index.per_node)} nodes)"
                )
        except ImportError:
            print("Warning: TraceIndex not available, trace file will be ignored")
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

    try:
        config = load_pipeline_from_yaml(yaml_path)
    except Exception as e:
        raise ValueError(f"Failed to load pipeline configuration: {e}")

    # Load trace data if provided
    trace_data = {}
    if trace_jsonl:
        try:
            from .trace_index import TraceIndex

            trace_index = TraceIndex.from_jsonl(trace_jsonl)

            # Build trace data for injection
            trace_meta = trace_index.get_meta()
            trace_summary = trace_index.summary()

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

            trace_mapping = {
                "label_to_uuid": label_to_uuid,
                "available_labels": [node["label"] for node in pipeline_data["nodes"]],
                "available_fqns": list(trace_index.fqn_to_node_uuid.keys()),
                "node_mappings": {
                    "index_to_uuid": index_to_uuid,
                    "uuid_to_index": trace_meta.get("node_mappings", {}).get(
                        "uuid_to_index", {}
                    ),
                },
            }

            # Store all trace data
            trace_data = {
                "meta": trace_meta,
                "summary": trace_summary,
                "mapping": trace_mapping,
                "node_events": {},  # Will be populated with individual node events
            }

            # Pre-load events for all mapped nodes
            for label, uuid in label_to_uuid.items():
                events_response = trace_index.node_events(uuid, offset=0, limit=100)
                trace_data["node_events"][uuid] = events_response

            print(
                f"Trace data loaded: {trace_meta['run_id']} ({len(label_to_uuid)} nodes mapped)"
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

    # Create data injection - no escaping needed for JavaScript literals
    data_json = json.dumps(data)
    trace_data_json = json.dumps(trace_data)

    # Build trace endpoint mocks if trace data is available
    trace_endpoints = ""
    if trace_data:
        trace_endpoints = """
  if (url === '/api/trace/meta') {
    return Promise.resolve({ok: true, json: () => Promise.resolve(window.TRACE_DATA.meta)});
  }
  if (url === '/api/trace/summary') {
    return Promise.resolve({ok: true, json: () => Promise.resolve(window.TRACE_DATA.summary)});
  }
  if (url === '/api/trace/mapping') {
    return Promise.resolve({ok: true, json: () => Promise.resolve(window.TRACE_DATA.mapping)});
  }
  if (url.startsWith('/api/trace/node/')) {
    const nodeUuid = url.split('/api/trace/node/')[1];
    const events = window.TRACE_DATA.node_events[nodeUuid];
    if (events) {
      return Promise.resolve({ok: true, json: () => Promise.resolve(events)});
    }
    return Promise.resolve({ok: false, status: 404});
  }"""

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
