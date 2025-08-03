# Semantiva Studio Viewer

A lightweight web-based viewer for Semantiva pipelines and components with interactive visualization capabilities.

## Overview

**Semantiva Studio Viewer** provides an intuitive web interface for exploring, analyzing, and visualizing Semantiva pipelines and component hierarchies. It offers both interactive web servers and standalone HTML export capabilities, making it perfect for development, debugging, documentation, and sharing pipeline configurations.

## Key Features

### Pipeline Visualization
- **Dual-Channel Layout**: Separates data processing and context processing operations for clarity
- **Interactive Node Inspection**: Click on any node to view detailed information about processors, parameters, and data types
- **Parameter Flow Tracking**: Visual representation of how parameters flow from configuration and context
- **Error Highlighting**: Invalid configurations and data type mismatches are clearly highlighted
- **Responsive Design**: Works on desktop and mobile devices

### Component Hierarchy Browser
- **Ontology Visualization**: Interactive tree view of the complete Semantiva component hierarchy
- **Type-Based Organization**: Components grouped by type (Data Processors, Context Processors, I/O Components, etc.)
- **Detailed Documentation**: Access docstrings, input/output types, and parameter information
- **Search and Filter**: Find components quickly with filtering capabilities

### Export Capabilities
- **Standalone HTML**: Generate self-contained HTML files for sharing and documentation
- **GitHub Pages Ready**: Export files work perfectly with static hosting services
- **Offline Viewing**: No server required for exported visualizations

## Installation

```bash
pip install semantiva-studio-viewer
```

Or with PDM:
```bash
pdm add semantiva-studio-viewer
```

## Quick Start

### Pipeline Visualization

1. **Start Interactive Server**:
   ```bash
   semantiva-studio-viewer serve-pipeline path/to/pipeline.yaml --port 8000
   ```
   Then open `http://127.0.0.1:8000` to explore your pipeline interactively.

2. **Export Standalone HTML**:
   ```bash
   semantiva-studio-viewer export-pipeline path/to/pipeline.yaml output.html
   ```

### Component Hierarchy Browser

1. **Start Interactive Server**:
   ```bash
   semantiva-studio-viewer serve-components semantiva_components.ttl --port 8001
   ```

2. **Export Standalone HTML**:
   ```bash
   semantiva-studio-viewer export-components semantiva_components.ttl components.html
   ```

## Use Cases

### Development & Debugging
- **Pipeline Development**: Visualize pipeline structure during development to ensure correct flow
- **Error Diagnosis**: Quickly identify configuration errors, missing parameters, or data type mismatches
- **Parameter Tracking**: Understand how context flows through your pipeline

### Documentation & Sharing
- **Team Collaboration**: Share pipeline visualizations with team members for review
- **Documentation**: Include exported HTML files in documentation or presentations
- **Educational**: Teach Semantiva concepts with visual pipeline examples

### Analysis & Optimization
- **Architecture Review**: Review pipeline architecture and node relationships
- **Validation**: Ensure pipelines conform to expected patterns and constraints

## Interface Overview

### Pipeline Viewer
- **Left Panel**: Categorized list of pipeline nodes (Data Processing, Context Processing, I/O)
- **Center Panel**: Interactive dual-channel graph visualization
- **Right Panel**: Detailed node information including parameters, types, and documentation

### Component Browser  
- **Left Panel**: Component groups with filtering options
- **Center Panel**: Interactive hierarchy tree
- **Right Panel**: Component details with full documentation

## Advanced Features

### Configuration Error Handling
The viewer can visualize even invalid pipeline configurations, helping you identify and fix issues:
- Missing required parameters
- Data type incompatibilities
- Invalid component references
- Context flow problems

### Parameter Resolution Display
Understand exactly how each node gets its parameters:
- **Pipeline Configuration**: Parameters directly specified in YAML
- **Context Values**: Parameters sourced from previous nodes' context output
- **Default Values**: When components use built-in defaults

### Export Options
- **Self-Contained**: All CSS, JavaScript, and data embedded in a single HTML file
- **CDN-Free**: No external dependencies for exported files
- **Cross-Platform**: Works in any modern web browser

## Integration with Semantiva

This viewer integrates seamlessly with the Semantiva framework:
- Uses the same configuration files and component definitions
- Leverages Semantiva's inspection system for accurate analysis
- Supports all Semantiva data types and component types
- Compatible with custom components and extensions

## License

Licensed under the Apache License, Version 2.0. See LICENSE file for details.