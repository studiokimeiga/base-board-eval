#!/usr/bin/env python3
"""Premise-claim drift: how often does a NON-OP poster speak in the first person about
the OP's situation, unmarked?

The reader's catch: reference instability about the OBJECT is the mechanism that makes
these threads work ("not my mug", "the phonebook is in your head"). Reference instability
about WHO IS WHO destroys them, because the person you were meant to worry about has
quietly swapped places with someone else and nobody in the thread notices.

Crude proxy: pull every "my X" phrase out of the opener, then count posts by anyone other
than the OP that reuse one. High = the premise is being adopted by the crowd.
"""
import json, re, sys
from collections import Counter

def phrases(opener):
    return set(re.findall(r"\bmy \w+", opener.lower()))

def drift(t, openers):
    op = t['posts'][0]['who']
    ph = phrases(openers[t['opener_index']])
    if not ph: return None
    gen = [p for p in t['posts'][1:] if p.get('text')]
    if not gen: return None
    hits = sum(1 for p in gen if p['who'] != op and any(x in p['text'].lower() for x in ph))
    others = sum(1 for p in gen if p['who'] != op)
    return hits / others if others else 0

def run(path):
    d = json.load(open(path))
    openers = d['openers'] if isinstance(d.get('openers'), list) else None
    if openers and isinstance(openers[0], dict):
        openers = [o['t'] for o in openers]
    by = {}
    for t in d['threads']:
        if t.get('quarantined') or t.get('abandoned'): continue
        v = drift(t, openers)
        if v is not None:
            by.setdefault(t.get('arm', '?'), []).append(v)
    print('%-10s %-4s %s' % ('arm', 'n', 'non-OP posts claiming the OP\'s premise'))
    for k in sorted(by):
        v = by[k]
        print('%-10s %-4d %.0f%%' % (k, len(v), 100*sum(v)/len(v)))

if __name__ == '__main__':
    run(sys.argv[1])
