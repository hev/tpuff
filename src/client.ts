import { Turbopuffer } from '@turbopuffer/turbopuffer';

export function getTurbopufferClient(): Turbopuffer {
  const apiKey = process.env.TURBOPUFFER_API_KEY;

  if (!apiKey) {
    console.error('Error: TURBOPUFFER_API_KEY environment variable is not set');
    process.exit(1);
  }

  const baseURL = process.env.TURBOPUFFER_BASE_URL;
  const region = process.env.TURBOPUFFER_REGION || 'aws-us-east-1';

  return new Turbopuffer({
    apiKey,
    region,
    ...(baseURL && { baseURL })
  });
}
