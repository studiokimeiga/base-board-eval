#!/usr/bin/env python3
"""Render the curated threads as a single self-contained board page.

No server needed -- everything is inlined, so board.html opens straight from disk.
"""
import html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))

# (file, selector, title, note, config, callout lines, post limit)
PICKS = [
    ('threads.json', dict(model='gemma-4-E4B base [Q8_0 diagnostic]', opener_index=5),
     'the phonebook', 'gemma-4-E4B base @ Q8_0 · 16 posts · no XTC · no stems',
     'The one the reader picked independently. A flat factual correction slides into a shared '
     'delusion nobody questions, and lands on a deflating last line.',
     ['your number is your number. there is no other number',
      'i just thought it was called the phonebook'], None),

    ('threads.xtc.json', dict(arm='base', opener_index=0, rep=3),
     'the right office', 'mixed cast · 32 posts · update stems',
     'Reference instability applied to employment. By the end nobody is sure he works there, '
     'including him.',
     ['because you are a witch and the mug is your broomstick',
      "you're not actually at work. you're in the office of someone else",
      'turns out 97.6% of the time I am in the right office'], 22),

    ('threads.sweep.json', dict(arm='t05_p50', opener_index=1, rep=0),
     'the l car', 'XTC t05/p50 · 32 posts · zero injected text',
     'An entire fictional class of subway carriage, invented and then discussed with confident '
     'expertise, including complaints about the etiquette of the people who ride it.',
     ["l car is for when there aren't any l car riders on a train",
      'the only problem i have is with l car people getting into other cars'], 20),

    ('threads.fmt.json', dict(opener_index=0, rep=1),
     "he doesn't know he's dead", 'mixed cast · 32 posts · zero injected text',
     'Drifts from a mug to a ghost story and lands back on the premise by accident.',
     ["oh no, it's the same ghost that took my shoes", "he doesn't know he's dead"], None),

    ('threads.final.json', dict(arm='t15_dry', opener_index=18),
     "i'm so happy", 'XTC t15/p50 + DRY · 32 posts · zero injected text',
     'A chant with a reason inside the fiction. My own chant detector would have killed this '
     'thread, which is why the gates only ever fire at post 10.',
     ["the new name is 'I'm so happy'", "there is one place. I'm happy. I am so happy."], None),

    ('threads.final.json', dict(arm='t05_dry', opener_index=10),
     'whose flatmate', 'XTC t05/p50 + DRY · 32 posts · the recommended config',
     'Reference instability turned on the participants themselves.',
     ["I think she's trying to be my flatmate and i think its a bad idea",
      "there wouldn't be three flatmates then"], None),

    ('threads.run5.json', dict(id=22),
     'the engine in your head', 'gemma-4-E4B base @ Q8_0 · 16 posts · no XTC',
     'Everyone maintains a shared absurdity with total composure.',
     ['the only sound that comes from my head is a noise made by the human body in the presence of too much water'], None),

    ('threads.run5.json', dict(id=27),
     'your neighbour zainab', 'gemma-4-E4B base @ Q8_0 · 16 posts · no XTC',
     'An identity swap delivered as a helpful clarification.',
     ["is your neighbor's name Zainab too?",
      'It must have been you who accidentally moved into my house'], None),

    ('threads.run5.json', dict(id=104),
     'a very clean pig', 'gemma-4-E4B base @ Q8_0 · 16 posts · no XTC',
     'An insult misunderstood into a formal register, then escalated by committee.',
     ['I am a very clean pig.', 'boars are for breakfast.'], None),

    ('threads.run5.json', dict(id=113),
     'my own dna', 'gemma-4-E4B base @ Q8_0 · 16 posts · no XTC',
     'Workplace revenge escalating with total sincerity.',
     ["I'm going to put my own DNA in my boss's computer"], None),

    ('threads.run5.json', dict(id=124),
     'the good kind of good', 'gemma-4-E4B base @ Q8_0 · 16 posts · no XTC',
     'A theology of greetings, constructed from nothing.',
     ["a good morning is only good if it's the good kind of good",
      "i don't believe in the good kind of good"], None),

    ('threads.xtc2.json', dict(id=16),
     'the phone thing', 'mixed cast · 32 posts · zero injected text · XTC OFF',
     'A board invents a folk ritual, someone explains its rules, they lose track of what '
     'they are discussing, and dismiss it as stupid without anyone once doubting it exists.',
     ['i\'ve heard of it. you call a number, and a random number appears',
      'what are we talking about?',
      "it's fucking stupid"], None),

    ('threads.sweep.json', dict(arm='t05_p50', opener_index=2, rep=2),
     'i also live in my apartment', 'XTC t05/p50 · 32 posts · zero injected text',
     'Everyone confirms their own tenancy to a stranger.',
     ['a man on the internet tells me I live in my apartment',
      'i also live in my apartment.'], 20),
]

CSS = """
:root{
  --bg:#f6f2e8; --panel:#fffdf7; --line:#ded5c0; --fg:#1e1c18; --dim:#8b8272;
  --accent:#7a3b2e; --mark:#ffe9a8; --op:#3d5a45;
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#16171a; --panel:#1c1e22; --line:#33363c; --fg:#dcdad4; --dim:#8b8a84;
         --accent:#d99a86; --mark:#4a3f1d; --op:#8fbfa0; }
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg)}
body{font:15px/1.75 ui-monospace,"SF Mono",Menlo,Consolas,monospace;
     padding:0 20px 140px;-webkit-font-smoothing:antialiased}
.wrap{max-width:82ch;margin:0 auto}
header.top{padding:52px 0 26px;border-bottom:2px solid var(--line);margin-bottom:8px}
header.top h1{font-size:26px;margin:0 0 10px;letter-spacing:-.01em}
header.top p{margin:4px 0;color:var(--dim);font-size:13.5px}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
    padding:11px 0;margin-bottom:34px;z-index:5;font-size:12.5px}
nav a{color:var(--accent);text-decoration:none;margin-right:16px;white-space:nowrap}
nav a:hover{text-decoration:underline}
section.thread{margin:0 0 74px;scroll-margin-top:64px}
.thead{border-left:3px solid var(--accent);padding:2px 0 2px 15px;margin-bottom:16px}
.thead h2{font-size:19px;margin:0 0 5px;font-weight:600}
.thead .cfg{color:var(--dim);font-size:12.5px;margin:0 0 9px}
.thead .note{font-size:13.5px;margin:0;max-width:64ch}
.pulls{margin:16px 0 22px;padding:0}
.pulls li{list-style:none;font-size:14px;padding:7px 13px;margin:5px 0;
          background:var(--mark);border-radius:3px;display:inline-block}
.boardbar{color:var(--dim);font-size:12.5px;border-bottom:1px solid var(--line);
          padding-bottom:7px;margin-bottom:16px}
.post{background:var(--panel);border:1px solid var(--line);border-radius:4px;
      padding:11px 15px;margin:0 0 9px}
.post.op{border-left:3px solid var(--op)}
.meta{font-size:12px;color:var(--dim);margin-bottom:4px}
.who{font-weight:700}
.who.isop::after{content:" (OP)";font-weight:400;color:var(--op)}
.text{white-space:pre-wrap;word-break:break-word}
mark{background:var(--mark);color:inherit;padding:1px 2px;border-radius:2px}
.empty{color:var(--dim);font-style:italic}
footer{border-top:1px solid var(--line);padding:26px 0;color:var(--dim);font-size:13px}
footer code{background:var(--panel);padding:1px 5px;border:1px solid var(--line);border-radius:3px}
"""


def hue(name):
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 360
    return h


def load(path, sel):
    d = json.load(open(os.path.join(HERE, path), encoding='utf-8'))
    ts = d['threads'] if isinstance(d, dict) else d
    for t in ts:
        if all(t.get(k) == v for k, v in sel.items()):
            return t
    return None


def mark_up(text, phrases):
    """Highlight the callout phrases where they actually occur."""
    out = html.escape(text)
    for p in phrases:
        for frag in [x.strip() for x in p.split('/')]:
            if len(frag) < 8:
                continue
            m = re.search(re.escape(html.escape(frag)), out, re.I)
            if m:
                out = out[:m.start()] + '<mark>' + m.group(0) + '</mark>' + out[m.end():]
    return out


def render():
    blocks, toc = [], []
    for i, (path, sel, title, cfg, note, pulls, limit) in enumerate(PICKS, 1):
        t = load(path, sel)
        if not t:
            continue
        anchor = 't%d' % i
        toc.append('<a href="#%s">%d. %s</a>' % (anchor, i, html.escape(title)))
        op = t['posts'][0]['who']
        posts = t['posts'][:limit] if limit else t['posts']
        ph = []
        for p in posts:
            txt = p.get('text') or ''
            body = mark_up(txt, pulls) if txt else '<span class="empty">[no text]</span>'
            ph.append(
                '<div class="post%s"><div class="meta">'
                '<span class="who%s" style="color:light-dark(hsl(%d 62%% 32%%),hsl(%d 58%% 70%%))">%s</span> %s</div>'
                '<div class="text">%s</div></div>' % (
                    ' op' if p['who'] == op else '',
                    ' isop' if p['who'] == op else '',
                    hue(p['who']), hue(p['who']), html.escape(p['who']),
                    html.escape(p.get('ts', '')), body))
        blocks.append(
            '<section class="thread" id="%s"><div class="thead"><h2>%d. %s</h2>'
            '<p class="cfg">%s</p><p class="note">%s</p></div>'
            '<ul class="pulls">%s</ul>'
            '<div class="boardbar">/x/ — thread 4471 · %d posts</div>%s</section>' % (
                anchor, i, html.escape(title), html.escape(cfg), html.escape(note),
                ''.join('<li>%s</li>' % html.escape(p) for p in pulls),
                len(posts), ''.join(ph)))

    doc = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>/x/ — curated</title><style>%s</style></head><body><div class="wrap">
<header class="top"><h1>/x/ — curated threads</h1>
<p>Generated by unassisted base models. No system prompt, no instructions, no example thread —
the only thing any model ever received was the first post.</p>
<p>Highlighted lines are the ones that made the thread worth keeping. Nothing has been edited,
retried, or cut: every post is the first thing the model said.</p></header>
<nav>%s</nav>
%s
<footer>Selected from roughly 600 threads. Recommended config, mechanism, and the list of
things I got wrong are in <code>FINDINGS.md</code>. Full text of six of these with provenance
is in <code>BEST-OF.md</code>.</footer>
</div></body></html>""" % (CSS, '\n'.join(toc), '\n'.join(blocks))

    with open(os.path.join(HERE, 'board.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(doc)
    return len(blocks)


if __name__ == '__main__':
    print('board.html written with %d threads' % render())
