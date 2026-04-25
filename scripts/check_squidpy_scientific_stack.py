#!/usr/bin/env python3
"""Smoke-check the pinned Squidpy scientific stack."""

from __future__ import annotations

import importlib


def module_version(module_name: str) -> str:
    module = importlib.import_module(module_name)
    return getattr(module, "__version__", "unknown")


def main() -> None:
    modules = ("scanpy", "squidpy", "spatialdata")
    for module_name in modules:
        version = module_version(module_name)
        print(f"{module_name}=={version}")


if __name__ == "__main__":
    main()
