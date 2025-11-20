# Usage Guide: Using semantic-code-search with tree-sitter CLI

This guide explains how to use `semantic-code-search` with the tree-sitter command-line tool instead of Python bindings.

## Prerequisites

1. **Install tree-sitter CLI**:
   ```bash
    sudo apt install tree-sitter-cli
   ```

2. **Install semantic-code-search**:
   ```bash
   # Install in development mode (editable install)
   pip3 install -e .
   ```

## Quick Start

The easiest way to get started is to use the provided example script:

```bash
# Run the example script from the repository root
./example.sh
```

This script will:
1. Generate tree-sitter parse outputs for all Python files in `src/semantic_code_search/`
2. Create a JSON input file (`Examples/input.json`) with file references
3. Generate embeddings using `sem embed --input-json`
4. Run an example query and output markdown results

See `Examples/example.sh` for detailed comments explaining each step.

## Manual Workflow

### Step 1: Generate tree-sitter output files

For each source file you want to index, generate a tree-sitter parse output file:

```bash
# Example: Parse a Python file
tree-sitter parse src/semantic_code_search/cli.py > src/semantic_code_search/cli.py.tree-sitter

# Parse multiple files (example script)
for file in src/semantic_code_search/*.py; do
    tree-sitter parse "$file" > "${file}.tree-sitter"
done
```

**Note**: Make sure tree-sitter has the language grammar installed. For Python, you may need:
```bash
tree-sitter build
```

### Step 2: Create JSON input file

Create a JSON file (e.g., `input.json`) that lists all source files and their corresponding tree-sitter output files:

```json
{
  "files": [
    {
      "path": "/absolute/path/to/src/semantic_code_search/cli.py",
      "tree_sitter_file": "/absolute/path/to/src/semantic_code_search/cli.py.tree-sitter"
    },
    {
      "path": "/absolute/path/to/src/semantic_code_search/embed.py",
      "tree_sitter_file": "/absolute/path/to/src/semantic_code_search/embed.py.tree-sitter"
    }
  ],
  "repo_root": "/absolute/path/to/repo",
  "model_name": "krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net",
  "batch_size": 32
}
```

See `Examples/example.json` for a template.

### Step 3: Generate embeddings

Run the embedding command with the JSON input file:

```bash
sem embed --input-json Examples/input.json
```

This will:
- Read all source files and tree-sitter outputs specified in the JSON
- Extract function definitions
- Generate embeddings
- Save them to `.embeddings` in the `repo_root` directory

**Exit codes**: 0 on success, non-zero on error (error messages go to stderr)

### Step 4: Query the codebase

Query the codebase using natural language:

```bash
sem query "authentication logic" --output-md --path-to-repo /path/to/repo
```

This will:
- Load the `.embeddings` file from the repo root
- Search for code matching your query
- Output markdown-formatted results to stdout

**Markdown output format**:
```markdown
# Search Results

## Result 1 (score: 0.85)
**File:** `/path/to/auth.py:42`

```python
def authenticate_user(...):
    ...
```

## Result 2 (score: 0.82)
**File:** `/path/to/middleware.py:15`

```python
def check_auth(...):
    ...
```
```


## Example Files

- `Examples/example.sh` - Complete example script with comments showing the full workflow
- `Examples/example.json` - Template JSON file showing the expected format

## Troubleshooting

- **"Tree-sitter output file not found"**: Make sure you've generated the `.tree-sitter` files and the paths in your JSON are correct (use absolute paths)
- **"No functions found"**: Check that tree-sitter is parsing your files correctly. Try running `tree-sitter parse` manually on a file
- **"Embeddings not found"**: Make sure you've run `sem embed` first, or check that the `repo_root` path is correct

## Supported Languages

The tool extracts functions from these node types:
- `function_definition`
- `method_definition`
- `function_declaration`
- `method_declaration`

Make sure tree-sitter can parse your language and that these node types exist in the grammar.

