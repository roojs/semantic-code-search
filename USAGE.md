# Usage Guide: Using semantic-code-search with tree-sitter CLI

This guide explains how to use `semantic-code-search` with the tree-sitter command-line tool instead of Python bindings.

## Prerequisites

1. **Install tree-sitter CLI**:
   ```bash
   # Using cargo (recommended)
   cargo install --locked tree-sitter-cli
   
   # Or using npm
   npm install -g tree-sitter-cli
   ```

2. **Install semantic-code-search**:
   ```bash
   pip install semantic-code-search
   ```

## Workflow

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

See `example.json` for a template.

### Step 3: Generate embeddings

Run the embedding command with the JSON input file:

```bash
sem embed --input-json input.json
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

## Complete Example

Here's a complete example using files in the current directory:

1. **Generate tree-sitter outputs**:
   ```bash
   cd /path/to/semantic-code-search
   mkdir -p tree-sitter-outputs
   
   for file in src/semantic_code_search/*.py; do
       tree-sitter parse "$file" > "tree-sitter-outputs/$(basename $file).tree-sitter"
   done
   ```

2. **Create input.json** (see `example.json` for template):
   ```bash
   # Edit example.json with correct absolute paths
   cp example.json input.json
   # Edit input.json with your paths
   ```

3. **Generate embeddings**:
   ```bash
   sem embed --input-json input.json
   ```

4. **Query**:
   ```bash
   sem query "command line argument parsing" --output-md --path-to-repo /path/to/semantic-code-search
   ```

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

