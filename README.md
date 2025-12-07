# Turbopuffer CLI (tpuff)

A TypeScript CLI for interacting with turbopuffer. This tool allows you to list and filter namespaces, browse namespace data, perform full-text search, and export metrics to Prometheus.

## Prerequisites

- Node.js 20+
- A turbopuffer API key
- Docker (optional, required for Python-only embedding models and/or exporter)

Set the following environment variables:
- `TURBOPUFFER_API_KEY`: Your turbopuffer API key
- `TURBOPUFFER_REGION`: Region to use (defaults to `aws-us-east-1`)

## Installation

Install globally via npm or bun:

```bash
npm install -g tpuff-cli
```

or 

```bash
bun add -g tpuff-cli
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
Xenova models allow for local embedding generation in typescript. 

```bash
tpuff search "your query text" -n my-namespace -m Xenova/all-MiniLM-L6-v2
```

**Using Python-only models (automatic Docker support):**
```bash
tpuff search "your query text" -n my-namespace -m sentence-transformers/all-MiniLM-L6-v2
```

The CLI automatically detects Python-only models and uses Docker to run a container to do embeddings On first use, it will pull the Docker image and start the container automatically.

See [DOCKER.md](./DOCKER.md) for detailed documentation on how it works, manual management, and troubleshooting.

**Full-text search (BM25):**
```bash
tpuff search "your query text" -n my-namespace --fts content-field
```

**Filter search:**
```bash
tpuff search "your query text" -n my-namespace -f '{"field": "value"}'
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


## Monitoring & Observability

The CLI includes a built-in Prometheus exporter and Grafana dashboard for monitoring your namespaces.

![image](./grafana.png)

See [monitoring.md](./monitoring.md) for detailed instructions on:
- Running the Prometheus exporter
- Configuring Grafana dashboards
- Observability best practices


## Roadmap
- Recall evaluation metrics
- Cursor for namespace pagination
- Cache status and warming option
- Namespace backup and restore (to s3 or file)
- Filterable property management
- Feedback welcome (file an issue)

