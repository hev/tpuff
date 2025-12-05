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

## Grafana Dashboard

A pre-built Grafana dashboard is included in the `grafana/` directory providing:

- **17 monitoring panels** across 7 rows
- **Real-time metrics** for namespace count, rows, storage, and unindexed bytes
- **2GB threshold alerts** with visual indicators (yellow warning at 2GB, red critical at 5GB)
- **Index health monitoring** showing percentage of up-to-date indexes
- **Per-namespace breakdown** with sortable table and gradient gauge visualization
- **Regional distribution** charts showing namespace and storage distribution
- **Multi-select variables** for filtering by region and namespace

### Dashboard Features

**Key Metrics:**
- Total namespaces, rows, and storage across your infrastructure
- Namespaces requiring attention (>2GB unindexed data)
- Index health percentage (target: >95%)
- Storage growth rate (bytes per second)

**Visualization:**
- Time series graphs showing trends for rows, storage, and unindexed bytes
- Table view with color-coded unindexed bytes column
- Pie charts for regional and encryption distribution
- Collapsed troubleshooting row for exporter health metrics

**Usage:**
- Set variables to "All" (default) to see aggregate metrics across all namespaces
- Filter by specific region or namespace to drill down
- Sort the table by unindexed bytes to identify namespaces requiring attention

See `grafana/README.md` for detailed documentation on importing, configuring, and using the dashboard.

## Docker Compose Example

### Basic Setup (Exporter + Prometheus)

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

### Complete Monitoring Stack (Exporter + Prometheus + Grafana)

For a complete observability setup with the Turbopuffer dashboard:

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
    command: ["--interval", "60", "--all-regions"]
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
    depends_on:
      - tpuff-exporter

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin  # Change this in production!
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./grafana/provisioning/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml
      - ./grafana/provisioning/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

**Setup steps:**

1. Create a `.env` file with your API key:
```bash
echo "TURBOPUFFER_API_KEY=your_api_key_here" > .env
```

2. Create `prometheus.yml`:
```yaml
global:
  scrape_interval: 60s
  evaluation_interval: 60s

scrape_configs:
  - job_name: 'turbopuffer'
    scrape_interval: 60s
    static_configs:
      - targets: ['tpuff-exporter:9876']
```

3. Start the stack:
```bash
docker-compose up -d
```

4. Access services:
   - **Grafana**: http://localhost:3000 (admin/admin - change on first login)
   - **Prometheus**: http://localhost:9090
   - **Exporter**: http://localhost:9876

5. The Turbopuffer Overview dashboard will be automatically provisioned in Grafana under the "Turbopuffer" folder.

**Note**: The grafana service mounts the dashboard files from the `./grafana` directory in this repository. Make sure you have the grafana folder with dashboards and provisioning files in the same directory as your `docker-compose.yml`.

### Complete Monitoring Stack with Alerting

For production deployments with alerting on the 2GB unindexed bytes threshold:

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
    command: ["--interval", "60", "--all-regions"]
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
      - ./prometheus/rules:/etc/prometheus/rules
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped
    depends_on:
      - tpuff-exporter

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin  # Change this in production!
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./grafana/provisioning/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml
      - ./grafana/provisioning/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  alertmanager_data:
  grafana_data:
```

**Required configuration files:**

1. **prometheus.yml** (with alert rules):
```yaml
global:
  scrape_interval: 60s
  evaluation_interval: 60s

# Load alert rules
rule_files:
  - '/etc/prometheus/rules/*.yml'

# Configure Alertmanager
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'turbopuffer'
    scrape_interval: 60s
    static_configs:
      - targets: ['tpuff-exporter:9876']
```

2. **alertmanager.yml** (example email config):
```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@example.com'
  smtp_auth_username: 'alerts@example.com'
  smtp_auth_password: 'your-app-password'

route:
  group_by: ['alertname', 'namespace']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'turbopuffer-team'
  routes:
    - match:
        severity: critical
      receiver: 'turbopuffer-critical'
      repeat_interval: 1h

receivers:
  - name: 'turbopuffer-team'
    email_configs:
      - to: 'team@example.com'
        headers:
          Subject: '[Turbopuffer] {{ .GroupLabels.alertname }}'

  - name: 'turbopuffer-critical'
    email_configs:
      - to: 'oncall@example.com'
        headers:
          Subject: '[CRITICAL] [Turbopuffer] {{ .GroupLabels.alertname }}'
```

3. **Start the complete stack**:
```bash
docker-compose up -d
```

4. **Access services**:
   - **Grafana**: http://localhost:3000 (dashboard with 2GB threshold visualization)
   - **Prometheus**: http://localhost:9090 (metrics and alert rules)
   - **Alertmanager**: http://localhost:9093 (alert routing and silences)
   - **Exporter**: http://localhost:9876

**Alert rules** are automatically loaded from `prometheus/rules/turbopuffer.yml` and include:
- **Warning**: Namespace >2GB unindexed (fires after 5 minutes)
- **Critical**: Namespace >5GB unindexed (fires after 10 minutes)
- **Infrastructure alerts**: Low index health, multiple namespaces requiring attention
- **Exporter health**: Down, slow scrapes, stale metrics

See `prometheus/README.md` for complete alert documentation, customization options, and Slack/PagerDuty integration examples.

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
