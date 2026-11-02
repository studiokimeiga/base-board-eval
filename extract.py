#!/usr/bin/env python3
"""Pull specific threads out of any run file into markdown, for the curated best-of."""
import json, sys

def get(path, **sel):
    d = json.load(open(path))
    ts = d['threads'] if isinstance(d, dict) else d
    for t in ts:
        if all(t.get(k) == v for k, v in sel.items()):
            return t
    return None

def md(t, title, note, lines=None, limit=None):
    out = ['### %s' % title, '', '*%s*' % note, '']
    if lines:
        out += ['> **The line:** %s' % l for l in lines] + ['']
    out += ['```']
    for p in (t['posts'][:limit] if limit else t['posts']):
        out.append('%-10s %s' % (p['who'], p['text'] or '[no text]'))
    out += ['```', '']
    return '\n'.join(out)
