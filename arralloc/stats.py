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
    
    df = pd.DataFrame(dicts)
    df = df.sort_values(by=["run", "timestamp"])
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
    
    df = pd.DataFrame(dicts)
    df = df.sort_values(by=["run", "round"])
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
        ns_start = run_df["alloc_start_time"] * NS_PER_SEC
        ns_end = run_df["alloc_end_time"] * NS_PER_SEC
        stats["alloc_secs"] = ((ns_end - ns_start) / NS_PER_SEC).sum()
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

        # mmap calls : malloc calls
        # ~1 is worst, lower is better
        stats["mmap_eff"] = srun_row["n_mmap"] / mrun_row["n_allocs"]

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
    memtest_df["alloc_end_time_ns"] = memtest_df["alloc_end_time"] * NS_PER_SEC
    strace_df["timestamp_ns"] = strace_df["timestamp"] * NS_PER_SEC

    # filter strace_df
    strace_tmp = strace_df[strace_df["call"].isin(["mmap", "munmap"])]
    strace_tmp = strace_tmp.sort_values(by=["timestamp_ns"])  # should be redundant but
    
    mrow_i = 0
    mmap_cumsum = 0
    munmap_cumsum = 0
    for srow in strace_tmp.itertuples(index=False):
        if srow.timestamp_ns > memtest_df.iloc[mrow_i].alloc_end_time_ns
            memtest_df.loc[mrow_i, "cumul_mmap_bytes"] = mmap_cumsum
            memtest_df.loc[mrow_i, "cumul_munmap_bytes"] = munmap_cumsum
            mrow_i += 1
            if mrow_i >= memtest_df.shape[0]:
                break
        if srow.call == "mmap":
            mmap_cumsum += srow.size
        elif srow.call == "munmap":
            munmap_cumsum += srow.size
        else:
            continue

    # clean up
    memtest_df.drop(columns=["alloc_end_time_ns"], inplace=True)

    # calculate fragmentation
    memtest_df["frag"] = memtest_df["cumul_mmap_bytes"] / memtest_df["total_bytes"]
    
    print("detailed user-side stats with fragmentation:")
    print(memtest_df.to_string(index=False))
    print()
    if out_file is not None:
        memtest_df.to_csv(out_file, index=False, sep="\t")


# For each run, plot fragmentation over time.
# Fragmentation is the number of bytes mmap'd over number of bytes malloc'd (1 is best
# and higher is worse). Because the kernel does not necessarily need to reclaim all 
# memory freed with munmap, we need to do this over time.
def plot_frag(strace_df, memtest_df, out_path):
    # # add two calculated columns to memtest_df
    # # cumul_mmap_bytes = cumulative mmap'd bytes
    # # cumul_munmap_bytes = cumulative munmap'd bytes
    # mmap_mask = strace_df["call"] == "mmap"
    # munmap_mask = strace_df["call"] == "munmap"
    # strace_df["timestamp_ns"] = strace_df["timestamp"] * NS_PER_SEC
    # for row in memtest_df.itertuples():
    #     # compare nanoseconds for both
    #     end_ns = row.alloc_end_time * NS_PER_SEC
    #     end_mask = strace_df["timestamp_ns"] <= end_ns
    #     # get all mmap calls up to alloc_end_time
    #     cumul_mmap_bytes = strace_df[mmap_mask & end_mask]["size"].sum()
    #     # get all munmap calls up to alloc_end_time
    #     cumul_munmap_bytes = strace_df[munmap_mask & end_mask]["size"].sum()
    #     # add to memtest_df
    #     memtest_df.loc[row.Index, "cumul_mmap_bytes"] = cumul_mmap_bytes
    #     memtest_df.loc[row.Index, "cumul_munmap_bytes"] = cumul_munmap_bytes
    
    # # print for debugging
    # print("detailed user-side stats with fragmentation:")
    # print(memtest_df.to_string(index=False))
    # print()
    
    # plot fragmentation over time (x axis is rounds)
    # for the nth row, frag = (cumul_mmap_bytes - cumul_munmap_bytes) / total_bytes
    plt.figure()
    y = memtest_df["cumul_mmap_bytes"] - memtest_df["cumul_munmap_bytes"]
    y /= memtest_df["total_bytes"]
    x = memtest_df["alloc_start_time"]
    plt.scatter(x, y)
    plt.xlabel("time")
    plt.ylabel("fragmentation")
    plt.grid(True, which="both")
    plt.title("Fragmentation over time")
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
    sdata_df = parse_strace(*sfiles, out_file=args.o / "strace_all.tsv")

    # read memtest files (prog_*.out) into df
    mfiles = [f for f in args.f if re.match(r"prog.*\.out", f.name)]
    mdata_df = parse_memtest(*mfiles, out_file=args.o / "memtest_all.tsv")
    
    # run analyses
    sstats_df = strace_stats(sdata_df, out_file=args.o / "strace_stats.tsv")
    mstats_df = memtest_stats(mdata_df, out_file=args.o / "memtest_stats.tsv")
    calc_frag_cols(sdata_df, mdata_df, out_file=args.o / "memtest_all.tsv")  # in-place
    summary_stats(sstats_df, mstats_df, out_file=args.o / "summary_stats.tsv")

    # plots
    if args.plot:
        plot_frag(sdata_df, mdata_df, args.o / "strace_plot.png")


if __name__ == "__main__":
    main()
