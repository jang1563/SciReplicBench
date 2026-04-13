from __future__ import annotations

import unittest
from pathlib import Path

from scireplicbench.tasks import COMPOSE_FILE, compose_file_for_paper


class TaskConfigTest(unittest.TestCase):
    def test_compose_file_for_known_paper_uses_paper_specific_file(self) -> None:
        compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.name, "compose.squidpy_spatial.yaml")
        self.assertTrue(compose_file.exists())

    def test_compose_file_for_unknown_paper_falls_back_to_default(self) -> None:
        compose_file = compose_file_for_paper("unknown_paper")
        self.assertEqual(compose_file, COMPOSE_FILE)
        self.assertEqual(compose_file, Path(COMPOSE_FILE))
