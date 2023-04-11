#!/bin/bash

N_ALLOCS=10001
ONE_MB=1048576
ONE_GB=1073741824

strace -e trace=memory -f -C ./a.out $N_ALLOCS $ONE_MB $ONE_GB \
    2> strace.out > prog.out

# sudo dtruss -b 100 -f -t mmap ./a.out 10000000 100 100000

# food for thought
# https://stackoverflow.com/a/64029488

# next up
# strace looks like this - a bunch of mmaps, a couple munmaps, and then some brks
# to resize the space we already got from the mmaps
