"""Binds judges' scores to the exact packets they read.

<round folder>/packet-hashes.json records, for every packet, the SHA-256 of the packet file
as written (the hash MANIFEST.sha256 lists for it) and the letters-to-arms key it was
lettered with. The scores-*.json in a folder are only meaningful against those packets, so:

  packets  refuses to replace a scored packet, or its key, with a different one
  gpt      refuses to skip or score anything while a scored packet or its key has changed,
           and refuses to score a packet that isn't in the record
  report   refuses to unblind scores whose key (or packet, when present) has changed

The packets themselves are private (see ../README.md); the record holds only hashes and keys.
"""
import glob, hashlib, json, os

RECORD = "packet-hashes.json"


def file_bytes(text):
    """Exactly what open(path, "w", encoding="utf-8").write(text) puts on disk here."""
    return text.replace("\n", os.linesep).encode("utf-8")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def load(folder):
    p = os.path.join(folder, RECORD)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def scored(folder):
    """Every packet name some judge in this folder has scored."""
    names = set()
    for f in glob.glob(os.path.join(folder, "scores-*.json")):
        with open(f, encoding="utf-8") as fh:
            names |= set(json.load(fh))
    return names


def refuse(folder, problems):
    raise SystemExit(
        "refusing: scores in %s were made against other packets:\n  %s\n"
        "Move that folder's scores-*.json aside (or judge in a new folder) first."
        % (folder, "\n  ".join(problems)))


def write(folder, texts, keys):
    """Write {name: text} packets and the record, unless that would strand existing scores.
    keys: {name: {letter: arm}}. Call before writing key.json."""
    record = load(folder)
    new = {n: {"sha256": sha256(file_bytes(t)), "key": keys[n]} for n, t in texts.items()}
    stale = ["%s: %s" % (n, "not in the new packets" if n not in new else
                         "no recorded packet" if n not in record else "packet or key would change")
             for n in sorted(scored(folder)) if n not in record or new.get(n) != record[n]]
    if stale:
        refuse(folder, stale)
    for n, t in texts.items():
        with open(os.path.join(folder, n + ".txt"), "wb") as f:
            f.write(file_bytes(t))
    with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)


def packet_matches(folder, name, record=None):
    """False if the packet file differs from the record (or isn't recorded); None if absent."""
    rec = (load(folder) if record is None else record).get(name)
    p = os.path.join(folder, name + ".txt")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return rec is not None and sha256(f.read()) == rec["sha256"]


def check(folder, key_of):
    """Refuse unless every scored packet is recorded, key_of(name) still gives its recorded
    key, and its packet file, if present, still has its recorded hash."""
    record, problems = load(folder), []
    for n in sorted(scored(folder)):
        if n not in record:
            problems.append("%s: no recorded packet" % n)
            continue
        if key_of(n) != record[n]["key"]:
            problems.append("%s: key.json no longer matches" % n)
        if packet_matches(folder, n, record) is False:
            problems.append("%s: packet text has changed" % n)
    if problems:
        refuse(folder, problems)
