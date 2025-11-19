import { Command } from 'commander';
import { getTurbopufferClient } from '../client.js';
import chalk from 'chalk';
import Table from 'cli-table3';
import { embeddingGenerator } from '../utils/embeddings.js';
import { debugLog } from '../utils/debug.js';

interface SearchOptions {
  namespace: string;
  topK: string;
  model?: string;
  distanceMetric?: 'cosine_distance' | 'euclidean_squared';
  filters?: string;
  region?: string;
  fts?: string;
  python?: boolean;
}

export function createSearchCommand(): Command {
  const search = new Command('search')
    .description('Search for documents in a namespace using vector similarity or full-text search')
    .argument('<query>', 'Search query text')
    .requiredOption('-n, --namespace <name>', 'Namespace to search in')
    .option('-m, --model <id>', 'HuggingFace model ID for vector search (e.g., Xenova/all-MiniLM-L6-v2)')
    .option('-k, --top-k <number>', 'Number of results to return', '10')
    .option('-d, --distance-metric <metric>', 'Distance metric for vector search (cosine_distance or euclidean_squared)', 'cosine_distance')
    .option('-f, --filters <filters>', 'Additional filters in JSON format')
    .option('--fts <field>', 'Field name to use for full-text search (BM25)')
    .option('--python', 'Force use of Docker/Python for embedding generation')
    .option('-r, --region <region>', 'Override the region (e.g., aws-us-east-1, gcp-us-central1)')
    .action(async (query: string, options: SearchOptions) => {
      const client = getTurbopufferClient(options.region);

      try {
        const namespace = options.namespace;
        const topK = parseInt(options.topK || '10', 10);
        const useFts = !!options.fts;

        // Validate options
        if (!useFts && !options.model) {
          console.error(chalk.red('Error: Either --model or --fts must be specified'));
          console.error(chalk.yellow('  Use --model for vector similarity search'));
          console.error(chalk.yellow('  Use --fts for full-text search'));
          process.exit(1);
        }

        if (useFts && options.model) {
          console.error(chalk.yellow('Warning: Both --fts and --model specified. Using FTS mode.'));
        }

        console.log(chalk.bold(`\nSearching in namespace: ${namespace}`));
        console.log(chalk.gray(`Query: "${query}"`));

        const ns = client.namespace(namespace);
        let queryParams: any;

        // Get namespace metadata to find vector attribute name (for exclude_attributes)
        const metadata = await ns.metadata();
        const vectorInfo = extractVectorInfo(metadata.schema);

        if (useFts) {
          // Full-text search mode
          console.log(chalk.gray(`Mode: Full-text search (BM25) on field "${options.fts}"\n`));

          queryParams = {
            rank_by: [options.fts, 'BM25', query],
            top_k: topK,
            exclude_attributes: vectorInfo ? [vectorInfo.attributeName] : undefined,
          };
        } else {
          // Vector search mode
          const modelId = options.model!;
          console.log(chalk.gray(`Mode: Vector similarity search`));
          console.log(chalk.gray(`Model: ${modelId}\n`));

          // Step 1: Generate embedding for query
          let embedding: number[];
          try {
            embedding = await embeddingGenerator.generateEmbedding(query, modelId, options.python);
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error);

            // Check if it's a model loading error
            if (errorMsg.includes('Could not locate file') ||
                errorMsg.includes('Unauthorized access') ||
                errorMsg.includes('onnx')) {
              console.error(chalk.red('\nError: Failed to load model'));
              console.error(chalk.yellow('\nThis CLI requires models from the Xenova organization that are in ONNX format.'));
              console.error(chalk.gray('\nPopular embedding models:'));
              console.error(chalk.gray('  • Xenova/all-MiniLM-L6-v2 (384 dimensions)'));
              console.error(chalk.gray('  • Xenova/bge-small-en-v1.5 (384 dimensions)'));
              console.error(chalk.gray('  • Xenova/bge-base-en-v1.5 (768 dimensions)'));
              console.error(chalk.gray('\nBrowse all 762 models: https://huggingface.co/Xenova\n'));
              process.exit(1);
            }

            // Re-throw other errors
            throw error;
          }

          console.log(chalk.gray(`Generated ${embedding.length}-dimensional embedding\n`));

          // Step 2: Verify vector configuration
          if (!vectorInfo) {
            console.error(chalk.red('Error: No vector attribute found in namespace schema'));
            process.exit(1);
          }

          // Verify dimensions match
          if (vectorInfo.dimensions !== embedding.length) {
            console.error(chalk.red(`Error: Dimension mismatch!`));
            console.error(chalk.yellow(`  Expected: ${vectorInfo.dimensions} dimensions (from namespace schema)`));
            console.error(chalk.yellow(`  Got: ${embedding.length} dimensions (from model ${modelId})`));
            console.error(chalk.yellow(`\nThe namespace may have been created with a different embedding model.`));
            process.exit(1);
          }

          // Determine distance metric
          const distanceMetric = options.distanceMetric || 'cosine_distance';
          console.log(chalk.gray(`Using distance metric: ${distanceMetric}\n`));

          queryParams = {
            rank_by: [vectorInfo.attributeName, 'ANN', embedding],
            top_k: topK,
            distance_metric: distanceMetric,
            exclude_attributes: [vectorInfo.attributeName],
          };
        }

        // Step 4: Parse filters if provided
        let parsedFilters: any = undefined;
        if (options.filters) {
          try {
            parsedFilters = JSON.parse(options.filters);
          } catch (error) {
            console.error(chalk.red('Error: Invalid filter JSON format'));
            console.error(chalk.yellow('Example: -f \'{"category": ["tech", "science"]}\''));
            process.exit(1);
          }
        }

        if (parsedFilters) {
          queryParams.filters = parsedFilters;
        }

        // Debug: Log query parameters
        debugLog('Query Parameters', queryParams);

        // Step 5: Query the namespace
        const startTime = Date.now();
        const result = await ns.query(queryParams);

        const queryTime = Date.now() - startTime;

        // Debug: Log API response
        debugLog('Query Response', result);

        if (!result.rows || result.rows.length === 0) {
          console.log(chalk.yellow('No documents found matching the query'));
          return;
        }

        // Debug: Log first row structure
        if (result.rows.length > 0) {
          debugLog('First Row Structure', {
            keys: Object.keys(result.rows[0]),
            data: result.rows[0]
          });
        }

        console.log(chalk.bold(`Found ${result.rows.length} result(s):\n`));

        // Step 6: Display results using table format (matching list command)
        const rows = result.rows;

        const headers = useFts
          ? ['ID', 'Contents', 'Score']
          : ['ID', 'Contents', 'Distance'];

        const table = new Table({
          head: headers.map(h => chalk.cyan(h)),
          style: {
            head: [],
            border: ['grey']
          }
        });

        // Add rows to table
        rows.forEach(row => {
          // For FTS, show only the searched field; for vector search, show all attributes
          let displayContents: string;

          if (useFts) {
            // Show only the FTS field
            const fieldValue = (row as any)[options.fts!];
            displayContents = fieldValue !== undefined ? String(fieldValue) : chalk.gray('N/A');

            // Truncate if too long
            const maxLength = 80;
            if (displayContents.length > maxLength) {
              displayContents = displayContents.substring(0, maxLength) + '...';
            }
          } else {
            // Vector search: show all attributes except system fields
            const contents: { [key: string]: any } = {};
            Object.keys(row).forEach(key => {
              // Exclude id, vector, $dist, $score, and attributes from display
              if (key !== 'id' && key !== 'vector' && key !== '$dist' && key !== '$score' && key !== 'attributes') {
                contents[key] = (row as any)[key];
              }
            });

            // Stringify and truncate contents
            const contentsStr = JSON.stringify(contents);
            const maxLength = 80;
            displayContents = contentsStr.length > maxLength
              ? contentsStr.substring(0, maxLength) + '...'
              : contentsStr;
          }

          const scoreValue = (row.$dist !== undefined && row.$dist !== null
            ? (row.$dist as number).toFixed(4)
            : chalk.gray('N/A'));

          const rowData: any[] = [
            row.id,
            displayContents,
            scoreValue
          ];

          table.push(rowData);
        });

        console.log(table.toString());
        console.log(chalk.gray(`\nSearch completed in ${queryTime}ms (query execution: ${result.performance.query_execution_ms.toFixed(2)}ms)`));
      } catch (error) {
        console.error(chalk.red('Error:'), error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  return search;
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
