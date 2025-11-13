#!/usr/bin/env node

import { Command } from 'commander';
import { createListCommand } from './commands/list';
import { createGetCommand } from './commands/get';

const program = new Command();

program
  .name('tpuff')
  .description('A TypeScript CLI for interacting with turbopuffer')
  .version('0.1.0');

// Add commands
program.addCommand(createListCommand());
program.addCommand(createGetCommand());

program.parse();
