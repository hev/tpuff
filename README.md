# Turbopuffer CLI (tpuff)

A TypeScript CLI for interacting with turbopuffer vector database. This tool allows you to list and filter namespaces, browse namespace data, perform full-text search, and execute admin functions.

## Prerequisites

- Node.js 20+
- A turbopuffer API key

Set the following environment variables:
- `TURBOPUFFER_API_KEY` (required): Your turbopuffer API key
- `TURBOPUFFER_REGION` (optional): Region to use (defaults to `aws-us-east-1`)
- `TURBOPUFFER_BASE_URL` (optional): Custom base URL for a specific region

## Installation

```bash
npm install
npm run build
```

## Usage

### Development Mode
```bash
npm run dev -- [command] [options]
```

### Production Mode
```bash
npm start [command] [options]
```

Or after building, link it globally:
```bash
npm link
tpuff [command] [options]
```

## Commands

### list (alias: ls)

List all namespaces with detailed metadata in a formatted table, or list documents in a specific namespace.

**List all namespaces:**
```bash
tpuff list
```

Displays a table with:
- Namespace name (bold)
- Approximate row count
- Logical bytes (formatted)
- Index status (green for "up-to-date", red for "updating")
- Created timestamp
- Updated timestamp

**List documents in a namespace:**
```bash
tpuff list <namespace>
```
(Coming soon)

## Future Features

See [claude.md](./claude.md) for planned features including:
- Full-text search (FTS)
- Namespace backup and restore
- Filterable property management
- Cache warming
- Recall evaluation
- And more...

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Build for production
npm run build

# Run built version
npm start
```
