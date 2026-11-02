# Judge prompts, as sent

Every Claude judge in the bake-off was a background subagent (Claude Opus 5.5, `claude-opus-5-5`,
default settings) launched by the session's Agent tool. Its prompt existed only in the session
transcript, so each one is recovered here verbatim, one file per launch. The file names give the
round and the packets that judge read. Each subagent opened only the packet files named in its
prompt; the round 8 transcripts were checked for this, and no judge opened a `key.json`.

The gpt-5.4 prompts were built in code, so they are not copied here:

| round | Claude prompt | gpt-5.4 prompt |
|---|---|---|
| 1-2 | `r1-2_claude_*` (rubric v1) | none, Claude only |
| 3, 4, 5 | `r3_*`, `r4_*`, `r5_*`: rubric v1 plus a note on long posts | `round3_judge.py gpt`, `RUBRIC` (v1). Round 3 ran on the free daily OpenAI allowance and stopped after 6 of 8 packets; rounds 4 and 5 went through OpenRouter (`--paid`), the same model at low reasoning effort |
| 6 | `r6_*`: rubric v1 plus "count deadpan and sincerely-wrong humour" | `RUBRIC` (v1) via OpenRouter (`--paid`), so **without** the humour instruction |
| 7 | `r7_*`: rubric v2 (contrast, sincerely-wrong humour, variety) | `RUBRIC` (v1) via OpenRouter, so no variety score |
| 8 | `r8_*`: rubric v2 | `RUBRIC_V2` via OpenRouter: the same criteria as Claude |
| JP | `jp_claude_*` (Japanese rubric, naturalness first) | none, Claude only |
| JP-5 | `jp-r5_claude_all.txt` | `jp-r5_gpt_judge.sh`, an inline script run from the session (Japanese `RUBRIC` from `jp_judge.py`) via OpenRouter |

`build_r1-2_packets.sh` is the inline script that built the round 1-2 packets and `../key.json`
(seed 9271). Later rounds were built by `round3_judge.py packets` and `jp_judge.py packets`.

Rubric v1 is `RUBRIC` in `round3_judge.py`; rubric v2 is `RUBRIC_V2`. The Claude copies differ
from those strings only in small wording changes (and, in rounds 3 to 6, a sentence about long
posts), except where the table says otherwise.
