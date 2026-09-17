#!/usr/bin/env python3
"""이전 Day-2 명령과의 호환 wrapper. 새 명령은 tooling/vcf/vcf_sync.py이다."""

import runpy
import sys
from pathlib import Path

TOOL_DIRECTORY = Path(__file__).resolve().parents[1] / "tooling" / "vcf"
sys.path.insert(0, str(TOOL_DIRECTORY))
runpy.run_path(str(TOOL_DIRECTORY / "vcf_sync.py"), run_name="__main__")
