"""
Setuptools + CMake build hook for `gfx1150-inference`.

Compiles the ROCm/HIP C++17 `matmul_module` extension via `CMakeLists.txt` during
`pip install .` or `pip install -e . --no-build-isolation` and places the compiled
shared object into both the setuptools extension output path and `build/`.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
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
            return

        ext_fullpath = os.path.abspath(self.get_ext_fullpath(ext.name))
        ext_dir = os.path.dirname(ext_fullpath)
        os.makedirs(ext_dir, exist_ok=True)

        build_dir = os.path.join(ext.sourcedir, "build")
        os.makedirs(build_dir, exist_ok=True)

        cmake_args = [
            "cmake",
            "-S",
            ext.sourcedir,
            "-B",
            build_dir,
            "-DCMAKE_BUILD_TYPE=Release",
        ]
        rocm_root = os.environ.get("ROCM_ROOT")
        if rocm_root:
            cmake_args.append(f"-DROCM_ROOT={rocm_root}")

        subprocess.check_call(cmake_args)
        subprocess.check_call(["cmake", "--build", build_dir, "-j"])

        built_candidates = sorted(glob.glob(os.path.join(build_dir, "matmul_module*.so")))
        if not built_candidates:
            raise RuntimeError(f"CMake build succeeded but no matmul_module*.so found in {build_dir}")

        src_so = built_candidates[0]
        if os.path.abspath(src_so) != ext_fullpath:
            shutil.copy2(src_so, ext_fullpath)


setup(
    ext_modules=[CMakeExtension("matmul_module")],
    cmdclass={"build_ext": CMakeBuild},
)

