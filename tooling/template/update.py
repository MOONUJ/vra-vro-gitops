# -*- coding: utf-8 -*-
"""Deprecated path wrapper for the packaged template-update command."""

from pathlib import Path
import sys


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "vcf"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from template_update import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
