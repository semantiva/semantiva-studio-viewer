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

"""Component hierarchy visualization web server and export functionality."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from rdflib import Graph, RDF, RDFS, OWL, Namespace

app = FastAPI()


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def build_component_json(ttl_path: str) -> Dict[str, Any]:
    """Build component hierarchy data from TTL ontology file.

    Args:
        ttl_path: Path to the ontology TTL file

    Returns:
        Dictionary containing nodes and edges for component hierarchy

    Raises:
        FileNotFoundError: If TTL file doesn't exist
        ValueError: If TTL file is invalid or malformed
    """
    ttl_file = Path(ttl_path)
    if not ttl_file.exists():
        raise FileNotFoundError(f"TTL file not found: {ttl_path}")

    if not ttl_file.is_file():
        raise ValueError(f"Path is not a file: {ttl_path}")

    try:
        g = Graph()
        g.parse(ttl_path, format="turtle")
    except Exception as e:
        raise ValueError(f"Failed to parse TTL file: {e}")

    SMTV = Namespace("http://semantiva.org/semantiva#")

    nodes: list[Dict[str, Any]] = []
    mapping: dict[Any, int] = {}
    for cls in g.subjects(RDF.type, OWL.Class):
        label = g.value(cls, RDFS.label) or str(cls).split("#")[-1]
        node_id = len(nodes)
        node = {
            "id": node_id,
            "label": str(label),
            "component_type": str(g.value(cls, SMTV.componentType) or ""),
            "docstring": str(g.value(cls, SMTV.docString) or ""),
            "input_type": str(g.value(cls, SMTV.inputDataType) or ""),
            "output_type": str(g.value(cls, SMTV.outputDataType) or ""),
            "parameters": str(g.value(cls, SMTV.parameters) or ""),
        }
        mapping[cls] = node_id
        nodes.append(node)

    edges: list[Dict[str, int]] = []
    for cls in g.subjects(RDF.type, OWL.Class):
        parent = g.value(cls, RDFS.subClassOf)
        if parent in mapping:
            edges.append({"source": mapping[parent], "target": mapping[cls]})

    return {"nodes": nodes, "edges": edges}


@app.get("/api/components")
def get_components_api() -> Dict[str, Any]:
    """Get component hierarchy data as JSON.

    Returns:
        Dict containing nodes and edges for component hierarchy

    Raises:
        HTTPException: If ontology is not loaded or processing fails
    """
    if not hasattr(app.state, "ttl_path"):
        raise HTTPException(status_code=404, detail="Ontology not loaded")

    try:
        return build_component_json(app.state.ttl_path)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process component data: {str(e)}"
        )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "web_gui" / "components.html")


def serve_components(ttl_path: str, host: str = "127.0.0.1", port: int = 8000):
    """Serve component hierarchy visualization web interface.

    Args:
        ttl_path: Path to ontology TTL file
        host: Host address to bind to
        port: Port number to listen on

    Raises:
        FileNotFoundError: If the TTL file doesn't exist
        ValueError: If port is not in valid range or TTL file is invalid
        OSError: If host/port combination is invalid
    """
    # Input validation
    ttl_file = Path(ttl_path)
    if not ttl_file.exists():
        raise FileNotFoundError(f"TTL file not found: {ttl_path}")

    if not ttl_file.is_file():
        raise ValueError(f"Path is not a file: {ttl_path}")

    if not 1 <= port <= 65535:
        raise ValueError(f"Port must be between 1 and 65535, got: {port}")

    # Validate host format (basic check)
    if not host or not isinstance(host, str):
        raise ValueError("Host must be a non-empty string")

    # Test that the TTL file can be parsed
    try:
        test_graph = Graph()
        test_graph.parse(ttl_path, format="turtle")
    except Exception as e:
        raise ValueError(f"Invalid TTL file: {e}")

    app.state.ttl_path = ttl_path

    static_dir = Path(__file__).parent / "web_gui" / "static"
    if not static_dir.exists():
        raise FileNotFoundError(f"Static files directory not found: {static_dir}")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    import uvicorn

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        raise OSError(f"Failed to start server on {host}:{port}: {e}")


def export_components(ttl_path: str, output_path: str):
    """Export component hierarchy visualization to standalone HTML file.

    Args:
        ttl_path: Path to ontology TTL file
        output_path: Path for output HTML file

    Raises:
        FileNotFoundError: If the TTL file doesn't exist
        ValueError: If paths are invalid or TTL file is malformed
        PermissionError: If output path is not writable
    """
    # Input validation
    ttl_file = Path(ttl_path)
    if not ttl_file.exists():
        raise FileNotFoundError(f"TTL file not found: {ttl_path}")

    if not ttl_file.is_file():
        raise ValueError(f"Path is not a file: {ttl_path}")

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
        data = build_component_json(ttl_path)
    except Exception as e:
        raise ValueError(f"Failed to process TTL file: {e}")

    template_dir = Path(__file__).parent / "web_gui"
    template_path = template_dir / "components.html"
    css_path = template_dir / "static" / "components.css"
    js_path = template_dir / "static" / "components.js"

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
        '<link rel="stylesheet" href="/static/components.css" />',
        f"<style>\n{css}\n</style>",
    )
    html = html.replace(
        '<script type="text/babel" src="/static/components.js"></script>',
        f'<script type="text/babel">\n{js}\n</script>',
    )

    # Create data injection with proper escaping
    import html as html_module

    escaped_data = html_module.escape(json.dumps(data))
    injection = (
        "<script>\n"
        f"window.COMPONENT_DATA = JSON.parse({json.dumps(escaped_data)});\n"
        "window.fetch = ((orig) => (url, options) => {\n"
        "  if (url === '/api/components') {\n"
        "    return Promise.resolve({ok: true, json: () => Promise.resolve(window.COMPONENT_DATA)});\n"
        "  }\n"
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


def main() -> None:
    """Command line interface for component hierarchy visualization."""
    parser = argparse.ArgumentParser(description="Semantiva Component GUI server")
    parser.add_argument("ttl", help="Path to ontology TTL file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    serve_components(args.ttl, args.host, args.port)


if __name__ == "__main__":
    main()
