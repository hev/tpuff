# Python Port - tpuff CLI

## Overview
Porting tpuff-cli from TypeScript to Python while maintaining the same command syntax and functionality.

## Key Decisions
- Use `click` for CLI framework (similar to Commander.js)
- Use `sentence-transformers` for embeddings (no Xenova support needed)
- Use `turbopuffer` Python SDK
- Use `requests` for HTTP, `rich` for terminal output

## Tasks

### Phase 1: Project Setup
- [ ] Create Python project structure (pyproject.toml, src layout)
- [ ] Set up dependencies
- [ ] Create main CLI entry point

### Phase 2: Core Utilities
- [ ] Port client.py (Turbopuffer client initialization)
- [ ] Port regions.py (all 13 supported regions)
- [ ] Port debug.py (debug logging utilities)
- [ ] Port embeddings.py (sentence-transformers integration)
- [ ] Port metadata_fetcher.py (namespace metadata fetching)
- [ ] Port metrics.py (Prometheus formatting)

### Phase 3: Commands
- [ ] Port list command (namespaces + documents)
- [ ] Port search command (vector + FTS)
- [ ] Port delete command (single, all, prefix)
- [ ] Port edit command (vim editing)
- [ ] Port get command (single document)
- [ ] Port export command (Prometheus exporter)

### Phase 4: Testing & Polish
- [ ] Test all commands
- [ ] Ensure output matches TypeScript version
- [ ] Add proper error handling

## Current Status
**Status**: Starting Phase 1 - Project Setup

## Session Log
- Session 1: Initial exploration and project setup
