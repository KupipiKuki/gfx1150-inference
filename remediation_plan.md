# Project Review & Remediation Plan: `gfx1150-inference`

## 1. Executive Summary & Project Review

A full review of [build_error.log](file:///home/kupipi/Documents/git/gfx1150-inference/build_error.log), [CMakeLists.txt](file:///home/kupipi/Documents/git/gfx1150-inference/CMakeLists.txt), [src/kernels/matmul.hip](file:///home/kupipi/Documents/git/gfx1150-inference/src/kernels/matmul.hip), [src/python_bindings/bindings.cpp](file:///home/kupipi/Documents/git/gfx1150-inference/src/python_bindings/bindings.cpp), [tests/test_matmul.py](file:///home/kupipi/Documents/git/gfx1150-inference/tests/test_matmul.py), [implementation_plan.md](file:///home/kupipi/Documents/git/gfx1150-inference/implementation_plan.md), and [Lessons_learned.md](file:///home/kupipi/Documents/git/gfx1150-inference/Lessons_learned.md) revealed **6 blocking build/runtime defects** and **3 high-impact optimization opportunities** that must be resolved for Phase 1 to build cleanly and pass all tests.

```mermaid
flowchart TD
    subgraph BuildFailures["Compile & Link Blockers"]
        B1["1. Host GCC compiles bindings.cpp<br/>which #includes matmul.hip"]
        B2["2. Target builds libhip_matmul.so<br/>instead of matmul_module.so"]
        B3["3. Links pybind11::embed<br/>instead of pybind11::module"]
    end

    subgraph RuntimeAndKernelBugs["Runtime & Numerical Bugs"]
        R1["4. py::array_t&lt;half&gt; lacks<br/>NumPy float16 ('e') descriptor"]
        R2["5. Early return before __syncthreads()<br/>breaks edge-case tiles (M=1, N=1, 1023)"]
        R3["6. Pure FP16 accumulation loses precision<br/>(fails tolerance &lt; 1e-3)"]
    end

    subgraph Optimizations["gfx1150 Optimizations"]
        O1["7. Device Workspace Reuse<br/>(avoid per-call hipMalloc/hipFree)"]
        O2["8. LDS Padding + Register Tiling /<br/>hipBLAS fast-path"]
        O3["9. HIP_CHECK error handling &<br/>GIL release"]
    end

    BuildFailures --> RuntimeAndKernelBugs --> Optimizations
```

---

## 2. Detailed Root Cause Analysis

### Issue 1: Host Compiler (`g++`) vs. HIP Device Compiler (`amdclang++`) in `bindings.cpp`
* **Evidence in [build_error.log](file:///home/kupipi/Documents/git/gfx1150-inference/build_error.log#L1-L38) & [build.make](file:///home/kupipi/Documents/git/gfx1150-inference/build/CMakeFiles/hip_matmul.dir/build.make#L72-L90)**:
  * `matmul.hip.o` **already compiled cleanly** with `/opt/rocm/bin/amdclang++ -x hip`.
  * The build fails at `[ 33%] Building CXX object ... bindings.cpp.o` because CMake compiles `.cpp` files with the host compiler (`/usr/bin/c++`, GCC 13).
  * [bindings.cpp](file:///home/kupipi/Documents/git/gfx1150-inference/src/python_bindings/bindings.cpp#L4) has `#include "matmul.hip"` and calls `hipLaunchKernelGGL(...)` directly.
  * When GCC compiles `bindings.cpp` without `-x hip`:
    1. `blockIdx`, `blockDim`, `threadIdx`, and `__syncthreads()` are undefined device built-ins.
    2. `<hip/hip_fp16.h>` falls back to `hip_fp16_gcc.h`, which does not define device intrinsics `__hmul` or `__hadd`.
    3. `hipLaunchKernelGGL` is unavailable in standard host C++.
    4. Even if compiled with HIP, `#include "matmul.hip"` in `bindings.cpp` while also compiling `matmul.hip` separately violates the C++ One Definition Rule (ODR) and causes duplicate symbol errors at link time.

### Issue 2: CMake Output Library Name & PyBind11 Target Mismatch
* **Evidence in [CMakeLists.txt](file:///home/kupipi/Documents/git/gfx1150-inference/CMakeLists.txt#L35-L48)**:
  * `add_library(hip_matmul SHARED ...)` produces `libhip_matmul.so`.
  * However, [bindings.cpp](file:///home/kupipi/Documents/git/gfx1150-inference/src/python_bindings/bindings.cpp#L57) defines `PYBIND11_MODULE(matmul_module, m)` and [tests/test_matmul.py](file:///home/kupipi/Documents/git/gfx1150-inference/tests/test_matmul.py#L12) executes `import matmul_module`. Python cannot find `matmul_module` if the shared object is named `libhip_matmul.so`.
  * Furthermore, `CMakeLists.txt` links `pybind11::embed` (intended for embedding a Python interpreter inside a C++ executable) rather than `pybind11::module`.

### Issue 3: PyBind11 `py::array_t<half>` Unregistered NumPy Format Descriptor
* **Evidence in [bindings.cpp](file:///home/kupipi/Documents/git/gfx1150-inference/src/python_bindings/bindings.cpp#L8-L15)**:
  * `pybind11` does not natively specialize `npy_format_descriptor` for HIP's `__half` (`half`) struct (`np.float16` uses PEP 3118 format string `'e'`).
  * Passing `np.ndarray(..., dtype=np.float16)` from [tests/test_matmul.py](file:///home/kupipi/Documents/git/gfx1150-inference/tests/test_matmul.py#L26-L35) to `py::array_t<half>` throws a runtime `TypeError` / unregistered dtype error unless `py::buffer` / `py::array` is used (or `npy_format_descriptor<half>` is explicitly specialized).

### Issue 4: Divergent `__syncthreads()` & Uninitialized Shared Memory in `matmul_kernel_tiled`
* **Evidence in [src/kernels/matmul.hip](file:///home/kupipi/Documents/git/gfx1150-inference/src/kernels/matmul.hip#L40-L74)**:
  ```cpp
  const int row = blockIdx.y * BLOCK_SIZE + threadIdx.y;
  const int col = blockIdx.x * BLOCK_SIZE + threadIdx.x;
  if (row >= M || col >= N) return; // <-- BUG: Exits before loading shared memory!
  ```
  * When `M` or `N` is not a multiple of 16 (such as `test_edge_cases()` with `(1, 1024, 1024)`, `(1024, 1, 1024)`, `(1, 1, 1)`, `(1023, 1023, 1023)`), threads with `row >= M` or `col >= N` return at line 43 **before** loading their share of tiles `As` and `Bs` and **before** `__syncthreads()`.
  * For example, when `M = 1, N = 1024, K = 1024`, threads with `threadIdx.y >= 1` exit immediately, so `Bs[1..15][threadIdx.x]` is **never loaded** into shared memory! Thread `threadIdx.y = 0` then multiplies `As[0][1..15]` by uninitialized garbage in `Bs[1..15][threadIdx.x]`, and hits `__syncthreads()` in divergent control flow.
  * Lines 50, 56, and 71 already have proper bounds checks (`if (row < M && ...)`), so line 43 must be removed.

### Issue 5: Pure FP16 Accumulation Fails PyTorch Accuracy Target (`tolerance = 1e-3`)
* **Evidence in [src/kernels/matmul.hip](file:///home/kupipi/Documents/git/gfx1150-inference/src/kernels/matmul.hip#L47-L66) & [tests/test_matmul.py](file:///home/kupipi/Documents/git/gfx1150-inference/tests/test_matmul.py#L18)**:
  * Accumulating `K = 1024` products in `half` (10-bit mantissa, $\text{ulp} \approx 0.03$ at magnitude 32) causes rounding errors of $\sim 0.05\text{--}0.2$, failing `test_matmul_correctness(tolerance=1e-3)`.
  * PyTorch's `torch.matmul` on `float16` (and AMD hardware dot instructions) accumulates in **FP32 (`float`)** and casts the final sum to `half`. Accumulating in `float` inside the kernel reduces `max_error` on `1024x1024` to $< 10^{-3}$ and uses native `v_fma_f32` instructions on `gfx1150`.

### Issue 6: Unchecked `[[nodiscard]] hipError_t` Warnings & Synchronization Order
* **Evidence in [build_error.log](file:///home/kupipi/Documents/git/gfx1150-inference/build_error.log#L40-L135)**:
  * Ignoring return values of `hipMalloc`, `hipMemcpy`, `hipFree`, and `hipDeviceSynchronize` produces 9 compiler warnings and hides runtime GPU errors.

---

## 3. Remediation & Optimization Plan

### Step 1: Separate Kernel Declaration (`matmul.h`) and Device Implementation (`matmul.hip`)

#### 1A. Create `src/kernels/matmul.h`
Declare a clean C++ host interface that does not expose device-only intrinsics or `hipLaunchKernelGGL` to `/usr/bin/c++`:

```cpp
#ifndef MATMUL_H
#define MATMUL_H

#include <cstdint>

// Host-callable launcher compiled by amdclang++ in matmul.hip.
// Accepts host pointers (or manages reusable device buffers) and runs FP16 matmul.
void launch_matmul_fp16(
    const void* h_A,
    const void* h_B,
    void* h_C,
    int M,
    int N,
    int K
);

#endif // MATMUL_H
```

#### 1B. Refactor & Optimize `src/kernels/matmul.hip`
* Remove the broken early return (`if (row >= M || col >= N) return;`) in [`matmul_kernel_tiled`](file:///home/kupipi/Documents/git/gfx1150-inference/src/kernels/matmul.hip#L43).
* Accumulate dot products in `float` (`FP32`) and convert to `half` at store time so `max_error < 1e-3`.
* Pad shared memory (`__shared__ half As[BLOCK_SIZE][BLOCK_SIZE + 1]`) to eliminate LDS bank conflicts on `gfx1150` (Wave32).
* Add a `HIP_CHECK` macro for all HIP runtime calls.
* **Optimization — Reusable Device Workspace Buffer**:
  * [tests/test_matmul.py](file:///home/kupipi/Documents/git/gfx1150-inference/tests/test_matmul.py#L34-L45) measures end-to-end wall time of `matmul_module.matmul(...)` and [implementation_plan.md](file:///home/kupipi/Documents/git/gfx1150-inference/implementation_plan.md#L54) targets `> 1 TFLOPS`.
  * Calling `hipMalloc` and `hipFree` on every invocation adds ~2 ms of OS/driver page-table overhead, which by itself caps a `1024x1024` matmul ($2.15 \times 10^9$ FLOPs) below 1 TFLOPS!
  * Maintaining a grow-only device workspace buffer (allocated on first call / grown only if a larger matrix is requested, freed at exit) eliminates recurring `hipMalloc`/`hipFree` overhead during inference and benchmarking.

```cpp
#include "matmul.h"
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <stdexcept>
#include <string>

#define HIP_CHECK(call)                                                        \
    do {                                                                       \
        hipError_t err = (call);                                               \
        if (err != hipSuccess) {                                               \
            throw std::runtime_error(                                          \
                std::string("HIP error at ") + __FILE__ + ":" +                \
                std::to_string(__LINE__) + " - " + hipGetErrorString(err));    \
        }                                                                      \
    } while (0)

constexpr int BLOCK_SIZE = 16;

// Naive FP16 matrix multiplication kernel (reference)
__global__ void matmul_kernel(
    const half* __restrict__ A,
    const half* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K
) {
    const int row = blockIdx.y * blockDim.y + threadIdx.y;
    const int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row >= M || col >= N) return;

    float sum = 0.0f;
    for (int k = 0; k < K; ++k) {
        sum += __half2float(A[row * K + k]) * __half2float(B[k * N + col]);
    }
    C[row * N + col] = __float2half(sum);
}

// Optimized shared-memory tiled FP16 kernel with FP32 accumulation & bank-conflict padding
__global__ void matmul_kernel_tiled(
    const half* __restrict__ A,
    const half* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K
) {
    const int tx = threadIdx.x;
    const int ty = threadIdx.y;
    const int row = blockIdx.y * BLOCK_SIZE + ty;
    const int col = blockIdx.x * BLOCK_SIZE + tx;

    // +1 padding avoids 32-bank LDS conflicts on RDNA3.5 (gfx1150)
    __shared__ float As[BLOCK_SIZE][BLOCK_SIZE + 1];
    __shared__ float Bs[BLOCK_SIZE][BLOCK_SIZE + 1];

    float sum = 0.0f;
    const int num_tiles = (K + BLOCK_SIZE - 1) / BLOCK_SIZE;

    for (int t = 0; t < num_tiles; ++t) {
        const int a_col = t * BLOCK_SIZE + tx;
        if (row < M && a_col < K) {
            As[ty][tx] = __half2float(A[row * K + a_col]);
        } else {
            As[ty][tx] = 0.0f;
        }

        const int b_row = t * BLOCK_SIZE + ty;
        if (b_row < K && col < N) {
            Bs[ty][tx] = __half2float(B[b_row * N + col]);
        } else {
            Bs[ty][tx] = 0.0f;
        }

        __syncthreads();

        #pragma unroll
        for (int i = 0; i < BLOCK_SIZE; ++i) {
            sum += As[ty][i] * Bs[i][tx];
        }

        __syncthreads();
    }

    if (row < M && col < N) {
        C[row * N + col] = __float2half(sum);
    }
}
```

---

### Step 2: Fix `src/python_bindings/bindings.cpp`

* Include only `<pybind11/pybind11.h>`, `<pybind11/numpy.h>`, and `"matmul.h"` (no HIP device code in the `.cpp` file).
* Accept `py::buffer` (or `py::array`) to support `numpy.float16` (`format == "e"`, `itemsize == 2`) without `py::array_t<half>` type-caster failures.
* Validate shapes `(M, K)`, `(K, N)`, `(M, N)` and contiguity before calling `launch_matmul_fp16`.
* Release the Python GIL (`py::gil_scoped_release`) during GPU execution.

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <stdexcept>
#include "matmul.h"

namespace py = pybind11;

void matmul(
    const py::array& A,
    const py::array& B,
    py::array& C,
    int M,
    int N,
    int K
) {
    if (A.itemsize() != 2 || B.itemsize() != 2 || C.itemsize() != 2) {
        throw std::invalid_argument("A, B, and C must be 2-byte FP16 (numpy.float16) arrays.");
    }
    if (!(A.flags() & py::array::c_style) ||
        !(B.flags() & py::array::c_style) ||
        !(C.flags() & py::array::c_style)) {
        throw std::invalid_argument("A, B, and C must be C-contiguous arrays.");
    }
    if (A.size() < static_cast<py::ssize_t>(M) * K ||
        B.size() < static_cast<py::ssize_t>(K) * N ||
        C.size() < static_cast<py::ssize_t>(M) * N) {
        throw std::invalid_argument("Array buffer sizes are smaller than specified M, N, K dimensions.");
    }

    const void* h_A = A.data();
    const void* h_B = B.data();
    void* h_C = C.mutable_data();

    py::gil_scoped_release release;
    launch_matmul_fp16(h_A, h_B, h_C, M, N, K);
}
```

---

### Step 3: Fix `CMakeLists.txt` Target & Module Configuration

Update [CMakeLists.txt](file:///home/kupipi/Documents/git/gfx1150-inference/CMakeLists.txt#L34-L55) so that:
1. The target is named `matmul_module` with `PREFIX ""` and `SUFFIX "${PYTHON_MODULE_EXTENSION}"` (or `MODULE` library type).
2. It links against `pybind11::module` instead of `pybind11::embed`.
3. It sets `BUILD_RPATH "/opt/rocm/lib;/opt/rocm/core-10.1/lib"` so `import matmul_module` works even without manually exporting `LD_LIBRARY_PATH`.

```cmake
add_library(matmul_module MODULE
    ${KERNEL_DIR}/matmul.hip
    ${BINDINGS_DIR}/bindings.cpp
)

target_include_directories(matmul_module PRIVATE ${KERNEL_DIR} ${BINDINGS_DIR})

target_link_libraries(matmul_module PRIVATE
    roc::hipblas
    roc::rocblas
    pybind11::module
)

target_compile_features(matmul_module PRIVATE cxx_std_17)
set_target_properties(matmul_module PROPERTIES
    PREFIX ""
    OUTPUT_NAME "matmul_module"
    HIP_STANDARD 17
    HIP_STANDARD_REQUIRED ON
    BUILD_RPATH "/opt/rocm/lib;/opt/rocm/core-10.1/lib"
)
```

---

### Step 4: Clean Up Documentation & Repository Files

1. **[.gitignore](file:///home/kupipi/Documents/git/gfx1150-inference/.gitignore#L1-L4)**: Remove the accidental Markdown header lines (`---`, `#### **6. Updated .gitignore**`, ```` ```gitignore ````) at the top of `.gitignore`.
2. **[Lessons_learned.md](file:///home/kupipi/Documents/git/gfx1150-inference/Lessons_learned.md)**:
   * Fix the stray outer ```` ```markdown ```` wrapper at lines 1–6.
   * Document the new Phase 1 lessons learned from `build_error.log`:
     * **Never `#include` a `.hip` file containing `__global__` kernels into a `.cpp` file compiled by host `g++`**—use a `.h` header for host declarations and keep `hipLaunchKernelGGL` / `<<<...>>>` inside `.hip`.
     * **Use `pybind11::module` (not `pybind11::embed`) and `PREFIX ""`** when building Python C++/HIP extensions, and ensure the CMake target name matches `PYBIND11_MODULE(name, m)`.
     * **Never return early before `__syncthreads()` in tiled kernels**—out-of-bounds threads must still load `0.0f` into shared memory tiles and participate in workgroup barriers.
     * **Accumulate FP16 dot products in FP32 (`float`)** to avoid catastrophic precision loss over large `K`.
3. **[README.md](file:///home/kupipi/Documents/git/gfx1150-inference/README.md#L25)**: Complete the truncated `### 📁 Structure` section and build/test commands.

---

## 4. Verification Plan

Once we apply the changes above:
1. Run `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j` and verify **0 errors and 0 warnings**.
2. Confirm `build/matmul_module*.so` is generated.
3. Run `PYTHONPATH=build python3 tests/test_matmul.py` and verify:
   * `test_matmul_correctness` passes with `max_error < 1e-3`.
   * All 6 `test_edge_cases` (`1x1024`, `1024x1`, `1x1`, `1023x1023`, `16x16`, `1024x512x256`) pass.
   * Benchmark throughput exceeds target.
