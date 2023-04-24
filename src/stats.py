from argparse import ArgumentParser
import numpy as np
from pathlib import Path
import pandas as pd
import regex as re
from matplotlib import pyplot as plt
from decimal import Decimal

NS_PER_SEC = 1000000000

# Each file is a list of memory-related calls recorded by strace
# for a single run of arralloc. The format per-line is:
# [timestamp] [call]([args]) = [return value] <[elapsed time]>
# The file ends with a message like +++ exited with # +++
# Read the files into a single pandas DataFrame.
def parse_strace(*files, out_file=None):
    dicts = []
    for fp in files:
        try:
            it = int(re.search(r"\d+", fp.name).group())  # get run number from name
        except:
            it = -1
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
                            d["timestamp"] = Decimal(elts[i])
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
                            d["elapsed"] = Decimal(elts[i + 2][1:-1])
                except:
                    print(f"error parsing line: {line}")
                    continue
                dicts.append(d)
    
    try:
        df = pd.DataFrame(dicts)
        df = df.sort_values(by=["run", "timestamp"])
    except Exception:
        print("error: could not parse strace files")
        print(df)
        exit(1)
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
        try:
            it = int(re.search(r"\d+", fp.name).group())  # get run number from name
        except:
            it = -1
        with open(fp, "r") as f:
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
                        try:
                            d[header[i]] = int(elts[i])
                        except:
                            d[header[i]] = Decimal(elts[i])
                except:
                    print(f"error parsing line: {line}")
                    continue
                dicts.append(d)
    
    try:
        df = pd.DataFrame(dicts)
        df = df.sort_values(by=["run", "round"])
    except Exception:
        print("error: could not parse program output files")
        print(df)
        exit(1)
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
        stats["sz_mmap"] = int(run_df[run_df["call"] == "mmap"]["size"].sum())
        stats["sz_munmap"] = int(run_df[run_df["call"] == "munmap"]["size"].sum())
        stats["sz_net"] = int(stats["sz_mmap"] - stats["sz_munmap"])
        stats["secs_mmap"] = run_df[run_df["call"] == "mmap"]["elapsed"].sum()
        stats["secs_munmap"] = run_df[run_df["call"] == "munmap"]["elapsed"].sum()
        stats["secs_total"] = stats["secs_mmap"] + stats["secs_munmap"]
        all_runs.append(stats)
    
    df = pd.DataFrame(all_runs)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    print("kernel-side stats:")
    print(df.to_string(index=False))
    print()
    return df


def memtest_stats(df, out_file=None):
    all_runs = []
    for run in df["run"].unique():
        stats = {"run": run}
        run_df = df[df["run"] == run]
        stats["n_allocs"] = run_df["allocs"].sum()
        stats["sz_allocs"] = run_df["total_bytes"].sum()
        delta_ns = run_df["alloc_end_ns"] - run_df["alloc_start_ns"]
        stats["alloc_secs"] = (delta_ns / NS_PER_SEC).sum()
        all_runs.append(stats)
    
    df = pd.DataFrame(all_runs)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    print("user-side stats:")
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

        # total number of mmap+munmap calls
        # absolute number, lower is better
        stats["n_mmap"] = int(srun_row["n_mmap"])

        # malloc calls: mmap calls
        # ~1 is worst, higher is better
        stats["mmap_eff"] =  mrun_row["n_allocs"] / srun_row["n_mmap"]

        # size mmap'd : size mallocd'd
        # gives fragmentation -- sense of how much memory is wasted
        # lower is better, 1 is best
        # stats["mmap_frag"] = srun_row["sz_mmap"] / mrun_row["sz_allocs"]

        # total elapsed time in mmap : number of mallocs
        # gives average time per malloc
        # lower is better
        stats["mmap_secs_per_call"] = srun_row["secs_mmap"] / mrun_row["n_allocs"]

        # total elapsed time in mmap : bytes allocated
        # gives average time per byte allocated
        # lower is better
        # stats["mmap_secs_per_byte"] = srun_row["secs_mmap"] / mrun_row["sz_allocs"]

        all_runs.append(stats)

    df = pd.DataFrame(all_runs)
    df = df.sort_values(by=["run"])
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    print("summary stats:")
    print(df.to_string(index=False))
    print()
    return df


# Modify memtest_df to add two columns: cumul_mmap_bytes and cumul_munmap_bytes.
# These are the cumulative number of bytes mmap'd and munmap'd, respectively, up to
# and including the given round. We need this because if the user frees a bunch 
# of memory in user space, not all of it may be unmapped by kernel.
def calc_frag_cols(strace_df, memtest_df, out_file=None):
    # convert timestamps
    memtest_df["kernel_secs"] = 0
    strace_df["timestamp_ns"] = (strace_df["timestamp"] * NS_PER_SEC).astype(int)
    strace_tmp = strace_df.sort_values(by=["timestamp_ns"])  # should be redundant but

    mrow_i = 0
    for run in memtest_df["run"].unique():
        mmap_cumsum = 0
        munmap_cumsum = 0
        time_col = "end"
        srun_df = strace_df[strace_df["run"] == run]

        # time_col needs explaining:
        # think about iterating through the strace rows in order of timestamp;
        # as soon as we hit the first end_time, that's cumul_mmap for the first round;
        # as soon as we hit the second start_time, that's cumul_unmap for second round

        for srow in srun_df.itertuples(index=False):
            if srow.timestamp_ns > memtest_df.loc[mrow_i, f"alloc_{time_col}_ns"]:
                if time_col == "end":
                    memtest_df.loc[mrow_i, "cumul_mmap_bytes"] = mmap_cumsum
                    time_col = "start"
                else:
                    mrow_i += 1
                    if mrow_i >= memtest_df.shape[0]:
                        break
                    if memtest_df.loc[mrow_i, "run"] != run:
                        break
                    memtest_df.loc[mrow_i, "cumul_munmap_bytes"] = munmap_cumsum
                    time_col = "end"
            if srow.call == "mmap":
                mmap_cumsum += srow.size
                memtest_df.loc[mrow_i, "kernel_secs"] += srow.elapsed
            elif srow.call == "munmap":
                munmap_cumsum += srow.size
                memtest_df.loc[mrow_i, "kernel_secs"] += srow.elapsed
            else:
                # skip brk, etc.
                continue

    # clean up
    memtest_df["cumul_munmap_bytes"] = memtest_df["cumul_munmap_bytes"].fillna(0)

    # calculate fragmentation
    numer = memtest_df["cumul_mmap_bytes"] - memtest_df["cumul_munmap_bytes"]
    denom = memtest_df["total_bytes"]
    memtest_df["frag"] = numer / denom
    
    print("detailed user-side stats with fragmentation:")
    print(memtest_df.to_string(index=False))
    print()
    if out_file is not None:
        memtest_df.to_csv(out_file, index=False, sep="\t")


# Plot fragmentation over time for each run.
# Fragmentation is defined as (mmap'd bytes - munmap'd bytes) / malloc'd bytes.
def plot_frag(strace_df, memtest_df, out_path):    
    plt.figure()
    for run in memtest_df["run"].unique():
        run_df = memtest_df[memtest_df["run"] == run].copy()
        min_time = run_df["alloc_start_ns"].min()
        run_df["elapsed_start_ns"] = run_df["alloc_start_ns"] - min_time
        plt.plot(run_df["elapsed_start_ns"], run_df["frag"], label=f"run {run}")
    plt.xlabel("elapsed run time (s)")
    plt.ylabel("fragmentation (mmap'd bytes / malloc'd bytes)")
    plt.grid(True, which="both")
    plt.title("Fragmentation over time")
    plt.ylim(0, 4)
    plt.savefig(out_path)
    plt.close()


# Plot the cumulative number of bytes mmap'd and munmap'd over time.
# This is distinct from fragmentation, which is the ratio of mmap'd to malloc'd bytes.
# This just gives a sense of the kernel-side activity of the allocator.
def plot_net_mmap(strace_df, out_path):
    plt.figure()
    strace_df["timestamp_ns"] = (strace_df["timestamp"] * NS_PER_SEC).astype(int)
    for run in strace_df["run"].unique()[:2]:
        run_df = strace_df[strace_df["run"] == run].copy()
        min_time = run_df["timestamp_ns"].min()
        run_df["elapsed_ns"] = run_df["timestamp_ns"] - min_time
        
        y = [0]  # net mmap
        x = [0]  # elapsed time
        for row in run_df.itertuples(index=False):
            if row.call == "mmap":
                y.append(y[-1] + row.size)
                x.append(row.elapsed_ns)
            elif row.call == "munmap":
                y.append(y[-1] - row.size)
                x.append(row.elapsed_ns)
            else:
                continue
        plt.plot(x, y)
    
    plt.xlabel("elapsed run time (s)")
    plt.ylabel("net mmap'd bytes")
    plt.grid(True, which="both")
    plt.title("Net mmap'd bytes over time")
    plt.savefig(out_path)
    plt.close()


# Plot seconds spent in kernel per million bytes requested by malloc.
# This is a measure of the kernel-side activity of the allocator.
def plot_kernel_secs(memtest_df, out_path):
    plt.figure()
    y = memtest_df["kernel_secs"]
    x = memtest_df["total_bytes"] / 1e6
    plt.scatter(x, y)
    plt.xlabel("million bytes malloc'd")
    plt.ylabel("time spent in mmap and munmap (s)")
    plt.grid(True, which="both")
    plt.title("Kernel time per million bytes requested")
    plt.savefig(out_path)
    plt.close()


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
    
    # regex expression matching strace*.out
    r = re.compile(r"strace.*\.out")

    sfiles = [f for f in args.f if re.match(r"strace.*\.out", f.name)]
    sdata_df = parse_strace(*sfiles, out_file=args.o / "strace_detail.tsv")

    # read memtest files (prog_*.out) into df
    mfiles = [f for f in args.f if re.match(r"prog.*\.out", f.name)]
    mdata_df = parse_memtest(*mfiles, out_file=args.o / "memtest_detail.tsv")
    
    # run analyses
    sstats_df = strace_stats(sdata_df, out_file=args.o / "strace_summary.tsv")
    mstats_df = memtest_stats(mdata_df, out_file=args.o / "memtest_summary.tsv")
    calc_frag_cols(sdata_df, mdata_df, out_file=args.o / "memtest_detail.tsv") # inplace
    summ_df = summary_stats(sstats_df, mstats_df, out_file=args.o / "summary.tsv")

    # plots
    if args.plot:
        plot_frag(sdata_df, mdata_df, args.o / "frag.png")
        plot_net_mmap(sdata_df, args.o / "net_mmap.png")
        plot_kernel_secs(mdata_df, args.o / "kernel_secs.png")


if __name__ == "__main__":
    main()
