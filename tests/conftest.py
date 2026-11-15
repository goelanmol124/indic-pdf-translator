import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_example():
    spec = importlib.util.spec_from_file_location("make_sample_pdf", ROOT / "examples" / "make_sample_pdf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> Path:
    return _load_example().make_sample(tmp_path_factory.mktemp("pdf") / "sample.pdf")
