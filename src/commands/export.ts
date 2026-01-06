import { Command } from 'commander';
import http from 'http';
import chalk from 'chalk';
import { debugLog } from '../utils/debug.js';
import {
  fetchNamespacesWithMetadata,
  getEncryptionType,
  getIndexStatus,
  getUnindexedBytes,
  type NamespaceWithMetadata
} from '../utils/metadata-fetcher.js';
import {
  formatPrometheusMetrics,
  createSimpleGauge,
  getCurrentTimestamp,
  type PrometheusMetric
} from '../utils/metrics.js';

interface ExportOptions {
  port: string;
  region?: string;
  allRegions?: boolean;
  interval: string;
  timeout: string;
  includeRecall?: boolean;
  recallInterval: string;
}

interface MetricsCache {
  data: string;
  lastUpdate: Date;
  error?: string;
}

interface RecallCache {
  data: Map<string, { recall: any; region?: string }>;
  lastUpdate: Date;
}

let metricsCache: MetricsCache = {
  data: '# Waiting for first scrape...\n',
  lastUpdate: new Date()
};

let recallCache: RecallCache = {
  data: new Map(),
  lastUpdate: new Date(0) // Epoch to trigger immediate first fetch
};

let lastScrapeSuccess = true;
let lastScrapeDuration = 0;

export function createExportCommand(): Command {
  const exportCmd = new Command('export')
    .alias('metrics')
    .description('Run Prometheus exporter for Turbopuffer namespace metrics')
    .option('-p, --port <number>', 'HTTP server port', '9876')
    .option('-r, --region <region>', 'Query specific region (default: TURBOPUFFER_REGION env)')
    .option('-A, --all-regions', 'Query all Turbopuffer regions', false)
    .option('-i, --interval <seconds>', 'Metric refresh interval in seconds', '60')
    .option('-t, --timeout <seconds>', 'API request timeout per region in seconds', '30')
    .option('--include-recall', 'Include recall estimation metrics (runs queries, incurs costs)', false)
    .option('--recall-interval <seconds>', 'Recall estimation refresh interval in seconds', '3600')
    .action(async (options: ExportOptions) => {
      const port = parseInt(options.port, 10);
      const interval = parseInt(options.interval, 10);
      const timeout = parseInt(options.timeout, 10);
      const recallInterval = parseInt(options.recallInterval, 10);

      // Validate options
      if (isNaN(port) || port < 1 || port > 65535) {
        console.error(chalk.red('Error: Port must be a number between 1 and 65535'));
        process.exit(1);
      }

      if (isNaN(interval) || interval < 1) {
        console.error(chalk.red('Error: Interval must be a positive number'));
        process.exit(1);
      }

      if (isNaN(timeout) || timeout < 1) {
        console.error(chalk.red('Error: Timeout must be a positive number'));
        process.exit(1);
      }

      if (isNaN(recallInterval) || recallInterval < 1) {
        console.error(chalk.red('Error: Recall interval must be a positive number'));
        process.exit(1);
      }

      // Validate mutual exclusivity of --all-regions and --region
      if (options.allRegions && options.region) {
        console.error(chalk.red('Error: Cannot use both --all-regions and --region flags together'));
        console.log(chalk.gray('Please use either --all-regions to query all regions, or --region to specify a single region'));
        process.exit(1);
      }

      try {
        await startHttpServer({
          port,
          region: options.region,
          allRegions: options.allRegions || false,
          interval,
          timeout,
          includeRecall: options.includeRecall || false,
          recallInterval
        });
      } catch (error) {
        console.error(chalk.red('Error starting exporter:'), error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  return exportCmd;
}

interface ServerOptions {
  port: number;
  region?: string;
  allRegions: boolean;
  interval: number;
  timeout: number;
  includeRecall: boolean;
  recallInterval: number;
}

async function startHttpServer(options: ServerOptions): Promise<void> {
  // Perform initial metrics fetch
  console.log(chalk.gray('Performing initial metrics fetch...'));
  await refreshMetrics(options);

  // Start background refresh
  const refreshInterval = setInterval(async () => {
    await refreshMetrics(options);
  }, options.interval * 1000);

  // Create HTTP server
  const server = http.createServer(async (req, res) => {
    const url = req.url || '/';

    if (url === '/metrics') {
      res.writeHead(200, {
        'Content-Type': 'text/plain; charset=utf-8'
      });
      res.end(metricsCache.data);
    } else if (url === '/health') {
      const health = {
        status: 'ok',
        lastUpdate: metricsCache.lastUpdate.toISOString(),
        error: metricsCache.error || null
      };
      res.writeHead(200, {
        'Content-Type': 'application/json'
      });
      res.end(JSON.stringify(health, null, 2));
    } else if (url === '/') {
      const html = `<!DOCTYPE html>
<html>
<head>
  <title>Turbopuffer Prometheus Exporter</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
    h1 { color: #333; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .info { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }
    code { background: #eee; padding: 2px 6px; border-radius: 3px; }
  </style>
</head>
<body>
  <h1>Turbopuffer Prometheus Exporter</h1>
  <div class="info">
    <p><strong>Status:</strong> Running</p>
    <p><strong>Last Update:</strong> ${metricsCache.lastUpdate.toISOString()}</p>
    <p><strong>Refresh Interval:</strong> ${options.interval}s</p>
    <p><strong>Region Mode:</strong> ${options.allRegions ? 'All regions' : options.region || 'Default'}</p>
    <p><strong>Recall Metrics:</strong> ${options.includeRecall ? `enabled (refresh: ${options.recallInterval}s)` : 'disabled'}</p>
  </div>
  <h2>Endpoints</h2>
  <ul>
    <li><a href="/metrics">/metrics</a> - Prometheus metrics endpoint</li>
    <li><a href="/health">/health</a> - Health check endpoint</li>
  </ul>
  <h2>Example Prometheus Configuration</h2>
  <pre><code>scrape_configs:
  - job_name: 'turbopuffer'
    scrape_interval: ${options.interval}s
    static_configs:
      - targets: ['localhost:${options.port}']</code></pre>
</body>
</html>`;
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8'
      });
      res.end(html);
    } else {
      res.writeHead(404, {
        'Content-Type': 'text/plain'
      });
      res.end('Not Found');
    }
  });

  // Graceful shutdown handler
  const shutdown = (signal: string) => {
    console.log(chalk.yellow(`\nReceived ${signal}, shutting down gracefully...`));
    clearInterval(refreshInterval);
    server.close(() => {
      console.log(chalk.gray('HTTP server closed'));
      process.exit(0);
    });

    // Force exit after 5 seconds if server hasn't closed
    setTimeout(() => {
      console.error(chalk.red('Forced shutdown after timeout'));
      process.exit(1);
    }, 5000);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Start server
  server.listen(options.port, () => {
    console.log(chalk.green(`✓ Turbopuffer Prometheus exporter running`));
    console.log(chalk.gray(`  Port:           ${options.port}`));
    console.log(chalk.gray(`  Refresh:        ${options.interval}s`));
    console.log(chalk.gray(`  Region mode:    ${options.allRegions ? 'All regions' : options.region || 'Default'}`));
    if (options.includeRecall) {
      console.log(chalk.yellow(`  Recall:         enabled (refresh: ${options.recallInterval}s)`));
      console.log(chalk.gray(`                  Note: Recall estimation runs queries and incurs costs`));
    } else {
      console.log(chalk.gray(`  Recall:         disabled (use --include-recall to enable)`));
    }
    console.log(chalk.gray(`\n  Endpoints:`));
    console.log(chalk.gray(`    http://localhost:${options.port}/metrics`));
    console.log(chalk.gray(`    http://localhost:${options.port}/health`));
    console.log(chalk.gray(`    http://localhost:${options.port}/`));
    console.log(chalk.gray(`\n  Press Ctrl+C to stop\n`));
  });

  // Handle server errors
  server.on('error', (error: NodeJS.ErrnoException) => {
    if (error.code === 'EADDRINUSE') {
      console.error(chalk.red(`Error: Port ${options.port} is already in use`));
      console.log(chalk.gray('Please choose a different port with --port <number>'));
    } else {
      console.error(chalk.red('Server error:'), error.message);
    }
    process.exit(1);
  });
}

async function refreshMetrics(options: ServerOptions): Promise<void> {
  const startTime = Date.now();

  try {
    debugLog('Starting metrics refresh', {
      allRegions: options.allRegions,
      region: options.region,
      includeRecall: options.includeRecall
    });

    // Determine if we should refresh recall data
    const timeSinceLastRecall = Date.now() - recallCache.lastUpdate.getTime();
    const shouldRefreshRecall = options.includeRecall &&
      (timeSinceLastRecall >= options.recallInterval * 1000);

    if (shouldRefreshRecall) {
      debugLog('Refreshing recall data', {
        timeSinceLastRecall: timeSinceLastRecall / 1000,
        recallInterval: options.recallInterval
      });
    }

    // Fetch namespaces with metadata (recall fetched separately on its own schedule)
    const namespaces = await fetchNamespacesWithMetadata({
      allRegions: options.allRegions,
      region: options.region,
      includeRecall: shouldRefreshRecall
    });

    debugLog('Fetched namespaces', {
      count: namespaces.length,
      refreshedRecall: shouldRefreshRecall
    });

    // Update recall cache if we refreshed it
    if (shouldRefreshRecall) {
      recallCache.data.clear();
      for (const ns of namespaces) {
        if (ns.recall) {
          recallCache.data.set(ns.namespace.id, {
            recall: ns.recall,
            region: ns.region
          });
        }
      }
      recallCache.lastUpdate = new Date();
      debugLog('Updated recall cache', {
        cachedNamespaces: recallCache.data.size
      });
    } else if (options.includeRecall) {
      // Merge cached recall data into namespaces
      for (const ns of namespaces) {
        const cached = recallCache.data.get(ns.namespace.id);
        if (cached && cached.region === ns.region) {
          ns.recall = cached.recall;
        }
      }
      debugLog('Merged cached recall data', {
        cachedNamespaces: recallCache.data.size
      });
    }

    // Generate Prometheus metrics
    const metrics = generatePrometheusMetrics(namespaces);

    // Add exporter self-monitoring metrics
    const scrapeDuration = (Date.now() - startTime) / 1000;
    lastScrapeDuration = scrapeDuration;
    lastScrapeSuccess = true;

    metrics.push(
      createSimpleGauge(
        'turbopuffer_exporter_scrape_duration_seconds',
        'Time taken to fetch metrics from Turbopuffer API',
        scrapeDuration
      )
    );

    metrics.push(
      createSimpleGauge(
        'turbopuffer_exporter_last_scrape_timestamp_seconds',
        'Unix timestamp of last successful scrape',
        getCurrentTimestamp()
      )
    );

    // Format all metrics
    const metricsText = formatPrometheusMetrics(metrics);

    // Update cache
    metricsCache = {
      data: metricsText,
      lastUpdate: new Date(),
      error: undefined
    };

    debugLog('Metrics refresh completed', {
      duration: scrapeDuration,
      namespaceCount: namespaces.length
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(chalk.red('Error refreshing metrics:'), errorMessage);
    debugLog('Metrics refresh failed', error);

    lastScrapeSuccess = false;

    // Keep serving old metrics with error comment
    const errorComment = `# Error refreshing metrics: ${errorMessage}\n# Last successful update: ${metricsCache.lastUpdate.toISOString()}\n\n`;
    metricsCache = {
      ...metricsCache,
      error: errorMessage,
      data: errorComment + metricsCache.data
    };
  }
}

function generatePrometheusMetrics(namespaces: NamespaceWithMetadata[]): PrometheusMetric[] {
  const metrics: PrometheusMetric[] = [];

  // Initialize metrics
  const rowsMetric: PrometheusMetric = {
    name: 'turbopuffer_namespace_rows',
    type: 'gauge',
    help: 'Approximate number of rows in namespace',
    values: []
  };

  const logicalBytesMetric: PrometheusMetric = {
    name: 'turbopuffer_namespace_logical_bytes',
    type: 'gauge',
    help: 'Approximate logical storage size in bytes',
    values: []
  };

  const unindexedBytesMetric: PrometheusMetric = {
    name: 'turbopuffer_namespace_unindexed_bytes',
    type: 'gauge',
    help: 'Number of unindexed bytes (0 when index is up-to-date)',
    values: []
  };

  const recallMetric: PrometheusMetric = {
    name: 'turbopuffer_namespace_recall',
    type: 'gauge',
    help: 'Average vector recall estimation (0-1 scale)',
    values: []
  };

  const infoMetric: PrometheusMetric = {
    name: 'turbopuffer_namespace_info',
    type: 'gauge',
    help: 'Namespace information with labels',
    values: []
  };

  // Populate metrics from namespace data
  for (const ns of namespaces) {
    if (!ns.metadata) {
      continue; // Skip namespaces without metadata
    }

    const labels = {
      namespace: ns.namespace.id,
      region: ns.region || 'unknown',
      encryption: getEncryptionType(ns.metadata),
      index_status: getIndexStatus(ns.metadata)
    };

    rowsMetric.values.push({
      labels,
      value: ns.metadata.approx_row_count
    });

    logicalBytesMetric.values.push({
      labels,
      value: ns.metadata.approx_logical_bytes
    });

    unindexedBytesMetric.values.push({
      labels,
      value: getUnindexedBytes(ns.metadata)
    });

    // Add recall metric if recall data is available
    if (ns.recall) {
      recallMetric.values.push({
        labels,
        value: ns.recall.avg_recall
      });
    }

    infoMetric.values.push({
      labels: {
        ...labels,
        updated_at: ns.metadata.updated_at
      },
      value: 1
    });
  }

  // Only add metrics that have values
  if (rowsMetric.values.length > 0) {
    metrics.push(rowsMetric);
  }
  if (logicalBytesMetric.values.length > 0) {
    metrics.push(logicalBytesMetric);
  }
  if (unindexedBytesMetric.values.length > 0) {
    metrics.push(unindexedBytesMetric);
  }
  if (recallMetric.values.length > 0) {
    metrics.push(recallMetric);
  }
  if (infoMetric.values.length > 0) {
    metrics.push(infoMetric);
  }

  return metrics;
}
