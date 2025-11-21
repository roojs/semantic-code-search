import os
import sys

import faiss
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from textwrap import indent

from semantic_code_search.embed import do_embed
from semantic_code_search.faiss_storage import (
    load_index, load_metadata, get_all_functions, get_db_path
)


def _read_function_text(file_path: str, line: int) -> str:
    """Read function text from source file at given line."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()
        
        # Read a reasonable amount of context around the function
        start_line = max(0, line)
        end_line = min(len(file_lines), start_line + 50)  # Read up to 50 lines
        
        return ''.join(file_lines[start_line:end_line]).rstrip()
    except Exception:
        return f"# Could not read file: {file_path}"


def _extract_embeddings_from_faiss(index: faiss.Index, functions: list) -> np.ndarray:
    """Extract embeddings from FAISS index for given functions."""
    if not functions:
        return np.zeros((0, index.d), dtype='float32')
    
    dimension = index.d
    
    # Reconstruct vectors from index
    embeddings = []
    valid_functions = []
    for func in functions:
        vector_id = func.get('vector_id')
        if vector_id is None:
            continue
        try:
            vec = np.zeros(dimension, dtype='float32')
            index.reconstruct(int(vector_id), vec)
            embeddings.append(vec)
            valid_functions.append(func)
        except Exception as e:
            # Vector might have been removed, skip it
            continue
    
    return np.array(embeddings) if embeddings else np.zeros((0, dimension), dtype='float32')


def _get_clusters(index: faiss.Index, functions: list, distance_threshold: float):
    """Get clusters from FAISS index."""
    if not functions:
        return []
    
    # Extract embeddings
    embeddings = _extract_embeddings_from_faiss(index, functions)
    
    # Normalize the embeddings to unit length
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    clustering_model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        compute_distances=True,
    )
    clustering_model.fit(embeddings)
    cluster_assignment = clustering_model.labels_
    cluster_distances = clustering_model.distances_
    cluster_children = clustering_model.children_

    clustered_functions = {}
    for idx, cluster_id in enumerate(cluster_assignment):
        if cluster_id not in clustered_functions:
            clustered_functions[cluster_id] = []

        ds_entry = functions[idx].copy()
        ds_entry['idx'] = idx

        clustered_functions[cluster_id].append(ds_entry)

    # filter out clusters with only one function
    clusters = []
    for cluster_id, funcs in clustered_functions.items():
        if len(funcs) > 1:
            fx_idx = funcs[0].get('idx')
            distances = []
            for f in funcs[1:]:
                f_idx = f.get('idx')
                for i, cc in enumerate(cluster_children):
                    if cc.tolist() == [fx_idx, f_idx]:
                        distances.append(cluster_distances[i])
            avg_distance = sum(distances) / \
                len(distances) if len(distances) > 0 else 0
            clusters.append(
                {'avg_distance': avg_distance, 'functions': funcs})

    return clusters


def do_cluster(args, model):
    # Load index and metadata
    index = load_index()
    if index is None:
        db_path = get_db_path()
        print('Database not found at {}. Generating embeddings now.'.format(db_path))
        do_embed(args, model)
        index = load_index()
        if index is None:
            print('Error: Failed to create index', file=sys.stderr)
            sys.exit(1)

    metadata = load_metadata()
    if metadata.get('model_name') != args.model_name_or_path:
        print('Model name mismatch. Regenerating embeddings.')
        do_embed(args, model)
        index = load_index()
        metadata = load_metadata()
    
    # Get all functions
    functions = get_all_functions()
    if not functions:
        print('No functions found in index', file=sys.stderr)
        sys.exit(1)
    
    # Get clusters
    clusters = _get_clusters(index, functions, args.cluster_max_distance)

    filtered_clusters = []
    for c in clusters:
        if args.cluster_ignore_identincal and c.get('avg_distance') == 0:
            continue
        
        # Read text from files to check line count
        functions_with_text = []
        for f in c.get('functions', []):
            file_path = f.get('file', '')
            line = f.get('line', 0)
            text = _read_function_text(file_path, line)
            func_with_text = f.copy()
            func_with_text['text'] = text
            functions_with_text.append(func_with_text)
        
        if any([len(f['text'].split('\n')) <= args.cluster_min_lines for f in functions_with_text]):
            continue
        if len(functions_with_text) < args.cluster_min_cluster_size:
            continue
        
        # Update cluster with functions that have text
        c['functions'] = functions_with_text
        filtered_clusters.append(c)

    for i, c in enumerate(filtered_clusters):
        print('Cluster #{}: avg_distance: {:.3} ================================================\n'.format(
            i, c.get('avg_distance')))
        for f in c.get('functions', []):
            print(indent(f.get('file', ''), '    ') + ':' + str(f.get('line', '')))
            print(indent(f.get('text', ''), '    ') + '\n')
