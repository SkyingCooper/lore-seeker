import unittest

from services.search_service import _evaluate_dynamic_need


class SearchServiceTests(unittest.TestCase):
    def test_dynamic_detection_uses_spa_markers_and_short_content(self) -> None:
        cfg = {
            "decision": {
                "static_min_text_length": 300,
                "static_min_html_bytes": 8192,
                "static_max_link_density": 0.35,
                "dynamic_threshold": 60,
                "score_weights": {
                    "empty_content": 35,
                    "short_content": 20,
                    "short_html": 15,
                    "spa_marker": 30,
                    "noscript_js_hint": 25,
                    "script_heavy_shell": 20,
                    "high_link_density": 15,
                    "anti_bot_keyword": 25,
                    "historical_static_failure": 25,
                    "historical_dynamic_success": 20,
                },
                "spa_markers": ["id=\"root\""],
                "error_keywords": [],
            }
        }
        decision = _evaluate_dynamic_need(
            html="<html><body><div id=\"root\"></div><script src=\"chunk.js\"></script></body></html>",
            extracted_text="loading",
            domain="example.com",
            profile={"static_attempts": 0, "static_successes": 0, "dynamic_attempts": 0, "dynamic_successes": 0},
            cfg=cfg,
        )
        self.assertTrue(decision["should_use_dynamic"])
        self.assertIn("spa_marker", decision["matched_rules"])

    def test_static_detection_accepts_substantial_content(self) -> None:
        cfg = {
            "decision": {
                "static_min_text_length": 300,
                "static_min_html_bytes": 4096,
                "static_max_link_density": 0.35,
                "dynamic_threshold": 60,
                "score_weights": {
                    "empty_content": 35,
                    "short_content": 20,
                    "short_html": 15,
                    "spa_marker": 30,
                    "noscript_js_hint": 25,
                    "script_heavy_shell": 20,
                    "high_link_density": 15,
                    "anti_bot_keyword": 25,
                    "historical_static_failure": 25,
                    "historical_dynamic_success": 20,
                },
                "spa_markers": ["id=\"root\""],
                "error_keywords": ["access denied"],
            }
        }
        long_text = "这是正文 " * 250
        html = f"<html><body><article>{long_text}</article></body></html>"
        decision = _evaluate_dynamic_need(
            html=html,
            extracted_text=long_text,
            domain="docs.python.org",
            profile={"static_attempts": 5, "static_successes": 5, "dynamic_attempts": 0, "dynamic_successes": 0},
            cfg=cfg,
        )
        self.assertFalse(decision["should_use_dynamic"])
        self.assertEqual(decision["reason"], "static_result_accepted")
