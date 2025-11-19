/**
 * Embedding generation utilities using @xenova/transformers
 */

import { pipeline, AutoTokenizer, AutoModel, env } from '@xenova/transformers';

// Disable local model cache path warnings
env.allowLocalModels = false;

/**
 * Mean pooling function for transformer outputs
 */
function meanPooling(modelOutput: any, attentionMask: any): number[] {
  const tokenEmbeddings = modelOutput.last_hidden_state;
  const inputMaskExpanded = attentionMask
    .unsqueeze(-1)
    .expand(tokenEmbeddings.dims)
    .to(tokenEmbeddings.dtype);

  const sum = tokenEmbeddings.mul(inputMaskExpanded).sum(1);
  const sumMask = inputMaskExpanded.sum(1);
  const clampedSumMask = sumMask.clamp(1e-9, null);

  return sum.div(clampedSumMask).tolist()[0];
}

/**
 * Embedding generator class with model caching
 */
class EmbeddingGenerator {
  private modelCache: Map<string, { tokenizer: any; model: any }> = new Map();

  /**
   * Generate an embedding for the given text using the specified HuggingFace model ID
   */
  async generateEmbedding(text: string, modelId: string): Promise<number[]> {
    // Load or retrieve cached model
    const { tokenizer, model } = await this.loadModel(modelId);

    // Tokenize the input
    const inputs = await tokenizer(text, {
      padding: true,
      truncation: true,
    });

    // Run the model
    const output = await model(inputs);

    // Apply mean pooling
    const embedding = meanPooling(output, inputs.attention_mask);

    // Normalize the embedding (for cosine similarity)
    const norm = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    const normalizedEmbedding = embedding.map(val => val / norm);

    return normalizedEmbedding;
  }

  /**
   * Load a model and tokenizer, using cache if available
   */
  private async loadModel(huggingFaceModel: string): Promise<{ tokenizer: any; model: any }> {
    if (this.modelCache.has(huggingFaceModel)) {
      return this.modelCache.get(huggingFaceModel)!;
    }

    console.error(`Loading model: ${huggingFaceModel}...`);

    const tokenizer = await AutoTokenizer.from_pretrained(huggingFaceModel);
    const model = await AutoModel.from_pretrained(huggingFaceModel);

    this.modelCache.set(huggingFaceModel, { tokenizer, model });

    console.error(`Model loaded successfully.`);

    return { tokenizer, model };
  }

  /**
   * Clear the model cache
   */
  clearCache(): void {
    this.modelCache.clear();
  }
}

// Singleton instance
export const embeddingGenerator = new EmbeddingGenerator();
