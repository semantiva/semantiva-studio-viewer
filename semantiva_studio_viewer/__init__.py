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

"""Semantiva Studio Viewer - Web-based visualization for Semantiva pipelines and components.

This package provides interactive web interfaces for exploring Semantiva pipelines and
component hierarchies. It includes both server-based interactive viewers and standalone
HTML export capabilities.
"""

__all__ = [
    "serve_pipeline",
    "serve_components",
    "export_pipeline",
    "export_components",
]

try:
    from .pipeline import serve_pipeline, export_pipeline
    from .components import serve_components, export_components
except ImportError:
    # Allow package to be imported even if dependencies are not available
    pass
