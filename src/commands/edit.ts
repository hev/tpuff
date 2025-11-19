import { Command } from 'commander';
import { getTurbopufferClient } from '../client.js';
import chalk from 'chalk';
import tmp from 'tmp';
import { spawn } from 'child_process';
import { writeFileSync, readFileSync } from 'fs';
import { debugLog } from '../utils/debug.js';

export function createEditCommand(): Command {
  const edit = new Command('edit')
    .description('Edit a document by ID from a namespace using vim')
    .argument('<id>', 'Document ID to edit')
    .requiredOption('-n, --namespace <name>', 'Namespace to query')
    .option('-r, --region <region>', 'Override the region (e.g., aws-us-east-1, gcp-us-central1)')
    .action(async (id: string, options: { namespace: string; region?: string }) => {
      const client = getTurbopufferClient(options.region);
      const namespace = options.namespace;

      try {
        console.log(chalk.bold(`\nFetching document with ID: ${id} from namespace: ${namespace}\n`));

        // Get namespace reference
        const ns = client.namespace(namespace);

        const queryParams = {
          filters: ['id', 'Eq', id] as any,
          top_k: 1
        };

        // Debug: Log query parameters
        debugLog('Query Parameters', queryParams);

        // Query with id filter
        const result = await ns.query(queryParams);

        // Debug: Log API response
        debugLog('Query Response', result);

        // Check if document was found
        if (!result.rows || result.rows.length === 0) {
          console.log(chalk.yellow('Document not found'));
          process.exit(1);
        }

        // Get the document and remove the vector field
        const doc = result.rows[0];
        const originalVector = doc.vector;

        // Create document for editing (without vector)
        const { vector, ...docWithoutVector } = doc;

        // Create a temporary file
        const tmpFile = tmp.fileSync({ postfix: '.json' });

        // Write the document to the temp file
        writeFileSync(tmpFile.name, JSON.stringify(docWithoutVector, null, 2));

        console.log(chalk.cyan('Opening vim editor...'));
        console.log(chalk.gray('Save and quit (:wq) to upsert changes, or quit without saving (:q!) to cancel.\n'));

        // Open vim
        const vim = spawn('vim', [tmpFile.name], {
          stdio: 'inherit'
        });

        await new Promise<void>((resolve, reject) => {
          vim.on('close', (code) => {
            if (code === 0) {
              resolve();
            } else {
              reject(new Error(`vim exited with code ${code}`));
            }
          });
        });

        // Read the edited content
        const editedContent = readFileSync(tmpFile.name, 'utf-8');

        // Clean up temp file
        tmpFile.removeCallback();

        // Parse the edited JSON
        let editedDoc;
        try {
          editedDoc = JSON.parse(editedContent);
        } catch (e) {
          console.error(chalk.red('\nError: Invalid JSON format'));
          process.exit(1);
        }

        // Restore the vector and ensure id is preserved
        editedDoc.vector = originalVector;
        editedDoc.id = id;

        // Upsert the document
        console.log(chalk.cyan('\nUpserting document...'));

        const upsertParams = {
          upsert_rows: [editedDoc],
          distance_metric: 'cosine_distance' as any
        };

        debugLog('Upsert Parameters', upsertParams);
        await ns.write(upsertParams);
        debugLog('Upsert Response', 'Success');

        console.log(chalk.green('✓ Document updated successfully'));

      } catch (error) {
        console.error('Error:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  return edit;
}
