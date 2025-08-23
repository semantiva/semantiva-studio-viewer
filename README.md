# Semantiva Studio Viewer

Web-based viewers and exporters for **Semantiva** pipelines and component hierarchies.

## Install

```bash
pip install semantiva-studio-viewer
````

This provides the `semantiva-studio-viewer` CLI.

---

## CLI overview

```bash
semantiva-studio-viewer --help
```

Main commands:

* **Pipeline inspection**

  * `serve-pipeline <pipeline.yaml> [--trace-jsonl <trace.jsonl>] [--host 127.0.0.1] [--port 8000]`
  * `export-pipeline <pipeline.yaml> <output.html> [--trace-jsonl <trace.jsonl>]`
* **Component inspection**

  * `serve-components <ontology.ttl> [--host 127.0.0.1] [--port 8000]`
  * `export-components <ontology.ttl> <output.html>`

---

## Pipeline inspector

Interactive view of a pipeline:

```bash
semantiva-studio-viewer serve-pipeline semantiva-imaging-pipeline.yaml --port 8000
```

Features:

* Dual-channel layout (data + context).
* Node details: parameters, types, provenance.
* Validation hints from Semantiva’s inspection system.

---

### Adding execution traces

Overlay a JSONL trace (from a previous run):

```bash
semantiva-studio-viewer serve-pipeline semantiva-imaging-pipeline.yaml \
  --trace-jsonl traces/20250823_run.jsonl
```

Trace overlay adds:

* Per-node execution summaries (phases, timings, counts).
* Deterministic node↔UUID binding (via **positional identity** in canonical spec).
* Per-node event APIs: `/api/trace/node/<uuid>?offset=&limit=`
* Trace metadata at `/api/trace/meta` and aggregated stats at `/api/trace/summary`.

You can also **export HTML with traces pre-baked**:

```bash
semantiva-studio-viewer export-pipeline semantiva-imaging-pipeline.yaml \
  pipeline_with_trace.html --trace-jsonl traces/run.jsonl
```

---

## Components browser

Explore Semantiva component ontologies:

```bash
semantiva-studio-viewer serve-components semantiva_components.ttl --port 8001
```

* Classes as nodes
* Subclass edges
* Metadata from docstrings, I/O types, parameters

Export standalone HTML:

```bash
semantiva-studio-viewer export-components semantiva_components.ttl components.html
```

---

## Notes

* The inspector tolerates partially invalid configs to aid debugging.
* When traces are present, **node→UUID mapping is positional** (from `canonical_spec`); label/FQN fallbacks are used only if necessary.

---

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).