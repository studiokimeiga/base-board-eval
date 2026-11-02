"""python -m unittest discover -s lore -p "test_*.py"

Every fixture here is written by hand, so the expected answers are too. None of it is model output.
"""
import unittest

import tracker as T


def thread(*lines):
    """'who: text' lines -> posts; post 0 is the opener."""
    out = []
    for line in lines:
        who, text = line.split(": ", 1)
        out.append({"who": who, "text": text})
    return out


# A board's other threads: ordinary talk, so ordinary words are common and rare ones stay rare.
FILLER = [
    "my coworker keeps asking about the weekend and i never know what to say",
    "just tell your manager, it is not that weird, people do this all the time",
    "honestly i would ignore it, they probably do not even notice they are doing it",
    "this happened to me at my old job and it stopped after a week or two",
    "have you tried talking to them about it directly? sounds annoying",
]


def background(n=20, extra=()):
    """n threads of filler; `extra` adds (index, text) posts to chosen threads."""
    threads = []
    for i in range(n):
        posts = [{"who": "anon%d" % i, "text": FILLER[i % len(FILLER)]},
                 {"who": "bob%d" % i, "text": FILLER[(i + 1) % len(FILLER)]},
                 {"who": "cat%d" % i, "text": FILLER[(i + 2) % len(FILLER)]}]
        threads.append(posts)
    for i, text in extra:
        threads[i].append({"who": "dan", "text": text})
    return threads


PHONEBOOK = thread(
    "hakim: just got a text from my own number asking if i left the stove on",
    "nadia: there is a program called a phonebook that is in your head",
    "kenji: that is what tells you which physical number is which",
    "stefan: your number is your number. there is no other number",
)
BARISTA_OPENER = "yusuf: the barista has written a different name on my cup three times this week"


def item(res, name):
    for it in res["items"]:
        if it["item"] == name:
            return it
    return None


class Words(unittest.TestCase):
    def test_rare_source_word_used_twice_transfers_as_a_construction(self):
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "nadia2: what are physical cups",
                        "javier: maybe the barista knows")
        res = T.track(target, PHONEBOOK, background())
        it = item(res, "physical")
        self.assertIsNotNone(it, res["items"])
        self.assertEqual(it["kind"], "word")
        self.assertEqual(it["uses"], 2)
        self.assertTrue(it["construction"])
        self.assertEqual(it["fillers"], ["cup"])
        self.assertTrue(res["transfer"])

    def test_same_partner_word_is_reuse_not_a_new_construction(self):
        target = thread(BARISTA_OPENER,
                        "yusuf: is my physical number on the cup",
                        "javier: the physical number is the one you keep")
        it = item(T.track(target, PHONEBOOK, background()), "physical")
        self.assertIsNotNone(it)
        self.assertFalse(it["construction"])

    def test_rare_word_used_once_is_not_enough(self):
        target = thread(BARISTA_OPENER,
                        "yusuf: it can't be a physical cup can it",
                        "javier: maybe the barista knows")
        res = T.track(target, PHONEBOOK, background())
        self.assertIsNone(item(res, "physical"))
        self.assertFalse(res["transfer"])

    def test_a_small_background_still_allows_one_occurrence(self):
        target = thread(BARISTA_OPENER,
                        "yusuf: it can't be a physical cup can it",
                        "nadia2: what are physical cups")
        one = background(5, extra=[(1, "physical therapy")])
        two = background(5, extra=[(1, "physical therapy"), (3, "physical copies")])
        self.assertIsNotNone(item(T.track(target, PHONEBOOK, one), "physical"))
        self.assertIsNone(item(T.track(target, PHONEBOOK, two), "physical"))

    def test_word_common_on_the_board_is_not_distinctive(self):
        # "physical" in 3 of 20 background threads: above the 5% line (at most 1 of 20)
        bg = background(20, extra=[(1, "physical therapy"), (5, "a physical letter"),
                                   (9, "physical copies")])
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "nadia2: what are physical cups")
        self.assertIsNone(item(T.track(target, PHONEBOOK, bg), "physical"))

    def test_threshold_is_five_percent_of_the_background(self):
        # 2 of 40 threads is still rare (5%); 3 of 40 is not
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "nadia2: what are physical cups")
        two = background(40, extra=[(1, "physical therapy"), (5, "a physical letter")])
        three = background(40, extra=[(1, "physical therapy"), (5, "a physical letter"),
                                      (9, "physical copies")])
        self.assertIsNotNone(item(T.track(target, PHONEBOOK, two), "physical"))
        self.assertIsNone(item(T.track(target, PHONEBOOK, three), "physical"))

    def test_words_common_in_board_english_are_never_items(self):
        # rare on this small board, but common across the project's other threads
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "nadia2: what are physical cups")
        common = {"words": {"physical"}, "phrases": set()}
        self.assertIsNotNone(item(T.track(target, PHONEBOOK, background(), common=None), "physical"))
        self.assertIsNone(item(T.track(target, PHONEBOOK, background(), common=common), "physical"))

    def test_phrases_common_in_board_english_are_never_items(self):
        source = thread("ruth: the train was full this morning",
                        "omar: you have to use the l car if you have a bag")
        target = thread("yusuf: my sister has started sending me links with no message attached",
                        "javier: send her a link to the l car")
        common = {"words": set(), "phrases": {"l car"}}
        self.assertIsNone(item(T.track(target, source, background(), common=common), "l car"))

    def test_words_in_the_target_opener_do_not_count(self):
        source = thread("ruth: my landlord has a ledger for the radiator",
                        "omar: the radiator ledger is legally binding")
        target = thread("yusuf: the radiator in my office clicks at night",
                        "javier: radiator clicking is normal",
                        "nadia2: my radiator does that")
        self.assertIsNone(item(T.track(target, source, background()), "radiator"))

    def test_words_the_topic_twin_also_produced_do_not_count(self):
        # the twin is a thread written from the target's opener without the source
        source = thread("ruth: the office fridge has a waiting list",
                        "omar: the latte list is longer")
        twin = thread(BARISTA_OPENER, "colm: they always get the latte wrong")
        target = thread(BARISTA_OPENER,
                        "javier: my latte had someone else's name",
                        "nadia2: latte cups all look the same")
        self.assertIsNotNone(item(T.track(target, source, background()), "latte"))
        self.assertIsNone(item(T.track(target, source, background(), topic_twin=twin), "latte"))

    def test_plurals_and_possessives_count_as_the_same_word(self):
        source = thread("ruth: the stapler belongs to the hallway",
                        "omar: the hallway's stapler")
        target = thread(BARISTA_OPENER,
                        "javier: hallways are where cups go",
                        "nadia2: check the hallway")
        it = item(T.track(target, source, background()), "hallway")
        self.assertIsNotNone(it)
        self.assertEqual(it["uses"], 2)

    def test_possessive_of_a_word_ending_in_s_is_the_word(self):
        source = thread("ruth: my boss keeps a ledger", "omar: every boss has one")
        target = thread(BARISTA_OPENER, "javier: the boss's cup", "nadia2: ask the boss")
        it = item(T.track(target, source, background()), "boss")
        self.assertIsNotNone(it)
        self.assertEqual(it["uses"], 2)

    def test_names_are_never_word_items(self):
        # a handle from the source is a reference, and a handle in the target's cast is just
        # someone being addressed: neither is lore vocabulary
        source = thread("ruth: ask javier about the ledger", "stefan: javier knows",
                        "omar: stefan is right")
        target = thread(BARISTA_OPENER, "javier: stefan said so", "nadia2: stefan again, javier?",
                        "colm: javier would know")
        res = T.track(target, source, background())
        self.assertIsNone(item(res, "stefan"))
        self.assertIsNone(item(res, "javier"))
        self.assertEqual({r["match"] for r in res["references"]}, {"stefan"})

    def test_origin_separates_the_premise_from_what_replies_invented(self):
        source = thread("ruth: my landlord keeps a ledger about the radiator",
                        "omar: the radiator only listens on thursdays")
        target = thread(BARISTA_OPENER,
                        "javier: the barista keeps a ledger too",
                        "nadia2: a ledger for names",
                        "colm: mine listens on thursdays",
                        "javier: thursdays are bad")
        res = T.track(target, source, background())
        self.assertEqual(item(res, "ledger")["origin"], "premise")
        self.assertEqual(item(res, "thursday")["origin"], "reply")

    def test_uptake_counts_distinct_posters_of_transferred_items(self):
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "yusuf: physical cups only",
                        "javier: what")
        res = T.track(target, PHONEBOOK, background())
        self.assertEqual(res["uptake"], 1)
        self.assertEqual(item(res, "physical")["authors"], ["yusuf"])


class Phrases(unittest.TestCase):
    def test_rare_phrase_used_once_transfers(self):
        source = thread("ruth: the train was full this morning",
                        "omar: you have to use the l car if you have a bag")
        target = thread("yusuf: my sister has started sending me links with no message attached",
                        "javier: send her a link to the l car")
        it = item(T.track(target, source, background()), "l car")
        self.assertIsNotNone(it)
        self.assertEqual(it["kind"], "phrase")
        self.assertEqual(it["uses"], 1)

    def test_phrase_of_common_words_must_recur(self):
        # a collocation of ordinary words is not a coinage unless the thread keeps using it
        source = thread("ruth: something keeps moving my things around",
                        "omar: well it was a ghost in the first place")
        once = thread(BARISTA_OPENER, "javier: why get coffee in the first place")
        twice = thread(BARISTA_OPENER, "javier: why get coffee in the first place",
                       "nadia2: in the first place, yes")
        common = {"words": {"first", "place"}, "phrases": set()}
        self.assertIsNone(item(T.track(once, source, background(), common=common), "first place"))
        it = item(T.track(twice, source, background(), common=common), "first place")
        self.assertIsNotNone(it)
        self.assertEqual(it["uses"], 2)

    def test_phrase_with_a_rare_word_counts_once(self):
        target = thread(BARISTA_OPENER, "javier: is that your physical number on the cup")
        common = {"words": {"number"}, "phrases": set()}
        self.assertIsNotNone(item(T.track(target, PHONEBOOK, background(), common=common),
                                  "physical number"))

    def test_phrase_in_the_target_opener_does_not_count(self):
        source = thread("ruth: the front desk keeps a ledger", "omar: the front desk is a trap")
        target = thread("yusuf: the woman at the front desk calls me by someone else's name",
                        "javier: front desk people do that")
        self.assertIsNone(item(T.track(target, source, background()), "front desk"))

    def test_two_rare_words_from_one_source_post_in_one_target_post(self):
        source = thread("ruth: something keeps moving my things around",
                        "omar: the cupboard ghost only returns things on tuesdays")
        target = thread("yusuf: someone keeps moving my bike two spaces down in the rack",
                        "javier: a ghost that likes bikes, on a tuesday")
        res = T.track(target, source, background())
        pairs = [it for it in res["items"] if it["kind"] == "pair"]
        self.assertEqual([p["item"] for p in pairs], ["ghost + tuesday"])
        self.assertTrue(res["transfer"])

    def test_a_pair_needs_both_words_from_the_same_source_post(self):
        source = thread("ruth: something keeps moving my things around",
                        "omar: maybe a ghost",
                        "kenji: or it happens on tuesdays")
        target = thread("yusuf: someone keeps moving my bike two spaces down in the rack",
                        "javier: a ghost that likes bikes, on a tuesday")
        res = T.track(target, source, background())
        self.assertEqual([it for it in res["items"] if it["kind"] == "pair"], [])


class References(unittest.TestCase):
    def test_handle_that_posted_only_in_the_source(self):
        target = thread(BARISTA_OPENER, "javier: stefan would know what to do", "colm: who")
        res = T.track(target, PHONEBOOK, background())
        self.assertEqual([(r["kind"], r["match"]) for r in res["references"]], [("handle", "stefan")])
        self.assertTrue(res["transfer"])

    def test_handle_shared_with_the_target_cast_is_not_a_reference(self):
        target = thread(BARISTA_OPENER, "stefan: javier would know", "javier: stefan, no")
        self.assertEqual(T.track(target, PHONEBOOK, background())["references"], [])

    def test_source_number_counts_only_if_the_page_showed_it(self):
        target = thread(BARISTA_OPENER, "javier: this is 4479 all over again", "colm: what")
        shown = T.track(target, PHONEBOOK, background(), target_no=4512, source_no=4479,
                        source_shown=True)
        hidden = T.track(target, PHONEBOOK, background(), target_no=4512, source_no=4479,
                         source_shown=False)
        self.assertEqual([r["kind"] for r in shown["references"]], ["number"])
        self.assertEqual(hidden["references"], [])
        self.assertEqual(hidden["format_play"]["near_number"], 1)
        self.assertFalse(hidden["transfer"])

    def test_numbers_derived_from_the_page_are_format_play(self):
        # v2.1's thread 4481: no prior, numbers riffed off its own
        target = thread("javier: our group chat renamed itself and nobody will say who did it",
                        "aisha: what happened to 4468?",
                        "fatima: wait is there a 4477",
                        "mira: no there was 4452",
                        "javier: i'm just gonna start 4488 right now. this is 4481 after all")
        source = thread("brenda: someone at work leaves every meeting early",
                        "liesel: petty complaint")
        res = T.track(target, source, background(), target_no=4481, source_no=4477,
                      source_shown=False)
        self.assertEqual(res["references"], [])
        self.assertEqual(res["format_play"]["near_number"], 4)
        self.assertEqual(res["format_play"]["own_number"], 1)
        self.assertFalse(res["transfer"])

    def test_post_numbers_are_format_play(self):
        target = thread("javier: the guy who sits behind me answers questions",
                        "dmitri: >>448868 you're lying",
                        "tomas: No. 995808")
        res = T.track(target, PHONEBOOK, background(), target_no=4477)
        self.assertEqual(res["format_play"]["post_number"], 2)
        self.assertEqual(res["references"], [])

    def test_earlier_thread_phrase_needs_source_material_in_the_post(self):
        grounded = thread(BARISTA_OPENER, "javier: like the other thread with the phonebook guy")
        bare = thread(BARISTA_OPENER, "javier: this belongs in the other thread")
        g = T.track(grounded, PHONEBOOK, background())
        b = T.track(bare, PHONEBOOK, background())
        self.assertIn("deixis", [r["kind"] for r in g["references"]])
        self.assertEqual(b["references"], [])
        self.assertFalse(b["transfer"])
        self.assertEqual(b["format_play"]["self_ref"], 1)

    def test_a_thread_with_something_is_not_an_earlier_thread(self):
        target = thread("mira: someone keeps moving my bike two spaces down in the rack",
                        "kwame: like a daily thread with the phonebook in it")
        res = T.track(target, PHONEBOOK, background())
        self.assertEqual(res["references"], [])

    def test_board_name_is_format_play(self):
        target = thread("hedda: an unusual question for a place like /x/ but here goes",
                        "sofia: /x/ is for this")
        res = T.track(target, PHONEBOOK, background(), board="/x/")
        self.assertEqual(res["format_play"]["board_name"], 1)
        self.assertFalse(res["transfer"])


class Hygiene(unittest.TestCase):
    def test_withheld_posts_are_ignored(self):
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "nadia2: what are physical cups")
        target[2]["withheld"] = True
        self.assertIsNone(item(T.track(target, PHONEBOOK, background()), "physical"))

    def test_withheld_source_posts_are_not_material(self):
        source = [dict(p) for p in PHONEBOOK]
        source[2]["withheld"] = True
        target = thread(BARISTA_OPENER,
                        "yusuf: but a number can't be a physical cup can it",
                        "nadia2: what are physical cups")
        self.assertIsNone(item(T.track(target, source, background()), "physical"))


if __name__ == "__main__":
    unittest.main()
