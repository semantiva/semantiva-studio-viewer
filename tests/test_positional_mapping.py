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

from fastapi.testclient import TestClient

from semantiva_studio_viewer.pipeline import app


def make_fake_trace_index():
    """Return a minimal fake TraceIndex-like object with 4 canonical nodes
    and node_mappings that map '0:0' -> the expected UUID used in tests.
    """
    uuid0 = "2a70cc06-a97a-5013-ba84-0a210fdf53cc"

    class FakeIndex:
        def __init__(self):
            # mimic a mapping of declaration_index:subindex -> node metadata
            # keep as dict so len(canonical_nodes) == 4
            self.canonical_nodes = {
                "0:0": {
                    "node_uuid": uuid0,
                    "declaration_index": 0,
                    "declaration_subindex": 0,
                },
                "1:0": {
                    "node_uuid": "u1",
                    "declaration_index": 1,
                    "declaration_subindex": 0,
                },
                "2:0": {
                    "node_uuid": "u2",
                    "declaration_index": 2,
                    "declaration_subindex": 0,
                },
                "3:0": {
                    "node_uuid": "u3",
                    "declaration_index": 3,
                    "declaration_subindex": 0,
                },
            }

            # minimal FQN map expected by pipeline endpoints
            self.fqn_to_node_uuid = {
                "fake.module.GENERATOR": uuid0,
                "fake.module.FITTER": "u1",
            }

        def get_meta(self):
            return {
                "node_mappings": {
                    "index_to_uuid": {
                        k: v["node_uuid"] for k, v in self.canonical_nodes.items()
                    },
                    "uuid_to_index": {
                        v["node_uuid"]: {
                            "declaration_index": v["declaration_index"],
                            "declaration_subindex": v["declaration_subindex"],
                        }
                        for v in self.canonical_nodes.values()
                    },
                }
            }

        def find_node_uuid_by_label(self, label):
            # simplistic fallback used only as a last-resort in pipeline; return None to
            # force positional mapping in tests
            return None

    return FakeIndex()


def test_index_to_uuid_from_canonical_nodes():
    idx = make_fake_trace_index()
    # there are 4 canonical nodes in pipeline_start (fake)
    assert len(idx.canonical_nodes) == 4

    meta = idx.get_meta()
    itumap = meta.get("node_mappings", {}).get("index_to_uuid", {})
    assert "0:0" in itumap
    # Check the first node uuid matches the provided example
    assert itumap["0:0"] == "2a70cc06-a97a-5013-ba84-0a210fdf53cc"


def test_trace_meta_exposes_index_maps():
    # Prepare app state
    app.state.config = []  # not used here
    app.state.trace_index = make_fake_trace_index()

    client = TestClient(app)
    resp = client.get("/api/trace/meta")
    assert resp.status_code == 200
    data = resp.json()

    nm = data.get("node_mappings", {})
    assert "index_to_uuid" in nm and "uuid_to_index" in nm
    assert nm["index_to_uuid"].get("0:0") == "2a70cc06-a97a-5013-ba84-0a210fdf53cc"


def test_trace_mapping_endpoint_uses_positional(monkeypatch):
    # Monkeypatch build_pipeline_json to return a synthetic pipeline with 4 nodes
    # Ensure labels do NOT match FQNs to force positional mapping
    fake_nodes = [
        {"id": 1, "label": "GENERATOR", "input_type": "", "output_type": "X"},
        {"id": 2, "label": "FITTER", "input_type": "X", "output_type": "X"},
        {"id": 3, "label": "MODEL-A", "input_type": "X", "output_type": "X"},
        {"id": 4, "label": "MODEL-B", "input_type": "X", "output_type": "X"},
    ]
    fake_edges = [
        {"source": 1, "target": 2},
        {"source": 2, "target": 3},
        {"source": 3, "target": 4},
    ]

    def fake_build_pipeline_json(_):
        return {"nodes": fake_nodes, "edges": fake_edges, "pipeline": {}}

    import semantiva_studio_viewer.pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module, "build_pipeline_json", fake_build_pipeline_json
    )

    # Prepare app state with trace loaded
    app.state.config = [{"dummy": True}]
    app.state.trace_index = make_fake_trace_index()

    client = TestClient(app)
    resp = client.get("/api/trace/mapping")
    assert resp.status_code == 200
    data = resp.json()
    mapping = data.get("label_to_uuid", {})
    # The first node label should map to the first uuid by positional index 0:0
    assert mapping.get("GENERATOR") == "2a70cc06-a97a-5013-ba84-0a210fdf53cc"


def test_pipeline_nodes_inject_node_uuid(monkeypatch):
    # Monkeypatch build_pipeline_json to return a synthetic pipeline in declaration order
    fake_nodes = [
        {"id": 1, "label": "GENERATOR"},
        {"id": 2, "label": "FITTER"},
        {"id": 3, "label": "MODEL-A"},
        {"id": 4, "label": "MODEL-B"},
    ]

    def fake_build_pipeline_json(_):
        return {"nodes": [n.copy() for n in fake_nodes], "edges": [], "pipeline": {}}

    import semantiva_studio_viewer.pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module, "build_pipeline_json", fake_build_pipeline_json
    )

    # Prepare app state
    app.state.config = [{"dummy": True}]
    app.state.trace_index = make_fake_trace_index()

    client = TestClient(app)
    resp = client.get("/api/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    nodes = data.get("nodes", [])
    assert len(nodes) == 4
    # First node should be enriched with node_uuid for (0,0)
    assert nodes[0].get("node_uuid") == "2a70cc06-a97a-5013-ba84-0a210fdf53cc"
