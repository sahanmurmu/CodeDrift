import ast

def get_python_context(source_code, target_line):
    try:
        # convert source code to AST
        tree = ast.parse(source_code)
        best_node = None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    if node.lineno <= target_line <= node.end_lineno:
                        best_node = node

                        # ast.walk() visits nodes breadth-first, so a
                        # parent node is always visited before its
                        # children. That means if both an outer and an
                        # inner function/class match the target line,
                        # the inner (more specific) one is visited last
                        # and overwrites best_node here — so best_node
                        # always ends up being the innermost match.

        if best_node:
            return ast.get_source_segment(source_code, best_node)
            
    except Exception as e:
        print(f"AST Error: {e}")
        
    return None

# --- TESTING ---
if __name__ == "__main__":
    sample_code = """
import os

# Global-level comment
x = 10

def process_data(value):
    # We want to strictly accept only the exact 'int' type here
    if type(value) == int:
        return value * 2
    return 0

def do_nothing():
    pass
"""
    
    print("🎯 Target Line: 9 (if type(value) == int:)")
    context = get_python_context(sample_code, 9)
    print("\n📦 Extracted Context by AST:\n")
    print(context)