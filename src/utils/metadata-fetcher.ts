import { getTurbopufferClient } from '../client.js';
import { debugLog } from './debug.js';
import { TURBOPUFFER_REGIONS } from './regions.js';

export interface NamespaceMetadata {
  approx_row_count: number;
  approx_logical_bytes: number;
  index: {
    status: 'up-to-date' | 'updating';
    unindexed_bytes?: number;
  };
  encryption?: {
    sse?: boolean;
    cmek?: {
      key_name: string;
    };
  };
  updated_at: string;
  created_at: string;
  schema: Record<string, any>;
}

export interface RecallData {
  avg_recall: number;
  avg_ann_count: number;
  avg_exhaustive_count: number;
}

export interface NamespaceWithMetadata {
  namespace: { id: string };
  metadata: NamespaceMetadata | null;
  region?: string;
  recall: RecallData | null;
}

export interface FetchNamespacesOptions {
  allRegions?: boolean;
  region?: string;
  includeRecall?: boolean;
}

/**
 * Fetches namespaces with their metadata from Turbopuffer API
 * Supports both single-region and multi-region queries
 */
export async function fetchNamespacesWithMetadata(
  options: FetchNamespacesOptions = {}
): Promise<NamespaceWithMetadata[]> {
  const { allRegions = false, region, includeRecall = false } = options;

  let namespacesWithMetadata: NamespaceWithMetadata[] = [];

  if (allRegions) {
    // Query all regions
    debugLog('Querying all regions', { regionCount: TURBOPUFFER_REGIONS.length });

    for (const currentRegion of TURBOPUFFER_REGIONS) {
      try {
        const regionalClient = getTurbopufferClient(currentRegion);
        const page = await regionalClient.namespaces();
        debugLog(`Namespaces in ${currentRegion}`, page);

        if (page.namespaces.length > 0) {
          // Fetch metadata for namespaces in this region in parallel
          const metadataPromises = page.namespaces.map(async ns => {
            debugLog(`Fetching metadata for namespace: ${ns.id} in ${currentRegion}`, {});
            try {
              const metadata = await regionalClient.namespace(ns.id).metadata();
              debugLog(`Metadata for ${ns.id}`, metadata);
              return metadata;
            } catch (error) {
              debugLog(`Failed to fetch metadata for ${ns.id}`, error);
              return null;
            }
          });
          const metadataList = await Promise.all(metadataPromises);

          // Add recall fetching in parallel if requested
          let recallList: (RecallData | null)[] = [];
          if (includeRecall) {
            const recallPromises = page.namespaces.map(ns =>
              fetchRecallData(regionalClient, ns.id)
            );
            recallList = await Promise.all(recallPromises);
          } else {
            recallList = page.namespaces.map(() => null);
          }

          // Add namespaces from this region with region info
          const regionalNamespaces = page.namespaces.map((ns, index) => ({
            namespace: ns,
            metadata: metadataList[index],
            recall: recallList[index],
            region: currentRegion
          }));

          namespacesWithMetadata.push(...regionalNamespaces);
        }
      } catch (error) {
        debugLog(`Failed to query region ${currentRegion}`, error);
        // Continue to next region on error
      }
    }
  } else {
    // Query single region
    const client = getTurbopufferClient(region);
    const page = await client.namespaces();
    debugLog('Namespaces API Response', page);
    const namespaces = page.namespaces;

    // Fetch metadata for each namespace in parallel
    const metadataPromises = namespaces.map(async ns => {
      debugLog(`Fetching metadata for namespace: ${ns.id}`, {});
      try {
        const metadata = await client.namespace(ns.id).metadata();
        debugLog(`Metadata for ${ns.id}`, metadata);
        return metadata;
      } catch (error) {
        debugLog(`Failed to fetch metadata for ${ns.id}`, error);
        return null;
      }
    });
    const metadataList = await Promise.all(metadataPromises);

    // Add recall fetching in parallel if requested
    let recallList: (RecallData | null)[] = [];
    if (includeRecall) {
      const recallPromises = namespaces.map(ns => fetchRecallData(client, ns.id));
      recallList = await Promise.all(recallPromises);
    } else {
      recallList = namespaces.map(() => null);
    }

    // Combine namespaces with their metadata
    namespacesWithMetadata = namespaces.map((ns, index) => ({
      namespace: ns,
      metadata: metadataList[index],
      recall: recallList[index],
      region
    }));
  }

  return namespacesWithMetadata;
}

/**
 * Fetches recall metrics for a namespace
 */
async function fetchRecallData(
  client: any,
  namespaceId: string
): Promise<RecallData | null> {
  try {
    debugLog(`Fetching recall for namespace: ${namespaceId}`, {});
    const recallResponse = await client.namespace(namespaceId).recall({
      num: 25,
      top_k: 10
    });
    debugLog(`Recall for ${namespaceId}`, recallResponse);
    return {
      avg_recall: recallResponse.avg_recall,
      avg_ann_count: recallResponse.avg_ann_count,
      avg_exhaustive_count: recallResponse.avg_exhaustive_count
    };
  } catch (error) {
    debugLog(`Failed to fetch recall for ${namespaceId}`, error);
    return null;
  }
}

/**
 * Extracts encryption type from metadata
 */
export function getEncryptionType(metadata: NamespaceMetadata | null): string {
  if (!metadata?.encryption) {
    return 'sse'; // Default to SSE
  }

  if (metadata.encryption.cmek) {
    return 'cmek';
  }

  return 'sse';
}

/**
 * Extracts index status from metadata
 */
export function getIndexStatus(metadata: NamespaceMetadata | null): 'up-to-date' | 'updating' {
  if (!metadata?.index) {
    return 'up-to-date';
  }

  return metadata.index.status;
}

/**
 * Gets unindexed bytes from metadata
 */
export function getUnindexedBytes(metadata: NamespaceMetadata | null): number {
  if (!metadata?.index) {
    return 0;
  }

  if (metadata.index.status === 'up-to-date') {
    return 0;
  }

  return metadata.index.unindexed_bytes || 0;
}
