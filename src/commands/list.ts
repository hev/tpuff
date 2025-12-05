import { Command } from 'commander';
import { getTurbopufferClient } from '../client.js';
import chalk from 'chalk';
import Table from 'cli-table3';
import { debugLog } from '../utils/debug.js';
import { fetchNamespacesWithMetadata } from '../utils/metadata-fetcher.js';

export function createListCommand(): Command {
  const list = new Command('list')
    .alias('ls')
    .description('List namespaces or documents in a namespace')
    .option('-n, --namespace <name>', 'Namespace to list documents from')
    .option('-k, --top-k <number>', 'Number of documents to return', '10')
    .option('-r, --region <region>', 'Override the region (e.g., aws-us-east-1, gcp-us-central1)')
    .option('-A, --all', 'Query all regions')
    .action(async (options?: { namespace?: string; topK: string; region?: string; all?: boolean }) => {
      const namespace = options?.namespace;
      const isAllRegions = options?.all || false;

      // Validate that --all and --region are not used together
      if (isAllRegions && options?.region) {
        console.error(chalk.red('Error: Cannot use both --all and --region flags together'));
        console.log(chalk.gray('Please use either --all to query all regions, or --region to specify a single region'));
        process.exit(1);
      }

      const client = isAllRegions ? null : getTurbopufferClient(options?.region);

      try {
        if (namespace) {
          // List documents in namespace
          if (isAllRegions) {
            console.error(chalk.red('Error: --all flag is not supported when querying a specific namespace'));
            console.log(chalk.gray('Please specify a region with -r <region> to query documents in a namespace'));
            process.exit(1);
          }

          if (!client) {
            console.error('Error: Client not initialized');
            process.exit(1);
          }

          const topK = parseInt(options?.topK || '10', 10);

          console.log(chalk.bold(`\nQuerying namespace: ${namespace} (top ${topK} results)\n`));

          // Get namespace metadata to extract schema
          const ns = client.namespace(namespace);
          const metadata = await ns.metadata();

          // Extract vector info from schema
          const vectorInfo = extractVectorInfo(metadata.schema);

          if (!vectorInfo) {
            console.error('Error: No vector attribute found in namespace schema');
            process.exit(1);
          }

          console.log(chalk.gray(`Using ${vectorInfo.dimensions}-dimensional zero vector for query\n`));

          // Create zero vector
          const zeroVector = new Array(vectorInfo.dimensions).fill(0);

          const queryParams = {
            rank_by: [vectorInfo.attributeName, 'ANN', zeroVector] as any,
            top_k: topK,
            exclude_attributes: [vectorInfo.attributeName]
          };

          // Debug: Log query parameters
          debugLog('Query Parameters', queryParams);

          // Query the namespace
          const result = await ns.query(queryParams);

          // Debug: Log API response
          debugLog('Query Response', result);

          if (!result.rows || result.rows.length === 0) {
            console.log('No documents found in namespace');
            return;
          }

          console.log(chalk.bold(`Found ${result.rows.length} document(s):\n`));

          // Create table for results
          const rows = result.rows;

          const headers = ['ID', 'Contents'];
          const table = new Table({
            head: headers.map(h => chalk.cyan(h)),
            style: {
              head: [],
              border: ['grey']
            }
          });

          // Add rows to table
          rows.forEach(row => {
            // Collect all attributes except system fields
            const contents: { [key: string]: any } = {};
            Object.keys(row).forEach(key => {
              // Exclude id, vector, $dist, and attributes from display
              if (key !== 'id' && key !== 'vector' && key !== '$dist' && key !== 'attributes') {
                contents[key] = (row as any)[key];
              }
            });

            // Stringify and truncate contents
            const contentsStr = JSON.stringify(contents);
            const maxLength = 80;
            const displayContents = contentsStr.length > maxLength
              ? contentsStr.substring(0, maxLength) + '...'
              : contentsStr;

            const rowData: any[] = [
              row.id,
              displayContents
            ];

            table.push(rowData);
          });

          console.log(table.toString());
          console.log(chalk.gray(`\nQuery took ${result.performance.query_execution_ms.toFixed(2)}ms`));
        } else {
          // List all namespaces using the shared metadata fetcher
          const namespacesWithMetadata = await fetchNamespacesWithMetadata({
            allRegions: isAllRegions,
            region: options?.region
          });

          if (namespacesWithMetadata.length === 0) {
            console.log('No namespaces found');
            return;
          }

          console.log(chalk.bold(`\nFound ${namespacesWithMetadata.length} namespace(s):\n`));

          namespacesWithMetadata.sort((a, b) => {
            // Handle cases where metadata might be null
            if (!a.metadata && !b.metadata) return 0;
            if (!a.metadata) return 1; // Put nulls at the end
            if (!b.metadata) return -1;

            // Sort by updated_at in descending order (most recent first)
            const dateA = new Date(a.metadata.updated_at).getTime();
            const dateB = new Date(b.metadata.updated_at).getTime();
            return dateB - dateA;
          });

          // Create table with conditional region column
          const headers = [
            chalk.cyan('Namespace'),
            ...(isAllRegions ? [chalk.cyan('Region')] : []),
            chalk.cyan('Rows'),
            chalk.cyan('Logical Bytes'),
            chalk.cyan('Index Status'),
            chalk.cyan('Unindexed Bytes'),
            chalk.cyan('Updated')
          ];

          const table = new Table({
            head: headers,
            style: {
              head: [],
              border: ['grey']
            }
          });

          // Add rows to table
          namespacesWithMetadata.forEach(({ namespace: ns, metadata, region }) => {
            if (metadata) {
              const indexInfo = extractIndexInfo(metadata.index);
              const indexStatus = indexInfo.status === 'up-to-date'
                ? chalk.green('up-to-date')
                : chalk.red('updating');
              const unindexedBytes = indexInfo.unindexedBytes > 0
                ? chalk.red(formatBytes(indexInfo.unindexedBytes))
                : formatBytes(0);

              const row = [
                chalk.bold(ns.id),
                ...(isAllRegions && region ? [chalk.gray(region)] : []),
                metadata.approx_row_count.toLocaleString(),
                formatBytes(metadata.approx_logical_bytes),
                indexStatus,
                unindexedBytes,
                formatUpdatedAt(metadata.updated_at)
              ];

              table.push(row);
            } else {
              const row = [
                chalk.bold(ns.id),
                ...(isAllRegions && region ? [chalk.gray(region)] : []),
                chalk.gray('N/A'),
                chalk.gray('N/A'),
                chalk.gray('N/A'),
                chalk.gray('N/A'),
                chalk.gray('N/A')
              ];

              table.push(row);
            }
          });

          console.log(table.toString());
        }
      } catch (error) {
        console.error('Error:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  return list;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Formats a timestamp smartly: time if today, date otherwise
 * @param timestamp ISO timestamp string
 * @returns Formatted string
 */
function formatUpdatedAt(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();

  // Check if the date is today
  const isToday = date.getDate() === now.getDate() &&
                  date.getMonth() === now.getMonth() &&
                  date.getFullYear() === now.getFullYear();

  if (isToday) {
    // Show time only
    return date.toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  } else {
    // Show date only
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  }
}

/**
 * Extracts vector attribute name and dimensions from namespace schema
 * @param schema The namespace schema
 * @returns Object with attribute name and dimensions, or null if no vector found
 */
function extractVectorInfo(schema: { [key: string]: any }): { attributeName: string; dimensions: number } | null {
  for (const [attrName, attrConfig] of Object.entries(schema)) {
    const typeStr = typeof attrConfig === 'string' ? attrConfig : attrConfig?.type;

    if (typeStr && typeof typeStr === 'string') {
      // Match patterns like [384]f32, [1536]f16, etc.
      const match = typeStr.match(/\[(\d+)\]f(?:16|32)/);
      if (match) {
        return {
          attributeName: attrName,
          dimensions: parseInt(match[1], 10)
        };
      }
    }
  }

  return null;
}

/**
 * Extracts index status and unindexed bytes from namespace metadata
 * @param index The index metadata from namespace
 * @returns Object with status and unindexedBytes
 */
function extractIndexInfo(index: any): { status: string; unindexedBytes: number } {
  if (index.status === 'up-to-date') {
    return {
      status: 'up-to-date',
      unindexedBytes: 0
    };
  } else {
    return {
      status: 'updating',
      unindexedBytes: index.unindexed_bytes
    };
  }
}
