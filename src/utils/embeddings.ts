/**
 * Embedding generation utilities using @xenova/transformers
 * with Docker fallback for Python-only models
 */

import { pipeline, AutoTokenizer, AutoModel, env } from '@xenova/transformers';
import {
  requiresPythonModel,
  isDockerAvailable,
  isDockerRunning,
  ensureContainerRunning,
  generateDockerEmbedding,
} from './docker-embeddings.js';
import chalk from 'chalk';

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
   * Automatically uses Docker for Python-only models
   */
  async generateEmbedding(text: string, modelId: string, forcePython: boolean = false): Promise<number[]> {
    // Check if this model requires Python/Docker
    const needsPython = forcePython || requiresPythonModel(modelId);

    if (needsPython) {
      return await this.generatePythonEmbedding(text, modelId);
    }

    // Try Xenova first
    try {
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
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);

      // Check if it's a model loading error that might be resolved with Python
      if (errorMsg.includes('Could not locate file') ||
          errorMsg.includes('Unauthorized access') ||
          errorMsg.includes('onnx')) {

        console.error(chalk.yellow('\nXenova model not available. Trying Docker/Python fallback...'));
        return await this.generatePythonEmbedding(text, modelId);
      }

      // Re-throw other errors
      throw error;
    }
  }

  /**
   * Generate embedding using Docker container with Python
   */
  private async generatePythonEmbedding(text: string, modelId: string): Promise<number[]> {
    console.log(chalk.blue(`\nDetected Python-only model: ${modelId}`));

    // Check Docker availability
    if (!isDockerAvailable()) {
      throw new Error(
        'Docker is not available. Please install Docker to use Python-only embedding models.\n' +
        'Visit: https://docs.docker.com/get-docker/'
      );
    }

    if (!isDockerRunning()) {
      throw new Error(
        'Docker daemon is not running. Please start Docker and try again.'
      );
    }

    console.log(chalk.green('Docker is available ✓'));

    // Ensure container is running
    await ensureContainerRunning();

    console.log(chalk.gray('Generating embedding using Docker container...'));

    // Generate embedding via Docker
    const embedding = await generateDockerEmbedding(text, modelId);

    return embedding;
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
