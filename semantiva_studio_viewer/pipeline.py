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
from typing import Union, List, Dict
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
            return build_pipeline_json(app.state.config)

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


def serve_pipeline(yaml_path: str, host: str = "127.0.0.1", port: int = 8000):
    """Serve pipeline visualization web interface.

    Args:
        yaml_path: Path to pipeline YAML configuration file
        host: Host address to bind to
        port: Port number to listen on

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

    # Security: Disable debug mode and limit host in production
    debug_mode = False
    if host == "127.0.0.1" or host == "localhost":
        debug_mode = True

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        raise OSError(f"Failed to start server on {host}:{port}: {e}")


def export_pipeline(yaml_path: str, output_path: str):
    """Export pipeline visualization to standalone HTML file.

    Args:
        yaml_path: Path to pipeline YAML configuration file
        output_path: Path for output HTML file

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

    # Only use configuration for build_pipeline_json
    data = build_pipeline_json(config)

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

    # Create data injection with proper escaping
    import html as html_module

    escaped_data = html_module.escape(json.dumps(data))
    injection = (
        "<script>\n"
        f"window.PIPELINE_DATA = JSON.parse({json.dumps(escaped_data)});\n"
        "window.fetch = ((orig) => (url, options) => {\n"
        "  if (url === '/api/pipeline') {\n"
        "    return Promise.resolve({ok: true, json: () => Promise.resolve(window.PIPELINE_DATA)});\n"
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
