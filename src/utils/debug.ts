import chalk from 'chalk';

/**
 * Global debug state - set via --debug flag or DEBUG env var
 */
let debugEnabled = false;

/**
 * Enable debug logging
 */
export function enableDebug(): void {
  debugEnabled = true;
}

/**
 * Check if debug is enabled
 */
export function isDebugEnabled(): boolean {
  return debugEnabled || process.env.DEBUG === 'true' || process.env.DEBUG === '1';
}

/**
 * Recursively filters out vector arrays from objects to make debug logs more readable
 */
function filterVectors(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  // If it's an array with all numbers and length > 10, it's likely a vector
  if (Array.isArray(obj)) {
    if (obj.length > 10 && obj.every(item => typeof item === 'number')) {
      return `[vector with ${obj.length} dimensions]`;
    }
    return obj.map(filterVectors);
  }

  // If it's an object, recursively filter its properties
  if (typeof obj === 'object') {
    const filtered: any = {};
    for (const [key, value] of Object.entries(obj)) {
      // Skip keys named 'vector' or attributes that are large number arrays
      if (key === 'vector' && Array.isArray(value) && value.length > 10) {
        filtered[key] = `[vector with ${value.length} dimensions]`;
      } else {
        filtered[key] = filterVectors(value);
      }
    }
    return filtered;
  }

  return obj;
}

/**
 * Log debug information (only shown when debug is enabled)
 */
export function debugLog(label: string, data: any): void {
  if (isDebugEnabled()) {
    console.log(chalk.gray(`\n[DEBUG] ${label}:`));
    const filtered = filterVectors(data);
    console.log(chalk.gray(typeof filtered === 'string' ? filtered : JSON.stringify(filtered, null, 2)));
  }
}

/**
 * Log raw API request
 */
export function debugRequest(method: string, url: string, payload?: any): void {
  if (isDebugEnabled()) {
    console.log(chalk.gray('\n[DEBUG] API Request:'));
    console.log(chalk.gray(`  Method: ${method}`));
    console.log(chalk.gray(`  URL: ${url}`));
    if (payload) {
      console.log(chalk.gray('  Payload:'));
      console.log(chalk.gray('  ' + JSON.stringify(payload, null, 2).replace(/\n/g, '\n  ')));
    }
  }
}

/**
 * Log raw API response
 */
export function debugResponse(status: number, data: any): void {
  if (isDebugEnabled()) {
    console.log(chalk.gray('\n[DEBUG] API Response:'));
    console.log(chalk.gray(`  Status: ${status}`));
    console.log(chalk.gray('  Data:'));
    console.log(chalk.gray('  ' + JSON.stringify(data, null, 2).replace(/\n/g, '\n  ')));
  }
}
