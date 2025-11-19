/**
 * Docker-based embedding utilities for Python-only models
 */

import { execSync, spawn } from 'child_process';
import chalk from 'chalk';

const CONTAINER_NAME = 'tpuff-embeddings';
const IMAGE_NAME = 'tpuff-embeddings';
const CONTAINER_PORT = 5050;
const HOST_PORT = 5050;

/**
 * Check if Docker is available on the system
 */
export function isDockerAvailable(): boolean {
  try {
    execSync('docker --version', { stdio: 'pipe' });
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Check if Docker daemon is running
 */
export function isDockerRunning(): boolean {
  try {
    execSync('docker info', { stdio: 'pipe' });
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Check if the embedding container is running
 */
export function isContainerRunning(): boolean {
  try {
    const result = execSync(
      `docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}"`,
      { encoding: 'utf-8', stdio: 'pipe' }
    );
    return result.trim() === CONTAINER_NAME;
  } catch (error) {
    return false;
  }
}

/**
 * Check if the container image exists locally
 */
export function isImageBuilt(): boolean {
  try {
    const result = execSync(
      `docker images -q ${IMAGE_NAME}`,
      { encoding: 'utf-8', stdio: 'pipe' }
    );
    return result.trim().length > 0;
  } catch (error) {
    return false;
  }
}

/**
 * Build the Docker image
 */
export async function buildImage(): Promise<void> {
  console.log(chalk.blue('Building tpuff-embeddings Docker image...'));
  console.log(chalk.gray('This may take a few minutes on first run.'));

  try {
    execSync(`docker build -t ${IMAGE_NAME} docker/`, {
      stdio: 'inherit',
      cwd: process.cwd()
    });
    console.log(chalk.green('Image built successfully!'));
  } catch (error) {
    throw new Error(`Failed to build Docker image: ${error}`);
  }
}

/**
 * Start the embedding container
 */
export async function startContainer(): Promise<void> {
  console.log(chalk.blue(`Starting ${CONTAINER_NAME} container...`));

  try {
    // Remove existing container if it exists (stopped)
    try {
      execSync(`docker rm -f ${CONTAINER_NAME}`, { stdio: 'pipe' });
    } catch (e) {
      // Container doesn't exist, that's fine
    }

    // Start the container
    execSync(
      `docker run -d --name ${CONTAINER_NAME} -p ${HOST_PORT}:${CONTAINER_PORT} ${IMAGE_NAME}`,
      { stdio: 'pipe' }
    );

    // Wait for container to be ready
    await waitForContainerReady();

    console.log(chalk.green('Container started successfully!'));
  } catch (error) {
    throw new Error(`Failed to start container: ${error}`);
  }
}

/**
 * Wait for the container to be ready to accept requests
 */
async function waitForContainerReady(maxAttempts: number = 30): Promise<void> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(`http://localhost:${HOST_PORT}/health`);
      if (response.ok) {
        return;
      }
    } catch (error) {
      // Container not ready yet
    }

    // Wait 1 second before next attempt
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  throw new Error('Container failed to become ready within timeout period');
}

/**
 * Stop the embedding container
 */
export function stopContainer(): void {
  try {
    execSync(`docker stop ${CONTAINER_NAME}`, { stdio: 'pipe' });
    execSync(`docker rm ${CONTAINER_NAME}`, { stdio: 'pipe' });
    console.log(chalk.green('Container stopped successfully!'));
  } catch (error) {
    throw new Error(`Failed to stop container: ${error}`);
  }
}

/**
 * Ensure the container is running, starting it if necessary
 */
export async function ensureContainerRunning(): Promise<void> {
  // Check if container is already running
  if (isContainerRunning()) {
    return;
  }

  // Check if image is built
  if (!isImageBuilt()) {
    await buildImage();
  }

  // Start the container
  await startContainer();
}

/**
 * Generate embedding using the Docker container
 */
export async function generateDockerEmbedding(
  text: string,
  modelId: string
): Promise<number[]> {
  try {
    const response = await fetch(`http://localhost:${HOST_PORT}/embed`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text,
        model: modelId,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json() as any;
      throw new Error(`Docker embedding failed: ${errorData.error || response.statusText}`);
    }

    const data = await response.json() as any;
    return data.embedding as number[];
  } catch (error) {
    throw new Error(`Failed to generate Docker embedding: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * Check if a model requires Python/Docker (not available in Xenova)
 */
export function requiresPythonModel(modelId: string): boolean {
  // Models that require Python embeddings
  const pythonOnlyPrefixes = [
    'sentence-transformers/',
    'intfloat/',
    'BAAI/',
    'thenlper/',
  ];

  // Models that are explicitly NOT Python-only (available in Xenova)
  const xenovaModels = [
    'Xenova/',
  ];

  // Check if it's a Xenova model
  if (xenovaModels.some(prefix => modelId.startsWith(prefix))) {
    return false;
  }

  // Check if it requires Python
  return pythonOnlyPrefixes.some(prefix => modelId.startsWith(prefix));
}

/**
 * Get container status information
 */
export function getContainerStatus(): {
  dockerAvailable: boolean;
  dockerRunning: boolean;
  containerRunning: boolean;
  imageBuilt: boolean;
} {
  return {
    dockerAvailable: isDockerAvailable(),
    dockerRunning: isDockerRunning(),
    containerRunning: isContainerRunning(),
    imageBuilt: isImageBuilt(),
  };
}
