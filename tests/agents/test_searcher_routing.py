import unittest

from agents.searcher import _build_jobs


class SearcherRoutingTests(unittest.TestCase):
    def test_crawl_mode_uses_site_api_override_when_available(self) -> None:
        jobs = _build_jobs(
            queries=["github issue search"],
            source_sites=["https://github.com/openai/openai-python"],
            search_mode="crawl",
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["kind"], "api")
        self.assertEqual(jobs[0]["tool"], "github_search")
