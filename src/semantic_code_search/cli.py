import argparse
import os
import sys
# from subprocess import run

# import torch
# from sentence_transformers import SentenceTransformer

# from semantic_code_search.embed import do_embed
# from semantic_code_search.query import do_query
# from semantic_code_search.cluster import do_cluster

# Force CPU usage to avoid CUDA out of memory errors
# torch.set_default_device('cpu')


# def git_root(path=None):
#     path_params = []
#     if path:
#         path_params = ['-C', path]
#     p = run(['git'] + path_params + ['rev-parse',
#             '--show-toplevel'], capture_output=True)
#     if p.returncode != 0:
#         if not path:
#             path = os.getcwd()
#         print('{} is not a git repo. Run this in a git repository or specify a path using the -p flag'.format(path))
#         sys.exit(1)
#     return p.stdout.decode('utf-8').strip()


# def embed_func(args):
#     # model = SentenceTransformer(args.model_name_or_path, device='cpu')
#     model = SentenceTransformer(args.model_name_or_path)
#     do_embed(args, model)


# def query_func(args):
#     # model = SentenceTransformer(args.model_name_or_path, device='cpu')
#     model = SentenceTransformer(args.model_name_or_path)
#     if len(args.query_text) > 0:
#         args.query_text = ' '.join(args.query_text)
#     else:
#         args.query_text = None
#     do_query(args, model)


# def cluster_func(args):
#     # model = SentenceTransformer(args.model_name_or_path, device='cpu')
#     model = SentenceTransformer(args.model_name_or_path)
#     do_cluster(args, model)


def main():
    parser = argparse.ArgumentParser(
        prog='sem', description='Search your codebase using natural language')
    parser.add_argument('-D', '--database', metavar='PATH', type=str, required=True,
                        help='Path to the embeddings database file (gzipped pickle file)')
    parser.add_argument('-m', '--model-name-or-path', metavar='MODEL', default='krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net',
                        type=str, required=False, help='Name or path of the model to use')
    parser.add_argument('-d', '--embed', action='store_true', default=False,
                        required=False, help='(Re)create the embeddings index for codebase')
    parser.add_argument('--input-json', metavar='JSON_FILE', type=str, required=False,
                        help='Path to JSON file with tree-sitter file references for embedding')
    parser.add_argument('-b', '--batch-size', metavar='BS',
                              type=int, default=32, help='Batch size for embeddings generation')

    parser.add_argument('-n', '--n-results', metavar='N', type=int,
                        required=False, default=5, help='Number of results to return')
    parser.add_argument('-c', '--cluster', action='store_true', default=False,
                        required=False, help='Generate clusters of code that is semantically similar. You can use this to spot near duplicates, results are simply printed to stdout')
    parser.add_argument('--cluster-max-distance', metavar='THRESHOLD', type=float, default=0.2, required=False,
                        help='How close functions need to be to one another to be clustered. Distance 0 means that the code is identical, smaller values (e.g. 0.2, 0.3) are stricter and result in fewer matches ')
    parser.add_argument('--cluster-min-lines', metavar='SIZE', type=int, default=0, required=False,
                        help='Ignore clusters with code snippets smaller than this size (lines of code). Use this if you are not interested in smaller duplications (eg. one liners)')
    parser.add_argument('--cluster-min-cluster-size', metavar='SIZE', type=int, default=2, required=False,
                        help='Ignore clusters smaller than this size. Use this if you want to find code that is similar and repeated many times (e.g. >5)')
    parser.add_argument('--cluster-ignore-identincal', action='store_true', default=True,
                        required=False, help='Ignore identical code / exact duplicates (where distance is 0)')
    # parser.set_defaults(func=query_func)
    parser.add_argument('query_text', nargs=argparse.REMAINDER)

    args = parser.parse_args()
    
    # Debug output
    print("=" * 60)
    print("Argument Parsing Results")
    print("=" * 60)
    print(f"sys.argv = {sys.argv}")
    print()
    print("Parsed arguments:")
    print("-" * 60)
    for key, value in vars(args).items():
        print(f"  {key:30} = {value}")
    print("-" * 60)
    print()
    
    if args.embed:
        print("Would call: embed_func(args)")
        # embed_func(args)
    elif args.cluster:
        print("Would call: cluster_func(args)")
        # cluster_func(args)
    else:
        print("Would call: query_func(args)")
        if args.query_text:
            query_text = ' '.join(args.query_text)
            print(f"Query text would be: {query_text}")
        # query_func(args)


if __name__ == '__main__':
    main()
