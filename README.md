# Turbopuffer CLI (tpuff)

A TypeScript CLI for interacting with turbopuffer vector database. This tool allows you to list and filter namespaces, browse namespace data, perform full-text search, and execute admin functions.

## Prerequisites

- Node.js 20+
- A turbopuffer API key
- Docker (optional, required for Python-only embedding models)

Set the following environment variables:
- `TURBOPUFFER_API_KEY`: Your turbopuffer API key
- `TURBOPUFFER_REGION`: Region to use (defaults to `aws-us-east-1`)

## Installation

Install globally via npm:

```bash
npm install -g tpuff-cli
```

Then use the `tpuff` command directly:

```bash
tpuff [command] [options]
```

### Development Installation

If you want to contribute or run from source:

```bash
git clone https://github.com/hev/tpuff.git
cd tpuff
npm install
npm run build
npm link
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
tpuff list -n <namespace>
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

**Full-text search (BM25):**
```bash
tpuff search "your query text" -n my-namespace --fts content
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

Delete a namespace:
```bash
tpuff delete -n my-namespace
```

Delete ALL namespaces (requires confirmation):
```bash
tpuff delete --all
```

### edit

Edit a document by ID using vim:
```bash
tpuff edit <document-id> -n my-namespace
```
This will open the document in vim. Save and quit (`:wq`) to upsert changes, or quit without saving (`:q!`) to cancel.

## Docker Support for Python Embedding Models

The CLI supports Python-only embedding models (like `sentence-transformers/*`, `intfloat/*`, etc.) through an automatic Docker integration.

### How it works

1. When you use a Python-only model, the CLI automatically:
   - Checks if Docker is available
   - Pulls the embedding service container from Docker Hub (first time only)
   - Starts the container if not running
   - Generates embeddings via the container API

2. The container stays running between searches for better performance

3. The pre-built image is available at `hevmind/tpuff-embeddings:0.1.0` (also tagged as `latest`)

4. Supported Python model prefixes:
   - `sentence-transformers/`
   - `intfloat/`
   - `BAAI/`
   - `thenlper/`

### Manual Docker Management

**Pull the container (optional, happens automatically):**
```bash
docker pull hevmind/tpuff-embeddings:0.1.0
```

**Start the container:**
```bash
npm run docker:start
```

**Stop the container:**
```bash
npm run docker:stop
```

**View container logs:**
```bash
npm run docker:logs
```

**Access container shell:**
```bash
npm run docker:shell
```

### Troubleshooting

**Docker not available:**
```
Error: Docker is not available. Please install Docker to use Python-only embedding models.
Visit: https://docs.docker.com/get-docker/
```
→ Install Docker Desktop for your platform

**Docker daemon not running:**
```
Error: Docker daemon is not running. Please start Docker and try again.
```
→ Start Docker Desktop

**Container pull takes too long:**
First pull can take a few minutes as it downloads the image (~2GB). Subsequent starts are instant since the image is cached locally.

## Future Features

See [claude.md](./claude.md) for planned features including:
- Namespace backup and restore
- Filterable property management
- Cache warming
- Recall evaluation
- Feedback welcome (file an issue)

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
