#!/bin/bash

strace -e trace=memory -f -C ./a.out 100000 100 100000 2> strace.out > prog.out
# sudo dtruss -b 100 -f -t mmap ./a.out 10000000 100 100000

# food for thought
https://stackoverflow.com/a/64029488

# next up
# strace looks like this - a bunch of mmaps, a couple munmaps, and then some brks
# to resize the space we already got from the mmaps
