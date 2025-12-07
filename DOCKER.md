# Turbopuffer Docker Support

This guide covers Docker support for both Python embedding models and the Prometheus exporter.

## Python Embedding Models

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

See [monitoring.md](./monitoring.md) for details on running the Prometheus exporter and configuring the monitoring stack.

