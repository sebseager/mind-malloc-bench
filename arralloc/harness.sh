#!/bin/bash

# config params
PARENT_DIR=$(dirname $0)
OUT_DIR=$PARENT_DIR/output
PROG_NAME=$PARENT_DIR/memtest
N_ITER=10

# per-iteration params
N_ALLOCS=$((1<<10))
MIN_ALLOC=$((1<<10))
MAX_ALLOC=$((1<<30))

# setup
mkdir -p $OUT_DIR

# run
gcc -O3 -o $PROG_NAME $PROG_NAME.c
for i in $(seq 1 $N_ITER); do
    echo "Running iteration $i..."
    
    # note: rough equivalent on Darwin is `sudo dtruss -b ### -f -t mmap ...`
    #       must be sudo to avoid blocking by SIP
    # flags: -e trace=memory: only trace memory-related syscalls
    #        -f: follow forks
    #        -ttt: print full UNIX timestamps
    #        -T: print call durations in seconds
    strace -e trace=memory -f -ttt -T \
        $PROG_NAME $N_ALLOCS $MIN_ALLOC $MAX_ALLOC \
        2> $OUT_DIR/strace_$i.out 1> $OUT_DIR/prog_$i.out
done


# food for thought
# https://stackoverflow.com/a/64029488

# next up
# strace looks like this - a bunch of mmaps, a couple munmaps, and then some brks
# to resize the space we already got from the mmaps
