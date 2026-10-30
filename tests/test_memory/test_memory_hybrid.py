import unittest

from jarvis_memory.hybrid import fuse_results


class HybridFusionTests(unittest.TestCase):
    def test_current_correction_wins_and_retired_entries_are_filtered(self):
        lexical = [
            {"id": "old", "key": "agent", "text": "I prefer Hermes", "status": "superseded", "score": 20},
            {"id": "new", "key": "agent", "text": "I prefer OMP", "status": "active",
             "source": "explicit-user-correction", "score": 2},
        ]
        result = fuse_results(lexical, [])
        self.assertEqual([item["id"] for item in result], ["new"])
        self.assertIn("active structured memory", result[0]["match_reason"])

    def test_duplicates_merge_metadata_and_channel_provenance(self):
        lexical = [{"id": "same", "text": "Use Python", "score": 4,
                    "match_reason": "lexical: python", "kind": "preference"}]
        semantic = [{"id": "same", "text": "Use Python", "score": .88,
                     "embedding_model": "synthetic"}]
        result = fuse_results(lexical, semantic)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["embedding_model"], "synthetic")
        self.assertEqual(result[0]["provenance"]["channels"], ["lexical", "semantic"])
        self.assertEqual(result[0]["lexical_score"], 4)
        self.assertEqual(result[0]["semantic_score"], .88)

    def test_semantic_paraphrase_can_surface(self):
        result = fuse_results([], [{"id": "p", "text": "Python is my coding choice", "score": .83}])
        self.assertEqual(result[0]["id"], "p")
        self.assertIn("semantic similarity", result[0]["match_reason"])

    def test_exact_lexical_evidence_outranks_weaker_semantic_only_match(self):
        lexical = [{"id": "exact", "text": "favorite language Python", "score": 1,
                    "match_reason": "lexical: python; normalized phrase"}]
        semantic = [{"id": "paraphrase", "text": "A coding preference", "score": .70}]
        self.assertEqual([item["id"] for item in fuse_results(lexical, semantic)],
                         ["exact", "paraphrase"])

    def test_low_score_semantic_only_candidate_is_excluded(self):
        result = fuse_results([], [{"id": "noise", "text": "Water the garden", "score": .34}],
                              semantic_min_score=.35)
        self.assertEqual(result, [])

    def test_ties_are_deterministic(self):
        candidates = [
            {"id": "b", "text": "B", "score": .8},
            {"id": "a", "text": "A", "score": .8},
        ]
        first = fuse_results([], candidates)
        second = fuse_results([], candidates)
        self.assertEqual(first, second)
        self.assertEqual([item["id"] for item in first], ["b", "a"])


if __name__ == "__main__":
    unittest.main()
