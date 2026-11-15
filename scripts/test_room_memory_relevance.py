#!/usr/bin/env python3
"""Evidence-linked recall, not a partner-name shortcut to arbitrary old topics."""
from __future__ import annotations
import copy
import unittest
import room_group_dynamics as group

AWAKE=("sarah","mara","owen","jules")
CFG={"group_dynamics":{"enabled":True}}


def record(i, speaker, text, cycle, target=None):
    return {"id":i,"speaker":speaker,"text":text,"target":target,
            "cycle":cycle,"at":"2026-10-28T10:00:00Z"}


def minds(encounters):
    return {"entities":{"owen":{
        "people":{"sarah":{},"mara":{},"jules":{}},
        "group_dynamics":{"encounters":encounters, "activities":[], "revisions":[]},
        "room_memories":[],"self_history":[]
    }}}


def context(text):
    return [record("live-source","jules",text,40)]


class MemoryRelevanceTests(unittest.TestCase):
    def test_partner_only_probability_quote_does_not_steal_species_context(self):
        old=record("partner-X","jules",
                   "The probability that random variable X equals 0.1 is worth testing.",
                   32)
        m=minds([old])
        source=context("What might species selection and evolutionary lineages reveal?")
        out=group.model_context(m,"owen","jules",source,AWAKE,CFG)
        self.assertEqual(out["encounters"],[])

    def test_topical_partner_and_nonpartner_memories_survive(self):
        old=record("partner-X","jules",
                   "We considered an unrelated random variable X probability.", 38)
        relevant=record("species-memory","mara",
                        "Evolutionary selection within species can split lineages.",
                        35)
        m=minds([old,relevant])
        out=group.model_context(m,"owen","jules",
            context("How does evolutionary selection split species lineages?"),
            AWAKE,CFG)
        self.assertIn("species-memory",[r["source"] for r in out["encounters"]])
        self.assertNotIn("partner-X",[r["source"] for r in out["encounters"]])

    def test_thin_topic_allows_at_most_one_recent_partner_background(self):
        items=[record(f"partner-{n}","jules",f"An unrelated personal memory number {n}.",
                      n) for n in (2,35,38,39)]
        out=group.model_context(minds(items),"owen","jules",
            context("Can you clarify?"),AWAKE,CFG)
        self.assertLessEqual(len(out["encounters"]),1)
        if out["encounters"]:
            self.assertEqual(out["encounters"][0]["source"],"partner-39")
            self.assertLessEqual(len(out["encounters"][0]["text"]),120)

    def test_recent_request_for_prior_exchange_may_recall_one_partner(self):
        item=record("recalled-exchange","jules",
                    "Our earlier conversation about river patterns was important.",
                    39)
        m=minds([item])
        out=group.model_context(m,"owen","jules",
            context("Can you remember what you told me last time?"),
            AWAKE,CFG)
        self.assertEqual([r["source"] for r in out["encounters"]],
                         ["recalled-exchange"])

    def test_stale_partner_only_quotation_not_retrieved(self):
        m=minds([record("very-old","jules","A story about another project.",1),
                 record("current","mara","I visited a field site last month.",40)])
        out=group.model_context(m,"owen","jules",
            context("Can you clarify?"),AWAKE,CFG)
        self.assertNotIn("very-old",[r["source"] for r in out["encounters"]])

    def test_no_memory_mutations_and_provenance_preserved(self):
        item=record("species-source","jules",
                    "The species lineage had several ecological branches.",39)
        m=minds([item])
        before=copy.deepcopy(m)
        result=group.model_context(m,"owen","jules",
            context("What evidence links species lineage and ecology?"),
            AWAKE,CFG)
        self.assertEqual(m,before)
        self.assertEqual(result["encounters"][0]["status"],
                         "remembered_speech_not_verified_fact")
        self.assertEqual(result["encounters"][0]["source"],"species-source")

    def test_empty_context_is_bounded_and_does_not_make_every_memory_topical(self):
        items=[record(f"u-{i}","jules",f"The unrelated number is {i}.",i)
               for i in range(1,20)]
        out=group.model_context(minds(items),"owen","jules",[],AWAKE,CFG)
        self.assertLessEqual(len(out["encounters"]),1)

    def test_offtopic_words_not_banned_and_interlocutor_can_be_absent(self):
        items=[record("clinic-source","jules",
                      "The clinic scheduling problem involves staff time.",40)]
        m=minds(items)
        out=group.model_context(m,"owen","jules",
           context("How did that clinic scheduling problem affect staff?"),
           AWAKE,CFG)
        self.assertEqual([r["source"] for r in out["encounters"]],
                         ["clinic-source"])
        without=group.model_context(m,"owen","jules",
            context("Tell me about species evolutionary adaptation."),
            ("sarah","mara","owen"),CFG)
        self.assertEqual(without["encounters"],[])


if __name__=="__main__":
    unittest.main()
