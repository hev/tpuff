import { Command } from 'commander';
import { getTurbopufferClient } from '../client';
import chalk from 'chalk';
import * as readline from 'readline';

/**
 * Prompts the user for input
 */
function prompt(question: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

export function createDeleteCommand(): Command {
  const deleteCmd = new Command('delete')
    .alias('rm')
    .description('Delete namespace(s)')
    .option('-n, --namespace <name>', 'Namespace to delete')
    .option('--all', 'Delete all namespaces')
    .action(async (options: { namespace?: string; all?: boolean }) => {
      const client = getTurbopufferClient();

      try {
        // Validate that exactly one option is provided
        if (!options.namespace && !options.all) {
          console.error(chalk.red('Error: You must specify either -n <namespace> or --all'));
          console.log('\nUsage:');
          console.log('  tpuff delete -n <namespace>  Delete a specific namespace');
          console.log('  tpuff delete --all           Delete all namespaces');
          process.exit(1);
        }

        if (options.namespace && options.all) {
          console.error(chalk.red('Error: Cannot use both -n and --all options together'));
          process.exit(1);
        }

        if (options.namespace) {
          // Delete single namespace
          const namespace = options.namespace;

          console.log(chalk.yellow(`\n⚠️  You are about to delete namespace: ${chalk.bold(namespace)}`));
          console.log(chalk.gray('This action cannot be undone.\n'));

          const answer = await prompt('Are you sure? (y/n): ');

          if (answer.toLowerCase() !== 'y' && answer.toLowerCase() !== 'yes') {
            console.log(chalk.gray('Deletion cancelled.'));
            process.exit(0);
          }

          // Delete the namespace
          console.log(chalk.gray(`\nDeleting namespace ${namespace}...`));
          const ns = client.namespace(namespace);
          await ns.deleteAll({ namespace });

          console.log(chalk.green(`✓ Namespace ${chalk.bold(namespace)} deleted successfully!`));

        } else if (options.all) {
          // Delete all namespaces
          console.log(chalk.yellow.bold('\n🚨 DANGER ZONE 🚨'));
          console.log(chalk.red('You are about to delete ALL namespaces!'));
          console.log(chalk.gray('This will permanently destroy all your data.\n'));

          // First, list all namespaces
          const page = await client.namespaces();
          const namespaces = page.namespaces;

          if (namespaces.length === 0) {
            console.log(chalk.gray('No namespaces found. Nothing to delete.'));
            process.exit(0);
          }

          console.log(chalk.yellow(`Found ${namespaces.length} namespace(s):`));
          namespaces.forEach(ns => {
            console.log(chalk.gray(`  - ${ns.id}`));
          });

          console.log(chalk.yellow.bold('\n💀 This is your last chance to back out! 💀'));
          console.log(chalk.gray(`To confirm, please type: ${chalk.bold.red('yolo')}\n`));

          const answer = await prompt('> ');

          if (answer !== 'yolo') {
            console.log(chalk.green('\n✨ Wise choice! Your data lives to see another day.'));
            console.log(chalk.gray('(Phew, that was close!)'));
            process.exit(0);
          }

          // User typed yolo, proceed with deletion
          console.log(chalk.red.bold('\n🎢 YOLO MODE ACTIVATED! 🎢'));
          console.log(chalk.gray('Deleting all namespaces...\n'));

          let successCount = 0;
          let failCount = 0;

          for (const ns of namespaces) {
            try {
              await client.namespace(ns.id).deleteAll({ namespace: ns.id });
              console.log(chalk.gray(`  ✓ Deleted: ${ns.id}`));
              successCount++;
            } catch (error) {
              console.log(chalk.red(`  ✗ Failed to delete: ${ns.id}`));
              console.error(chalk.gray(`    Error: ${error instanceof Error ? error.message : String(error)}`));
              failCount++;
            }
          }

          console.log(chalk.green.bold(`\n🎉 Deletion complete!`));
          console.log(chalk.gray(`Successfully deleted: ${successCount}`));
          if (failCount > 0) {
            console.log(chalk.red(`Failed: ${failCount}`));
          }
          console.log(chalk.gray('\n(Hope you had backups! 😅)'));
        }

      } catch (error) {
        console.error(chalk.red('Error:'), error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  return deleteCmd;
}
