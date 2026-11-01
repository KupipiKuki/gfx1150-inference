"""
Setuptools + CMake build hook for `gfx1150-inference`.

Compiles the ROCm/HIP C++17 `matmul_module` extension via `CMakeLists.txt` during
`pip install .` or `pip install -e . --no-build-isolation` and places the compiled
shared object into both the setuptools extension output path and `build/`.
(Long-term packaging alternative: `scikit-build-core` once ROCm wheel toolchains are standardized.)
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import warnings
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


class CMakeExtension(Extension):
    def __init__(self, name: str, sourcedir: str = "") -> None:
        super().__init__(name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def build_extension(self, ext: Extension) -> None:
        if not isinstance(ext, CMakeExtension):
            super().build_extension(ext)
            return

        if os.environ.get("GFX1150_SKIP_CMAKE", "0") == "1":
            warnings.warn(
                "GFX1150_SKIP_CMAKE=1 is set: skipping CMake compilation of 'matmul_module'. "
                "The resulting installation will support CPU-only utilities until built with ROCm.",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if shutil.which("cmake") is None:
            raise RuntimeError(
                "CMake (>= 3.21) is required to build the 'matmul_module' HIP extension, "
                "but 'cmake' was not found on PATH. Install cmake or run "
                "'pip install -e . --no-build-isolation'."
            )

        rocm_root = os.environ.get("ROCM_ROOT", "/opt/rocm")
        hip_compiler = os.path.join(rocm_root, "bin", "amdclang++")
        hipcc_path = os.path.join(rocm_root, "bin", "hipcc")
        if not (os.path.isdir(rocm_root) and (os.path.exists(hip_compiler) or os.path.exists(hipcc_path))):
            raise RuntimeError(
                f"ROCm toolchain not found at ROCM_ROOT='{rocm_root}' "
                f"(expected '{hip_compiler}' or '{hipcc_path}').\n"
                "Ensure ROCm 6.1+ is installed, set ROCM_ROOT=/path/to/rocm if installed "
                "in a non-default location, and install with:\n"
                "  pip install -e . --no-build-isolation\n"
                "(To install Python-only modules without compiling HIP kernels, set GFX1150_SKIP_CMAKE=1.)"
            )

        ext_fullpath = os.path.abspath(self.get_ext_fullpath(ext.name))
        ext_dir = os.path.dirname(ext_fullpath)
        os.makedirs(ext_dir, exist_ok=True)

        build_temp = os.path.abspath(getattr(self, "build_temp", os.path.join(ext.sourcedir, "build")))
        os.makedirs(build_temp, exist_ok=True)

        cmake_args = [
            "cmake",
            "-S",
            ext.sourcedir,
            "-B",
            build_temp,
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DROCM_ROOT={rocm_root}",
        ]

        # Point CMake at this interpreter's pybind11 package. Without this, a clean
        # `pip install` from an sdist fails in find_package(pybind11) on systems where
        # pybind11's CMake config is only present inside site-packages.
        try:
            import pybind11

            pybind11_cmake_dir = pybind11.get_cmake_dir()
        except Exception:  # pragma: no cover - pybind11 is a declared build requirement
            pybind11_cmake_dir = None
        if pybind11_cmake_dir and os.path.isdir(pybind11_cmake_dir):
            cmake_args.append(f"-Dpybind11_DIR={pybind11_cmake_dir}")

        max_jobs = str(min(os.cpu_count() or 4, 8))
        subprocess.check_call(cmake_args)
        subprocess.check_call(["cmake", "--build", build_temp, "-j", max_jobs])

        built_candidates = sorted(glob.glob(os.path.join(build_temp, "matmul_module*.so")))
        if not built_candidates:
            raise RuntimeError(f"CMake build succeeded but no matmul_module*.so found in {build_temp}")

        src_so = built_candidates[0]
        if os.path.abspath(src_so) != ext_fullpath:
            shutil.copy2(src_so, ext_fullpath)

        # Also copy to in-tree build/ directory if present or in editable mode
        in_tree_build = os.path.join(ext.sourcedir, "build")
        if os.path.isdir(in_tree_build):
            dst_in_tree = os.path.join(in_tree_build, os.path.basename(src_so))
            if os.path.abspath(src_so) != os.path.abspath(dst_in_tree):
                shutil.copy2(src_so, dst_in_tree)


setup(
    ext_modules=[CMakeExtension("matmul_module")],
    cmdclass={"build_ext": CMakeBuild},
)
