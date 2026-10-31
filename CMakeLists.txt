cmake_minimum_required(VERSION 3.21)

# 1. CRITICAL: Paths must be set BEFORE the project() call so CMake 
# can find the HIP compiler and internal language configurations.
list(APPEND CMAKE_PREFIX_PATH "/opt/rocm")
set(CMAKE_HIP_COMPILER "/opt/rocm/bin/amdclang++")

# 2. Define target GPU architecture natively (replaces --amdgpu-target)
set(CMAKE_HIP_ARCHITECTURES "gfx1150")

project(gfx1150-inference LANGUAGES CXX HIP)

# 3. Find ROCm math libraries (hip package is omitted as it's built-in via LANGUAGES HIP)
find_package(hipblas REQUIRED)
find_package(rocblas REQUIRED)

# Verify math library targets
if(NOT TARGET roc::hipblas)
    message(FATAL_ERROR "roc::hipblas target not found")
endif()
if(NOT TARGET roc::rocblas)
    message(FATAL_ERROR "roc::rocblas target not found")
endif()

# --- PyBind11 Configuration ---
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 REQUIRED)

# --- Project Structure ---
set(SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(KERNEL_DIR ${SOURCE_DIR}/kernels)
set(BINDINGS_DIR ${SOURCE_DIR}/python_bindings)

# --- HIP Matmul Python Extension Module ---
# Target name matches PYBIND11_MODULE(matmul_module, m) and `import matmul_module`
add_library(matmul_module MODULE
    ${KERNEL_DIR}/matmul.hip
    ${KERNEL_DIR}/dequantize.hip
    ${BINDINGS_DIR}/bindings.cpp
)

target_include_directories(matmul_module PRIVATE ${KERNEL_DIR} ${BINDINGS_DIR})

# 4. Link dependencies. Use pybind11::module for Python extension modules.
target_link_libraries(matmul_module PRIVATE
    roc::hipblas
    roc::rocblas
    pybind11::module
)

# Enable C++17 globally for HIP/PyBind11 compatibility
target_compile_features(matmul_module PRIVATE cxx_std_17)
set_target_properties(matmul_module PROPERTIES
    PREFIX ""
    OUTPUT_NAME "matmul_module"
    HIP_STANDARD 17
    HIP_STANDARD_REQUIRED ON
    BUILD_RPATH "/opt/rocm/lib;/opt/rocm/core-10.1/lib"
)
