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
- FAISS vector database for fast similarity search
- Incremental updates - update individual files without full rebuild
- Multi-project support - store embeddings from multiple projects in one index
- Query filtering - restrict search to specific files using JSON configuration
- Language filtering - restrict search by file extension (e.g., `.py`, `.js`)
- All processing happens locally - no data leaves your computer
- Outputs results in markdown format for easy consumption

---

## How It Works

### Architecture Overview

The tool uses a **FAISS (Facebook AI Similarity Search) vector database** to store and search code embeddings efficiently. Here's how the system works:

#### 1. **Embedding Generation**

When you run `sem --embed`:
1. **Function Extraction**: Tree-sitter parses source files and extracts function/method definitions
2. **Embedding Creation**: Each function is converted to a dense vector (embedding) using a transformer model
3. **Storage**: Embeddings are stored in a FAISS index along with metadata

#### 2. **Storage Structure**

All data is stored at `~/.local/share/semantic_code_search/`:

```
~/.local/share/semantic_code_search/
├── index.faiss          # FAISS vector index (binary)
├── index.json           # Global metadata (pretty-printed)
│   ├── file_to_meta     # Maps file paths to metadata filenames
│   ├── next_vector_id    # Next available vector ID
│   ├── model_name        # Model used for embeddings
│   └── version           # Schema version
└── files/               # Per-file metadata (compact JSON)
    ├── <hash1>.json     # Metadata for file 1
    ├── <hash2>.json     # Metadata for file 2
    └── ...
```

**Per-file metadata** (`files/*.json`) contains:
- `vector_ids`: List of vector IDs for this file's functions
- `function_lines`: Array of line numbers where functions start (e.g., `[16, 30, 45]`)
- `file_md5`: MD5 hash of file contents (for change detection)
- `file_mtime`: File modification timestamp (for change detection)

**Note**: Function text is **not stored** in metadata - it's read directly from source files when needed. This keeps metadata files small and ensures results always reflect current source code.

#### 3. **Incremental Updates**

The system tracks file changes using **MD5 hashes** and **modification timestamps**:

- When embedding, files are checked against stored metadata
- If a file's MD5 hash and mtime match, it's skipped (no re-embedding needed)
- If a file has changed, its old vectors are removed and new ones are added
- Use `--update` to force re-embedding even if files haven't changed

This means:
- **Fast updates**: Only changed files are processed
- **Efficient storage**: No duplicate embeddings
- **Automatic cleanup**: Removed files are detected and their vectors are pruned

#### 4. **Multi-Project Support**

All projects share a **single FAISS index** with a **shared vector ID space**:

- Embeddings from multiple projects are stored in one index
- Each project's files are tracked separately in metadata
- Vector IDs are globally unique across all projects
- Querying searches all projects by default

**Benefits**:
- Cross-project code search (e.g., find similar patterns across repos)
- Efficient storage (single index file)
- Easy project management (add/remove projects by updating files)

#### 5. **Query Filtering**

You can restrict searches in two ways:

**File Filtering** (`--filter-json`):
- Provide a JSON file (same format as `--input-json`) listing specific files
- Only results from those files are returned
- Useful for searching within a specific project or subset of files

**Language Filtering** (`--lang`):
- Specify file extensions separated by commas (e.g., `--lang .py,.js`)
- Only results from files with matching extensions are returned
- Useful for searching within a specific language

**Example**:
```bash
# Search only Python files
sem --query "authentication" --lang .py

# Search only files listed in filter.json
sem --query "authentication" --filter-json filter.json

# Combine both (files in filter.json that are Python)
sem --query "authentication" --filter-json filter.json --lang .py
```

#### 6. **Search Process**

When you run `sem --query`:

1. **Query Embedding**: Your natural language query is converted to a vector using the same model
2. **FAISS Search**: FAISS performs fast nearest-neighbor search using cosine similarity
3. **Filtering**: Results are filtered by file/language if specified
4. **Text Retrieval**: Function text is read from source files (not from metadata)
5. **Formatting**: Results are formatted as markdown with syntax highlighting

**Why FAISS?**
- **Fast**: Optimized C++ implementation with efficient indexing
- **Scalable**: Handles millions of vectors efficiently
- **Accurate**: Uses cosine similarity for semantic matching
- **Local**: All processing happens on your machine

#### 7. **Vector ID Management**

The system uses FAISS's `IndexIDMap2` wrapper to manage vector IDs:

- Each function gets a unique vector ID (globally unique across all projects)
- IDs are stored in metadata, allowing efficient removal of individual vectors
- When files are removed, their vectors are automatically cleaned up
- Orphaned vectors (vectors without metadata) are pruned during embedding

This ensures the index stays synchronized with your source files.

---

# Usage Guide: Using semantic-code-search with tree-sitter CLI

This guide explains how to use `semantic-code-search` with the tree-sitter command-line tool.

## Prerequisites

1. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```
   
   Or install PyTorch separately (if you don't have a GPU capable of running PyTorch):
   ```bash
   pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   pip3 install faiss-cpu
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
2. Use the JSON input file (`Examples/example.json`) with relative file references
3. Generate embeddings using `sem --embed --input-json Examples/example.json`
4. Run an example query and output markdown results

Tree-sitter outputs are stored in the `build/` directory. Embeddings are automatically stored at `~/.local/share/semantic_code_search/`.

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

Run the embedding command with the JSON input file:

```bash
sem --embed --input-json build/files.json
```

Or use the short flag:

```bash
sem -d --input-json build/files.json
```

**Options:**
- `-d, --embed`: Generate embeddings (required for embedding mode)
- `--input-json PATH`: Path to JSON file with file references (required for embedding)
- `--update`: Incremental update mode - update only files specified in input-json (default: skip existing files)
- `-m, --model-name-or-path MODEL`: Model to use (default: `krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net`)
- `-b, --batch-size N`: Batch size for embeddings (default: 32)
- `--gpu`: Use GPU instead of CPU (default: CPU)

**Example with GPU:**
```bash
sem --embed --input-json build/files.json --gpu
```

**Example with incremental update:**
```bash
sem --embed --input-json build/files.json --update
```

This will:
- Read all source files and tree-sitter outputs specified in the JSON (paths resolved relative to JSON file)
- Extract function definitions
- Generate embeddings using CPU (or GPU if `--gpu` is specified)
- Save them to `~/.local/share/semantic_code_search/` (fixed location, no need to specify)

**Exit codes**: 0 on success, non-zero on error (error messages go to stderr)

**Note**: Embeddings are stored at `~/.local/share/semantic_code_search/`. Files are processed incrementally - existing files are skipped unless `--update` is used.

### Step 4: Query the codebase

Query the codebase using natural language:

```bash
sem --query "authentication logic"
```

Or use the short flag:

```bash
sem -q "authentication logic"
```

**Options:**
- `-q, --query QUERY`: Query text to search for (required for query mode)
- `--filter-json PATH`: Optional JSON file (same format as input-json) to restrict search to specific files
- `--lang EXTENSIONS`: Comma-separated file extensions to filter by (e.g., `".py,.js"` or `"py,js"`)
- `-n, --n-results N`: Number of results to return (default: 5)
- `-m, --model-name-or-path MODEL`: Model to use (must match the model used for embedding)
- `--gpu`: Use GPU instead of CPU (default: CPU)

**Example with more results:**
```bash
sem --query "authentication logic" --n-results 10
```

**Example with file filtering:**
```bash
sem --query "authentication logic" --filter-json build/files.json
```

**Example with language filtering:**
```bash
sem --query "authentication logic" --lang .py
sem --query "authentication logic" --lang ".py,.js"
```

This will:
- Load the embeddings database from `~/.local/share/semantic_code_search/`
- Optionally filter to only search files specified in the filter JSON or by file extension
- Search for code matching your query
- Output markdown-formatted results to stdout

**Markdown output format**:
```markdown
# Search Results

## Result 1 (score: 0.411)
**File:** `/path/to/auth.py:42`

```python:40:44
def authenticate_user(...):
    ...
```

## Result 2 (score: 0.364)
**File:** `/path/to/middleware.py:15`

```python:13:17
def check_auth(...):
    ...
```
```

Each result shows:
- Score (cosine similarity, higher is better)
- File path and line number
- Code block with 5 lines of context (2 lines before, match line, 2 lines after)
- Language-specific syntax highlighting in the code block

### Step 5: Cluster similar code (optional)

Find clusters of semantically similar code:

```bash
sem --cluster
```

Or use the short flag:

```bash
sem -c
```

**Options:**
- `-c, --cluster`: Generate clusters (required for cluster mode)
- `--cluster-max-distance THRESHOLD`: Maximum distance for clustering (default: 0.2)
- `--cluster-min-lines SIZE`: Minimum lines of code to consider (default: 0)
- `--cluster-min-cluster-size SIZE`: Minimum cluster size (default: 2)
- `--cluster-ignore-identincal`: Ignore identical code (default: True)
- `-m, --model-name-or-path MODEL`: Model to use (must match the model used for embedding)
- `--gpu`: Use GPU instead of CPU (default: CPU)

**Example:**
```bash
sem --cluster --cluster-max-distance 0.3 --cluster-min-lines 5
```

This will:
- Load the embeddings database from `~/.local/share/semantic_code_search/`
- Find clusters of similar code functions
- Print results to stdout showing groups of similar code


## Example Files

- `example.sh` - Complete example script with comments showing the full workflow (run from repository root)
- `Examples/example.json` - Template JSON file showing the expected format with relative paths

## Command Reference

### Common Options

Optional options available for all commands:
- `-m, --model-name-or-path MODEL`: Model to use (default: `krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net`)
- `--gpu`: Use GPU instead of CPU (default: CPU)

**Note**: All embeddings are stored at `~/.local/share/semantic_code_search/`. No database path needs to be specified.

### Embed Command

Generate embeddings from source files:

```bash
sem --embed --input-json PATH [OPTIONS]
```

**Required:**
- `-d, --embed`: Enable embedding mode
- `--input-json PATH`: JSON file with file references

**Optional:**
- `--update`: Incremental update mode - update files even if they already exist
- `-b, --batch-size N`: Batch size (default: 32)
- `-m, --model-name-or-path MODEL`: Model name/path
- `--gpu`: Use GPU

**Example:**
```bash
sem --embed --input-json Examples/example.json --batch-size 64
```

**Example with incremental update:**
```bash
sem --embed --input-json Examples/example.json --update
```

### Query Command

Search the codebase:

```bash
sem --query "QUERY TEXT" [OPTIONS]
```

**Required:**
- `-q, --query QUERY`: Query text

**Optional:**
- `--filter-json PATH`: JSON file (same format as input-json) to restrict search to specific files
- `--lang EXTENSIONS`: Comma-separated file extensions to filter by (e.g., `".py,.js"`)
- `-n, --n-results N`: Number of results (default: 5)
- `-m, --model-name-or-path MODEL`: Model name/path
- `--gpu`: Use GPU

**Example:**
```bash
sem --query "authentication logic" --n-results 10
```

**Example with file filtering:**
```bash
sem --query "authentication logic" --filter-json Examples/example.json
```

**Example with language filtering:**
```bash
sem --query "authentication logic" --lang .py
sem --query "authentication logic" --lang ".py,.js"
```

### Cluster Command

Find similar code clusters:

```bash
sem --cluster [OPTIONS]
```

**Required:**
- `-c, --cluster`: Enable cluster mode

**Optional:**
- `--cluster-max-distance THRESHOLD`: Max distance (default: 0.2)
- `--cluster-min-lines SIZE`: Min lines (default: 0)
- `--cluster-min-cluster-size SIZE`: Min cluster size (default: 2)
- `--cluster-ignore-identincal`: Ignore identical code (default: True)
- `-m, --model-name-or-path MODEL`: Model name/path
- `--gpu`: Use GPU

**Example:**
```bash
sem --cluster --cluster-max-distance 0.3
```

## Troubleshooting

- **"Tree-sitter output file not found"**: Make sure you've generated the `.tree-sitter` files and the paths in your JSON are correct (relative paths are resolved relative to the JSON file's directory)
- **"No functions found"**: Check that tree-sitter is parsing your files correctly. Try running `npx tree-sitter parse` manually on a file
- **"Database not found"** or **"No index found"**: Make sure you've run `sem --embed` first. The database is stored at `~/.local/share/semantic_code_search/`
- **"Error: --input-json is required for embedding"**: You must provide the `--input-json` argument when generating embeddings
- **"ModuleNotFoundError: No module named 'faiss'"**: Install FAISS with `pip3 install faiss-cpu` or `pip3 install -r requirements.txt`
- **CUDA/GPU errors**: If you get CUDA errors, make sure you have the correct PyTorch version installed for your GPU, or use CPU mode (default)
- **"Model name mismatch"**: The model used for querying must match the model used for embedding. Either use the same `--model-name-or-path` or regenerate embeddings
- **Files not updating**: Use `--update` flag when embedding to force update of existing files

## Supported Languages

The tool extracts functions from these node types:
- `function_definition`
- `method_definition`
- `function_declaration`
- `method_declaration`

Make sure tree-sitter can parse your language and that these node types exist in the grammar.

