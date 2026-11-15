#!/usr/bin/env python3
import copy
import unittest

from retrieval_evidence import serialize_retrieval_evidence


class Node:
    def __init__(self):
        self.node_id = "node-17"
        self.node_type = "event"
        self.content = "Emily observes a message from Olivia: hello there"
        self.importance = "importance: 73"
        self.created = 41
        self.last_retrieved = 48


class RetrievalEvidenceTests(unittest.TestCase):
    def test_metadata_is_ranked_and_contains_no_memory_text(self):
        node = Node()
        result = serialize_retrieval_evidence([node], 52)
        self.assertEqual(result[0]["retrieval_rank"], 1)
        self.assertEqual(result[0]["stanford_node_id"], "node-17")
        self.assertEqual(result[0]["stanford_importance_raw"], 73.0)
        self.assertEqual(result[0]["stanford_created"], 41)
        self.assertEqual(result[0]["stanford_last_retrieved"], 48)
        self.assertEqual(result[0]["observed_time_step"], 52)
        self.assertEqual(len(result[0]["content_hash"]), 20)
        self.assertNotIn("content", result[0])
        self.assertNotIn("hello there", repr(result))

    def test_serializer_does_not_mutate_node(self):
        node = Node()
        before = copy.deepcopy(node.__dict__)
        serialize_retrieval_evidence([node], 52)
        self.assertEqual(node.__dict__, before)

    def test_rank_order_is_preserved(self):
        first, second = Node(), Node()
        second.node_id = "node-18"
        second.content = "different memory"
        result = serialize_retrieval_evidence([first, second], 60)
        self.assertEqual([row["retrieval_rank"] for row in result], [1, 2])
        self.assertEqual([row["stanford_node_id"] for row in result], ["node-17", "node-18"])


if __name__ == "__main__":
    unittest.main()
