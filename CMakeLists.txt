cmake_minimum_required(VERSION 3.21)

# 1. CRITICAL: Paths must be set BEFORE the project() call so CMake
# can find the HIP compiler and internal language configurations.
# Override with -DROCM_ROOT=/path/to/rocm if your installation differs.
set(ROCM_ROOT "/opt/rocm" CACHE PATH "ROCm installation root")
list(APPEND CMAKE_PREFIX_PATH "${ROCM_ROOT}")
set(CMAKE_HIP_COMPILER "${ROCM_ROOT}/bin/amdclang++" CACHE FILEPATH "HIP compiler")

# 2. Define target GPU architecture natively (replaces --amdgpu-target)
set(CMAKE_HIP_ARCHITECTURES "gfx1150")

# --- PyBind11 Configuration ---
# pybind11 is a Python package, so on most systems its CMake package lives
# inside site-packages rather than on CMAKE_PREFIX_PATH. A plain
# find_package(pybind11) therefore fails on a clean tree (G0 condition C-1),
# and the documented build command only worked if the caller happened to export
# pybind11_DIR. Ask the interpreter we are building for where its pybind11
# CMake package is -- the same thing setup.py does for `pip install`. An
# explicit -Dpybind11_DIR=... still takes precedence.
#
# This runs before project() so that a missing pybind11 is reported as such
# instead of being masked by a missing HIP toolchain, and so that the
# discovery can be exercised on a host without ROCm.
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)

find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    message(STATUS "pybind11 CMake package: ${pybind11_DIR}")
else()
    set(_pybind11_cmake_dir "")
    # pybind11 >= 2.6 ships a --cmakedir entry point.
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -m pybind11 --cmakedir
        RESULT_VARIABLE _pybind11_probe_status
        OUTPUT_VARIABLE _pybind11_probe_output
        ERROR_VARIABLE _pybind11_probe_error
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(_pybind11_probe_status EQUAL 0 AND IS_DIRECTORY "${_pybind11_probe_output}")
        set(_pybind11_cmake_dir "${_pybind11_probe_output}")
    else()
        # Older pybind11 releases expose the same directory via the module.
        execute_process(
            COMMAND "${Python_EXECUTABLE}" -c "import pybind11; print(pybind11.get_cmake_dir())"
            RESULT_VARIABLE _pybind11_probe_status
            OUTPUT_VARIABLE _pybind11_probe_output
            ERROR_VARIABLE _pybind11_probe_error
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        if(_pybind11_probe_status EQUAL 0 AND IS_DIRECTORY "${_pybind11_probe_output}")
            set(_pybind11_cmake_dir "${_pybind11_probe_output}")
        endif()
    endif()
    if(_pybind11_cmake_dir)
        message(STATUS "pybind11 CMake package: ${_pybind11_cmake_dir}")
        find_package(pybind11 CONFIG REQUIRED PATHS "${_pybind11_cmake_dir}" NO_DEFAULT_PATH)
    else()
        message(FATAL_ERROR
            "pybind11 was not found for ${Python_EXECUTABLE}.\n"
            "Install it for that interpreter:\n"
            "  ${Python_EXECUTABLE} -m pip install 'pybind11>=2.12'\n"
            "or point CMake at an existing installation:\n"
            "  cmake -B build -DCMAKE_BUILD_TYPE=Release -Dpybind11_DIR=/path/to/pybind11/share/cmake/pybind11\n"
            "(probe output was: ${_pybind11_probe_output} ${_pybind11_probe_error})")
    endif()
endif()

project(gfx1150-inference LANGUAGES CXX HIP)

# --- Project Structure ---
set(SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(KERNEL_DIR ${SOURCE_DIR}/kernels)
set(BINDINGS_DIR ${SOURCE_DIR}/python_bindings)

# --- HIP Matmul Python Extension Module ---
# Target name matches PYBIND11_MODULE(matmul_module, m) and `import matmul_module`
add_library(matmul_module MODULE
    ${KERNEL_DIR}/matmul.hip
    ${KERNEL_DIR}/dequantize.hip
    ${KERNEL_DIR}/rmsnorm.hip
    ${KERNEL_DIR}/rope.hip
    ${KERNEL_DIR}/attention.hip
    ${KERNEL_DIR}/mlp.hip
    ${BINDINGS_DIR}/bindings.cpp
)

target_include_directories(matmul_module PRIVATE ${KERNEL_DIR} ${BINDINGS_DIR})

# 3. Link dependencies. All compute kernels are custom HIP C++17; no external BLAS required.
target_link_libraries(matmul_module PRIVATE
    pybind11::module
)

# Enable C++17 globally for HIP/PyBind11 compatibility
target_compile_features(matmul_module PRIVATE cxx_std_17)
set_target_properties(matmul_module PROPERTIES
    PREFIX ""
    OUTPUT_NAME "matmul_module"
    HIP_STANDARD 17
    HIP_STANDARD_REQUIRED ON
    BUILD_RPATH "${ROCM_ROOT}/lib"
)
