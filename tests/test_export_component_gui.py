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

from pathlib import Path

from semantiva_studio_viewer.components import export_components


def test_export_components_creates_standalone_html(monkeypatch, tmp_path):
    dummy_ttl = tmp_path / "components.ttl"
    dummy_ttl.write_text("@prefix smtv: <http://semantiva.org/semantiva#> .")
    output_file = tmp_path / "output.html"

    dummy_data = {"nodes": [], "edges": []}

    # Mock the build_component_json function
    import semantiva_studio_viewer.components as components_module

    monkeypatch.setattr(
        components_module, "build_component_json", lambda path: dummy_data
    )

    # Mock file reading
    def mock_read_text(self, encoding=None):
        if self.name.endswith(".html"):
            return "<html><body>Hello</body></html>"
        elif self.name.endswith(".css"):
            return "body { margin: 0; }"
        elif self.name.endswith(".js"):
            return "console.log('test');"
        return ""

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    written = {}

    def fake_write_text(self, content, encoding=None):
        written["content"] = content

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    export_components(str(dummy_ttl), str(output_file))

    content = written.get("content", "")
    # The data is now JSON.parse(escaped_data) instead of direct injection
    assert "window.COMPONENT_DATA = JSON.parse(" in content
    assert content.count("<script>") >= 1
