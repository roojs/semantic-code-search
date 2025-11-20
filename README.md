# Semantic Code Search

> Originally based on [semantic-code-search](https://github.com/sturdy-dev/semantic-code-search)

A command-line tool for searching codebases using natural language queries. This tool uses machine learning embeddings to find semantically similar code functions and methods based on natural language descriptions.

## About This Fork

This version has been refactored to use the **tree-sitter CLI** instead of Python bindings, making it easier to deploy and avoiding issues with tree-sitter Python package builds. The tool now accepts tree-sitter parse output files via JSON configuration, making it more flexible and easier to integrate with other tools.

For more details about semantic code search in general, see [README.old.md](README.old.md) or the [original codebase](https://github.com/sturdy-dev/semantic-code-search).

## What This Tool Does

`semantic-code-search` allows you to search your codebase using natural language queries instead of exact text matching. For example, you can ask:

- "Where are API requests authenticated?"
- "Saving user objects to the database"
- "Handling of webhook events"
- "Where are jobs read from the queue?"

The tool uses a transformer-based neural network model to generate embeddings (numerical representations) of code functions and your query, then finds the most semantically similar matches using cosine similarity.

**Key Features:**
- Natural language code search - no need for exact keyword matching
- Extracts function and method definitions from source code
- Generates embeddings using sentence transformers
- All processing happens locally - no data leaves your computer
- Outputs results in markdown format for easy consumption

---

# Usage Guide: Using semantic-code-search with tree-sitter CLI

This guide explains how to use `semantic-code-search` with the tree-sitter command-line tool.

## Prerequisites

1. **Install PyTorch** (if you don't have a GPU capable of running PyTorch):
   ```bash
   pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   ```

2. **Install tree-sitter CLI**:
   ```bash
   npm install tree-sitter-cli
   ```

3. **Install tree-sitter language parsers**:
   
   Set up tree-sitter to use local language parsers:
   
   ```bash
   # Step 1: Initialize tree-sitter config
   npx tree-sitter init-config
   
   # Step 2: Create directory for language parsers
   mkdir -p ~/.local/share/tree-sitter
   
   # Step 3: Clone language parsers into that directory
   cd ~/.local/share/tree-sitter
   git clone https://github.com/tree-sitter/tree-sitter-python
   
   # Step 4: Build each parser
   cd tree-sitter-python
   npx tree-sitter generate
   cd ..
   
   # Repeat for other languages you need
   # git clone https://github.com/tree-sitter/tree-sitter-javascript
   # cd tree-sitter-javascript
   # npx tree-sitter generate
   # cd ..
   ```
   
   **Important**: Modify your local tree-sitter config (created by `init-config`) to point to `~/.local/share/tree-sitter` instead of individual language subdirectories.
   
   The config file (typically `~/.config/tree-sitter/config.json`) should list the directory containing your language parsers. For example:
   
   ```json
   {
     "parser-directories": [
       "/home/alan/.local/share/tree-sitter", 
     ]
   }
   ```
   
   This tells tree-sitter where to find the language parsers you've cloned and built. After setting this up, you can use `npx tree-sitter parse` from any directory.
   
   See the [List of parsers](https://github.com/tree-sitter/tree-sitter/wiki/List-of-parsers) for available language parsers and their repository URLs.
   
   Once set up, you can use `npx tree-sitter parse` from any directory to parse files in supported languages.

## Installation

Clone the repository and install semantic-code-search:

```bash
git clone https://github.com/roojais/semantic-code-search
cd semantic-code-search

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
2. Create a JSON input file (`build/files.json`) with relative file references
3. Generate embeddings using `sem embed --input-json build/files.json --database build/semantic.db`
4. Run an example query and output markdown results

All output files (tree-sitter outputs, JSON config, and database) are stored in the `build/` directory.

See `example.sh` for detailed comments explaining each step.

## Manual Workflow

### Step 1: Generate tree-sitter output files

Create a `build/` directory and generate tree-sitter parse outputs for each source file:

```bash
mkdir -p build

# Example: Parse a Python file
npx tree-sitter parse src/semantic_code_search/cli.py > build/cli.py.tree-sitter

# Parse multiple files
for file in src/semantic_code_search/*.py; do
    npx tree-sitter parse "$file" > "build/$(basename $file).tree-sitter"
done
```

**Note**: Make sure you have set up tree-sitter language parsers following the prerequisites above. Once configured, you can use `tree-sitter parse` from any directory to parse files in supported languages.

See the [List of parsers](https://github.com/tree-sitter/tree-sitter/wiki/List-of-parsers) for available language parsers.

### Step 2: Create JSON input file

Create a JSON file (e.g., `build/files.json`) that lists all source files and their corresponding tree-sitter output files. Paths are relative to the JSON file's directory:

```json
{
  "files": [
    {
      "path": "src/semantic_code_search/cli.py",
      "tree_sitter_file": "build/cli.py.tree-sitter"
    },
    {
      "path": "src/semantic_code_search/embed.py",
      "tree_sitter_file": "build/embed.py.tree-sitter"
    }
  ],
  "model_name": "krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net",
  "batch_size": 32
}
```

See `Examples/example.json` for a template.

### Step 3: Generate embeddings

Run the embedding command with the JSON input file and database path:

```bash
sem embed --input-json build/files.json --database build/semantic.db
```

This will:
- Read all source files and tree-sitter outputs specified in the JSON (paths resolved relative to JSON file)
- Extract function definitions
- Generate embeddings
- Save them to the specified database file (`build/semantic.db`)

**Exit codes**: 0 on success, non-zero on error (error messages go to stderr)

**Note**: The `--database` argument is required and specifies where to store/load the embeddings database.

### Step 4: Query the codebase

Query the codebase using natural language:

```bash
sem query "authentication logic" --database build/semantic.db
```

This will:
- Load the embeddings database from the specified path
- Search for code matching your query
- Output markdown-formatted results to stdout (default behavior)

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

- `example.sh` - Complete example script with comments showing the full workflow (run from repository root)
- `Examples/example.json` - Template JSON file showing the expected format with relative paths

## Troubleshooting

- **"Tree-sitter output file not found"**: Make sure you've generated the `.tree-sitter` files and the paths in your JSON are correct (relative paths are resolved relative to the JSON file's directory)
- **"No functions found"**: Check that tree-sitter is parsing your files correctly. Try running `npx tree-sitter parse` manually on a file
- **"Database not found"**: Make sure you've run `sem embed` first with the `--database` argument, or check that the database path is correct
- **"Error: --input-json is required for embedding"**: You must provide the `--input-json` argument when generating embeddings
- **"Error: --database is required"**: The `--database` argument is required for all operations (embed, query, cluster)

## Supported Languages

The tool extracts functions from these node types:
- `function_definition`
- `method_definition`
- `function_declaration`
- `method_declaration`

Make sure tree-sitter can parse your language and that these node types exist in the grammar.

