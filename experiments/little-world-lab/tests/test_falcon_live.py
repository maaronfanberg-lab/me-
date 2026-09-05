import unittest

from falcon_live import extract_first_complete_json_object


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


if __name__ == "__main__":
    unittest.main()
