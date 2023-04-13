#!/bin/bash

N_ALLOCS=50001
ONE_MB=100
ONE_GB=1073741824
PARENT_DIR=$(dirname $0)
OUT_DIR=$PARENT_DIR/output
PROG_NAME=$PARENT_DIR/a.out

if [ -z "$1" ]; then
    echo "Usage: $0 <n_iter>"
    exit 1
fi

n_iter=$1
mkdir -p $OUT_DIR

for i in $(seq 1 $n_iter); do
    echo "Running iteration $i..."
    # note: rough equivalent on Darwin is `sudo dtruss -b ### -f -t mmap ...`
    # must be sudo to avoid blocking by SIP
    strace -e trace=memory -f -C \
        $PROG_NAME $N_ALLOCS $ONE_MB $ONE_GB \
        2> $OUT_DIR/strace_$i.out 1> $OUT_DIR/prog_$i.out
done


# sudo dtruss -b 100 -f -t mmap ./a.out 10000000 100 100000

# food for thought
# https://stackoverflow.com/a/64029488

# next up
# strace looks like this - a bunch of mmaps, a couple munmaps, and then some brks
# to resize the space we already got from the mmaps
