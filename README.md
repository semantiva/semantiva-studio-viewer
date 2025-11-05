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

### Viewing Multiple Executions in One Trace File

Studio now supports JSON/JSONL files that contain **multiple SER runs**.

* Use `--trace-jsonl` to point to a combined file containing multiple execution runs.
* A **Run** dropdown appears in the header (format: `run_id[:8] • started_at`).
* Selecting a run updates the overlays and URL (`?run=<id>`).
* Node detail panels now show **Run Args** (e.g., run-space pins) and an **Environment** slice
  (including `registry.fingerprint`) when present in SER.

**Multi-run file formats supported:**
* **JSONL format**: One SER record per line, multiple runs mixed together
* **JSON array format**: Array of SER records from different runs

**Example multi-run trace file (JSONL)**:
```jsonl
{"type":"ser","ids":{"run_id":"run-1","pipeline_id":"p"},"timing":{"start":"2025-01-01T00:00:01Z"},"status":"completed"}
{"type":"ser","ids":{"run_id":"run-2","pipeline_id":"p"},"timing":{"start":"2025-01-01T00:00:03Z"},"status":"completed"}
{"type":"ser","ids":{"run_id":"run-1","pipeline_id":"p"},"timing":{"start":"2025-01-01T00:00:05Z"},"status":"completed"}
```

#### Run-Space Launch Filtering

When traces contain **run-space metadata** (from parameter sweeps or fanout executions), the viewer provides:

* **Run-Space dropdown**: Filter runs by `(launch_id, attempt)` pair
  * **All**: Show all runs (default)
  * **None**: Show only runs without run-space decoration (orphan runs)
  * **Launch entries**: One option per unique `(launch_id, attempt)` with format:  
    `<launch_id> · attempt <N> · <combine_mode> · <total_runs>`
* **Deep-link support**: Share specific run-space views via URL  
  `?launch=<launch_id>&attempt=<N>&run=<run_id>`
* **Backward compatible**: Traces without run-space metadata work as before

**Run-space fields in traces** (optional, from `pipeline_start` events):
* `run_space_launch_id`: Unique identifier for the sweep/launch
* `run_space_attempt`: Attempt number for retry/variant tracking
* `run_space_index`: Position within the launch (for ordering)
* `run_space_combine_mode`: How parameters were combined (`product`, `zip`, etc.)

**Run Args panel** displays run-space parameters and other execution arguments:
* `fanout.index`, `fanout.values`, `values_file_sha256`, etc.
* Derived from `checks.why_ok.args` in SER records
* Includes JSON view toggle for detailed inspection

**Environment panel** shows execution environment details:
* Python version, platform, Semantiva version
* Registry fingerprint for reproducibility tracking
* Derived from `checks.why_ok.env` in SER records

**API support for multi-run traces:**
* New endpoint: `GET /api/runs` lists available runs with metadata
* All trace endpoints accept optional `?run=<run_id>` parameter
* Backward compatible: single-run files work without any changes

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
* **SER v1 format** is used for execution traces.
* When traces are present, **node→UUID mapping uses SER identity** first, then **positional identity** (from `canonical_spec`); FQN fallbacks are used only if necessary.
* **SER-only mode**: If only SER data is available (no pipeline config), Studio can reconstruct basic graph topology from SER `dependencies.upstream` relationships.

---

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).