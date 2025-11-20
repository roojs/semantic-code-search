import gzip
import json
import os
import sys
import pickle
from typing import List

import numpy as np
from tqdm import tqdm

from semantic_code_search.tree_parser import extract_functions_from_tree


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
    
    functions = _get_functions_from_tree_sitter_files(args.input_json, nodes_to_extract)
    
    # Get config from JSON
    with open(args.input_json, 'r') as f:
        config = json.load(f)
    
    # Override model_name and batch_size from JSON if present
    if 'model_name' in config:
        args.model_name_or_path = config['model_name']
    if 'batch_size' in config:
        args.batch_size = config['batch_size']

    if not functions:
        print('No functions found. Exiting', file=sys.stderr)
        sys.exit(1)

    print('Embedding {} functions in {} batches. This is done once and cached in database'.format(
        len(functions), int(np.ceil(len(functions)/args.batch_size))))
    corpus_embeddings = model.encode(
        [f['text'] for f in functions], convert_to_tensor=True, show_progress_bar=True, batch_size=args.batch_size)

    dataset = {'functions': functions,
               'embeddings': corpus_embeddings, 'model_name': args.model_name_or_path}
    
    # Use database path from args (required)
    with gzip.open(args.database, 'w') as f:
        f.write(pickle.dumps(dataset))
    return dataset
