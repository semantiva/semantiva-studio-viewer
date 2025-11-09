# Changelog

All notable changes to the Semantiva Studio Viewer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - TBD

### Fixed
- **Identity Handling**: Removed local identity recomputation; no runtime IDs (`pipeline_id`, `run_id`) in inspection mode
  - `/api/pipeline` now uses official identity from `semantiva.inspection.build()` (YAML SSOT)
  - Fixed trace adapter fallbacks: `semantic_id` no longer substituted with `config_id`
  - `config_id` correctly uses `pipeline_config_id` as alias fallback only
  - Ensures deterministic identity computation across viewer sessions

### Added
- **Identity Health**: YAML↔Trace consistency badges when both sources available
  - Semantic ID match badge (✓ green for match, ✗ red for mismatch)
  - Config ID match badge (⚠ yellow for expected variation, ✗ red for mismatch)
  - Run-Space Plan match badge (✓ green for match, ✗ red for mismatch)
  - Helps diagnose wrong YAML used to inspect trace or parameter drift
- **Identity Sources Documentation**: New README section explaining YAML vs Trace identity sources
  - Links to Core Identity Cheatsheet in main Semantiva documentation
  - Clarifies when each identity source is used and what each ID represents
- **Run-Space Configuration Panel**: Pipeline Metadata panel now displays run-space configuration
  - Shows run-space identities (Spec ID, Launch ID, Inputs ID) with copyable values
  - Displays configuration (combine mode, planned/total runs, max runs limit)
  - Interactive fingerprints table with copyable digests and file details
  - Optional planner metadata (collapsible JSON viewer)
  - New backend endpoint: `/api/runspace/launch_details`
  - Smart empty states for "All" and "None" run-space selections
- **Run-Space Launch Selector**: New top-right dropdown to filter runs by run-space launch
  - Displays all unique (launch_id, attempt) combinations found in traces
  - Filters the Run dropdown to show only runs belonging to the selected launch
  - Deep-link support via `?launch=<id>&attempt=<n>&run=<run_id>` query parameters
  - "All" option to show all runs regardless of run-space
  - "None" option to show only runs without run-space decoration (orphan runs)
  - Graceful fallback for traces without run-space metadata (backward compatible)
  - New backend API endpoints: `/api/runspace/launches` and `/api/runspace/runs`
- **Initial Release**: Semantiva Studio Viewer package extracted from Semantiva core
- **Pipeline Visualization**: Interactive web-based visualization for Semantiva pipelines
  - Dual-channel layout separating Data Processing and Context Processing operations
  - Interactive node inspection with detailed parameter and type information
  - Parameter flow tracking showing how values flow from configuration and context
  - Error highlighting for invalid configurations and data type mismatches
  - Responsive design with zoom controls and mobile support
- **Component Hierarchy Browser**: Interactive visualization of Semantiva component ontology
  - Tree-view of complete component hierarchy with inheritance relationships
  - Type-based organization (Data Processors, Context Processors, I/O Components, etc.)
  - Detailed documentation access with docstrings and parameter information
  - Search and filter capabilities for finding components quickly
- **Export Capabilities**: Generate standalone HTML files for sharing and documentation
  - Self-contained HTML with embedded CSS, JavaScript, and data
  - No external dependencies for exported files
  - GitHub Pages ready and offline viewing compatible
- **Command Line Interface**: Easy-to-use CLI commands
  - `semantiva-studio-viewer serve-pipeline` - Start pipeline visualization server
  - `semantiva-studio-viewer serve-components` - Start component hierarchy server
  - `semantiva-studio-viewer export-pipeline` - Export pipeline to standalone HTML
  - `semantiva-studio-viewer export-components` - Export component hierarchy to standalone HTML
- **Comprehensive Test Suite**: Full test coverage for all functionality
  - Server functionality tests
  - Export functionality tests
  - Pipeline visualization tests
  - Component hierarchy tests

### Changed
- **Frontend Identity State**: Split identity into `inspectionIdentity` (YAML) and `traceIdentity` (Runtime)
  - Configuration Identity card now shows YAML-only fields (`semantic_id`, `config_id`, `run_space.spec_id`)
  - Runtime Execution card shows trace-only fields (`run_id`, `pipeline_id`, timestamps, context)
  - Identity Health section appears when both sources available for comparison
- **Trace Adapter**: Improved identity mapping consistency with Semantiva Core
  - `semantic_id` extraction without fallback (can be `None`)
  - `config_id` prefers explicit field, falls back to `pipeline_config_id` alias
  - Prevents identity conflation and follows schema properly

