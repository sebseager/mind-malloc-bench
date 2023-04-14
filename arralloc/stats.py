from argparse import ArgumentParser
from pathlib import Path
import pandas as pd
import regex as re

# Each file is a list of memory-related calls recorded by strace
# for a single run of arralloc. The format per-line is:
# [timestamp] [call]([args]) = [return value] <[elapsed time]>
# The file ends with a message like +++ exited with # +++
# Read the files into a single pandas DataFrame.
def parse_strace(*files, out_file=None):
    dicts = []
    for fp in files:
        it = int(re.search(r"\d+", fp.name).group())  # get run number from file name
        with open(fp, "r") as f:
            for line in f:
                line = line.strip()
                if line == "":
                    continue
                if "+++" in line:
                    continue
                elts = line.split()
                n_elts = len(elts)
                try:
                    d = {"run": it}
                    for i in range(n_elts):
                        if i == 0:
                            d["timestamp"] = float(elts[i])
                        elif i == 1:
                            d["call"] = elts[i].split("(")[0]
                        elif i == 2:
                            if d["call"] == "mmap":
                                d["size"] = int(elts[i].split(",")[0])
                            elif d["call"] == "munmap":
                                d["size"] = int(elts[i].split(")")[0])
                        if elts[i] == "=":
                            d["return"] = elts[i + 1]  # as hex string
                            # drop < and > surrounding elapsed time
                            d["elapsed"] = float(elts[i + 2][1:-1])
                except:
                    print(f"error parsing line: {line}")
                    continue
                dicts.append(d)
    
    df = pd.DataFrame(dicts)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    return df


# Each file is a table describing each alloc in the memtest program.
# Starts with an elapsed_time header line, followed by a table of:
# slot_index, allocs, frees, total_bytes, current_bytes
# total_bytes is the total number of bytes allocated in that slot across all calls
# current_bytes is the number of bytes allocated in that slot at the end of the run
# To find freed_bytes we can do total_bytes - current_bytes.
def parse_memtest(*files, out_file=None):
    dicts = []
    for fp in files:
        it = int(re.search(r"\d+", fp.name).group())  # get run number from file name
        with open(fp, "r") as f:
            elapsed = f.readline().strip().split()[1]  # TODO: unused right now
            header = f.readline().strip().split()
            for line in f:
                line = line.strip()
                if line == "":
                    continue
                elts = line.split()
                n_elts = len(elts)
                try:
                    d = {"run": it}
                    for i in range(n_elts):
                        d[header[i]] = int(elts[i])
                except:
                    print(f"error parsing line: {line}")
                    continue
                dicts.append(d)
    
    df = pd.DataFrame(dicts)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    return df


def strace_stats(df, out_file=None):
    all_runs = []
    for run in df["run"].unique():
        stats = {"run": run}
        run_df = df[df["run"] == run]
        stats["n_mmap"] = run_df[run_df["call"] == "mmap"].shape[0]
        stats["n_munmap"] = run_df[run_df["call"] == "munmap"].shape[0]
        stats["n_total"] = stats["n_mmap"] + stats["n_munmap"]
        stats["sz_mmap"] = run_df[run_df["call"] == "mmap"]["size"].sum()
        stats["sz_munmap"] = run_df[run_df["call"] == "munmap"]["size"].sum()
        stats["sz_net"] = stats["sz_mmap"] - stats["sz_munmap"]
        stats["secs_mmap"] = run_df[run_df["call"] == "mmap"]["elapsed"].sum()
        stats["secs_munmap"] = run_df[run_df["call"] == "munmap"]["elapsed"].sum()
        stats["secs_total"] = stats["secs_mmap"] + stats["secs_munmap"]
        all_runs.append(stats)
    
    df = pd.DataFrame(all_runs)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    print("strace stats:")
    print(df.to_string(index=False))
    print()
    return df


def memtest_stats(df, out_file=None):
    all_runs = []
    for run in df["run"].unique():
        stats = {"run": run}
        run_df = df[df["run"] == run]
        stats["n_allocs"] = run_df["allocs"].sum()
        stats["n_frees"] = run_df["frees"].sum()
        stats["n_total"] = stats["n_allocs"] + stats["n_frees"]
        stats["sz_allocs"] = run_df["total_bytes"].sum()
        stats["sz_frees"] = stats["sz_allocs"] - run_df["current_bytes"].sum()
        stats["sz_leaked"] = stats["sz_allocs"] - stats["sz_frees"]
        all_runs.append(stats)
    
    df = pd.DataFrame(all_runs)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    print("memtest stats:")
    print(df.to_string(index=False))
    print()
    return df


def summary_stats(strace_stats_df, memtest_stats_df, out_file=None):
    all_runs = []
    for run in strace_stats_df["run"].unique():
        stats = {"run": run}
        # warning: next two lines cast things to a float
        srun_row = strace_stats_df[strace_stats_df["run"] == run].squeeze()
        mrun_row = memtest_stats_df[memtest_stats_df["run"] == run].squeeze()
        if srun_row.shape[0] == 0 or mrun_row.shape[0] == 0:
            print("skipping summary for run", run)
            continue
        # total number of mmap/munmap calls -- lower is better
        stats["n_syscalls"] = int(srun_row["n_total"])
        # malloc calls : mmap calls -- lower is better
        stats["mmap_freq"] = mrun_row["n_allocs"] / srun_row["n_mmap"]
        # number of mallocs/frees per kernel call -- higher is better
        stats["call_eff"] = mrun_row["n_total"] / srun_row["n_total"]
        # bytes used by program : bytes given by kernel
        # e.g. allocator could give 1GB for a 1KB allocation to reduce syscalls
        stats["mmap_util"] = mrun_row["sz_allocs"] / srun_row["sz_mmap"]
        # bytes unmapped by kernel : bytes freed by program
        # e.g. allocator could never reclaim memory to reduce syscalls
        stats["munmap_recl"] = srun_row["sz_munmap"] / mrun_row["sz_frees"]
        # overall memory overhead of allocator: (malloc - free) / (mmap - munmap)
        stats["mem_overhead"] = mrun_row["sz_leaked"] / srun_row["sz_net"]
        all_runs.append(stats)

    df = pd.DataFrame(all_runs)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    print("summary stats:")
    print(df.to_string(index=False))
    print()
    return df


def parse_args():
    parser = ArgumentParser(description="Test the performance of array allocation")
    parser.add_argument("-f", nargs="+", required=True,
                        help="strace output files (with flags -e trace=memory -ttt -T)")
    parser.add_argument("-o", nargs=1, required=True, help="output directory")
    parser.add_argument("--plot", action="store_true", help="plot the results")
    args = parser.parse_args()

    # validation and arg processing
    args.o = Path(args.o[0])
    args.o.mkdir(parents=True, exist_ok=True)
    args.f = [Path(f) for f in args.f]

    return args


def main():
    args = parse_args()
    
    # read strace files (strace_*.out) into df
    sfiles = [f for f in args.f if re.match(r"strace_\d+\.out", f.name)]
    sdata_df = parse_strace(*sfiles, out_file=args.o / "strace_all.tsv")

    # read memtest files (prog_*.out) into df
    mfiles = [f for f in args.f if re.match(r"prog_\d+\.out", f.name)]
    mdata_df = parse_memtest(*mfiles, out_file=args.o / "memtest_all.tsv")
    
    # run analyses
    sstats_df = strace_stats(sdata_df, out_file=args.o / "strace_stats.tsv")
    mstats_df = memtest_stats(mdata_df, out_file=args.o / "memtest_stats.tsv")
    summary_stats(sstats_df, mstats_df, out_file=args.o / "summary_stats.tsv")


if __name__ == "__main__":
    main()
