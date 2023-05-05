# An Analysis of Memory Allocation Strategies for MIND

This repository accompanies a thesis submitted to the Yale University Department of Computer Science in partial fulfillment of the requirements for the degree of Bachelor of Science.

## Introduction

Due to advances in network performance, modern distributed computing networks benefit from separation of resources into compute and memory “blades.” However, this kind of architecture can present challenges for implementing an efficient shared memory abstraction with performant memory management. The MIND project ([Lee et al., 2021](https://doi.org/10.1145/3477132.3483561)) demonstrates a solution for memory management in disaggregated computing architectures by embedding memory management logic in the network switch itself. Doing so allows for notable latency improvements without significant cost to bandwidth.

In MIND, CPU blades encapsulate CPU cores and DRAM (as a local high-speed cache). Memory access operations first check whether the target virtual address is available in the DRAM cache. Upon a page fault, the page fault handler updates the cache using a direct memory access (RDMA) request for the intended virtual address. The network switch handles the rest of the memory management logic from here. Because memory allocation and mapping is handled in this way within the network fabric, this also means that memory blades do not need their own CPUs for polling tasks, etc.

Placement of memory management logic in the network fabric allows for (1) simplified memory metadata coherence, (2) use of network switches with programmable circuitry for line-rate memory management, even with high-bandwidth traffic, and (3) implementations of low-latency cache coherence algorithms.

## Motivation

Currently, MIND uses a first-fit slab allocator on the kernel level  and Linux (glibc) malloc on the user level. Glibc’s allocator groups memory into chunks, which contain a small range of usable memory bounded by header regions recording information like chunk size and allocation status. Upon receiving an allocation request, a heap can reuse a previously freed chunk; if no chunks are large enough, the heap can either carve out a new memory block from the end of the top chunk, or can ask the kernel to extend the heap with a call to `sbrk`. To improve multi-threaded performance, glibc malloc maintains arenas, which can be created and assigned to threads as needed.

While the glibc allocator works well on traditional systems, memory disaggregation on MIND introduces a new source of latency. Because memory management is handled via the network fabric, using an allocator not optimized for this bottleneck can impact performance. We therefore aim to evaluate different allocator designs in the context of the MIND system by measuring their usage of system calls like mmap.

## Usage

To reproduce our results, use `./install.sh` (modifying it as needed) to download and build allocators to a temporary directory at the script path. The test harness, `./harness.sh` can now be configured and called directly to run the whole test pipeline automatically.

The test pipeline consists of the following components:

1. `Makefile` provides targets for compiling our `memtest` program with each of the allocators. We assume glibc allocator (labeled `ptmalloc`) is the default system malloc. These targets can be modified to test different linking strategies or add allocators to the test framework as needed.
2. `memtest.c` provides a configurable multi-round allocation benchmark with support for multithreaded testing. It can be built with `make <target>` (refer to `Makefile`). Call it without arguments for usage.
3. `stats.py` computes a variety of statistics, tables, and plots to analyse benchmark results. Use `stats.py -h` for usage.

## Author

[Seb Seager](https://github.com/sebseager/)

## Acknowledgements

- [Prof. Anurag Khandelwal](https://www.anuragkhandelwal.com/) ([GitHub](https://github.com/anuragkh))
- [Seung-seob Lee](https://www.seungseoblee.com/blog/) ([GitHub](https://github.com/shsym))
