import json
import unittest

from falcon_live import FalconBackend, extract_first_complete_json_object
from living_world import Agent


class FalconLiveTests(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(extract_first_complete_json_object('{"type":"observe"}'), {"type": "observe"})

    def test_leading_and_trailing_text(self):
        text = 'Action: {"type":"rest"}\nDone.'
        self.assertEqual(extract_first_complete_json_object(text), {"type": "rest"})

    def test_braces_inside_string_do_not_break_balance(self):
        text = '{"type":"talk","target":"Mira","utterance":"I found {two} marks."}'
        self.assertEqual(extract_first_complete_json_object(text)["utterance"], "I found {two} marks.")

    def test_escaped_quote_and_backslash(self):
        text = r'{"type":"talk","target":"Mira","utterance":"She said \"go\" at C:\\shed"}'
        value = extract_first_complete_json_object(text)
        self.assertEqual(value["type"], "talk")
        self.assertIn('"go"', value["utterance"])
        self.assertIn('C:\\shed', value["utterance"])

    def test_first_complete_object_wins(self):
        text = '{"type":"observe"} trailing {"type":"rest"}'
        self.assertEqual(extract_first_complete_json_object(text), {"type": "observe"})

    def test_truncated_object_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_first_complete_json_object('{"type":"move","location":"market"')

    def test_malformed_object_is_rejected_not_repaired(self):
        with self.assertRaises(ValueError):
            extract_first_complete_json_object('{"type":"observe",}')

    def test_array_only_response_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_first_complete_json_object('[{"type":"observe"}]')

    def test_prompt_exposes_only_visible_feasibility_values(self):
        agent = Agent(
            name="Probe",
            traits=["careful"],
            goals=["stay grounded"],
            location="square",
        )
        observation = {
            "location": "square",
            "neighbor_locations": ["kitchen", "workshop"],
            "resources": {"water": 4},
            "co_located_agents": ["Ivo"],
            "recent_local_incidents": [],
            "relevant_private_memories": [],
        }
        _, user = FalconBackend._prompt(agent, observation, 3)
        payload = json.loads(user)
        self.assertEqual(payload["feasibility"]["move_locations"], ["kitchen", "workshop"])
        self.assertEqual(payload["feasibility"]["interaction_targets"], ["Ivo"])
        self.assertEqual(payload["feasibility"]["work_resources"], ["water"])
        self.assertEqual(payload["feasibility"]["always_allowed"], ["rest", "observe"])
        self.assertNotIn("square", payload["feasibility"]["move_locations"])

    def test_response_schema_contains_only_feasible_action_branches(self):
        observation = {
            "location": "square",
            "neighbor_locations": ["kitchen", "workshop"],
            "resources": {"water": 4},
            "co_located_agents": ["Ivo"],
        }
        schema = FalconBackend._response_schema(observation)
        branches = {
            branch["properties"]["type"]["enum"][0]: branch
            for branch in schema["oneOf"]
        }
        self.assertEqual(set(branches), {"move", "talk", "help", "work", "rest", "observe"})
        self.assertEqual(branches["move"]["properties"]["location"]["enum"], ["kitchen", "workshop"])
        self.assertEqual(branches["talk"]["properties"]["target"]["enum"], ["Ivo"])
        self.assertEqual(branches["help"]["properties"]["target"]["enum"], ["Ivo"])
        self.assertEqual(branches["work"]["properties"]["resource"]["enum"], ["water"])
        self.assertTrue(all(branch["additionalProperties"] is False for branch in branches.values()))

    def test_response_schema_omits_infeasible_dependent_actions(self):
        observation = {
            "location": "room",
            "neighbor_locations": [],
            "resources": {},
            "co_located_agents": [],
        }
        schema = FalconBackend._response_schema(observation)
        action_types = {
            branch["properties"]["type"]["enum"][0]
            for branch in schema["oneOf"]
        }
        self.assertEqual(action_types, {"rest", "observe"})

    def test_empty_visibility_lists_disable_dependent_action_arguments(self):
        observation = {
            "location": "room",
            "neighbor_locations": [],
            "resources": {},
            "co_located_agents": [],
        }
        constraints = FalconBackend._feasibility_constraints(observation)
        self.assertEqual(constraints["move_locations"], [])
        self.assertEqual(constraints["interaction_targets"], [])
        self.assertEqual(constraints["work_resources"], [])

    def test_visible_work_resource_location_alias_is_canonicalized(self):
        observation = {
            "location": "shop",
            "neighbor_locations": [],
            "resources": {"parts": 1},
            "co_located_agents": [],
        }
        value = FalconBackend._canonicalize_proposal({"type": "work", "location": "parts"}, observation)
        self.assertEqual(value, {"type": "work", "resource": "parts"})

    def test_unknown_work_alias_is_not_repaired(self):
        observation = {
            "location": "shop",
            "neighbor_locations": [],
            "resources": {"parts": 1},
            "co_located_agents": [],
        }
        value = FalconBackend._canonicalize_proposal({"type": "work", "location": "imaginary"}, observation)
        self.assertEqual(value, {"type": "work", "location": "imaginary"})


if __name__ == "__main__":
    unittest.main()
