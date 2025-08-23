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

from semantiva_studio_viewer.pipeline import export_pipeline


class DummyPipeline:
    pass


def test_export_pipeline_creates_standalone_html(monkeypatch, tmp_path):
    # Prepare dummy input YAML and output path
    dummy_yaml = tmp_path / "pipeline.yaml"
    dummy_yaml.write_text("dummy: config")
    output_file = tmp_path / "output.html"

    # Dummy pipeline data
    dummy_data = {"foo": "bar"}

    # Mock the semantiva imports and functions
    import semantiva_studio_viewer.pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module, "load_pipeline_from_yaml", lambda path: [{"dummy": True}]
    )
    monkeypatch.setattr(pipeline_module, "Pipeline", lambda config: DummyPipeline())
    monkeypatch.setattr(
        pipeline_module, "build_pipeline_json", lambda config: dummy_data
    )

    # Monkeypatch reading template HTML
    def mock_read_text(self, encoding=None):
        if self.name.endswith(".html"):
            return "<html><body>Hello</body></html>"
        elif self.name.endswith(".css"):
            return "body { margin: 0; }"
        elif self.name.endswith(".js"):
            return "console.log('test');"
        return ""

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    # Capture written content
    written = {}

    def fake_write_text(self, content, encoding=None):
        written["content"] = content

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    # Run export
    export_pipeline(str(dummy_yaml), str(output_file))

    # Verify that the script injection contains the pipeline data
    content = written.get("content", "")
    # The data is now JSON.parse(escaped_data) instead of direct injection
    assert "window.PIPELINE_DATA = JSON.parse(" in content
    assert content.count("<script>") >= 1
