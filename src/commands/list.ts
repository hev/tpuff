import { Command } from 'commander';
import { getTurbopufferClient } from '../client';
import chalk from 'chalk';
import Table from 'cli-table3';

export function createListCommand(): Command {
  const list = new Command('list')
    .alias('ls')
    .description('List namespaces or documents in a namespace')
    .option('-n, --namespace <name>', 'Namespace to list documents from')
    .option('-k, --top-k <number>', 'Number of documents to return', '10')
    .action(async (options?: { namespace?: string; topK: string }) => {
      const namespace = options?.namespace;
      const client = getTurbopufferClient();

      try {
        if (namespace) {
          // List documents in namespace
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

          // Query the namespace
          const result = await ns.query({
            rank_by: [vectorInfo.attributeName, 'ANN', zeroVector],
            top_k: topK,
            include_attributes: true
          });

          if (!result.rows || result.rows.length === 0) {
            console.log('No documents found in namespace');
            return;
          }

          console.log(chalk.bold(`Found ${result.rows.length} document(s):\n`));

          // Create table for results
          const rows = result.rows;

          const headers = ['ID', 'Contents', 'Distance'];
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
              displayContents,
              row.$dist !== undefined ? row.$dist.toFixed(4) : chalk.gray('N/A')
            ];

            table.push(rowData);
          });

          console.log(table.toString());
          console.log(chalk.gray(`\nQuery took ${result.performance.query_execution_ms.toFixed(2)}ms`));
        } else {
          // List all namespaces
          const page = await client.namespaces();
          const namespaces = page.namespaces;

          if (namespaces.length === 0) {
            console.log('No namespaces found');
            return;
          }

          console.log(chalk.bold(`\nFound ${namespaces.length} namespace(s):\n`));

          // Fetch metadata for each namespace
          const metadataPromises = namespaces.map(ns =>
            client.namespace(ns.id).metadata().catch(() => null)
          );
          const metadataList = await Promise.all(metadataPromises);

          // Create table
          const table = new Table({
            head: [
              chalk.cyan('Namespace'),
              chalk.cyan('Rows'),
              chalk.cyan('Logical Bytes'),
              chalk.cyan('Index Status'),
              chalk.cyan('Created At'),
              chalk.cyan('Updated At')
            ],
            style: {
              head: [],
              border: ['grey']
            }
          });

          // Add rows to table
          namespaces.forEach((ns, index) => {
            const metadata = metadataList[index];

            // Truncate long namespace names
            const maxNameLength = 50;
            const truncatedName = ns.id.length > maxNameLength
              ? ns.id.substring(0, maxNameLength) + '...'
              : ns.id;

            if (metadata) {
              const indexStatus = metadata.index.status === 'up-to-date'
                ? chalk.green('up-to-date')
                : chalk.red(`updating (${formatBytes(metadata.index.status === 'updating' ? (metadata.index as any).unindexed_bytes : 0)} unindexed)`);

              table.push([
                chalk.bold(truncatedName),
                metadata.approx_row_count.toLocaleString(),
                formatBytes(metadata.approx_logical_bytes),
                indexStatus,
                new Date(metadata.created_at).toLocaleString(),
                new Date(metadata.updated_at).toLocaleString()
              ]);
            } else {
              table.push([
                chalk.bold(truncatedName),
                chalk.gray('N/A'),
                chalk.gray('N/A'),
                chalk.gray('N/A'),
                chalk.gray('N/A'),
                chalk.gray('N/A')
              ]);
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
