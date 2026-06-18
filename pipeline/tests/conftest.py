from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def contratos_menores_atom() -> Path:
    return FIXTURES / "sample_contratos_menores.atom"
