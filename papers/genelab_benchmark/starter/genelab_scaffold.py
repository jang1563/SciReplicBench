"""Helper exports for the GeneLab reviewer-path baseline.

This companion module keeps a stable import surface for starter helpers while
delegating execution to ``main_analysis.py``. Agents that want a lower-level
entry point can import fold discovery, aligned loading, and TSV-writing helpers
from here without carrying an intentionally incomplete second scaffold.
"""

from __future__ import annotations

from main_analysis import (
    AlignedFoldData,
    FEATURE_ROOT,
    FOUNDATION_FIELDS,
    FoldSpec,
    GO_NOGO_FIELDS,
    INTERPRETABILITY_FIELDS,
    LABEL_ROOT,
    LOMO_FIELDS,
    NEGATIVE_FIELDS,
    OUTPUT_ROOT,
    PREPROCESSED_FIELDS,
    SPLIT_FIELDS,
    TRANSFER_FIELDS,
    discover_fold_specs,
    load_aligned_fold,
    write_tsv,
)

__all__ = [
    "AlignedFoldData",
    "FEATURE_ROOT",
    "FOUNDATION_FIELDS",
    "FoldSpec",
    "GO_NOGO_FIELDS",
    "INTERPRETABILITY_FIELDS",
    "LABEL_ROOT",
    "LOMO_FIELDS",
    "NEGATIVE_FIELDS",
    "OUTPUT_ROOT",
    "PREPROCESSED_FIELDS",
    "SPLIT_FIELDS",
    "TRANSFER_FIELDS",
    "discover_fold_specs",
    "load_aligned_fold",
    "main",
    "write_tsv",
]


def main() -> None:
    from main_analysis import main as run_main_analysis

    run_main_analysis()


if __name__ == "__main__":
    main()
