# BLOCKER-7C-1 — clean/sdist install cannot import `model_spec`

**Status:** fixed by the post-audit packaging commit (see the branch log).
**Found by:** CI on the first pushed 7C merge (`6820932`), not by the source-tree
lanes. This is exactly why the clean-install lane exists.

## Symptom

The first pushed 7C merge failed:

- CPU-Only Verification & Regression CI (`42315223493`): **failure**
  (CPU Parser/Tokenizer/Sampler/Packaging Suite and Sdist Install jobs)
- Clean-Clone Build CI (`42315223473`): **failure**

Root cause: `pyproject.toml` `[tool.setuptools] py-modules` listed
`gguf_parser, weight_loader, layer, kv_cache, tokenizer, inference` but not the
new `model_spec.py`. Source-tree tests passed because `src/` is on the path;
a clean/sdist install has no `model_spec`, so `layer.py`/`inference.py` fail to
import it.

## Fix

- Add `"model_spec"` to `pyproject.toml` `py-modules`.
- Extend `tests/test_cpu_only.py` V-8 to (a) require every top-level `src/*.py`
  module to appear in `py-modules`, and (b) require `src/model_spec.py` in the
  built sdist. This makes the same omission a CPU-only test failure, not only a
  post-merge CI failure.

## Verification

- `python3 tests/test_cpu_only.py` → **OK (12/12)**
- `python3 -O tests/test_cpu_only.py` → **OK (12/12)**
- `python3 setup.py sdist` → exit 0; archive contains `src/model_spec.py`
- fresh venv + `GFX1150_SKIP_CMAKE=1 pip install <sdist>` → exit 0
- installed `import model_spec` → `site-packages/model_spec.py`,
  `SUPPORTED_ARCHS = ['gemma', 'llama', 'phi3']`

CI re-run on the fixed merge is the remaining gate check; see the final
signoff for the run IDs.

## Scope note

The 7C brief's allowed-file list did not include `pyproject.toml`; the change is
limited to the new module entry (no packaging metadata/version/dependency change)
and is required for a clean install. The audit treats it as a justified
packaging-fix exception, not a new feature.
