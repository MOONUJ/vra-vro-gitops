"""VCF Automation GitOps 공통 tooling package.

기존 script entry point의 절대 import 호환성은 0.x 전환 기간에만 유지한다.
"""

from pathlib import Path
import sys


_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

__version__ = "0.3.2"
