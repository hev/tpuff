# Release Instructions for tpuff-cli v0.1.0

This document outlines the steps to publish tpuff-cli v0.1.0 to npm and create the corresponding GitHub release.

## Prerequisites

Before you begin, ensure you have:

1. **npm account** with publish permissions
   - Log in: `npm login`
   - Verify: `npm whoami`

2. **Docker Hub account** with push permissions to `hevmind/tpuff-embeddings`
   - Log in: `docker login`

3. **GitHub CLI** installed and authenticated
   - Verify: `gh auth status`

## Automated Release (Recommended)

We provide a release script that automates the entire release process.

### Using the Release Script

1. **Ensure all changes are committed**
   ```bash
   git add .
   git commit -m "Prepare v0.1.0 release"
   git push
   ```

2. **Run the release script**
   ```bash
   ./scripts/release.sh
   ```

The script will:
- ✓ Verify npm, Docker, and GitHub CLI authentication
- ✓ Build the npm package
- ✓ Publish `tpuff-cli@0.1.0` to npm
- ✓ Build and push Docker image `hevmind/tpuff-embeddings:0.1.0`
- ✓ Create and push git tag `v0.1.0`
- ✓ Create GitHub release with auto-generated notes

The script includes safety checks and confirmations at each step, so you can review before proceeding.

## Manual Release (Alternative)

If you prefer to run each step manually:

### 1. Build and Publish to npm

```bash
# Build the package
npm run build

# Test the package locally
npm pack --dry-run

# Publish to npm (public)
npm publish --access public
```

### 2. Build and Push Docker Image

```bash
# Build and tag Docker image
docker build -t tpuff-embeddings:0.1.0 docker/
docker tag tpuff-embeddings:0.1.0 tpuff-embeddings:latest
docker tag tpuff-embeddings:0.1.0 hevmind/tpuff-embeddings:0.1.0
docker tag tpuff-embeddings:0.1.0 hevmind/tpuff-embeddings:latest

# Push to Docker Hub
docker push hevmind/tpuff-embeddings:0.1.0
docker push hevmind/tpuff-embeddings:latest
```

### 3. Create GitHub Release

```bash
# Create and push tag
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0

# Create release via gh CLI
gh release create v0.1.0 \
  --title "v0.1.0" \
  --generate-notes \
  --notes "## Installation

\`\`\`bash
npm install -g tpuff-cli
\`\`\`

## Docker Image

\`\`\`bash
docker pull hevmind/tpuff-embeddings:0.1.0
\`\`\`"
```

## Verification

After release, verify:

1. **npm package**
   ```bash
   npm view tpuff-cli
   ```

2. **Docker image**
   ```bash
   docker pull hevmind/tpuff-embeddings:0.1.0
   ```

3. **GitHub release**
   - Visit: https://github.com/hev/tpuff/releases/tag/v0.1.0

4. **Install test**
   ```bash
   npm install -g tpuff-cli
   tpuff --version
   ```

## Changes in This Release

### Package Configuration
- Renamed package to `tpuff-cli` for npm publication
- Added `files` field to only include necessary files in package
- Added `prepublishOnly` script to ensure build runs before publish
- Added repository, bugs, and homepage fields
- Updated keywords for better discoverability

### Docker
- Pinned Docker image to version `0.1.0`
- Changed from local build to Docker Hub pull
- Updated `docker:build` script to tag both versioned and latest
- Modified `docker-embeddings.ts` to use versioned image from Docker Hub

### Documentation
- Updated README with npm installation instructions
- Simplified installation process for end users
- Added development installation section
- Updated Docker references to use Docker Hub image

### Automation
- Created release script for one-command releases
- Includes safety checks and confirmations

## Troubleshooting

### npm publish fails with 403
- Ensure you're logged in: `npm whoami`
- Verify you have publish permissions
- Check if package name is already taken: `npm view tpuff-cli`

### Docker push fails
- Ensure you're logged in: `docker login`
- Verify you have push permissions to `hevmind/tpuff-embeddings`
- Check Docker daemon is running: `docker info`

### GitHub release creation fails
- Ensure gh CLI is authenticated: `gh auth status`
- Verify you have write permissions to the repository
- Check that the tag doesn't already exist: `git tag -l v0.1.0`

### Release script fails mid-way
- The script is designed to be safe to re-run
- Each step checks if it needs to be performed
- You can also complete remaining steps manually (see Manual Release section)
