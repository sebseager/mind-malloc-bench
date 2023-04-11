#!/bin/bash

strace -e trace=memory ./a.out 1000000 100 100000 2> strace.out > prog.out
# sudo dtruss -b 100 -f -t mmap ./a.out 10000000 100 100000
