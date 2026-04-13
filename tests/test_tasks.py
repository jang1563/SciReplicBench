from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scireplicbench.tasks import (
    COMPOSE_FILE,
    COMPOSE_OVERRIDE_ENV,
    ENV_VARIANT_ENV,
    compose_file_for_paper,
)


class TaskConfigTest(unittest.TestCase):
    def test_compose_file_for_known_paper_uses_paper_specific_file(self) -> None:
        compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.name, "compose.squidpy_spatial.yaml")
        self.assertTrue(compose_file.exists())

    def test_compose_file_for_unknown_paper_falls_back_to_default(self) -> None:
        compose_file = compose_file_for_paper("unknown_paper")
        self.assertEqual(compose_file, COMPOSE_FILE)
        self.assertEqual(compose_file, Path(COMPOSE_FILE))

    def test_compose_file_variant_uses_smoke_compose(self) -> None:
        with patch.dict(os.environ, {ENV_VARIANT_ENV: "smoke"}, clear=False):
            compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.name, "compose.smoke.yaml")
        self.assertTrue(compose_file.exists())

    def test_compose_file_override_uses_explicit_path(self) -> None:
        override = "environments/compose.smoke.yaml"
        with patch.dict(os.environ, {COMPOSE_OVERRIDE_ENV: override}, clear=False):
            compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.resolve(), (Path(COMPOSE_FILE).parent / "compose.smoke.yaml").resolve())
