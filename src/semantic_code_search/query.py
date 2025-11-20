import gzip
import os
import pickle
import sys

import torch
from sentence_transformers import util

from semantic_code_search.embed import do_embed


def _search(query_embedding, corpus_embeddings, functions, k=5):
    cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    top_results = torch.topk(cos_scores, k=min(k, len(cos_scores)), sorted=True)
    out = []
    for score, idx in zip(top_results[0], top_results[1]):
        out.append((score, functions[idx]))
    return out


def _query_embeddings(model, args):
    with gzip.open(args.database, 'r') as f:
        dataset = pickle.loads(f.read())
        if dataset.get('model_name') != args.model_name_or_path:
            print('Model name mismatch. Regenerating embeddings.', file=sys.stderr)
            dataset = do_embed(args, model)
        query_embedding = model.encode(args.query_text, convert_to_tensor=True)
        results = _search(query_embedding, dataset.get(
            'embeddings'), dataset.get('functions'), k=args.n_results)
        return results


def query_to_markdown(query_text: str, model, args) -> str:
    """
    Query embeddings and return results as markdown string.
    
    Returns markdown formatted results optimized for LLM consumption.
    """
    if not query_text:
        return ""
    
    if not os.path.isfile(args.database):
        return "# Error\n\nDatabase not found. Please generate embeddings first.\n"
    
    with gzip.open(args.database, 'r') as f:
        dataset = pickle.loads(f.read())
        if dataset.get('model_name') != args.model_name_or_path:
            return "# Error\n\nModel name mismatch. Please regenerate embeddings.\n"
    
    query_embedding = model.encode(query_text, convert_to_tensor=True)
    results = _search(query_embedding, dataset.get('embeddings'), 
                     dataset.get('functions'), k=args.n_results)
    
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
            # Fallback to stored text if file can't be read
            context_text = func_info['text']
            start_line_1indexed = match_line_1indexed
            end_line_1indexed = match_line_1indexed
        
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
