# Lessons Learned: gfx1150 Inference Engine

> **Documenting the journey of building an SSD-offloaded LLM inference engine for AMD gfx1150**

This file captures **key insights, pitfalls, and solutions** encountered during development. Use it as a reference to avoid repeating mistakes and to onboard new contributors.

---

## 📌 Table of Contents
1. [Phase 1: Environment Setup](#phase-1-environment-setup)
2. [Phase 1: Build System](#phase-1-build-system)
3. [Phase 1: HIP Kernel Development](#phase-1-hip-kernel-development)
4. [General Best Practices](#general-best-practices)
5. [Debugging Tips](#debugging-tips)

---

## Phase 1: Environment Setup

### ⚠️ Lesson: ROCm Installation Paths Vary
**Problem**: ROCm can be installed in multiple locations depending on the installer:
- Standard ROCm: `/opt/rocm/`
- HPC SDK: `/opt/rocm/core-10.1/`
- System-wide: `/usr/`

**Solution**:
1. **Locate your installation**:
   ```bash
   which hipcc          # Usually /opt/rocm/bin/hipcc or /usr/bin/hipcc
   find / -name "hip-config.cmake" 2>/dev/null

    Set paths explicitly in CMake:

    set(hip_DIR "/opt/rocm/lib/cmake/hip")
    set(rocblas_DIR "/opt/rocm/lib/cmake/rocblas")
    set(hipblas_DIR "/opt/rocm/lib/cmake/hipblas")

Key Takeaway: Never assume ROCm is in /opt/rocm/. Always verify with which hipcc.
⚠️ Lesson: gfx1150 May Not Be Detected by Default

Problem: ROCm 6.0 and earlier do not officially support gfx1150 (Radeon 890M/AI 370). Even with ROCm 6.1+, the GPU might not appear in rocminfo.

Solution:

    Force detection with environment variable:

    export HSA_OVERRIDE_GFX_VERSION=11.5.0
    rocminfo | grep gfx1150

    Verify driver support:
    dmesg | grep amdgpu
        Look for gfx1150 in the output.
        If missing, update your kernel and AMD GPU drivers.

Key Takeaway: gfx1150 support is new—expect to manually enable it.
⚠️ Lesson: ROCm Packages May Be Incomplete

Problem: Some ROCm installations miss critical packages like hipblas or rocblas.

Solution:

    Install missing packages:

    # Ubuntu/Debian
    sudo apt install rocm-hip-sdk rocm-rocblas rocm-hipblas

    Verify libraries exist:

    ls /opt/rocm/lib/libhipblas.so
    ls /opt/rocm/lib/librocblas.so

Key Takeaway: Always verify libraries exist before debugging CMake errors.
✅ Lesson: Use HSA_OVERRIDE_GFX_VERSION for Testing

Problem: Need to test gfx1150 support without waiting for official ROCm updates.

Solution:

# Prepend to any command that uses the GPU
HSA_OVERRIDE_GFX_VERSION=11.5.0 python your_script.py
HSA_OVERRIDE_GFX_VERSION=11.5.0 cmake --build .

Key Takeaway: This is a lifesaver for testing on unsupported GPUs.
Phase 1: Build System
⚠️ Lesson: .hip Files Are Source Code (Not Binaries)

Problem: Initially added *.hip to .gitignore, which blocked HIP kernel source files from being tracked in Git.

Solution:

    Remove *.hip from .gitignore (source files should be tracked).
    Keep *.hip.o and *.hsaco in .gitignore (compiled binaries).

Updated .gitignore Rule:

# HIP/ROCm
*.hip.o      # Compiled HIP objects (ignore)
*.hsaco      # HSA CO objects (ignore)
# *.hip     # Source files (DO NOT IGNORE)

Key Takeaway: Treat .hip files like .cpp or .py—they are source code.
⚠️ Lesson: pybind11 Requires Python Development Headers

Problem: CMake fails with Could NOT find Python or Python.h not found.

Solution:

    Install Python dev headers:

    # Ubuntu/Debian
    sudo apt install python3-dev

    Add to CMakeLists.txt:
    find_package(Python COMPONENTS Interpreter Development REQUIRED)

Key Takeaway: pybind11 needs both Python runtime and development headers.
⚠️ Lesson: CMake Needs Explicit Paths for ROCm

Problem: find_package(hip) fails with Could NOT find hipconfig.cmake.

Solution:

    Set CMAKE_PREFIX_PATH:
    cmake .. -DCMAKE_PREFIX_PATH=/opt/rocm
    Or set individual package paths:

    cmake .. \
        -Dhip_DIR=/opt/rocm/lib/cmake/hip \
        -Drocblas_DIR=/opt/rocm/lib/cmake/rocblas \
        -Dhipblas_DIR=/opt/rocm/lib/cmake/hipblas

Key Takeaway: ROCm’s CMake files are not always in the default search path.
⚠️ Lesson: hipblas::hipblas Target May Not Exist

Problem: CMake fails with Target "hipblas::hipblas" not found.

Solution:

    Verify the target name:

    find_package(hipblas REQUIRED)
    if(NOT TARGET hipblas::hipblas)
        message(FATAL_ERROR "hipblas::hipblas not found!")
    endif()

    Fallback to direct linking:

    find_library(HIPBLAS_LIB hipblas HINTS /opt/rocm/lib)
    target_link_libraries(your_target PRIVATE ${HIPBLAS_LIB})

Key Takeaway: ROCm’s CMake targets can vary by version. Always verify with if(NOT TARGET ...).
✅ Lesson: Use CMAKE_BUILD_TYPE=Release for Performance

Problem: Debug builds are 10–100x slower than Release builds.

Solution:
cmake .. -DCMAKE_BUILD_TYPE=Release

Key Takeaway: Always use Release for performance-critical code.
✅ Lesson: Clean Builds Avoid CMake Cache Issues

Problem: CMake caches old paths, leading to confusing errors after fixing issues.

Solution:

rm -rf build && mkdir build && cd build
cmake ..

Key Takeaway: Always start fresh when debugging CMake issues.
Phase 1: HIP Kernel Development
⚠️ Lesson: gfx1150 Has Workgroup Size Limits

Problem: Kernel crashes with hipErrorInvalidWorkgroupSize if workgroups are too large.

Solution:

    Max workgroup size for gfx1150: 256 threads (16x16, 32x8, etc.).
    Example:

    dim3 blockDim(16, 16);  // 256 threads (safe)
    dim3 blockDim(32, 32);  // 1024 threads (FAILS on gfx1150)

Key Takeaway: Check rocminfo | grep "Max Workgroup Size" for your GPU.
⚠️ Lesson: FP16 Precision Is Limited

Problem: FP16 matmul results differ from PyTorch by >1e-3.

Solution:

    Loosen tolerance for FP16:
    tolerance = 1e-2 # Instead of 1e-3
    Use FP32 for validation (if precision is critical).

Key Takeaway: FP16 has ~3–4 decimal digits of precision. Expect errors in the 1e-3–1e-2 range.
✅ Lesson: Use __restrict__ for Memory Aliasing

Problem: HIP kernels run slower than expected due to memory aliasing.

Solution:

__global__ void kernel(const half* __restrict__ A, half* __restrict__ B) {
    // __restrict__ tells the compiler A and B don't overlap
}

Key Takeaway: __restrict__ can boost performance by 10–30% for memory-bound kernels.
✅ Lesson: Tiling Improves Memory Locality

Problem: Naive matmul kernel is memory-bound (low GPU utilization).

Solution:
Use shared memory tiling to reduce global memory accesses:

__global__ void matmul_tiled(const half* A, const half* B, half* C) {
    __shared__ half As[16][16];  // Tile size = 16x16
    __shared__ half Bs[16][16];
    // Load tiles into shared memory
    // Compute with local data
}

Key Takeaway: Tiling can 2–10x throughput for matmul.
⚠️ Lesson: HIP Kernels Need __syncthreads()

Problem: Race conditions in HIP kernels due to missing synchronization.

Solution:
Always add __syncthreads() after loading shared memory:

As[threadIdx.y][threadIdx.x] = A[...];
__syncthreads();  // Ensure all threads have loaded data
// Now compute

Key Takeaway: Forgetting __syncthreads() causes subtle bugs that are hard to debug.
General Best Practices
✅ Always Verify GPU Detection

Before running any code:
rocminfo | grep gfx1150

If missing:
HSA_OVERRIDE_GFX_VERSION=11.5.0 rocminfo | grep gfx1150
✅ Use LD_LIBRARY_PATH for ROCm Libraries

Problem: Runtime errors like libhipblas.so: cannot open shared object file.

Solution:
export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH
✅ Use PYTHONPATH for Local Modules

Problem: ModuleNotFoundError: matmul_module after building.

Solution:
export PYTHONPATH=$(pwd)/build:$PYTHONPATH
✅ Log Everything for Debugging

Problem: Hard to reproduce issues without logs.

Solution:

    Save CMake output:
    cmake .. 2>&1 | tee cmake_log.txt
    Save build output:
    cmake --build . 2>&1 | tee build_log.txt
    Save GPU info:
    rocminfo > rocminfo_log.txt 2>&1

Debugging Tips
🔍 Debugging ROCm/HIP Issues
Symptom	Debug Command	Likely Fix
GPU not detected	rocminfo	Update ROCm/drivers or use HSA_OVERRIDE_GFX_VERSION
hipconfig.cmake missing	find / -name "hip-config.cmake"	Set hip_DIR in CMake
libhipblas.so missing	find / -name "libhipblas.so"	Install rocm-hipblas
Kernel crashes	dmesg | grep amdgpu	Check workgroup size, memory access
Low throughput	rocm-smi --showpower	Optimize kernel (tiling, __restrict__)
🔍 Debugging CMake Issues
Error	Debug Step	Likely Fix
Could NOT find hip	Check CMAKE_PREFIX_PATH	Set to /opt/rocm
Target not found	Verify with if(NOT TARGET ...)	Use direct library paths
Python.h not found	Check python3-dev	Install Python dev headers
pybind11 not found	Check pip list	Install pybind11
🔍 Debugging HIP Kernels
Error	Debug Step	Likely Fix
hipErrorInvalidWorkgroupSize	Check workgroup dimensions	Reduce to ≤256 threads
hipErrorOutOfMemory	Check rocm-smi --showmeminfo	Reduce batch size
Incorrect results	Compare to PyTorch	Check FP16 precision, memory access
Low GPU utilization	rocm-smi --showpower	Optimize kernel (tiling, coalescing)
📚 Useful Commands
ROCm Info

# GPU info
rocminfo
rocm-smi --showproductname
rocm-smi --showmeminfo

# Driver info
dmesg | grep amdgpu
lspci | grep AMD

# HIP info
hipcc --version
/opt/rocm/bin/hipconfig

CMake Debugging

# Clean build
rm -rf build && mkdir build && cd build

# Verbose CMake
cmake .. -DCMAKE_VERBOSE_MAKEFILE=ON

# List all CMake variables
cmake .. -LA | grep hip

HIP Debugging

# Compile HIP to SASS (for inspection)
hipcc --amdgpu-target=gfx1150 -S kernel.hip -o kernel.s

# Check HIP runtime version
python3 -c "import pyhip; print(pyhip.hipRuntimeGetVersion())"

🎯 Key Takeaways

    ROCm paths vary – Always verify with which hipcc and find / -name "hip-config.cmake".
    gfx1150 is new – Use HSA_OVERRIDE_GFX_VERSION=11.5.0 if not detected.
    .hip files are source – Do NOT gitignore them.
    pybind11 needs Python dev headers – Install python3-dev.
    CMake needs explicit paths – Set CMAKE_PREFIX_PATH or individual *_DIR variables.
    Workgroup size matters – gfx1150 max is 256 threads.
    FP16 has limited precision – Expect errors in the 1e-3–1e-2 range.
    Tiling boosts performance – Use shared memory for matmul/attention.
    Always use __syncthreads() – Avoid race conditions in HIP kernels.
    Log everything – Save CMake, build, and GPU info for debugging.

📅 Changelog
Date	Lesson Added	Phase	Owner
2026-10-28	ROCm paths vary	Phase 1	KupipiKuki
2026-10-28	gfx1150 detection	Phase 1	KupipiKuki
2026-10-28	.hip gitignore issue	Phase 1	KupipiKuki
2026-10-28	pybind11 Python headers	Phase 1	KupipiKuki
2026-10-28	CMake explicit paths	Phase 1	KupipiKuki
2026-10-28	hipblas target not found	Phase 1	KupipiKuki
2026-10-28	Workgroup size limits	Phase 1	KupipiKuki
2026-10-28	FP16 precision limits	Phase 1	KupipiKuki
2026-10-30	Host vs HIP compiler separation (.h vs .hip)	Phase 1	KupipiKuki
2026-10-30	pybind11::module vs pybind11::embed & target naming	Phase 1	KupipiKuki
2026-10-30	Avoid early return before __syncthreads() in tiled kernels	Phase 1	KupipiKuki
2026-10-30	FP32 dot-product accumulation for FP16 matmul	Phase 1	KupipiKuki
2026-10-30	Release memoryviews before closing Python mmap (BufferError)	Phase 2	KupipiKuki
2026-10-30	Wave32 intra-wavefront shuffle reduction for fused Q4_0 GEMV	Phase 2	KupipiKuki
💬 How to Contribute

    Add new lessons as you encounter them.
    Update existing lessons if you find better solutions.
    Link to external docs (e.g., AMD ROCm docs, Stack Overflow).
    Keep it concise – Focus on actionable insights.

🔗 References

     AMD ROCm Documentation
     HIP Programming Guide
     ROCm Installation Guide
     PyBind11 Documentation
     CMake FindHIP
