<!-- 52ea5283-374d-48a4-b97e-2439c72a3cee e0ba6549-9e4e-49f8-b421-2d1abcc2adde -->
# FAISS Integration with Multi-Project Support

## Overview

Replace the current pickle-based storage with FAISS vector database and JSON metadata, enabling:

- Incremental file updates (add/remove single files without full rebuild)
- Multi-project support in a single index
- Query filtering via same JSON format used for embedding
- Per-file metadata storage for efficient updates
- Fixed storage location: `~/.local/semantic_code_search/`

## Database Structure

```
~/.local/semantic_code_search/
├── index.faiss              # Single FAISS index (all projects, all files)
├── index.json               # Global metadata index
└── files/                   # Per-file metadata
    ├── {file_hash}.json     # Individual file metadata (JSON, not pickle)
    └── ...
```

**index.json structure:**

```json
{
  "file_to_meta": {
    "/absolute/path/to/file1.py": "files/abc123.json",
    "/absolute/path/to/file2.py": "files/def456.json"
  },
  "next_vector_id": 10000,
  "model_name": "krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net",
  "version": 1
}
```

**Per-file metadata ({file_hash}.json):**

```json
{
  "vector_ids": [0, 1, 2],
  "functions": [
    {"line": 10, "text": "..."},
    {"line": 25, "text": "..."}
  ]
}
```

## Implementation Tasks

### 1. Add FAISS Dependency

- Update `requirements.txt` to include `faiss-cpu` (or `faiss-gpu` if GPU support needed)
- Update `pyproject.toml` if using setuptools

### 2. Create FAISS Storage Module (`src/semantic_code_search/faiss_storage.py`)

New module to handle FAISS index operations:

**Functions to implement:**

- `load_index(db_path)` - Load FAISS index and metadata
- `create_index(db_path, dimension, model_name)` - Create new empty index
- `add_file_vectors(index, embeddings, file_path, functions, metadata)` - Add vectors for a file
- `remove_file_vectors(index, file_path, metadata)` - Remove vectors for a file
- `get_file_vector_ids(file_path, metadata)` - Get vector IDs for a file
- `normalize_path(path)` - Normalize file paths consistently
- `get_file_hash(file_path)` - Generate hash for metadata filename

**Key implementation details:**

- Use `faiss.IndexFlatIP` for inner product (cosine similarity with normalized vectors)
- Normalize embeddings with `faiss.normalize_L2()` before adding
- Use shared vector ID space (single global counter)
- Store file paths as absolute normalized paths in index.json

### 3. Update Embed Module (`src/semantic_code_search/embed.py`)

**Modify `do_embed()` function:**

- Check if database exists and is FAISS format (check for `index.faiss` file)
- If old pickle format detected, migrate or error with migration instructions
- For each file in input JSON:
  - Check if file already exists in index
  - If exists: remove old vectors (incremental update)
  - Extract functions and generate embeddings
  - Add new vectors to FAISS index
  - Save per-file metadata
- Update global `index.json` with file mappings
- Save FAISS index

**Add new function:**

- `update_file_in_index(file_path, tree_sitter_file, args, model)` - Incremental update for single file

**Path normalization:**

- Use same normalization logic as current code (`os.path.abspath()` + `os.path.normpath()`)
- Store absolute normalized paths consistently

### 4. Update Query Module (`src/semantic_code_search/query.py`)

**Modify `query_to_markdown()` and `_query_embeddings()`:**

- Load FAISS index instead of pickle
- Load global metadata (`index.json`)
- If `--filter-json` provided:
  - Load filter JSON file
  - Extract list of files to search
  - Normalize filter file paths (absolute, normalized)
  - Get vector IDs for filtered files
  - Use `faiss.IDSelectorBatch` to restrict search (or post-filter results)
- Generate query embedding
- Search FAISS index
- Map vector IDs back to function metadata via per-file metadata files
- Return filtered results

**Add filtering logic:**

- `load_filter_files(filter_json_path)` - Load and normalize filter file paths
- `get_filtered_vector_ids(filter_files, metadata)` - Get vector IDs for filtered files
- `filter_search_results(results, filter_files)` - Post-filter if needed

**Filter JSON format:**

```json
{
  "files": [
    "/absolute/path/to/file1.py",
    "/absolute/path/to/file2.py"
  ]
}
```

### 5. Update CLI (`src/semantic_code_search/cli.py`)

**Add new arguments:**

- `--filter-json PATH` - Optional JSON file specifying files to search
- `--update` - Incremental update mode (update only files in input-json)

**Modify argument handling:**

- `--embed` mode: Support both full rebuild and incremental update
- `--query` mode: Support `--filter-json` for restricted search

### 6. Update Cluster Module (`src/semantic_code_search/cluster.py`)

**Modify `do_cluster()`:**

- Load FAISS index instead of pickle
- Load metadata and per-file metadata
- Extract embeddings from FAISS index
- Continue with existing clustering logic

### 7. Backward Compatibility

**Migration path:**

- Detect old pickle format (`.db` file without `index.faiss`)
- Provide migration utility or auto-migrate on first use
- Migration: Load pickle, create FAISS index, save new format

**Or:**

- Support both formats during transition
- Check file extension or magic bytes to determine format

### 8. Error Handling

**Add checks for:**

- FAISS index corruption
- Metadata file missing
- Vector ID mismatches
- File path normalization issues
- Filter JSON file format errors

## File Changes Summary

**New files:**

- `src/semantic_code_search/faiss_storage.py` - FAISS operations module

**Modified files:**

- `src/semantic_code_search/embed.py` - Use FAISS for storage
- `src/semantic_code_search/query.py` - Use FAISS for search, add filtering
- `src/semantic_code_search/cluster.py` - Use FAISS for clustering
- `src/semantic_code_search/cli.py` - Add `--filter-json` and `--update` flags
- `requirements.txt` - Add `faiss-cpu`

## Testing Considerations

- Test incremental updates (add file, modify file, remove file)
- Test query filtering with various filter JSON files
- Test multi-project scenarios
- Test backward compatibility/migration
- Test error cases (missing files, corrupted index)

## Performance Notes

- FAISS index is single file, all vectors
- Per-file metadata enables fast incremental updates
- Filtering via IDSelector is more efficient than post-filtering
- Consider using `IndexIVFFlat` or `IndexHNSWFlat` for very large indexes (>100K vectors)

### To-dos

- [ ] Add faiss-cpu to requirements.txt and update dependencies
- [ ] Create faiss_storage.py with core FAISS operations (load, create, add, remove vectors)
- [ ] Modify embed.py to use FAISS storage with incremental update support
- [ ] Modify query.py to use FAISS search and implement --filter-json filtering
- [ ] Add --filter-json and --update flags to cli.py
- [ ] Modify cluster.py to work with FAISS index
- [ ] Add migration path or dual-format support for old pickle databases