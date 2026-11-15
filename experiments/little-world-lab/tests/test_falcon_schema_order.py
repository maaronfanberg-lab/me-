import unittest

from falcon_schema_order import ALL_BRANCHES, OrderedFalconBackend, parse_branch_order


class FalconSchemaOrderTests(unittest.TestCase):
    def test_parse_branch_order_accepts_exact_permutation(self):
        value = parse_branch_order("move,rest,observe,talk,help,work")
        self.assertEqual(value, ("move", "rest", "observe", "talk", "help", "work"))

    def test_parse_branch_order_rejects_missing_or_duplicate_actions(self):
        with self.assertRaises(ValueError):
            parse_branch_order("move,rest,observe,talk,help,help")
        with self.assertRaises(ValueError):
            parse_branch_order("move,rest,observe,talk,help")

    def test_schema_preserves_requested_order_for_feasible_actions(self):
        backend = OrderedFalconBackend(
            branch_order=("work", "help", "talk", "move", "observe", "rest")
        )
        observation = {
            "location": "square",
            "neighbor_locations": ["kitchen"],
            "resources": {"water": 2},
            "co_located_agents": ["Ivo"],
        }
        schema = backend._response_schema(observation)
        action_types = [
            branch["properties"]["type"]["enum"][0]
            for branch in schema["oneOf"]
        ]
        self.assertEqual(action_types, ["work", "help", "talk", "move", "observe", "rest"])

    def test_schema_filters_unavailable_actions_without_reordering_remaining(self):
        backend = OrderedFalconBackend(branch_order=ALL_BRANCHES)
        observation = {
            "location": "room",
            "neighbor_locations": [],
            "resources": {},
            "co_located_agents": [],
        }
        schema = backend._response_schema(observation)
        action_types = [
            branch["properties"]["type"]["enum"][0]
            for branch in schema["oneOf"]
        ]
        self.assertEqual(action_types, ["rest", "observe"])


if __name__ == "__main__":
    unittest.main()
