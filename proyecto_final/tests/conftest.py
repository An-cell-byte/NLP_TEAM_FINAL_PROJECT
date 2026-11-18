import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore", category=FutureWarning)


@pytest.fixture(scope="session")
def encoder():
    from soporte_pln.encoder import Encoder
    return Encoder()


@pytest.fixture(scope="session")
def sistema(encoder):
    from soporte_pln.api import cargar_sistema
    return cargar_sistema(encoder=encoder)
