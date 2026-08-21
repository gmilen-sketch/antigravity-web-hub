---
name: diagram-renderer
description: Compiles and renders Mermaid, Graphviz, PlantUML, and Cloud architecture diagrams directly to PNG/SVG with zero cloud dependencies.
version: 1.0.0
---

# Diagram Renderer (Clean-Room Edition)

Compiles text-based architecture and topology diagrams to high-resolution PNG/SVG vector assets.

## Supported Formats
* **Mermaid.js**: Flowcharts, Sequence Diagrams, State Machines, C4 Contexts.
* **Graphviz DOT**: Complex directed graphs, cluster topologies.
* **PlantUML**: Component diagrams, sequence protocols.

## Usage
```bash
# Render Mermaid diagram
npx -y @mermaid-js/mermaid-cli -i input.mmd -o output.png -b transparent

# Render Graphviz DOT
dot -Tpng input.dot -o output.png
```
