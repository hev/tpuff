/**
 * All available Turbopuffer regions
 * Source: https://turbopuffer.com/docs/regions
 */
export const TURBOPUFFER_REGIONS = [
  // GCP Regions
  'gcp-us-central1',
  'gcp-us-west1',
  'gcp-us-east4',
  'gcp-northamerica-northeast2',
  'gcp-europe-west3',
  'gcp-asia-southeast1',
  'gcp-asia-northeast3',
  // AWS Regions
  'aws-ap-southeast-2',
  'aws-eu-central-1',
  'aws-eu-west-1',
  'aws-us-east-1',
  'aws-us-east-2',
  'aws-us-west-2',
  'aws-ap-south-1',
] as const;

export type TurbopufferRegion = typeof TURBOPUFFER_REGIONS[number];
