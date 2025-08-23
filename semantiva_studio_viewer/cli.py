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

"""Command-line interface for Semantiva Studio Viewer."""

import argparse
import sys

from .pipeline import serve_pipeline, export_pipeline
from .components import serve_components, export_components


def serve_pipeline_command(args) -> None:
    """Handle serve-pipeline command."""
    serve_pipeline(args.yaml, args.host, args.port, getattr(args, "trace_jsonl", None))


def serve_components_command(args) -> None:
    """Handle serve-components command."""
    serve_components(args.ttl, args.host, args.port)


def export_pipeline_command(args) -> None:
    """Handle export-pipeline command."""
    export_pipeline(args.yaml, args.output, getattr(args, "trace_jsonl", None))


def export_components_command(args) -> None:
    """Handle export-components command."""
    export_components(args.ttl, args.output)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Semantiva Studio Viewer - Web-based visualization for Semantiva pipelines and components"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve pipeline command
    serve_pipeline_parser = subparsers.add_parser(
        "serve-pipeline", help="Start interactive pipeline visualization server"
    )
    serve_pipeline_parser.add_argument(
        "yaml", help="Path to pipeline YAML configuration"
    )
    serve_pipeline_parser.add_argument(
        "--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)"
    )
    serve_pipeline_parser.add_argument(
        "--port", type=int, default=8000, help="Port number (default: 8000)"
    )
    serve_pipeline_parser.add_argument(
        "--trace-jsonl", help="Path to trace JSONL file", default=None
    )
    serve_pipeline_parser.set_defaults(func=serve_pipeline_command)

    # Serve components command
    serve_components_parser = subparsers.add_parser(
        "serve-components",
        help="Start interactive component hierarchy visualization server",
    )
    serve_components_parser.add_argument("ttl", help="Path to ontology TTL file")
    serve_components_parser.add_argument(
        "--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)"
    )
    serve_components_parser.add_argument(
        "--port", type=int, default=8000, help="Port number (default: 8000)"
    )
    serve_components_parser.set_defaults(func=serve_components_command)

    # Export pipeline command
    export_pipeline_parser = subparsers.add_parser(
        "export-pipeline", help="Export pipeline visualization to standalone HTML"
    )
    export_pipeline_parser.add_argument(
        "yaml", help="Path to pipeline YAML configuration"
    )
    export_pipeline_parser.add_argument("output", help="Output HTML file path")
    export_pipeline_parser.add_argument(
        "--trace-jsonl", help="Path to trace JSONL file", default=None
    )
    export_pipeline_parser.set_defaults(func=export_pipeline_command)

    # Export components command
    export_components_parser = subparsers.add_parser(
        "export-components",
        help="Export component hierarchy visualization to standalone HTML",
    )
    export_components_parser.add_argument("ttl", help="Path to ontology TTL file")
    export_components_parser.add_argument("output", help="Output HTML file path")
    export_components_parser.set_defaults(func=export_components_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
