"""Openers for the final run.

Design rules, all derived from measurement rather than taste:

  * MUNDANE SOCIAL FRICTION, not planted anomaly. Unseeded openers were flagged at 17%
    vs 11% for seeded ones, and the single best performer in 142 threads was the mug
    complaint at 4/14. An anomaly I plant is a hook I wrote; friction gives the model
    somewhere ordinary to start and its own reason to leave.
  * A BORING EXPLANATION IS ALWAYS AVAILABLE. He's being tidy, she's distracted, it's a
    clerical error, ordinary cowardice. If a thread turns, the model turned it.
  * NO GENRE VOCABULARY anywhere, and nothing that only resolves supernaturally.
  * Several touch NAMING, OWNERSHIP or IDENTITY on purpose. 15 of the 20 lines the
    reader flagged contain no number at all; what they share is reference instability --
    "not my mug", "is your neighbor's name Zainab too?", "my girlfriend is a podcast".
    These openers put a referent in play without asserting anything strange about it.
  * MANY of them. Openers are now the only authored text in the system, and they are
    per-thread, so a large set means a reader never sees the same words twice -- which
    is exactly what went wrong with "update:".

First five are the originals that survived; the rest are new.
"""

OPENERS = [
    # --- retained: best measured performer, and the four survivors ---
    "someone at work keeps taking my mug, washing it, and putting it back in a different cupboard",
    "my roommate has started labelling things in the fridge and i don't know how to bring it up",
    "the guy who sits behind me has started answering questions that people asked me",
    "my neighbour has started saying good morning in a way i'm fairly sure is sarcastic",
    "i've been pretending to like a podcast my girlfriend recommended since february",
    # --- new: work ---
    "a coworker has started copying my manager on everything, including thank yous",
    "someone at work leaves every meeting five minutes early and nobody has ever mentioned it",
    "the woman at the front desk calls me by someone else's name and i've stopped correcting her",
    "the guy at the gym uses the machine next to mine every single time now",
    "my manager replies to every message with a thumbs up and nothing else",
    # --- new: home and building ---
    "my flatmate has started buying the exact brand of yoghurt i buy",
    "someone in my building keeps putting my recycling bin back on the wrong side of the gate",
    "my housemate has started washing up my dishes but not their own",
    "i've been getting someone else's post for a year and i've started reading it",
    "my upstairs neighbour vacuums at the same time every night and i've started waiting for it",
    "someone keeps moving my bike two spaces down in the rack",
    # --- new: family and friends ---
    "my sister has started sending me links with no message attached",
    "my dad has started forwarding me his own emails",
    "our group chat renamed itself and nobody will say who did it",
    "my friend has started saying my name at the end of every sentence",
    # --- new: small public encounters ---
    "the barista has written a different name on my cup three times this week",
    "the man who walks his dog past my window at seven has started nodding at me",
]

# The one seeded opener worth keeping: it produced the phonebook thread, the best single
# output of the project. Kept separate so the seeded/unseeded split stays measurable.
SEEDED = [
    "just got a text from my own number asking if i left the stove on",
]

ALL = OPENERS + SEEDED
