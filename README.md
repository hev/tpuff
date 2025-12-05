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

### export (alias: metrics)

Run a Prometheus exporter for namespace metrics:
```bash
tpuff export
```
See the [Prometheus Exporter](#prometheus-exporter) section below for complete documentation.

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

## Prometheus Exporter

The CLI includes a built-in Prometheus exporter that exports namespace metrics for monitoring and alerting.

### export (alias: metrics)

Run a Prometheus exporter that exposes Turbopuffer namespace metrics:

```bash
tpuff export
```

This starts an HTTP server that Prometheus can scrape for metrics about your namespaces.

**Options:**
- `-p, --port <number>`: HTTP server port (default: 9876)
- `-r, --region <region>`: Query specific region (default: TURBOPUFFER_REGION env)
- `-A, --all-regions`: Query all Turbopuffer regions
- `-i, --interval <seconds>`: Metric refresh interval (default: 60)
- `-t, --timeout <seconds>`: API request timeout per region (default: 30)

**Examples:**

```bash
# Run exporter with default settings
tpuff export

# Custom port and faster refresh
tpuff export --port 8080 --interval 30

# Monitor all regions
tpuff export --all-regions

# Specific region with custom timeout
tpuff export --region aws-eu-west-1 --timeout 60
```

### Exposed Metrics

The exporter provides the following metrics:

- `turbopuffer_namespace_rows` - Approximate number of rows in namespace
- `turbopuffer_namespace_logical_bytes` - Approximate logical storage size in bytes
- `turbopuffer_namespace_unindexed_bytes` - Number of unindexed bytes (0 when index is up-to-date)
- `turbopuffer_namespace_info` - Namespace information with labels
- `turbopuffer_exporter_scrape_duration_seconds` - Time taken to fetch metrics from API
- `turbopuffer_exporter_last_scrape_timestamp_seconds` - Unix timestamp of last successful scrape

All namespace metrics include labels:
- `namespace` - Namespace ID
- `region` - Turbopuffer region
- `encryption` - Encryption type (sse/cmk)
- `index_status` - Index status (up-to-date/indexing)

### Endpoints

Once running, the exporter exposes:

- `http://localhost:9876/metrics` - Prometheus metrics endpoint
- `http://localhost:9876/health` - Health check (JSON)
- `http://localhost:9876/` - Web UI with status information

### Prometheus Configuration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'turbopuffer'
    scrape_interval: 60s
    static_configs:
      - targets: ['localhost:9876']
```

### Docker Deployment

For production deployments, use the Docker image:

**Pull and run:**
```bash
docker pull hevmind/tpuff-exporter:latest
docker run -d \
  --name tpuff-exporter \
  -p 9876:9876 \
  -e TURBOPUFFER_API_KEY=your_api_key \
  hevmind/tpuff-exporter:latest
```

**With custom options:**
```bash
docker run -d \
  --name tpuff-exporter \
  -p 9876:9876 \
  -e TURBOPUFFER_API_KEY=your_api_key \
  hevmind/tpuff-exporter:latest \
  --interval 30 \
  --all-regions
```

**Docker Compose example:**
```yaml
version: '3.8'

services:
  tpuff-exporter:
    image: hevmind/tpuff-exporter:latest
    container_name: tpuff-exporter
    ports:
      - "9876:9876"
    environment:
      - TURBOPUFFER_API_KEY=${TURBOPUFFER_API_KEY}
    command: ["--interval", "30", "--all-regions"]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:9876/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

volumes:
  prometheus_data:
```

**Using npm scripts:**
```bash
# Build the exporter image locally
npm run docker:exporter:build

# Start the exporter container
TURBOPUFFER_API_KEY=your_key npm run docker:exporter:start

# View logs
npm run docker:exporter:logs

# Stop the container
npm run docker:exporter:stop
```

See [DOCKER.md](./DOCKER.md) for complete Docker documentation including a full monitoring stack with Grafana.

## Monitoring & Observability

### Grafana Dashboard

A comprehensive Grafana dashboard is included for visualizing Turbopuffer metrics collected by the Prometheus exporter.

**Features:**
- **17 monitoring panels** showing namespace health, storage trends, and index status
- **Real-time aggregate metrics** across all namespaces (total rows, storage, unindexed bytes)
- **2GB threshold alerts** with color-coded warnings (yellow at 2GB, red at 5GB)
- **Index health monitoring** showing percentage of up-to-date indexes (target: >95%)
- **Per-namespace breakdown** with sortable table and gradient gauge visualization
- **Multi-select variables** for filtering by region and namespace
- **Time series graphs** showing trends over time
- **Regional distribution** charts

**Quick Start:**

1. Start the complete monitoring stack:
```bash
# See DOCKER.md for the full docker-compose.yml
docker-compose up -d
```

2. Access Grafana:
```
http://localhost:3000
Default credentials: admin/admin (change on first login)
```

3. The "Turbopuffer Overview" dashboard will be automatically provisioned in the "Turbopuffer" folder.

**Dashboard Highlights:**

- **Namespaces Requiring Attention**: Shows count of namespaces with >2GB unindexed data
- **Index Health %**: Gauge showing percentage of namespaces with up-to-date indexes
- **Storage Growth Rate**: Real-time bytes-per-second growth across namespaces
- **Unindexed Bytes Over Time**: Time series with 2GB threshold line for early warning
- **Table View**: Sortable per-namespace details with color-coded unindexed bytes

**Manual Import:**

1. Open Grafana → Dashboards → Import
2. Upload `grafana/dashboards/turbopuffer-overview.json`
3. Select your Prometheus datasource
4. Click Import

For detailed documentation, configuration options, PromQL queries, troubleshooting, and alerting examples, see [grafana/README.md](./grafana/README.md).

### Observability Best Practices

**Recommended monitoring setup:**

1. **Exporter**: Run the tpuff exporter to collect namespace metrics
   - Use `--all-regions` to monitor all your Turbopuffer regions
   - Set `--interval 60` for 1-minute refresh (balance freshness vs API load)

2. **Prometheus**: Scrape the exporter every 60 seconds
   - Retention: 15+ days recommended for trend analysis
   - Consider recording rules for frequently-used aggregations

3. **Grafana**: Use the provided dashboard for visualization
   - Dashboard includes 2GB threshold visualization across all panels

4. **Alertmanager**: Configure alerts for proactive monitoring
   - **Pre-configured alert rules** are included in `prometheus/rules/turbopuffer.yml`
   - **2GB threshold alert**: Fires when namespace has >2GB unindexed data for 5+ minutes (warning)
   - **5GB critical alert**: Fires when namespace has >5GB unindexed data for 10+ minutes (critical)
   - **Index health alert**: Fires when <95% of namespaces have up-to-date indexes
   - **Exporter health alerts**: Monitor exporter uptime and performance
   - See `prometheus/README.md` for setup instructions and Slack/PagerDuty/email integration examples

5. **Regular Reviews**:
   - Monitor the "Namespaces Requiring Attention" panel daily
   - Track storage growth rate to plan capacity
   - Use the table view to identify namespaces needing optimization

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
