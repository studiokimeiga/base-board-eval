import json, re, sys
from collections import Counter
STOP=set("""the a an and or but if then than that this these those is are was were be been being have has
had do does did not no yes it its i you he she they we me him her them my your his their of in on at to for
from with about into over after before between out up down off just so too very can will would could should
might must dont didnt cant im ive youre thats whats there here when where why how what who which all any
both each few more most other some such only own same as by like get got know think really one two also
even still back way something anything nothing someone thing things time""".split())
def _c(s): return {w for w in re.findall(r"[a-z']{4,}",s.lower()) if w not in STOP}
def contin(g):
    if len(g)<2: return 0
    h=sum(1 for i,x in enumerate(g[1:],1) if _c(x)&set().union(*[_c(y) for y in g[max(0,i-3):i]]))
    return h/(len(g)-1)
def one(t):
    g=[p['text'] for p in t['posts'][1:] if p['text']]
    if not g: return None
    toks=re.findall(r"[a-z']+",' '.join(g).lower())
    tri=[tuple(toks[i:i+3]) for i in range(max(0,len(toks)-2))]
    dist=len(set(tri))/len(tri) if tri else 0
    heads=Counter(' '.join(re.findall(r"[a-z']+",x.lower())[:3]) for x in g)
    top=heads.most_common(1)[0][1] if heads else 0
    body=re.sub(r'\s','',' '.join(g))
    words=re.findall(r"[A-Za-z']{2,}",' '.join(g))
    return dict(dist=dist, chant=(dist<0.55 or top>=10), cont=contin(g),
                quote=sum(1 for x in g if x.lstrip().startswith('>'))/len(g),
                vocab=len(set(toks))/len(toks) if toks else 0,
                wpp=sum(len(x.split()) for x in g)/len(g),
                frag=sum(1 for x in g if len(x.split())<4)/len(g),
                wl=100*sum(len(w) for w in words)/max(1,len(body)))
def table(path, groupby='arm'):
    d=json.load(open(path))
    groups={}
    for t in d['threads']:
        if t.get('quarantined'): continue
        m=one(t)
        if m: groups.setdefault(t.get(groupby,'?'),[]).append(m)
    print('%-9s %-4s %-9s %-8s %-7s %-7s %-8s %-6s %-6s'%(
        groupby,'n','chant','tri-dist','contin','>quote','type/tok','w/post','frag'))
    order=list(d.get('arms',{}).keys()) or sorted(groups)
    for k in order:
        ms=groups.get(k)
        if not ms: continue
        n=len(ms); f=lambda key: sum(m[key] for m in ms)/n
        print('%-9s %-4d %-9s %-8.2f %-7.2f %-7.1f %-8.3f %-6.1f %-6.2f'%(
            k,n,'%d (%2.0f%%)'%(sum(m['chant'] for m in ms),100*f('chant')),
            f('dist'),f('cont'),100*f('quote'),f('vocab'),f('wpp'),f('frag')))
if __name__=='__main__':
    table(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else 'arm')
