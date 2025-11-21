import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np


def get_db_path() -> Path:
    """Get the database storage path: ~/.local/share/semantic_code_search/"""
    home = Path.home()
    db_path = home / '.local' / 'share' / 'semantic_code_search'
    db_path.mkdir(parents=True, exist_ok=True)
    return db_path


def normalize_path(path: str) -> str:
    """Normalize a file path to absolute, normalized form."""
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    return os.path.normpath(path)


def get_file_hash(file_path: str) -> str:
    """Generate a hash for a file path to use as metadata filename."""
    normalized = normalize_path(file_path)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]


def compute_file_md5(file_path: str) -> str:
    """Compute MD5 hash of file contents."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


def get_file_mtime(file_path: str) -> float:
    """Get file modification time."""
    try:
        return os.path.getmtime(file_path)
    except Exception:
        return None


def is_file_unchanged(file_path: str) -> bool:
    """Check if file has changed since last embedding."""
    file_meta = load_file_metadata(file_path)
    if file_meta is None:
        return False
    
    stored_md5 = file_meta.get('file_md5')
    stored_mtime = file_meta.get('file_mtime')
    
    if stored_md5 is None and stored_mtime is None:
        return False
    
    # Check MD5 if available (more reliable)
    if stored_md5:
        current_md5 = compute_file_md5(file_path)
        if current_md5 != stored_md5:
            return False
    
    # Check mtime as backup
    if stored_mtime:
        current_mtime = get_file_mtime(file_path)
        if current_mtime is None or abs(current_mtime - stored_mtime) > 0.1:  # 0.1s tolerance
            return False
    
    return True


def get_files_dir() -> Path:
    """Get the path to the per-file metadata directory."""
    files_dir = get_db_path() / 'files'
    files_dir.mkdir(parents=True, exist_ok=True)
    return files_dir


def load_metadata() -> Dict:
    """Load the global metadata index.json file."""
    metadata_path = get_db_path() / 'index.json'
    if not metadata_path.exists():
        return {
            'file_to_meta': {},
            'next_vector_id': 0,
            'model_name': None,
            'version': 1
        }
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f'Error loading metadata: {e}', file=sys.stderr)
        sys.exit(1)


def save_metadata(metadata: Dict):
    """Save the global metadata index.json file."""
    metadata_path = get_db_path() / 'index.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def load_file_metadata(file_path: str) -> Optional[Dict]:
    """Load per-file metadata for a given file path."""
    normalized_path = normalize_path(file_path)
    metadata = load_metadata()
    
    if normalized_path not in metadata['file_to_meta']:
        return None
    
    meta_filename = metadata['file_to_meta'][normalized_path]
    meta_path = get_files_dir() / meta_filename
    
    if not meta_path.exists():
        return None
    
    try:
        with open(meta_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f'Error loading file metadata for {file_path}: {e}', file=sys.stderr)
        return None


def save_file_metadata(file_path: str, file_meta: Dict):
    """Save per-file metadata."""
    normalized_path = normalize_path(file_path)
    file_hash = get_file_hash(normalized_path)
    meta_filename = f'{file_hash}.json'
    meta_path = get_files_dir() / meta_filename
    
    with open(meta_path, 'w') as f:
        json.dump(file_meta, f)
    
    # Update global metadata
    metadata = load_metadata()
    metadata['file_to_meta'][normalized_path] = meta_filename
    save_metadata(metadata)


def delete_file_metadata(file_path: str):
    """Delete per-file metadata."""
    normalized_path = normalize_path(file_path)
    metadata = load_metadata()
    
    if normalized_path not in metadata['file_to_meta']:
        return
    
    meta_filename = metadata['file_to_meta'][normalized_path]
    meta_path = get_files_dir() / meta_filename
    
    if meta_path.exists():
        meta_path.unlink()
    
    del metadata['file_to_meta'][normalized_path]
    save_metadata(metadata)


def load_index() -> Optional[faiss.Index]:
    """Load the FAISS index from disk."""
    index_path = get_db_path() / 'index.faiss'
    if not index_path.exists():
        return None
    
    try:
        return faiss.read_index(str(index_path))
    except Exception as e:
        print(f'Error loading FAISS index: {e}', file=sys.stderr)
        return None


def create_index(dimension: int, model_name: str) -> faiss.Index:
    """Create a new empty FAISS index."""
    # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
    # Wrap with IndexIDMap2 to support arbitrary IDs and removal
    base_index = faiss.IndexFlatIP(dimension)
    index = faiss.IndexIDMap2(base_index)
    
    # Initialize metadata
    metadata = {
        'file_to_meta': {},
        'next_vector_id': 0,
        'model_name': model_name,
        'version': 1
    }
    save_metadata(metadata)
    
    return index


def save_index(index: faiss.Index):
    """Save the FAISS index to disk."""
    index_path = get_db_path() / 'index.faiss'
    faiss.write_index(index, str(index_path))


def get_or_create_index(dimension: int, model_name: str) -> Tuple[faiss.Index, Dict]:
    """Load existing index or create a new one."""
    metadata = load_metadata()
    index = load_index()
    
    # Check if we need to create a new index
    if index is None:
        index = create_index(dimension, model_name)
        metadata = load_metadata()  # Reload after creation
    elif metadata.get('model_name') != model_name:
        print(f'Warning: Model name mismatch. Expected {model_name}, found {metadata.get("model_name")}', file=sys.stderr)
        print('Creating new index with correct model.', file=sys.stderr)
        index = create_index(dimension, model_name)
        metadata = load_metadata()
    
    return index, metadata


def add_file_vectors(index: faiss.Index, embeddings: np.ndarray, file_path: str, 
                    functions: List[Dict], model_name: str) -> List[int]:
    """Add vectors for a file to the index and return vector IDs."""
    normalized_path = normalize_path(file_path)
    
    # Load metadata
    metadata = load_metadata()
    
    # Check if file already exists (should be removed first)
    if normalized_path in metadata['file_to_meta']:
        print(f'Warning: File {normalized_path} already exists in index. Removing old vectors first.', file=sys.stderr)
        remove_file_vectors(index, normalized_path)
        metadata = load_metadata()  # Reload after removal
    
    # Normalize embeddings for cosine similarity
    embeddings_np = embeddings.cpu().numpy() if hasattr(embeddings, 'cpu') else embeddings
    embeddings_np = embeddings_np.astype('float32')
    faiss.normalize_L2(embeddings_np)
    
    # Get starting vector ID
    start_id = metadata['next_vector_id']
    num_vectors = embeddings_np.shape[0]
    
    # Generate vector IDs
    vector_ids = np.array(list(range(start_id, start_id + num_vectors)), dtype=np.int64)
    
    # Add vectors to index with IDs (IndexIDMap2 supports this)
    index.add_with_ids(embeddings_np, vector_ids)
    
    # Compute file checksums for change detection
    file_md5 = compute_file_md5(normalized_path)
    file_mtime = get_file_mtime(normalized_path)
    
    # Save per-file metadata (without file path, stored in index.json key)
    # Only store line numbers as array - text can be read from source file when needed
    file_meta = {
        'vector_ids': vector_ids.tolist(),
        'function_lines': [f['line'] for f in functions],
        'file_md5': file_md5,
        'file_mtime': file_mtime
    }
    save_file_metadata(normalized_path, file_meta)
    
    # Reload metadata after save_file_metadata (it updates file_to_meta)
    metadata = load_metadata()
    
    # Update global metadata
    metadata['next_vector_id'] = int(start_id + num_vectors)
    metadata['model_name'] = model_name
    save_metadata(metadata)
    
    return vector_ids.tolist()


def remove_file_vectors(index: faiss.Index, file_path: str):
    """Remove vectors for a file from the index."""
    normalized_path = normalize_path(file_path)
    file_meta = load_file_metadata(normalized_path)
    
    if file_meta is None:
        return
    
    vector_ids = file_meta.get('vector_ids', [])
    if not vector_ids:
        return
    
    # Remove vectors from index (IndexIDMap2 supports remove_ids)
    try:
        index.remove_ids(np.array(vector_ids, dtype=np.int64))
    except Exception as e:
        print(f'Warning: Could not remove vectors from index: {e}', file=sys.stderr)
        print('Index may not support remove_ids. Consider rebuilding the index.', file=sys.stderr)
    
    # Delete file metadata
    delete_file_metadata(normalized_path)


def get_file_vector_ids(file_path: str) -> List[int]:
    """Get vector IDs for a file."""
    file_meta = load_file_metadata(file_path)
    if file_meta is None:
        return []
    return file_meta.get('vector_ids', [])


def get_filtered_vector_ids(filter_files: List[str]) -> List[int]:
    """Get all vector IDs for a list of files."""
    all_vector_ids = []
    for file_path in filter_files:
        normalized = normalize_path(file_path)
        vector_ids = get_file_vector_ids(normalized)
        all_vector_ids.extend(vector_ids)
    return all_vector_ids


def extract_embeddings_from_index(index: faiss.Index, vector_ids: List[int] = None) -> np.ndarray:
    """Extract embeddings from a FAISS index for given vector IDs."""
    if vector_ids is None:
        # Get all vector IDs from index
        if hasattr(index, 'id_map'):
            vector_ids = [index.id_map.at(i) for i in range(index.ntotal)]
        else:
            vector_ids = list(range(index.ntotal))
    
    dimension = index.d
    vectors = []
    
    # Reconstruct vectors (works for IndexIDMap2)
    for vid in vector_ids:
        vec = np.zeros(dimension, dtype='float32')
        try:
            index.reconstruct(int(vid), vec)
            vectors.append(vec)
        except Exception as e:
            # Vector might have been removed, skip it
            continue
    
    return np.array(vectors) if vectors else np.zeros((0, dimension), dtype='float32')


def get_all_functions() -> List[Dict]:
    """Get all functions from all files in the index."""
    metadata = load_metadata()
    all_functions = []
    
    for file_path in metadata['file_to_meta'].keys():
        file_meta = load_file_metadata(file_path)
        if file_meta is None:
            continue
        
        vector_ids = file_meta.get('vector_ids', [])
        function_lines = file_meta.get('function_lines', [])
        
        for i, line_num in enumerate(function_lines):
            if i < len(vector_ids):
                all_functions.append({
                    'file': file_path,
                    'line': line_num,
                    'vector_id': vector_ids[i]
                })
    
    return all_functions


def get_all_valid_vector_ids() -> set:
    """Get set of all vector IDs that have corresponding metadata."""
    all_functions = get_all_functions()
    return {f['vector_id'] for f in all_functions}


def prune_orphaned_vectors(index: faiss.Index) -> int:
    """
    Remove vectors from index that don't have corresponding metadata.
    Returns the number of orphaned vectors removed.
    """
    if not hasattr(index, 'id_map') or not hasattr(index, 'ntotal'):
        return 0
    
    valid_vector_ids = get_all_valid_vector_ids()
    orphaned_vector_ids = []
    
    # Check all positions in the index
    for i in range(index.ntotal):
        try:
            vector_id = int(index.id_map.at(i))
            if vector_id not in valid_vector_ids:
                orphaned_vector_ids.append(vector_id)
        except (AttributeError, IndexError, ValueError, RuntimeError):
            # Skip invalid positions
            continue
    
    if not orphaned_vector_ids:
        return 0
    
    # Remove orphaned vectors
    try:
        index.remove_ids(np.array(orphaned_vector_ids, dtype=np.int64))
        print(f'Removed {len(orphaned_vector_ids)} orphaned vectors from index', file=sys.stderr)
        return len(orphaned_vector_ids)
    except Exception as e:
        print(f'Warning: Could not remove orphaned vectors: {e}', file=sys.stderr)
        return 0

