import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.catalog import load_catalog  # noqa: E402


@pytest.fixture(scope="session")
def cat():
    return load_catalog(strict=True)
