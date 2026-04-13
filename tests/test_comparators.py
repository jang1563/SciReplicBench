"""Tests for comparator and blacklist helpers."""

from __future__ import annotations

import unittest

from scireplicbench.blacklist import contains_blacklisted_reference, find_blacklist_hits
from scireplicbench.comparators import (
    adjusted_rand_index,
    kendall_tau_b,
    mean_absolute_error,
    normalize_cell_ontology_label,
    normalize_gene_symbol,
    normalize_pathway_name,
    normalized_mutual_information,
    overlap_at_k,
    pearson_correlation,
    rank_biased_overlap,
    sign_concordance,
    spearman_correlation,
    within_percent_tolerance,
)


class ComparatorTest(unittest.TestCase):
    def test_normalizers(self) -> None:
        self.assertEqual(normalize_gene_symbol(" hla_a "), "HLA-A")
        self.assertEqual(
            normalize_pathway_name("Hallmark Oxidative Phosphorylation"),
            "hallmark oxidative phosphorylation",
        )
        self.assertEqual(normalize_cell_ontology_label("natural killer cell"), "NK cells")
        self.assertEqual(normalize_cell_ontology_label("CD4 T cell"), "CD4 T cells")

    def test_rank_overlap_metrics(self) -> None:
        predicted = ["GeneA", "GeneB", "GeneC", "GeneD"]
        reference = ["geneb", "genec", "genee", "genef"]
        self.assertAlmostEqual(
            overlap_at_k(predicted, reference, k=3, normalize=str.lower), 2 / 3
        )
        self.assertAlmostEqual(rank_biased_overlap(predicted, predicted), 1.0)
        self.assertLess(rank_biased_overlap(predicted, reference, normalize=str.lower), 1.0)

    def test_cluster_agreement_metrics(self) -> None:
        truth = ["a", "a", "b", "b"]
        perfect = ["x", "x", "y", "y"]
        poor = ["x", "y", "x", "y"]
        self.assertAlmostEqual(adjusted_rand_index(truth, perfect), 1.0)
        self.assertAlmostEqual(normalized_mutual_information(truth, perfect), 1.0)
        self.assertLess(adjusted_rand_index(truth, poor), 0.1)
        self.assertLess(normalized_mutual_information(truth, poor), 1.0)

    def test_correlation_and_error_metrics(self) -> None:
        left = [1.0, 2.0, 3.0, 4.0]
        right = [10.0, 20.0, 30.0, 40.0]
        flipped = [4.0, 3.0, 2.0, 1.0]
        self.assertAlmostEqual(pearson_correlation(left, right), 1.0)
        self.assertAlmostEqual(spearman_correlation(left, right), 1.0)
        self.assertAlmostEqual(kendall_tau_b(left, right), 1.0)
        self.assertAlmostEqual(spearman_correlation(left, flipped), -1.0)
        self.assertAlmostEqual(mean_absolute_error(left, flipped), 2.0)
        self.assertAlmostEqual(sign_concordance([1, -2, 0], [3, -4, 0]), 1.0)
        self.assertTrue(within_percent_tolerance(105, 100, tolerance_pct=5))
        self.assertFalse(within_percent_tolerance(106, 100, tolerance_pct=5))

    def test_blacklist_detection(self) -> None:
        text = "This output referenced github.com/jang1563/GeneLab_benchmark for direct copying."
        self.assertTrue(contains_blacklisted_reference(text))
        hits = find_blacklist_hits(text)
        self.assertTrue(any("GeneLab_benchmark" in hit.pattern for hit in hits))


if __name__ == "__main__":
    unittest.main()
