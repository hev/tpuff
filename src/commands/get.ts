import { Command } from 'commander';
import { getTurbopufferClient } from '../client.js';
import chalk from 'chalk';

export function createGetCommand(): Command {
  const get = new Command('get')
    .description('Get a document by ID from a namespace')
    .argument('<id>', 'Document ID to retrieve')
    .requiredOption('-n, --namespace <name>', 'Namespace to query')
    .option('-r, --region <region>', 'Override the region (e.g., aws-us-east-1, gcp-us-central1)')
    .action(async (id: string, options: { namespace: string; region?: string }) => {
      const client = getTurbopufferClient(options.region);
      const namespace = options.namespace;

      try {
        console.log(chalk.bold(`\nQuerying document with ID: ${id} from namespace: ${namespace}\n`));

        // Get namespace reference
        const ns = client.namespace(namespace);

        // Query with id filter
        const result = await ns.query({
          filters: ['id', 'Eq', id],
          top_k: 1,
          include_attributes: true
        });

        // Check if document was found
        if (!result.rows || result.rows.length === 0) {
          console.log(chalk.yellow('Document not found'));
          process.exit(1);
        }

        // Get the document
        const doc = result.rows[0];

        // Display document
        console.log(chalk.cyan('Document:'));
        console.log(JSON.stringify(doc, null, 2));

        console.log(chalk.gray(`\nQuery took ${result.performance.query_execution_ms.toFixed(2)}ms`));
      } catch (error) {
        console.error('Error:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  return get;
}
