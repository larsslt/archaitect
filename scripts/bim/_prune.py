"""One-off helper for the BIM merge: remove top-level functions/classes (with their decorators) from a Python file by name.

    python scripts/bim/_prune.py FILE name1 name2 ...
"""
import ast
import sys

path, names = sys.argv[1], set(sys.argv[2:])
src = open(path, encoding="utf-8").read()
tree = ast.parse(src)
lines = src.splitlines(keepends=True)
cut = []
found = set()
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
        start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        cut.append((start, node.end_lineno))
        found.add(node.name)
    elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
        cut.append((node.lineno - 1, node.end_lineno))
        found.update(t.id for t in node.targets if isinstance(t, ast.Name))
missing = names - found
if missing:
    sys.exit(f"not found: {sorted(missing)}")
for a, b in sorted(cut, reverse=True):
    del lines[a:b]
out = "".join(lines)
while "\n\n\n\n" in out:
    out = out.replace("\n\n\n\n", "\n\n\n")
ast.parse(out)
open(path, "w", encoding="utf-8").write(out)
print(f"removed {sorted(found)} from {path}")
