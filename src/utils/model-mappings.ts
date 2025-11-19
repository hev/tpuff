/**
 * Model mappings for embedding model slugs to HuggingFace model names
 */

export interface ModelConfig {
  huggingFaceModel: string;
  dimensions: number;
  defaultDistanceMetric: 'cosine_distance' | 'euclidean_squared';
}

/**
 * Mapping of model slugs to their configurations
 * Model slugs are used as namespace prefixes (e.g., "all-minilm-l6-v2-documents")
 */
export const MODEL_MAPPINGS: Record<string, ModelConfig> = {
  'all-minilm-l6-v2': {
    huggingFaceModel: 'Xenova/all-MiniLM-L6-v2',
    dimensions: 384,
    defaultDistanceMetric: 'cosine_distance',
  },
  'sentence-transformers-all-minilm-l6-v2': {
    huggingFaceModel: 'Xenova/all-MiniLM-L6-v2',
    dimensions: 384,
    defaultDistanceMetric: 'cosine_distance',
  },
  'nomic-embed-text-v1': {
    huggingFaceModel: 'nomic-ai/nomic-embed-text-v1',
    dimensions: 768,
    defaultDistanceMetric: 'cosine_distance',
  },
  'gte-small': {
    huggingFaceModel: 'Xenova/gte-small',
    dimensions: 384,
    defaultDistanceMetric: 'cosine_distance',
  },
  'gte-base': {
    huggingFaceModel: 'Xenova/gte-base',
    dimensions: 768,
    defaultDistanceMetric: 'cosine_distance',
  },
  'bge-small-en-v1.5': {
    huggingFaceModel: 'Xenova/bge-small-en-v1.5',
    dimensions: 384,
    defaultDistanceMetric: 'cosine_distance',
  },
  'bge-base-en-v1.5': {
    huggingFaceModel: 'Xenova/bge-base-en-v1.5',
    dimensions: 768,
    defaultDistanceMetric: 'cosine_distance',
  },
};

/**
 * Extract the model slug from a namespace name
 * Expected format: <model-slug>-<anything>
 * Example: "all-minilm-l6-v2-documents" -> "all-minilm-l6-v2"
 */
export function extractModelFromNamespace(namespace: string): string | null {
  // Try to match known model patterns
  const sortedModels = Object.keys(MODEL_MAPPINGS).sort((a, b) => b.length - a.length);

  for (const modelSlug of sortedModels) {
    if (namespace.startsWith(modelSlug + '-') || namespace === modelSlug) {
      return modelSlug;
    }
  }

  return null;
}

/**
 * Get the model configuration for a given model slug
 */
export function getModelConfig(modelSlug: string): ModelConfig | null {
  return MODEL_MAPPINGS[modelSlug] || null;
}

/**
 * List all supported model slugs
 */
export function getSupportedModels(): string[] {
  return Object.keys(MODEL_MAPPINGS);
}
