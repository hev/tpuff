# Turbopuffer Prometheus Exporter - Docker

A Prometheus exporter for Turbopuffer namespace metrics, packaged as a Docker container.

## Quick Start

Pull and run the exporter:

```bash
docker pull hevmind/tpuff-exporter:latest
docker run -d \
  --name tpuff-exporter \
  -p 9876:9876 \
  -e TURBOPUFFER_API_KEY=your_api_key_here \
  hevmind/tpuff-exporter:latest
```

## Configuration

### Environment Variables

- `TURBOPUFFER_API_KEY` (required): Your Turbopuffer API key

### Command Line Options

You can override default options by passing arguments:

```bash
docker run -d \
  --name tpuff-exporter \
  -p 9876:9876 \
  -e TURBOPUFFER_API_KEY=your_api_key \
  hevmind/tpuff-exporter:latest \
  --port 9876 \
  --interval 30 \
  --all-regions
```

Available options:
- `--port <number>`: HTTP server port (default: 9876)
- `--region <region>`: Query specific region (default: TURBOPUFFER_REGION env)
- `--all-regions`: Query all Turbopuffer regions
- `--interval <seconds>`: Metric refresh interval (default: 60)
- `--timeout <seconds>`: API request timeout per region (default: 30)

## Endpoints

Once running, the exporter exposes the following endpoints:

- `http://localhost:9876/metrics` - Prometheus metrics endpoint
- `http://localhost:9876/health` - Health check endpoint (JSON)
- `http://localhost:9876/` - Web UI with status information

## Prometheus Configuration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'turbopuffer'
    scrape_interval: 60s
    static_configs:
      - targets: ['tpuff-exporter:9876']
```

## Metrics Exported

- `turbopuffer_namespace_rows` - Approximate number of rows in namespace
- `turbopuffer_namespace_logical_bytes` - Approximate logical storage size in bytes
- `turbopuffer_namespace_unindexed_bytes` - Number of unindexed bytes
- `turbopuffer_namespace_info` - Namespace information with labels
- `turbopuffer_exporter_scrape_duration_seconds` - Time taken to fetch metrics
- `turbopuffer_exporter_last_scrape_timestamp_seconds` - Unix timestamp of last scrape

All metrics include labels:
- `namespace` - Namespace ID
- `region` - Turbopuffer region
- `encryption` - Encryption type (sse/cmk)
- `index_status` - Index status (up-to-date/indexing)

## Docker Compose Example

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
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:9876/health', (res) => { process.exit(res.statusCode === 200 ? 0 : 1); }).on('error', () => process.exit(1));"]
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

## Health Checks

The health endpoint returns JSON:

```json
{
  "status": "ok",
  "lastUpdate": "2025-12-01T23:19:57.365Z",
  "error": null
}
```

## Building from Source

```bash
# Clone the repository
git clone https://github.com/hev/tpuff.git
cd tpuff

# Build the Docker image
docker build -f Dockerfile.exporter -t tpuff-exporter:latest .

# Run locally
docker run -d \
  --name tpuff-exporter \
  -p 9876:9876 \
  -e TURBOPUFFER_API_KEY=your_api_key \
  tpuff-exporter:latest
```

## Troubleshooting

### Check container logs

```bash
docker logs tpuff-exporter
```

### Check if the exporter is running

```bash
curl http://localhost:9876/health
```

### Verify metrics are being collected

```bash
curl http://localhost:9876/metrics
```

### Common Issues

1. **401 Unauthorized**: Check that `TURBOPUFFER_API_KEY` is set correctly
2. **Connection refused**: Ensure the container is running and port is mapped correctly
3. **Empty metrics**: Verify your API key has access to namespaces

## License

MIT
