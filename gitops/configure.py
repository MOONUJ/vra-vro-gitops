#!/usr/bin/env python3
"""이전 설정 명령과의 호환 wrapper."""

import runpy
import sys
from pathlib import Path

TOOL_DIRECTORY = Path(__file__).resolve().parents[1] / "tooling" / "vcf"
sys.path.insert(0, str(TOOL_DIRECTORY))
runpy.run_path(str(TOOL_DIRECTORY / "configure.py"), run_name="__main__")
