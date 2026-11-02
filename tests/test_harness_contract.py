"""Meta-tests that enforce the Phase 7A-1 pytest harness contract.

These are *harness* tests: they assert properties of the test suite itself
rather than of the runtime. They exist because the G0 audit found that 13
baseline test functions returned ``True``/``False`` instead of asserting, and
pytest ignores a test's return value — such a test could never fail (audit
AUD-2). A regression in that property must fail the suite loudly.

Audit trace: AUD-2, QAQC-2. Phase 7A-1.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

_TESTS_DIR = pathlib.Path(__file__).resolve().parent

# These are harness meta-tests: they are pure CPU and belong to the CPU lane.
pytestmark = pytest.mark.cpu


def _iter_test_modules():
    """Yield every test module under ``tests/``."""
    for path in sorted(_TESTS_DIR.glob("test_*.py")):
        yield path


def _test_functions(tree: ast.Module):
    """Yield ``(node, module_path)`` for every ``test_*`` function definition."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                yield node


class _OwnBodyVisitor(ast.NodeVisitor):
    """Collects ``Return``/``Assert`` nodes without descending into nested defs.

    A helper defined *inside* a test function (e.g. ``_cpu_layer_ref``) is not
    the test's own return value, so nested definitions are not traversed.
    """

    def __init__(self) -> None:
        self.returns: list[ast.Return] = []
        self.asserts = 0

    def visit_FunctionDef(self, node):  # noqa: N802 - ast visitor protocol
        pass

    def visit_AsyncFunctionDef(self, node):  # noqa: N802 - ast visitor protocol
        pass

    def visit_Lambda(self, node):  # noqa: N802 - ast visitor protocol
        pass

    def visit_ClassDef(self, node):  # noqa: N802 - ast visitor protocol
        pass

    def visit_Return(self, node):  # noqa: N802 - ast visitor protocol
        self.returns.append(node)

    def visit_Assert(self, node):  # noqa: N802 - ast visitor protocol
        self.asserts += 1


@pytest.mark.parametrize(
    "module_path", list(_iter_test_modules()), ids=lambda p: p.name
)
def test_no_test_function_returns_a_value(module_path: pathlib.Path) -> None:
    """No ``test_*`` function may return a value (AUD-2).

    Pytest ignores a test function's return value and only emits a warning, so
    a test that ``return False`` instead of asserting can never fail.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    offenders = []
    for func in _test_functions(tree):
        visitor = _OwnBodyVisitor()
        for stmt in func.body:
            visitor.visit(stmt)
        for ret in visitor.returns:
            if ret.value is not None:
                offenders.append(f"{module_path.name}:{ret.lineno} {func.name}() returns a value")
    assert not offenders, (
        "Test functions must assert and return None:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "module_path", list(_iter_test_modules()), ids=lambda p: p.name
)
def test_no_test_function_is_annotated_bool(module_path: pathlib.Path) -> None:
    """No ``test_*`` function may be annotated ``-> bool`` (AUD-2)."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    offenders = []
    for func in _test_functions(tree):
        returns = func.returns
        if returns is not None and ast.unparse(returns) == "bool":
            offenders.append(f"{module_path.name}:{func.lineno} {func.name}() -> bool")
    assert not offenders, (
        "Test functions must not be annotated '-> bool':\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "module_path", list(_iter_test_modules()), ids=lambda p: p.name
)
def test_every_test_function_asserts_or_raises(module_path: pathlib.Path) -> None:
    """Every ``test_*`` function must contain an assertion or an explicit raise.

    A test body that can neither assert nor raise cannot fail.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    offenders = []
    for func in _test_functions(tree):
        visitor = _OwnBodyVisitor()
        for stmt in func.body:
            visitor.visit(stmt)
        has_raise = any(
            isinstance(node, ast.Raise)
            for stmt in func.body
            for node in ast.walk(stmt)
            if node is not None
            and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
        )
        # unittest-style self.assertX(...) also counts as an assertion.
        has_unittest_assert = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            for stmt in func.body
            for node in ast.walk(stmt)
        )
        # A call with doraise=True (e.g. py_compile.compile) raises on failure.
        has_doraise = any(
            isinstance(node, ast.Call)
            and any(
                kw.arg == "doraise"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            )
            for stmt in func.body
            for node in ast.walk(stmt)
        )
        if visitor.asserts == 0 and not has_raise and not has_unittest_assert and not has_doraise:
            offenders.append(f"{module_path.name}:{func.lineno} {func.name}()")
    assert not offenders, (
        "Every test function must assert or raise:\n  " + "\n  ".join(offenders)
    )


def test_gpu_lane_is_marked_and_cpu_lane_is_not() -> None:
    """The ``gpu`` marker must select exactly the hardware tests (AUD-2).

    ``pytest -m "not gpu"`` must select only CPU tests, and ``pytest -m gpu``
    must select only GPU tests. A module that is not marked at all would be
    collected by *both* selectors, which is the defect AUD-2 found at baseline
    (18 GPU tests were collected by ``-m "not gpu"``).

    The rule enforced here: every test module must declare ``pytestmark``
    explicitly. The GPU modules declare ``pytest.mark.gpu``; the CPU-only
    module declares ``pytest.mark.cpu``. A module with no ``pytestmark`` at all
    lands in *both* lanes and is therefore rejected.
    """
    unmarked_modules = []
    for path in _iter_test_modules():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        has_gpu_test = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            for node in ast.walk(tree)
        )
        if not has_gpu_test:
            continue
        if not re.search(r"pytestmark\s*=\s*pytest\.mark\.\w+", source):
            unmarked_modules.append(path.name)
    assert not unmarked_modules, (
        "Every module containing tests must declare pytestmark explicitly "
        "(pytest.mark.gpu or pytest.mark.cpu): " + ", ".join(unmarked_modules)
    )


def test_cpu_only_module_is_not_marked_gpu() -> None:
    """The CPU-only suite must be in the CPU lane, never the GPU lane.

    ``tests/test_cpu_only.py`` is the self-contained CPU regression suite; it
    must be selected by ``-m "not gpu"`` and deselected by ``-m gpu``.
    """
    source = (_TESTS_DIR / "test_cpu_only.py").read_text(encoding="utf-8")
    assert not re.search(r"pytestmark\s*=\s*pytest\.mark\.gpu", source), (
        "tests/test_cpu_only.py must not be marked 'gpu': it is the CPU-only lane"
    )


def test_no_module_level_matmul_module_import() -> None:
    """No test module may import ``matmul_module`` at module scope (AUD-2).

    A module-scope import of the extension makes collection fail with exit code
    2 on a CPU-only host. The extension must be obtained through the
    ``matmul_module`` fixture instead.
    """
    offenders = []
    for path in _iter_test_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:  # module scope only
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                targets = [node.module or ""]
                targets += [alias.name for alias in node.names]
            if any(t == "matmul_module" or t.startswith("matmul_module.") for t in targets):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "matmul_module must not be imported at module scope; use the "
        "'matmul_module' fixture:\n  " + "\n  ".join(offenders)
    )


def test_pytest_config_declares_required_markers() -> None:
    """``pyproject.toml`` must register the ``gpu``, ``cpu`` and ``slow`` markers.

    An unregistered marker makes ``-m`` selection silently match nothing (or
    error under ``--strict-markers``), which would break the lane split.
    """
    pyproject = (_TESTS_DIR.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.pytest.ini_options]" in pyproject, (
        "pyproject.toml must contain a [tool.pytest.ini_options] section"
    )
    for marker in ("gpu", "cpu", "slow"):
        assert re.search(rf'"{marker}\s*:', pyproject), (
            f"pytest marker '{marker}' must be registered in pyproject.toml"
        )
    assert "PytestReturnNotNoneWarning" in pyproject, (
        "pyproject.toml must turn PytestReturnNotNoneWarning into an error"
    )
