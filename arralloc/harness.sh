#!/bin/bash

# config params
PARENT_DIR=$(dirname $0)
OUT_DIR=$PARENT_DIR/output
PROG_NAME=$PARENT_DIR/memtest
STATS_DIR=$PARENT_DIR/stats
N_ITER=1

# per-iteration params
N_ROUNDS=20
MIN_ALLOC=$((1<<20))
MAX_ALLOC=$((1<<24))

# setup
mkdir -p $OUT_DIR
make

# clean up old output
rm -f $OUT_DIR/*.out

# note: rough equivalent on Darwin is `sudo dtruss -b ### -f -t mmap ...`
#       must be sudo to avoid blocking by SIP
# flags: -e trace=memory: only trace memory-related syscalls
#        -f: follow forks
#        -T: print call durations in seconds
#        --absolute-timestamps: print full UNIX timestamps
# can also use -e to filter only mmap syscalls, but looks like overhead 
# does not change, as strace still has to stop all syscalls
for i in $(seq 1 $N_ITER); do
    strace -e trace=memory -f -T --absolute-timestamps=format:unix,precision:ns \
        $PROG_NAME $N_ROUNDS $MIN_ALLOC $MAX_ALLOC \
        2> $OUT_DIR/strace_$i.out 1> $OUT_DIR/prog_$i.out
done

# analysis
python3 $PARENT_DIR/stats.py -f $OUT_DIR/*.out -o $STATS_DIR --plot
