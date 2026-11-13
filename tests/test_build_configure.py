"""Smoke test for the documented clean-clone build entry point.

Phase 7A-8. Audit trace: G0 condition C-1 ("the README's documented
``cmake -B build -DCMAKE_BUILD_TYPE=Release`` command fails on a clean tree"
because ``find_package(pybind11)`` cannot see the CMake package that ships
inside site-packages).

The test runs the documented configure command against a *fresh* build
directory, so no pre-existing CMake cache can hide a discovery failure, and
with ``pybind11_DIR`` removed from the environment, so the command cannot
silently depend on an ambient hint.

The build needs two independent prerequisites: a Python package (pybind11) and
a system toolchain (ROCm/HIP). pybind11 is checked here directly. ROCm is not:
the pybind11 discovery happens before the HIP language is enabled, so the
discovery is verified even on a host without ROCm, and the configure is only
required to succeed outright when the HIP toolchain is present.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

# A build-configure test needs neither the compiled extension nor a GPU.
pytestmark = pytest.mark.cpu

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The documented command. The build directory is redirected to a temporary
#: path so the run starts from a clean cache and leaves no artefact behind.
_DOCUMENTED_ARGS = ("-DCMAKE_BUILD_TYPE=Release",)

#: CMake's own "I could not find pybind11" wording.
_PYBIND11_NOT_FOUND = 'Could not find a package configuration file provided by "pybind11"'

#: Emitted by CMakeLists.txt once the pybind11 CMake package has been located.
_DISCOVERY_MARKER = "pybind11 CMake package:"


def _hip_toolchain_available() -> bool:
    """True when the ROCm HIP compiler is present on this host."""
    rocm_root = pathlib.Path(os.environ.get("ROCM_ROOT", "/opt/rocm"))
    return (rocm_root / "bin" / "amdclang++").exists()


def _pybind11_installed() -> bool:
    """True when pybind11 is importable for the interpreter running the tests."""
    try:
        import pybind11  # noqa: F401
    except ImportError:
        return False
    return True


def _run_configure(build_dir: pathlib.Path) -> subprocess.CompletedProcess:
    """Run the documented configure command against a fresh build directory."""
    env = dict(os.environ)
    # The documented command must not depend on an ambient hint.
    env.pop("pybind11_DIR", None)
    env.pop("CMAKE_PREFIX_PATH", None)
    return subprocess.run(
        [
            "cmake",
            "-S",
            str(_REPO_ROOT),
            "-B",
            str(build_dir),
            *_DOCUMENTED_ARGS,
        ],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def test_documented_configure_locates_pybind11_without_an_ambient_hint(
    tmp_path: pathlib.Path,
) -> None:
    """The documented configure must find pybind11 on its own (G0 C-1).

    Before the fix, ``find_package(pybind11 REQUIRED)`` only worked if the
    caller happened to export ``pybind11_DIR``, or if the interpreter's
    installation prefix happened to be on ``PATH``; on a clean tree with the
    documented prerequisites the command failed at ``CMakeLists.txt`` with
    "Could not find a package configuration file provided by pybind11".

    The discovery must therefore be explicit, which is what the CMake status
    marker asserts: a build that only works because of an ambient hint is not
    a fixed build.
    """
    if shutil.which("cmake") is None:
        pytest.skip("cmake is not installed on this host")
    if not _pybind11_installed():
        pytest.skip(
            "pybind11 is not installed for this interpreter (a documented "
            "prerequisite); the discovery cannot be exercised"
        )

    build_dir = tmp_path / "build"
    result = _run_configure(build_dir)
    output = result.stdout + result.stderr

    assert _PYBIND11_NOT_FOUND not in output, (
        "the documented configure could not find pybind11; it must be "
        "discovered from the interpreter, not from an ambient pybind11_DIR\n"
        f"{output}"
    )
    assert _DISCOVERY_MARKER in output, (
        "the configure did not report a pybind11 CMake package; the discovery "
        f"step did not run\n{output}"
    )


def test_documented_configure_succeeds_with_the_hip_toolchain(
    tmp_path: pathlib.Path,
) -> None:
    """The documented command must configure the project end to end.

    This needs the ROCm/HIP toolchain, because the project enables the HIP
    language. Without it the configure cannot get past ``project()``, so the
    check is skipped rather than silently passing -- the pybind11 half of the
    contract is covered by the test above, which needs no ROCm.
    """
    if shutil.which("cmake") is None:
        pytest.skip("cmake is not installed on this host")
    if not _hip_toolchain_available():
        pytest.skip(
            "no ROCm/HIP toolchain on this host; the configure cannot enable "
            "the HIP language"
        )

    build_dir = tmp_path / "build"
    result = _run_configure(build_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"the documented configure failed with exit {result.returncode}\n{output}"
    )


def test_configure_does_not_leave_a_cache_outside_the_build_directory(
    tmp_path: pathlib.Path,
) -> None:
    """A configure run must not write into the source tree.

    The documented command builds in ``build/``; the test redirects it to a
    temporary directory, and the repository must stay clean so that the next
    run really starts from a fresh cache.
    """
    if shutil.which("cmake") is None:
        pytest.skip("cmake is not installed on this host")

    before = sorted(p.name for p in _REPO_ROOT.iterdir())
    build_dir = tmp_path / "build"
    _run_configure(build_dir)
    after = sorted(p.name for p in _REPO_ROOT.iterdir())

    assert before == after, (
        "the configure wrote into the source tree; a clean-clone build must "
        f"not depend on or leave artefacts there\nbefore={before}\nafter={after}"
    )
