"""Meta-tests that enforce the Phase 7A-1 pytest harness contract.

These are *harness* tests: they assert properties of the test suite itself
rather than of the runtime. They exist because the G0 audit found that 13
baseline test functions returned ``True``/``False`` instead of asserting, and
pytest ignores a test's return value — such a test could never fail (audit
AUD-2). A regression in that property must fail the suite loudly.

The G1 audit found two weaknesses in the first version of these meta-tests
(AUD-7A1-1 / AUD-7A1-2): the lane check accepted *any* marker, and the
assertion check counted a ``raise`` inside a nested, never-called helper. Both
are now exact.

Audit trace: AUD-2, AUD-7A1-1, AUD-7A1-2, QAQC-2. Phase 7A-1 follow-up.
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
    """Collects failure mechanisms without descending into nested defs.

    A helper defined *inside* a test function (e.g. ``_cpu_layer_ref``) is not
    part of the test's own failure path, so nested definitions are not traversed.
    This is what makes the contract "the test itself must have a failure path",
    not "somewhere inside the test there is a ``raise``".

    Collecting every failure mechanism through one pruning visitor keeps the
    check consistent: ``assert``, ``raise``, ``self.assertX(...)`` and
    ``doraise=True`` calls are all measured at the same nesting level.
    """

    def __init__(self) -> None:
        self.returns: list[ast.Return] = []
        self.asserts = 0
        self.raises: list[ast.Raise] = []
        self.unittest_asserts = 0
        self.doraise_calls = 0

    def visit_FunctionDef(self, node):  # noqa: N802 - ast visitor protocol
        pass  # nested function: do not descend

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

    def visit_Raise(self, node):  # noqa: N802 - ast visitor protocol
        self.raises.append(node)

    def visit_Call(self, node):  # noqa: N802 - ast visitor protocol
        # unittest-style self.assertX(...) also counts as an assertion.
        if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert"):
            self.unittest_asserts += 1
        # A call with doraise=True raises on failure (e.g. py_compile.compile).
        elif any(
            kw.arg == "doraise"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        ):
            self.doraise_calls += 1
        self.generic_visit(node)


def _module_lane(tree: ast.Module) -> str | None:
    """Return the lane marker declared at module scope by ``pytestmark``.

    Only module-scope assignments count, matching pytest's own semantics: a
    ``pytestmark`` inside a function or class body does not mark the module.
    A module-level ``if`` guard (as used by ``test_cpu_only.py``, which imports
    pytest optionally) is still module scope and is therefore honoured.
    """
    lanes: list[str] = []

    class _ModuleScopeVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):  # noqa: N802 - ast visitor protocol
            pass  # not module scope

        def visit_AsyncFunctionDef(self, node):  # noqa: N802 - ast visitor protocol
            pass

        def visit_ClassDef(self, node):  # noqa: N802 - ast visitor protocol
            pass

        def visit_Assign(self, node):  # noqa: N802 - ast visitor protocol
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "pytestmark":
                    name = _marker_name(node.value)
                    if name:
                        lanes.append(name)
            self.generic_visit(node)

    def _marker_name(value: ast.expr) -> str | None:
        """Extract the marker name from ``pytest.mark.<name>``."""
        if isinstance(value, ast.Attribute):
            return value.attr
        if isinstance(value, (ast.List, ast.Tuple)):
            for element in value.elts:
                name = _marker_name(element)
                if name:
                    return name
        return None

    _ModuleScopeVisitor().visit(tree)
    if not lanes:
        return None
    if len(set(lanes)) > 1:
        return "<conflicting:" + ",".join(sorted(set(lanes))) + ">"
    return lanes[0]


def _handles_import_error(handler: ast.ExceptHandler) -> bool:
    """Return True if an except handler catches ImportError/ModuleNotFoundError."""
    if handler.type is None:  # bare except
        return True
    if isinstance(handler.type, ast.Name):
        return handler.type.id in ("ImportError", "ModuleNotFoundError")
    if isinstance(handler.type, ast.Tuple):
        return any(
            isinstance(elt, ast.Name) and elt.id in ("ImportError", "ModuleNotFoundError")
            for elt in handler.type.elts
        )
    return False


class _ExtensionUseVisitor(ast.NodeVisitor):
    """Finds hard dependencies on the compiled HIP extension.

    A request for the ``matmul_module`` fixture is always a hard dependency.
    An ``import matmul_module`` inside a test body is a hard dependency only
    when it is *unguarded*: a guarded import (inside a ``try`` whose handler
    catches ``ImportError``) provides a stub fallback and still runs on a
    CPU-only host, so it does not make the module a GPU test.
    """

    def __init__(self) -> None:
        self.uses_extension = False
        self._guarded_depth = 0

    def visit_FunctionDef(self, node):  # noqa: N802 - ast visitor protocol
        for arg in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
            if arg.arg == "matmul_module":
                self.uses_extension = True
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncFunctionDef(self, node):  # noqa: N802 - ast visitor protocol
        self.visit_FunctionDef(node)

    def visit_Try(self, node):  # noqa: N802 - ast visitor protocol
        # An import in the `try` body is guarded when a handler catches
        # ImportError: the import may fail and the handler supplies a fallback.
        guarded = any(_handles_import_error(h) for h in node.handlers)
        self._guarded_depth += 1 if guarded else 0
        for stmt in node.body:
            self.visit(stmt)
        self._guarded_depth -= 1 if guarded else 0
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)
        for handler in node.handlers:
            for stmt in handler.body:
                self.visit(stmt)

    def visit_Import(self, node):  # noqa: N802 - ast visitor protocol
        if self._guarded_depth == 0 and any(
            alias.name == "matmul_module" for alias in node.names
        ):
            self.uses_extension = True

    def visit_ImportFrom(self, node):  # noqa: N802 - ast visitor protocol
        if self._guarded_depth == 0 and node.module == "matmul_module":
            self.uses_extension = True


def _uses_matmul_module(tree: ast.Module) -> bool:
    """Return True if the module *hard*-depends on the compiled HIP extension.

    A module that requests the ``matmul_module`` fixture is a GPU test by
    construction and must live in the ``gpu`` lane. So is a module that imports
    ``matmul_module`` unguarded inside a test body — without the extension that
    import raises and the test errors.

    An *optional* import (guarded by ``except ImportError`` with a stub
    fallback) does not count: the test still runs on a CPU-only host, so the
    module belongs in the ``cpu`` lane. ``tests/test_cpu_only.py`` uses exactly
    that pattern to exercise the CPU paths on a host with no extension.
    """
    visitor = _ExtensionUseVisitor()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                visitor.visit_FunctionDef(node)
    return visitor.uses_extension


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
    """Every ``test_*`` function must have a **top-level** failure path.

    A test body that can neither assert nor raise cannot fail.

    The failure mechanism must belong to the test itself: a ``raise`` inside a
    nested, never-called helper does not make the test able to fail. All four
    mechanisms (``assert``, ``raise``, ``self.assertX(...)`` and a call with
    ``doraise=True``) are therefore measured with the same nested-def-pruning
    visitor, so a nested helper cannot satisfy the contract (AUD-7A1-2).
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    offenders = []
    for func in _test_functions(tree):
        visitor = _OwnBodyVisitor()
        for stmt in func.body:
            visitor.visit(stmt)
        if (
            visitor.asserts == 0
            and not visitor.raises
            and visitor.unittest_asserts == 0
            and visitor.doraise_calls == 0
        ):
            offenders.append(f"{module_path.name}:{func.lineno} {func.name}()")
    assert not offenders, (
        "Every test function must assert or raise at its own top level "
        "(a raise inside a nested helper does not count):\n  "
        + "\n  ".join(offenders)
    )


#: The lane every test module belongs to. A new test module must be added here
#: deliberately: the check is not satisfied by "some marker exists" but by the
#: module declaring exactly the marker this mapping requires (AUD-7A1-1).
EXPECTED_LANES = {
    "test_matmul.py": "gpu",
    "test_gguf_and_q4.py": "gpu",
    "test_layer.py": "gpu",
    "test_full_model.py": "gpu",
    "test_phase5_scale.py": "gpu",
    "test_cpu_only.py": "cpu",
    "test_harness_contract.py": "cpu",
}


def test_every_test_module_declares_its_exact_lane() -> None:
    """Every test module must declare exactly the lane it belongs to.

    ``pytest -m "not gpu"`` must select only CPU tests, and ``pytest -m gpu``
    must select only GPU tests. A module that is not marked at all lands in
    *both* selectors, which is the defect AUD-2 found at baseline (18 GPU tests
    were collected by ``-m "not gpu"``).

    The check is deliberately exact rather than presence-only: a module marked
    ``cpu`` that requests the ``matmul_module`` fixture is a GPU test in the
    wrong lane, and must be rejected (AUD-7A1-1). Every module must appear in
    :data:`EXPECTED_LANES`, so a new test file forces a deliberate lane choice.
    """
    offenders = []
    for path in _iter_test_modules():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        has_tests = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            for node in ast.walk(tree)
        )
        if not has_tests:
            continue

        expected = EXPECTED_LANES.get(path.name)
        if expected is None:
            offenders.append(
                f"{path.name}: not classified — add it to EXPECTED_LANES with its lane"
            )
            continue

        actual = _module_lane(tree)
        if actual is None:
            offenders.append(f"{path.name}: no module-level pytestmark (expected '{expected}')")
            continue
        if actual != expected:
            offenders.append(
                f"{path.name}: pytestmark is '{actual}', expected '{expected}'"
            )
            continue

        # Defence in depth: a module that needs the extension is a GPU test by
        # construction and must not sit in the CPU lane.
        if expected == "cpu" and _uses_matmul_module(tree):
            offenders.append(
                f"{path.name}: uses the matmul_module extension but is in the 'cpu' lane"
            )

    assert not offenders, (
        "Every test module must declare exactly its expected lane:\n  "
        + "\n  ".join(offenders)
    )


def test_cpu_only_module_is_not_marked_gpu() -> None:
    """The CPU-only suite must be in the CPU lane, never the GPU lane.

    ``tests/test_cpu_only.py`` is the self-contained CPU regression suite; it
    must be selected by ``-m "not gpu"`` and deselected by ``-m gpu``. This is
    implied by :data:`EXPECTED_LANES`, and asserted separately so the specific
    regression is named.
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
