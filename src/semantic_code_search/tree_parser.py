import re
from typing import List, Dict, Tuple


class TreeNode:
    """Represents a node in the parsed tree-sitter S-expression tree."""
    def __init__(self, node_type: str, start_line: int = 0, start_col: int = 0, 
                 end_line: int = 0, end_col: int = 0, children: List['TreeNode'] = None):
        self.node_type = node_type
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = end_line
        self.end_col = end_col
        self.children = children or []

    def __repr__(self):
        return f"TreeNode({self.node_type}, {self.start_line}:{self.start_col}-{self.end_line}:{self.end_col})"


def parse_s_expression(s_expr: str) -> TreeNode:
    """
    Parse tree-sitter S-expression output into a TreeNode structure.
    
    Tree-sitter CLI output format:
    (node_type [start_line:start_col-end_line:end_col] (child1) (child2))
    
    Example:
    (source_file [0:0-10:0] (function_definition [1:0-5:0] ...))
    """
    s_expr = s_expr.strip()
    if not s_expr.startswith('('):
        raise ValueError("Invalid S-expression: must start with '('")
    
    return _parse_node(s_expr, 0)[0]


def _parse_node(s_expr: str, pos: int) -> Tuple[TreeNode, int]:
    """Parse a single node from S-expression, returns (node, next_position)."""
    # Skip opening parenthesis
    if s_expr[pos] != '(':
        raise ValueError(f"Expected '(' at position {pos}")
    pos += 1
    
    # Skip whitespace
    while pos < len(s_expr) and s_expr[pos] in ' \t\n':
        pos += 1
    
    if pos >= len(s_expr):
        raise ValueError("Unexpected end of S-expression")
    
    # Parse node type (until space, colon, bracket, or closing paren)
    node_type_end = pos
    while (node_type_end < len(s_expr) and 
           s_expr[node_type_end] not in ' \t\n():[]'):
        node_type_end += 1
    
    node_type = s_expr[pos:node_type_end]
    pos = node_type_end
    
    # Skip whitespace
    while pos < len(s_expr) and s_expr[pos] in ' \t\n':
        pos += 1
    
    # Parse position range [start_line:start_col-end_line:end_col] if present
    start_line, start_col, end_line, end_col = 0, 0, 0, 0
    if pos < len(s_expr) and s_expr[pos] == '[':
        pos += 1
        # Parse start_line:start_col-end_line:end_col
        match = re.match(r'(\d+):(\d+)-(\d+):(\d+)', s_expr[pos:])
        if match:
            start_line = int(match.group(1))
            start_col = int(match.group(2))
            end_line = int(match.group(3))
            end_col = int(match.group(4))
            pos += match.end()
        
        # Find closing bracket
        while pos < len(s_expr) and s_expr[pos] != ']':
            pos += 1
        if pos < len(s_expr):
            pos += 1
    
    # Skip whitespace
    while pos < len(s_expr) and s_expr[pos] in ' \t\n':
        pos += 1
    
    # Parse children
    children = []
    while pos < len(s_expr) and s_expr[pos] == '(':
        child, pos = _parse_node(s_expr, pos)
        children.append(child)
        # Skip whitespace
        while pos < len(s_expr) and s_expr[pos] in ' \t\n':
            pos += 1
    
    # Skip closing parenthesis
    if pos >= len(s_expr) or s_expr[pos] != ')':
        raise ValueError(f"Expected ')' at position {pos}")
    pos += 1
    
    node = TreeNode(node_type, start_line, start_col, end_line, end_col, children)
    return node, pos


def extract_nodes_by_type(root: TreeNode, node_types: List[str]) -> List[TreeNode]:
    """Extract all nodes matching the given types from the tree."""
    results = []
    
    def traverse(node: TreeNode):
        if node.node_type in node_types:
            results.append(node)
        for child in node.children:
            traverse(child)
    
    traverse(root)
    return results


def extract_functions_from_tree(tree_sitter_output: str, file_path: str, 
                                file_content: str, relevant_node_types: List[str]) -> List[Dict]:
    """
    Extract function definitions from tree-sitter S-expression output.
    
    Args:
        tree_sitter_output: S-expression string from tree-sitter CLI
        file_path: Path to the source file
        file_content: Content of the source file
        relevant_node_types: List of node types to extract (e.g., ['function_definition'])
    
    Returns:
        List of dicts with 'file', 'line', and 'text' keys
    """
    try:
        root = parse_s_expression(tree_sitter_output)
        matching_nodes = extract_nodes_by_type(root, relevant_node_types)
    except Exception as e:
        # If parsing fails, return empty list (file might have syntax errors)
        return []
    
    functions = []
    lines = file_content.split('\n')
    
    for node in matching_nodes:
        # Use node's line information (0-indexed in tree-sitter)
        start_line = node.start_line
        
        # Extract text from the file using line range
        # tree-sitter uses 0-indexed lines, so we need to handle that
        if start_line < len(lines):
            # Get all lines from start to end
            end_line = min(node.end_line + 1, len(lines))
            node_lines = lines[start_line:end_line]
            node_text = '\n'.join(node_lines)
            
            # Dedent the text
            from textwrap import dedent
            node_text = dedent(node_text)
            
            functions.append({
                'file': file_path,
                'line': start_line,
                'text': node_text
            })
    
    return functions

