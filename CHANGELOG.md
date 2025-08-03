# Changelog

All notable changes to the Semantiva Studio Viewer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - TBD

### Added
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

