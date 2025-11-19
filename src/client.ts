import { Turbopuffer } from '@turbopuffer/turbopuffer';
import { debugLog } from './utils/debug.js';

export function getTurbopufferClient(regionOverride?: string): Turbopuffer {
  const apiKey = process.env.TURBOPUFFER_API_KEY;

  if (!apiKey) {
    console.error('Error: TURBOPUFFER_API_KEY environment variable is not set');
    process.exit(1);
  }

  const baseURL = process.env.TURBOPUFFER_BASE_URL;
  const region = regionOverride || process.env.TURBOPUFFER_REGION || 'aws-us-east-1';

  const client = new Turbopuffer({
    apiKey,
    region,
    ...(baseURL && { baseURL })
  });

  debugLog('Turbopuffer Client Configuration', {
    region,
    baseURL: baseURL || 'default',
    apiKeyPresent: !!apiKey
  });

  return client;
}
