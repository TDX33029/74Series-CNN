"""Minimal s-expression parser for KiCad netlists."""
import re

_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')

def parse(text):
    stack = [[]]
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok == '(':
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif tok == ')':
            if len(stack) > 1:
                stack.pop()
        else:
            if tok.startswith('"'):
                tok = tok[1:-1].replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
            stack[-1].append(tok)
    return stack[0]

def children(node, tag):
    """All direct sub-nodes whose first element == tag."""
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == tag]

def child(node, tag):
    """First direct sub-node whose first element == tag."""
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == tag:
            return c
    return None

def val(node, tag):
    """Value of (tag "value") direct child, or None."""
    c = child(node, tag)
    return c[1] if c and len(c) > 1 else None

def props(node):
    """Dict of (name value) pairs for all (property (name X) (value Y)) children."""
    out = {}
    for p in children(node, 'property'):
        n = val(p, 'name')
        v = val(p, 'value')
        if n is not None:
            out[n] = v
    return out

def fields(node):
    """Dict of (name value) pairs for all (field (name X) (value Y)) children."""
    out = {}
    for f in children(node, 'field'):
        n = val(f, 'name')
        v = val(f, 'value')
        if n is not None:
            out[n] = v
    return out
