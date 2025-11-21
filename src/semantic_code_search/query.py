import json
import os
import sys

import faiss
import numpy as np
import torch

from semantic_code_search.faiss_storage import (
    load_index, load_metadata, load_file_metadata, get_filtered_vector_ids,
    normalize_path, get_all_functions
)


def _load_filter_files(filter_json_path: str) -> list:
    """Load and normalize file paths from filter JSON (same format as embed JSON)."""
    with open(filter_json_path, 'r') as f:
        config = json.load(f)
    
    files = config.get('files', [])
    normalized_files = []
    
    for file_info in files:
        file_path = file_info.get('path')
        if not file_path:
            continue
        
        # Normalize path (same as embed.py)
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        normalized_files.append(normalize_path(file_path))
    
    return normalized_files


def _search_faiss(query_embedding, index: faiss.Index, filter_files: list = None, 
                  filter_extensions: list = None, k=5):
    """Search FAISS index with optional file and extension filtering."""
    # Normalize query embedding
    query_np = query_embedding.cpu().numpy().astype('float32')
    query_np = query_np.reshape(1, -1)  # Ensure 2D
    faiss.normalize_L2(query_np)
    
    # Get all functions and create a mapping from vector_id to function
    all_functions = get_all_functions()
    if not all_functions:
        return []
    
    vector_id_to_function = {f['vector_id']: f for f in all_functions}
    
    # Normalize extensions (remove leading dots, make lowercase)
    normalized_exts = None
    if filter_extensions:
        normalized_exts = {ext.lstrip('.').lower() for ext in filter_extensions}
    
    # Build filter set if files are specified
    filter_set = set(filter_files) if filter_files else None
    
    # Build combined filter (files + extensions)
    if filter_set or normalized_exts:
        filter_vector_ids = set()
        for f in all_functions:
            # Check file filter
            if filter_set and f['file'] not in filter_set:
                continue
            
            # Check extension filter
            if normalized_exts:
                file_ext = os.path.splitext(f['file'])[1].lstrip('.').lower()
                if file_ext not in normalized_exts:
                    continue
            
            filter_vector_ids.add(f['vector_id'])
        
        if not filter_vector_ids:
            return []
    else:
        filter_vector_ids = None
    
    # Perform search - search all vectors to find valid ones
    # This is necessary because removed vectors may still score higher than valid ones
    # We'll filter to only valid vector IDs and then take top k
    
    # For IndexIDMap2, search the base index directly to avoid bug with removed vectors
    # Then map results through id_map
    if hasattr(index, 'index') and hasattr(index, 'id_map'):
        # Search base index directly (this works correctly after removals)
        base_index = index.index
        search_k = base_index.ntotal
        distances, indices = base_index.search(query_np, search_k)
    else:
        # Fallback to normal search
        search_k = index.ntotal
        distances, indices = index.search(query_np, search_k)
    
    # Map results back to functions, filtering out invalid vector IDs
    results = []
    
    for dist, idx in zip(distances[0], indices[0]):
        # Filter out invalid indices immediately
        idx_int = int(idx)
        if idx_int < 0:
            continue
        
        # For IndexIDMap2, idx is the position in the base index, need to get the actual vector ID
        try:
            if hasattr(index, 'id_map') and hasattr(index.id_map, 'at'):
                # Check bounds - idx should be < ntotal
                if idx_int >= index.ntotal:
                    continue
                actual_id = int(index.id_map.at(idx_int))
            else:
                # Fallback: assume sequential IDs
                if idx_int >= index.ntotal:
                    continue
                actual_id = idx_int
        except (AttributeError, IndexError, ValueError, RuntimeError) as e:
            # RuntimeError can occur if id_map access is out of bounds
            # Skip this result and continue
            continue
        
        # Skip if vector ID doesn't exist in our metadata (removed vectors)
        if actual_id not in vector_id_to_function:
            continue
        
        # Apply combined filter if specified
        if filter_vector_ids is not None and actual_id not in filter_vector_ids:
            continue
        
        func = vector_id_to_function[actual_id]
        score = float(dist)
        
        results.append((score, {
            'file': func['file'],
            'line': func['line']
        }))
        
        # Stop once we have enough results
        if len(results) >= k:
            break
    
    # Sort by score descending (should already be sorted, but ensure it)
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:k]


def _query_embeddings(model, args):
    """Query FAISS index with optional file and language filtering."""
    # Load index and metadata
    index = load_index()
    if index is None:
        print('Error: No index found. Please generate embeddings first.', file=sys.stderr)
        sys.exit(1)
    
    metadata = load_metadata()
    if metadata.get('model_name') != args.model_name_or_path:
        print('Error: Model name mismatch. Expected {}, found {}. Please regenerate embeddings.'.format(
            args.model_name_or_path, metadata.get('model_name')), file=sys.stderr)
        sys.exit(1)
    
    # Load filter files if specified
    filter_files = None
    if hasattr(args, 'filter_json') and args.filter_json:
        filter_files = _load_filter_files(args.filter_json)
        print('Filtering search to {} files'.format(len(filter_files)))
    
    # Parse language extensions if specified
    filter_extensions = None
    if hasattr(args, 'lang') and args.lang:
        filter_extensions = [ext.strip() for ext in args.lang.split(',')]
        print('Filtering search to languages: {}'.format(', '.join(filter_extensions)))
    
    # Generate query embedding
    query_embedding = model.encode(args.query_text, convert_to_tensor=True)
    
    # Search
    results = _search_faiss(query_embedding, index, filter_files, filter_extensions, k=args.n_results)
    return results


def query_to_markdown(query_text: str, model, args) -> str:
    """
    Query embeddings and return results as markdown string.
    
    Returns markdown formatted results optimized for LLM consumption.
    """
    if not query_text:
        return ""
    
    # Load index and metadata
    index = load_index()
    if index is None:
        return "# Error\n\nDatabase not found. Please generate embeddings first.\n"
    
    metadata = load_metadata()
    if metadata.get('model_name') != args.model_name_or_path:
        return "# Error\n\nModel name mismatch. Please regenerate embeddings.\n"
    
    # Load filter files if specified
    filter_files = None
    if hasattr(args, 'filter_json') and args.filter_json:
        try:
            filter_files = _load_filter_files(args.filter_json)
        except Exception as e:
            return f"# Error\n\nFailed to load filter JSON: {e}\n"
    
    # Parse language extensions if specified
    filter_extensions = None
    if hasattr(args, 'lang') and args.lang:
        filter_extensions = [ext.strip() for ext in args.lang.split(',')]
    
    # Generate query embedding
    query_embedding = model.encode(query_text, convert_to_tensor=True)
    
    # Search
    results = _search_faiss(query_embedding, index, filter_files, filter_extensions, k=args.n_results)
    
    # Format as markdown
    markdown_lines = ["# Search Results\n"]
    
    for i, (score, func_info) in enumerate(results, 1):
        file_path = func_info['file']
        match_line_0indexed = func_info['line']  # 0-indexed
        match_line_1indexed = match_line_0indexed + 1  # Convert to 1-indexed
        
        # Determine language for code block
        lang = ""
        if file_path.endswith('.py'):
            lang = "python"
        elif file_path.endswith('.js'):
            lang = "javascript"
        elif file_path.endswith('.ts'):
            lang = "typescript"
        elif file_path.endswith('.go'):
            lang = "go"
        elif file_path.endswith('.rs'):
            lang = "rust"
        elif file_path.endswith('.java'):
            lang = "java"
        elif file_path.endswith('.rb'):
            lang = "ruby"
        elif file_path.endswith('.php'):
            lang = "php"
        elif file_path.endswith(('.c', '.h')):
            lang = "c"
        elif file_path.endswith(('.cpp', '.hpp')):
            lang = "cpp"
        elif file_path.endswith(('.kt', '.kts', '.ktm')):
            lang = "kotlin"
        elif file_path.endswith(('.vala', '.vapi')):
            lang = "vala"
        
        # Read the source file to extract 5 lines around the match
        # Show lines: match_line-2, match_line-1, match_line, match_line+1, match_line+2
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_lines = f.readlines()
            
            # Calculate line range (0-indexed)
            start_line = max(0, match_line_0indexed - 2)
            end_line = min(len(file_lines), match_line_0indexed + 3)  # +3 because range is exclusive
            
            # Extract the 5 lines (or fewer if near start/end of file)
            context_lines = file_lines[start_line:end_line]
            context_text = ''.join(context_lines).rstrip()
            
            # Calculate 1-indexed line numbers for display
            start_line_1indexed = start_line + 1
            end_line_1indexed = end_line
            
        except Exception as e:
            # If file can't be read, skip this result
            print(f'Warning: Could not read file {file_path}: {e}', file=sys.stderr)
            continue
        
        markdown_lines.append(f"## Result {i} (score: {score:.3f})")
        markdown_lines.append(f"**File:** `{file_path}:{match_line_1indexed}`\n")
        markdown_lines.append(f"```{lang}:{start_line_1indexed}:{end_line_1indexed}")
        markdown_lines.append(context_text)
        markdown_lines.append("```\n")
    
    return "\n".join(markdown_lines)


def do_query(args, model):
    if not args.query_text:
        print('Error: provide a query', file=sys.stderr)
        sys.exit(1)
    
    query_text = ' '.join(args.query_text) if isinstance(args.query_text, list) else args.query_text
    markdown_output = query_to_markdown(query_text, model, args)
    print(markdown_output)
    sys.exit(0)
