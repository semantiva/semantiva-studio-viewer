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

Overlay execution data from **SER (Step Evidence Record)** or legacy JSONL traces:

```bash
semantiva-studio-viewer serve-pipeline semantiva-imaging-pipeline.yaml \
  --trace-jsonl traces/execution.ser.jsonl
```

**SER v1.1+ support** (recommended):
* Full execution evidence: checks, IO deltas, summaries, timing
* Pre/post-execution validation results
* Policy compliance indicators  
* Created/updated/read keys tracking
* Rich data type summaries with hashes

**Legacy trace support** (deprecated):
* Basic before/after/error events
* Timing and hash summaries
* Backward compatibility for older runs

Trace overlay adds:

* Per-node execution summaries (phases, timings, counts).
* SER-specific features: checks badges, IO delta summaries, policy results
* Deterministic node↔UUID binding (via **positional identity** or SER labels).
* Per-node event APIs: `/api/trace/node/<uuid>?offset=&limit=`
* Trace metadata at `/api/trace/meta` and aggregated stats at `/api/trace/summary`.

You can also **export HTML with traces pre-baked**:

```bash
semantiva-studio-viewer export-pipeline semantiva-imaging-pipeline.yaml \
  pipeline_with_trace.html --trace-jsonl traces/execution.ser.jsonl
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
* **SER v0 (draft) format** is used for execution traces in the current version.
* When traces are present, **node→UUID mapping uses SER labels** first, then **positional identity** (from `canonical_spec`); FQN fallbacks are used only if necessary.
* **SER-only mode**: If only SER data is available (no pipeline config), Studio can reconstruct basic graph topology from SER `upstream` relationships.

---

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).