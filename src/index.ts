#!/usr/bin/env node

import { Command } from 'commander';
import { createListCommand } from './commands/list.js';
import { createEditCommand } from './commands/edit.js';
import { createDeleteCommand } from './commands/delete.js';
import { createSearchCommand } from './commands/search.js';
import { createExportCommand } from './commands/export.js';
import { enableDebug } from './utils/debug.js';

const program = new Command();

program
  .name('tpuff')
  .description('A TypeScript CLI for interacting with turbopuffer')
  .version('0.1.0')
  .option('--debug', 'Enable debug logging to see raw API requests/responses')
  .hook('preAction', (thisCommand) => {
    // Enable debug if --debug flag is passed at any level
    if (thisCommand.opts().debug) {
      enableDebug();
    }
  });

// Add commands
program.addCommand(createListCommand());
program.addCommand(createEditCommand());
program.addCommand(createDeleteCommand());
program.addCommand(createSearchCommand());
program.addCommand(createExportCommand());

program.parse();
