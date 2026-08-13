from pathlib import Path


def test_default_extra_forbids_sbi_torch_cuda():
    text = Path("pyproject.toml").read_text()
    for banned in ("sbi", "torch", "cuda", "cupy"):
        assert banned not in text.lower()
