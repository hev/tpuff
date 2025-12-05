#!/bin/bash

# Release script for tpuff-cli
# This script automates the release process including:
# - Building the npm package
# - Publishing to npm
# - Building and pushing Docker image
# - Creating GitHub release tag

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get version from package.json
VERSION=$(node -p "require('./package.json').version")
DOCKER_USERNAME="hevmind"
EMBEDDINGS_IMAGE="tpuff-embeddings"
EXPORTER_IMAGE="tpuff-exporter"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  tpuff-cli Release Script v${VERSION}${NC}"
echo -e "${BLUE}======================================${NC}"
echo

# Verify we're on a clean working directory
if [[ -n $(git status -s) ]]; then
  echo -e "${YELLOW}Warning: You have uncommitted changes.${NC}"
  read -p "Continue anyway? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Verify npm login
echo -e "${BLUE}Verifying npm authentication...${NC}"
if ! npm whoami > /dev/null 2>&1; then
  echo -e "${RED}Error: Not logged in to npm. Please run 'npm login' first.${NC}"
  exit 1
fi
NPM_USER=$(npm whoami)
echo -e "${GREEN}✓ Logged in as: ${NPM_USER}${NC}"
echo

# Verify Docker login
echo -e "${BLUE}Verifying Docker Hub authentication...${NC}"
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}Error: Docker daemon is not running.${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"
echo

# Verify gh CLI
echo -e "${BLUE}Verifying GitHub CLI authentication...${NC}"
if ! gh auth status > /dev/null 2>&1; then
  echo -e "${RED}Error: Not authenticated with GitHub CLI. Please run 'gh auth login' first.${NC}"
  exit 1
fi
echo -e "${GREEN}✓ GitHub CLI authenticated${NC}"
echo

# Confirm release
echo -e "${YELLOW}You are about to release version ${VERSION}${NC}"
echo "This will:"
echo "  1. Build the npm package"
echo "  2. Publish tpuff-cli@${VERSION} to npm"
echo "  3. Build and push Docker images:"
echo "     - ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:${VERSION}"
echo "     - ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:${VERSION}"
echo "  4. Create and push git tag v${VERSION}"
echo "  5. Create GitHub release"
echo
read -p "Continue with release? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Release cancelled.${NC}"
  exit 1
fi
echo

# Step 1: Build npm package
echo -e "${BLUE}Step 1: Building npm package...${NC}"
npm run build
echo -e "${GREEN}✓ Build complete${NC}"
echo

# Step 2: Test the package
echo -e "${BLUE}Step 2: Testing package contents...${NC}"
npm pack --dry-run
echo -e "${GREEN}✓ Package verified${NC}"
echo

# Step 3: Publish to npm
echo -e "${BLUE}Step 3: Publishing to npm...${NC}"
npm publish --access public
echo -e "${GREEN}✓ Published to npm${NC}"
echo

# Step 4: Build Docker images
echo -e "${BLUE}Step 4: Building Docker images...${NC}"

echo "Building embeddings image..."
docker build -t ${EMBEDDINGS_IMAGE}:${VERSION} docker/
docker tag ${EMBEDDINGS_IMAGE}:${VERSION} ${EMBEDDINGS_IMAGE}:latest
docker tag ${EMBEDDINGS_IMAGE}:${VERSION} ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:${VERSION}
docker tag ${EMBEDDINGS_IMAGE}:${VERSION} ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:latest
echo -e "${GREEN}✓ Embeddings image built${NC}"

echo "Building exporter image..."
docker build -f Dockerfile.exporter -t ${EXPORTER_IMAGE}:${VERSION} .
docker tag ${EXPORTER_IMAGE}:${VERSION} ${EXPORTER_IMAGE}:latest
docker tag ${EXPORTER_IMAGE}:${VERSION} ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:${VERSION}
docker tag ${EXPORTER_IMAGE}:${VERSION} ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:latest
echo -e "${GREEN}✓ Exporter image built${NC}"
echo

# Step 5: Push Docker images
echo -e "${BLUE}Step 5: Pushing Docker images to Docker Hub...${NC}"

echo "Pushing embeddings image..."
docker push ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:${VERSION}
docker push ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:latest
echo -e "${GREEN}✓ Embeddings image pushed${NC}"

echo "Pushing exporter image..."
docker push ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:${VERSION}
docker push ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:latest
echo -e "${GREEN}✓ Exporter image pushed${NC}"
echo

# Step 6: Create and push git tag
echo -e "${BLUE}Step 6: Creating git tag...${NC}"
if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
  echo -e "${YELLOW}Warning: Tag v${VERSION} already exists locally${NC}"
  read -p "Delete and recreate? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    git tag -d "v${VERSION}"
  else
    echo -e "${YELLOW}Skipping tag creation${NC}"
  fi
fi

if ! git rev-parse "v${VERSION}" >/dev/null 2>&1; then
  git tag -a "v${VERSION}" -m "Release v${VERSION}"
  echo -e "${GREEN}✓ Tag created${NC}"
fi

echo -e "${BLUE}Pushing tag to GitHub...${NC}"
git push origin "v${VERSION}" --force
echo -e "${GREEN}✓ Tag pushed${NC}"
echo

# Step 7: Create GitHub release
echo -e "${BLUE}Step 7: Creating GitHub release...${NC}"
gh release create "v${VERSION}" \
  --title "v${VERSION}" \
  --generate-notes \
  --notes "## Installation

\`\`\`bash
npm install -g tpuff-cli
\`\`\`

## Docker Images

\`\`\`bash
# Embeddings service
docker pull ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:${VERSION}

# Prometheus exporter
docker pull ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:${VERSION}
\`\`\`"

echo -e "${GREEN}✓ GitHub release created${NC}"
echo

# Summary
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Release Complete! 🎉${NC}"
echo -e "${GREEN}======================================${NC}"
echo
echo "Released version: ${VERSION}"
echo "npm package: https://www.npmjs.com/package/tpuff-cli"
echo "Docker images:"
echo "  - https://hub.docker.com/r/${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}"
echo "  - https://hub.docker.com/r/${DOCKER_USERNAME}/${EXPORTER_IMAGE}"
echo "GitHub release: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/releases/tag/v${VERSION}"
echo
echo -e "${BLUE}Verify the release:${NC}"
echo "  npm view tpuff-cli"
echo "  docker pull ${DOCKER_USERNAME}/${EMBEDDINGS_IMAGE}:${VERSION}"
echo "  docker pull ${DOCKER_USERNAME}/${EXPORTER_IMAGE}:${VERSION}"
echo
