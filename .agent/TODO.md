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
- [x] Create Python project structure (pyproject.toml, src layout)
- [x] Set up dependencies
- [x] Create main CLI entry point

### Phase 2: Core Utilities
- [x] Port client.py (Turbopuffer client initialization)
- [x] Port regions.py (all 13 supported regions)
- [x] Port debug.py (debug logging utilities)
- [x] Port embeddings.py (sentence-transformers integration)
- [x] Port metadata_fetcher.py (namespace metadata fetching)
- [x] Port metrics.py (Prometheus formatting)

### Phase 3: Commands
- [x] Port list command (namespaces + documents)
- [x] Port search command (vector + FTS)
- [x] Port delete command (single, all, prefix)
- [x] Port edit command (vim editing)
- [x] Port get command (single document)
- [x] Port export command (Prometheus exporter)

### Phase 4: Testing & Polish
- [ ] Test all commands
- [ ] Ensure output matches TypeScript version
- [ ] Add proper error handling

## Current Status
**Status**: Phase 3 Complete - All commands ported!

## Session Log
- Session 1: Initial exploration and project setup
- Session 2: Completed metadata_fetcher.py utility with parallel fetching support
- Session 3: Completed metrics.py (Prometheus formatting utilities)
- Session 4: Ported list command + fixed client.py and metadata_fetcher.py for new turbopuffer SDK v1.2.0
- Session 5: Ported search, delete, get, edit, and export commands
