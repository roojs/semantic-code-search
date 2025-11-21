#!/bin/bash
# Example script for using semantic-code-search with tree-sitter CLI
#
# This script demonstrates how to:
# 1. Generate tree-sitter parse outputs for Python files
# 2. Use Examples/example.json as input
# 3. Generate embeddings
# 4. Query the codebase
#
# Prerequisites:
# - tree-sitter CLI installed (npm install tree-sitter-cli)
# - semantic-code-search installed (pip3 install -e .)
# - This script should be run from the repository root

set -e  # Exit on error

# Configuration
REPO_ROOT="$(pwd)"
BUILD_DIR="${REPO_ROOT}/build"
INPUT_JSON="${REPO_ROOT}/Examples/example.json"
# Note: Database is automatically stored at ~/.local/share/semantic_code_search/

echo "=== Step 1: Generate tree-sitter output files ==="
mkdir -p "${BUILD_DIR}"

# Generate tree-sitter parse outputs for Python files
echo "Parsing Python files with tree-sitter..."
npx tree-sitter parse src/semantic_code_search/__init__.py > "${BUILD_DIR}/__init__.py.tree-sitter" || echo "Warning: Failed to parse __init__.py"
npx tree-sitter parse src/semantic_code_search/cli.py > "${BUILD_DIR}/cli.py.tree-sitter" || echo "Warning: Failed to parse cli.py"
npx tree-sitter parse src/semantic_code_search/cluster.py > "${BUILD_DIR}/cluster.py.tree-sitter" || echo "Warning: Failed to parse cluster.py"
npx tree-sitter parse src/semantic_code_search/embed.py > "${BUILD_DIR}/embed.py.tree-sitter" || echo "Warning: Failed to parse embed.py"
npx tree-sitter parse src/semantic_code_search/prompt.py > "${BUILD_DIR}/prompt.py.tree-sitter" || echo "Warning: Failed to parse prompt.py"
npx tree-sitter parse src/semantic_code_search/query.py > "${BUILD_DIR}/query.py.tree-sitter" || echo "Warning: Failed to parse query.py"
npx tree-sitter parse src/semantic_code_search/tree_parser.py > "${BUILD_DIR}/tree_parser.py.tree-sitter" || echo "Warning: Failed to parse tree_parser.py"

echo ""
echo "=== Step 2: Using JSON input file ==="
echo "Using ${INPUT_JSON}"
echo ""

echo "=== Step 3: Generate embeddings ==="
echo "Running: sem --embed --input-json ${INPUT_JSON}"
echo "Note: Embeddings are stored at ~/.local/share/semantic_code_search/"
sem --embed --input-json "${INPUT_JSON}"

echo ""
echo "=== Step 4: Query example ==="
echo "Example query: 'command line argument parsing'"
echo "Running: sem --query 'command line argument parsing'"
echo ""
sem --query "command line argument parsing"

echo ""
echo "=== Done! ==="
echo "You can now query your codebase with:"
echo "  sem --query 'your query here'"
echo ""
echo "To restrict search to specific files, use --filter-json:"
echo "  sem --query 'your query' --filter-json Examples/example.json"

