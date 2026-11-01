cmake_minimum_required(VERSION 3.21)

# 1. CRITICAL: Paths must be set BEFORE the project() call so CMake
# can find the HIP compiler and internal language configurations.
# Override with -DROCM_ROOT=/path/to/rocm if your installation differs.
set(ROCM_ROOT "/opt/rocm" CACHE PATH "ROCm installation root")
list(APPEND CMAKE_PREFIX_PATH "${ROCM_ROOT}")
set(CMAKE_HIP_COMPILER "${ROCM_ROOT}/bin/amdclang++" CACHE FILEPATH "HIP compiler")

# 2. Define target GPU architecture natively (replaces --amdgpu-target)
set(CMAKE_HIP_ARCHITECTURES "gfx1150")

project(gfx1150-inference LANGUAGES CXX HIP)

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
