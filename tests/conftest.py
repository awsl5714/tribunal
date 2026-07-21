from pathlib import Path

import pytest

from tribunal import load_rubric

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def rubric():
    return load_rubric(EXAMPLES / "rubric.yaml")
