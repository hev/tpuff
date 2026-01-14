# Turbopuffer CLI (tpuff)

A Python CLI for interacting with turbopuffer. This tool allows you to list and filter namespaces, browse namespace data, perform full-text search, and export metrics to Prometheus.

## Prerequisites

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) package manager (recommended)
- A turbopuffer API key

Set the following environment variables:
- `TURBOPUFFER_API_KEY`: Your turbopuffer API key
- `TURBOPUFFER_REGION`: Region to use (defaults to `aws-us-east-1`)

## Installation

### Using UV (recommended)

Install UV if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install tpuff as a global tool:
```bash
uv tool install tpuff
```

Or install from source:
```bash
git clone https://github.com/hev/tpuff
cd tpuff
uv sync
```

### Using pip

```bash
pip install tpuff
```

Then use the `tpuff` command directly:

```bash
tpuff [command] [options]
```

## Usage

### list (alias: ls)

List all namespaces with detailed metadata in a formatted table, or list documents in a specific namespace.

**List all namespaces:**
```bash
tpuff ls
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
tpuff list -n <namespace>
```
**List all namespaces across regions:**
```bash
tpuff ls -A
```

### search

Search for documents in a namespace using vector similarity or full-text search.

**Vector similarity search:**
```bash
tpuff search "your query text" -n my-namespace -m sentence-transformers/all-MiniLM-L6-v2
```

**Full-text search (BM25):**
```bash
tpuff search "your query text" -n my-namespace --fts content-field
```

**Filter search:**
```bash
tpuff search "your query text" -n my-namespace -f '["field", "Eq", "value"]'
```

**Options:**
- `-n, --namespace <name>`: Namespace to search in (required)
- `-m, --model <id>`: HuggingFace model ID for vector search
- `-k, --top-k <number>`: Number of results to return (default: 10)
- `-d, --distance-metric <metric>`: Distance metric (cosine_distance or euclidean_squared)
- `-f, --filters <filters>`: Additional filters in JSON format
- `--fts <field>`: Field name to use for full-text search (BM25)
- `-r, --region <region>`: Override the region

### delete

**Delete a namespace:**
```bash
tpuff delete -n my-namespace
```

**Delete a prefix of namespaces:**
```bash
tpuff delete --prefix my-namespace-
```

**Delete ALL namespaces (requires confirmation):**
```bash
tpuff delete --all
```

### edit

**Edit a document by ID using vim:**
```bash
tpuff edit <document-id> -n my-namespace
```
This will open the document in vim. Save and quit (`:wq`) to upsert changes, or quit without saving (`:q!`) to cancel.

## Development

```bash
# Clone and setup
git clone https://github.com/hev/tpuff
cd tpuff
uv sync

# Run in development
uv run tpuff --help

# Run tests
uv run pytest

# Build package
uv build
```

## Monitoring & Observability

The CLI includes a built-in Prometheus exporter and Grafana dashboard for monitoring your namespaces.

![image](./grafana.png)

See [monitoring.md](./monitoring.md) for detailed instructions on:
- Running the Prometheus exporter
- Configuring Grafana dashboards
- Observability best practices


## Roadmap
- Cursor for namespace pagination
- Cache status and warming option
- Third party embedding generation (e.g. OpenAI, Cohere, etc.)
- Namespace backup and restore (to s3 or file)
- Filterable property management
- Feedback welcome (file an issue)
