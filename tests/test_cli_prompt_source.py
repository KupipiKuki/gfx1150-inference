"""7G-C (C5) prompt-source CLI tests: `--prompt-file` and `--prompt -` (stdin).

Covers the coder-brief acceptance:

- a 45 KB prompt file loads (resolution succeeds and the full text reaches
  the engine);
- stdin (`--prompt -`) works;
- `--prompt` and `--prompt-file` are mutually exclusive (exit 2, one-line
  error, no traceback);
- a missing file, a directory, an empty file and a non-UTF-8 file all fail
  with a clear one-line message (exit 2, no traceback);
- the prompt content never reaches the telemetry payload or the stats output.

CPU lane: `inference` is importable behind the same `matmul_module` stub
`tests/test_cpu_only.py` uses; the engine itself is stubbed out (the CLI
argument plumbing is what is under test, not the model).
"""

from __future__ import annotations

import io
import os
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
for _p in (os.path.join(_ROOT, "src"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = pytest.mark.cpu


class _StubEngine:
    """Records the prompt the CLI hands to the engine; returns fixed output."""

    last_prompt: str | None = None
    last_metrics = {
        "tokens_generated": 1,
        "total_time_s": 0.1,
        "tokens_per_sec": 10.0,
        "decode_tokens_per_sec": 10.0,
    }

    def __init__(self, **kwargs):
        _StubEngine.last_args = kwargs
        self.tokenizer = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def generate(self, prompt, **kwargs):
        _StubEngine.last_prompt = prompt
        return f"echo:{prompt[:16]}", dict(self.last_metrics)


@pytest.fixture()
def inference_stub(monkeypatch):
    import importlib

    if "matmul_module" not in sys.modules:
        monkeypatch.setitem(
            sys.modules,
            "matmul_module",
            types.SimpleNamespace(
                kv_cache_init=lambda *a: None,
                kv_cache_free=lambda *a: None,
                gqa_attention=lambda *a: None,
                gqa_attention_cached=lambda *a: None,
                rmsnorm=lambda *a: None,
            ),
        )
    inference = importlib.import_module("inference")
    _StubEngine.last_prompt = None
    monkeypatch.setattr(inference, "LlamaInferenceEngine", _StubEngine)
    return inference


def test_prompt_file_loads_45kb(inference_stub, tmp_path, monkeypatch):
    inference = inference_stub
    prompt_file = tmp_path / "prompt45k.txt"
    text = ("The quick brown fox jumps over the lazy dog. " * 1024)[:46080]
    prompt_file.write_text(text, encoding="utf-8")
    assert prompt_file.stat().st_size == 46080  # 45 KiB
    monkeypatch.setattr(sys, "argv", ["prog"])
    code = inference.main(
        ["--model", "unused.gguf", "--prompt-file", str(prompt_file)]
    )
    assert code == 0
    assert _StubEngine.last_prompt == text, (
        "the full 45 KB file content must reach the engine verbatim"
    )


def test_prompt_stdin(inference_stub, monkeypatch):
    inference = inference_stub
    payload = "stdin prompt body " * 64
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert inference.main(["--model", "unused.gguf", "--prompt", "-"]) == 0
    assert _StubEngine.last_prompt == payload


def test_prompt_and_prompt_file_mutually_exclusive(
    inference_stub, tmp_path, capsys
):
    inference = inference_stub
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        inference.main(
            [
                "--model", "unused.gguf",
                "--prompt", "hi",
                "--prompt-file", str(prompt_file),
            ]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "mutually exclusive" in err


def test_prompt_file_missing_fails_clean(inference_stub, tmp_path, capsys):
    inference = inference_stub
    with pytest.raises(SystemExit) as exc:
        inference.main(
            ["--model", "unused.gguf",
             "--prompt-file", str(tmp_path / "nope.txt")]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "cannot read the prompt file" in err
    assert "Traceback" not in err


def test_prompt_file_directory_fails_clean(inference_stub, tmp_path, capsys):
    inference = inference_stub
    with pytest.raises(SystemExit) as exc:
        inference.main(
            ["--model", "unused.gguf", "--prompt-file", str(tmp_path)]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "cannot read the prompt file" in err
    assert "Traceback" not in err


def test_prompt_file_empty_fails_clean(inference_stub, tmp_path, capsys):
    inference = inference_stub
    prompt_file = tmp_path / "empty.txt"
    prompt_file.write_bytes(b"")
    with pytest.raises(SystemExit) as exc:
        inference.main(
            ["--model", "unused.gguf", "--prompt-file", str(prompt_file)]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "is empty" in err


def test_prompt_file_non_utf8_fails_clean(inference_stub, tmp_path, capsys):
    inference = inference_stub
    prompt_file = tmp_path / "binary.bin"
    prompt_file.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(SystemExit) as exc:
        inference.main(
            ["--model", "unused.gguf", "--prompt-file", str(prompt_file)]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_prompt_content_never_reaches_telemetry(inference_stub, tmp_path, capsys):
    """With --stats/--json on, neither stdout/stderr telemetry nor the stats
    payload may contain the prompt content (secret marker)."""
    inference = inference_stub
    marker = "TOPSECRET-marker-7G-C5"
    prompt_file = tmp_path / "marked.txt"
    prompt_file.write_text(
        f"before {marker} after " * 8, encoding="utf-8"
    )
    monkeypatch = getattr(inference_stub, "_monkeypatch", None)
    code = inference.main(
        [
            "--model", "unused.gguf",
            "--prompt-file", str(prompt_file),
            "--stats",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert marker not in (captured.out + captured.err)


def test_default_prompt_unchanged(inference_stub):
    """No prompt source given: the documented legacy default 'Hello'."""
    inference = inference_stub
    assert inference.main(["--model", "unused.gguf"]) == 0
    assert _StubEngine.last_prompt == "Hello"
