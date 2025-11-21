import json
import os
import sys
from typing import List

import numpy as np
import torch
from tqdm import tqdm

from semantic_code_search.tree_parser import extract_functions_from_tree
from semantic_code_search.faiss_storage import (
    get_or_create_index, save_index, add_file_vectors, remove_file_vectors,
    normalize_path, load_metadata, is_file_unchanged, prune_orphaned_vectors
)


def _get_functions_from_tree_sitter_files(json_input_path: str, relevant_node_types: List[str]):
    """
    Read functions from tree-sitter output files specified in JSON input.
    
    JSON format:
    {
        "files": [
            {"path": "/path/to/file.py", "tree_sitter_file": "/path/to/file.py.tree-sitter"},
            ...
        ],
        "repo_root": "/repo/root",
        "model_name": "...",
        "batch_size": 32
    }
    """
    with open(json_input_path, 'r') as f:
        config = json.load(f)
    
    # Resolve paths relative to current working directory (repo root)
    # Paths in JSON are assumed to be relative to where the command is run from
    files = config.get('files', [])
    functions = []
    
    print('Extracting functions from {} files'.format(len(files)))
    for file_info in tqdm(files):
        file_path = file_info.get('path')
        tree_sitter_file = file_info.get('tree_sitter_file')
        
        if not file_path or not tree_sitter_file:
            continue
        
        # Resolve relative paths relative to current working directory
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        if not os.path.isabs(tree_sitter_file):
            tree_sitter_file = os.path.abspath(tree_sitter_file)
        
        # Normalize paths
        file_path = os.path.normpath(file_path)
        tree_sitter_file = os.path.normpath(tree_sitter_file)
        
        if not os.path.isfile(file_path):
            print('Warning: Source file not found: {}'.format(file_path), file=sys.stderr)
            continue
        
        if not os.path.isfile(tree_sitter_file):
            print('Warning: Tree-sitter output file not found: {}'.format(tree_sitter_file), file=sys.stderr)
            continue
        
        # Read source file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            print('Warning: Failed to read {}: {}'.format(file_path, e), file=sys.stderr)
            continue
        
        # Read tree-sitter output
        try:
            with open(tree_sitter_file, 'r', encoding='utf-8') as f:
                tree_sitter_output = f.read()
        except Exception as e:
            print('Warning: Failed to read {}: {}'.format(tree_sitter_file, e), file=sys.stderr)
            continue
        
        # Extract functions using tree parser
        file_functions = extract_functions_from_tree(
            tree_sitter_output, file_path, file_content, relevant_node_types
        )
        functions.extend(file_functions)
    
    return functions


def do_embed(args, model):
    nodes_to_extract = ['function_definition', 'method_definition',
                        'function_declaration', 'method_declaration']
    
    # Require input_json for embedding
    if not hasattr(args, 'input_json') or not args.input_json:
        print('Error: --input-json is required for embedding', file=sys.stderr)
        sys.exit(1)
    
    # Get config from JSON
    with open(args.input_json, 'r') as f:
        config = json.load(f)
    
    # Override model_name and batch_size from JSON if present
    if 'model_name' in config:
        args.model_name_or_path = config['model_name']
    if 'batch_size' in config:
        args.batch_size = config['batch_size']
    
    # Get embedding dimension from model
    # Create a dummy embedding to get the dimension
    dummy_embedding = model.encode(['dummy'], convert_to_tensor=True)
    dimension = dummy_embedding.shape[1]
    
    # Get or create FAISS index
    index, metadata = get_or_create_index(dimension, args.model_name_or_path)
    
    # Prune orphaned vectors (vectors without corresponding metadata)
    # This cleans up any vectors from files that were removed but not properly cleaned up
    if index.ntotal > 0:
        pruned_count = prune_orphaned_vectors(index)
        if pruned_count > 0:
            # Reload metadata after pruning
            metadata = load_metadata()
            # Save the cleaned index
            save_index(index)
    
    # Process files from JSON
    files = config.get('files', [])
    if not files:
        print('No files specified in input JSON', file=sys.stderr)
        sys.exit(1)
    
    # Track if any files actually need processing
    files_to_process = []
    skipped_count = 0
    
    # First pass: determine which files need processing
    for file_info in files:
        file_path = file_info.get('path')
        if not file_path:
            continue
        
        # Normalize file path
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        file_path = normalize_path(file_path)
        
        if not os.path.isfile(file_path):
            print('Warning: Source file not found: {}'.format(file_path), file=sys.stderr)
            continue
        
        # Check if file already exists in index (incremental update)
        if file_path in metadata['file_to_meta']:
            # Check if file has changed
            file_changed = not is_file_unchanged(file_path)
            force_update = hasattr(args, 'update') and args.update
            
            if not file_changed and not force_update:
                skipped_count += 1
                continue
        
        files_to_process.append(file_info)
    
    if not files_to_process:
        print('All {} files are up to date. Nothing to process.'.format(len(files)))
        if skipped_count > 0:
            print('(Use --update to force update of unchanged files)')
        return {'index': index, 'metadata': metadata}
    
    print('Processing {} files ({} skipped as unchanged)'.format(
        len(files_to_process), skipped_count))
    
    # Process files that need updating
    for file_info in tqdm(files_to_process, desc='Processing files'):
        file_path = file_info.get('path')
        tree_sitter_file = file_info.get('tree_sitter_file')
        
        # Normalize file path (already done in first pass, but ensure it's normalized)
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        file_path = normalize_path(file_path)
        
        # Remove old vectors if file exists in index (will be replaced with new ones)
        if file_path in metadata['file_to_meta']:
            file_changed = not is_file_unchanged(file_path)
            force_update = hasattr(args, 'update') and args.update
            
            if file_changed:
                print('File {} has changed, updating...'.format(file_path))
            elif force_update:
                print('Force updating file: {} (--update flag)'.format(file_path))
            
            remove_file_vectors(index, file_path)
            metadata = load_metadata()  # Reload after removal
        
        # Read tree-sitter output if provided
        if tree_sitter_file:
            if not os.path.isabs(tree_sitter_file):
                tree_sitter_file = os.path.abspath(tree_sitter_file)
            tree_sitter_file = normalize_path(tree_sitter_file)
            
            if not os.path.isfile(tree_sitter_file):
                print('Warning: Tree-sitter output file not found: {}'.format(tree_sitter_file), file=sys.stderr)
                continue
            
            # Read tree-sitter output
            try:
                with open(tree_sitter_file, 'r', encoding='utf-8') as f:
                    tree_sitter_output = f.read()
            except Exception as e:
                print('Warning: Failed to read {}: {}'.format(tree_sitter_file, e), file=sys.stderr)
                continue
        else:
            # No tree-sitter file provided, skip this file
            print('Warning: No tree_sitter_file specified for {}, skipping'.format(file_path), file=sys.stderr)
            continue
        
        # Read source file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            print('Warning: Failed to read {}: {}'.format(file_path, e), file=sys.stderr)
            continue
        
        # Extract functions using tree parser
        file_functions = extract_functions_from_tree(
            tree_sitter_output, file_path, file_content, nodes_to_extract
        )
        
        if not file_functions:
            continue
        
        # Generate embeddings for this file's functions
        function_texts = [f['text'] for f in file_functions]
        file_embeddings = model.encode(
            function_texts, convert_to_tensor=True, show_progress_bar=False, batch_size=args.batch_size
        )
        
        # Add vectors to index
        add_file_vectors(index, file_embeddings, file_path, file_functions, args.model_name_or_path)
        metadata = load_metadata()  # Reload after addition
    
    # Save the index
    save_index(index)
    print('Embeddings saved successfully')
    
    return {'index': index, 'metadata': metadata}
