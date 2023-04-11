#!/bin/bash

strace ./a.out 1000000 100 100000
# sudo dtruss -b 100 -f -t mmap ./a.out 10000000 100 100000