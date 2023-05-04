#!/bin/bash

# test directories
PARENT_DIR=$(dirname $0)
OUT_DIR=$PARENT_DIR/output
PROG_NAME=$PARENT_DIR/memtest
STATS_DIR=$PARENT_DIR/stats

# configuration
ALLOCATORS="ptmalloc jemalloc hoard"
N_ITER=4
N_THREADS=1  # best if N_ROUNDS % N_THREADS is 0 but should work if not

# per-iteration params
N_ROUNDS=10
MIN_ALLOC=$((1<<18))  # to avoid brk, want MIN_ALLOC > M_MMAP_THRESHOLD (default 128KB)
MAX_ALLOC=$((1<<24))

# note: rough equivalent of strace on Darwin is `sudo dtruss -b ### -f -t mmap ...`
#       must be sudo to avoid blocking by SIP
# flags: -e trace=memory: only trace memory-related syscalls
#        -f: follow forks
#        -T: print call durations in seconds
#        --absolute-timestamps: print full UNIX timestamps
# can also use -e to filter only mmap syscalls, but looks like overhead 
# does not change, as strace still has to stop all syscalls

for a in $ALLOCATORS; do
    # setup
    make clean
    make $a
    ALLOC_OUT_DIR=$OUT_DIR/$a
    rm -rf $ALLOC_OUT_DIR
    mkdir -p $ALLOC_OUT_DIR

    echo -e "----- $a -----\n"

    # run
    for i in $(seq 1 $N_ITER); do
        strace -e trace=memory -f -T --absolute-timestamps=format:unix,precision:ns \
            $PROG_NAME $N_ROUNDS $MIN_ALLOC $MAX_ALLOC $N_THREADS \
            2> $ALLOC_OUT_DIR/strace_$i.out 1> $ALLOC_OUT_DIR/prog_$i.out
        sed -zi 's/strace: Process [[:digit:]]* attached\n//g' $ALLOC_OUT_DIR/strace_$i.out
    done

    # analysis
    python3 $PARENT_DIR/stats.py -f $ALLOC_OUT_DIR/*.out -o $STATS_DIR/$a --plot
done
