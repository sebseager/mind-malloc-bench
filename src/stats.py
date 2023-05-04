from argparse import ArgumentParser
import numpy as np
from pathlib import Path
import pandas as pd
import regex as re
from matplotlib import pyplot as plt
from decimal import Decimal

NS_PER_SEC = 1000000000
US_PER_SEC = 1000000

# Each file is a list of memory-related calls recorded by strace
# for a single run of arralloc. The format per-line is:
# [timestamp] [call]([args]) = [return value] <[elapsed time]>
# The file ends with a message like +++ exited with # +++
# Read the files into a single pandas DataFrame.
def parse_strace(*files, out_file=None, delay_us=10):
    def dict_for_line(string):
        line = string.strip()
        # empty line, end of file, or syscall interrupted by SIG
        if line == "" or "+++" in line or "---" in line:
            return None, None
        elts = line.split()
        try:
            pid = None
            d = {"state": None}
            if "[pid" in elts:
                pid = int(elts[1][:-1])
                elts = elts[2:]
            
            # set state based on whether call is complete
            if "<unfinished" in elts:  # call interrupted by context switch
                d["state"] = "unfinished"
            elif "resumed>)" in elts:  # call resumed from context switch
                d["state"] = "resumed"
            else:  # call completed in its entirety
                d["state"] = "complete"
            
            # write fields
            d["timestamp_ns"] = int(Decimal(elts[0]) * NS_PER_SEC)
            d["call"] = elts[2] if d["state"] == "resumed" else elts[1].split("(")[0]
            if d["state"] != "unfinished":
                d["return"] =  elts[-2]
                d["elapsed"] = Decimal(elts[-1][1:-1])
                # add postive random latency to elapsed time
                d["elapsed"] += Decimal(abs(np.random.normal(0, delay_us / US_PER_SEC)))
            else:
                d["return"] = None
                d["elapsed"] = None
            if d["state"] != "resumed" and d["call"] in ("mmap", "munmap"):
                d["size"] = int(elts[2][:-1])
            else:
                d["size"] = None
        except Exception as e:
            import pdb; pdb.set_trace()
            print(f"error parsing line: {line} (reason {e})")
            d = None
        return pid, d

    dfs = []
    for fp in files:
        try:
            # get run number from name
            run = int(re.search(r"\d+", fp.name).group())
        except:
            run = -1
        lines = {}  # keyed by pid
        with open(fp, "r") as f:
            for line in f:
                pid, d = dict_for_line(line)
                if d is None:
                    continue
                d = {"run": run, **d}
                if pid not in lines:
                    lines[pid] = []
                lines[pid].append(d)
        
        # now combine unfinished/resumed calls
        # why must strace be this way? damn you, strace.
        for pid, pid_lines in lines.items():
            completed_lines = []
            i = 0
            while i < len(pid_lines):
                if pid_lines[i]["state"] == "complete":
                    line = pid_lines[i]
                    i += 1
                elif pid_lines[i]["state"] == "unfinished":
                    first_half = pid_lines[i]
                    try:
                        second_half = pid_lines[i + 1]
                        assert(second_half["state"] == "resumed")
                        assert(second_half["call"] == first_half["call"])
                    except Exception as e:
                        print(f"error: unfinished call after {first_half} (reason {e})")
                        exit(1)
                    try:
                        line = {
                            "run": first_half["run"],
                            "pid": pid,  # add this in, not in original line
                            "state": "complete",
                            "timestamp_ns": first_half["timestamp_ns"],
                            "call": first_half["call"],
                            "return": second_half["return"],
                            "elapsed": second_half["elapsed"],
                             "size": first_half["size"]
                        }
                    except:
                        import pdb; pdb.set_trace()
                    i += 2  # skip over resumed call
                else:
                    # shouldn't happen - no completed calls before unfinished
                    print(f"error: bad call order after {pid_lines[i]}")
                    exit(1)
                completed_lines.append(line)
            lines[pid] = completed_lines  # replace with fully completed lines

        # now combine lines from different pids
        all_lines = [l for pid_lines in lines.values() for l in pid_lines]
        df = pd.DataFrame(all_lines)
        assert((df["state"] == "complete").all())
        dfs.append(df)

    try:
        df = pd.concat(dfs, ignore_index=True)
    except Exception:
        print("error: could not parse strace files")
        print(df)
        exit(1)
    
    # lines will be in pid order, so interleave by timestamp again
    df = df.sort_values(by=["run", "timestamp_ns"])

    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t", na_rep="NULL")
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
        df.to_csv(out_file, index=False, sep="\t", na_rep="NULL")
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
        df.to_csv(out_file, index=False, sep="\t", na_rep="NULL")
    print("kernel-side stats:")
    print(df.to_string(index=False))
    print()
    return df


def memtest_stats(df, out_file=None):
    all_runs = []
    for run in df["run"].unique():
        stats = {"run": run}
        run_df = df[df["run"] == run]
        stats["n_allocs"] = Decimal(str(run_df["allocs"].sum()))
        stats["sz_allocs"] = Decimal(str(run_df["total_bytes"].sum()))
        delta_ns = run_df["alloc_end_ns"] - run_df["alloc_start_ns"]
        stats["alloc_secs"] = (delta_ns / NS_PER_SEC).sum()
        all_runs.append(stats)
    
    df = pd.DataFrame(all_runs)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t", na_rep="NULL")
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
        stats["mmap_eff"] =  round(mrun_row["n_allocs"] / srun_row["n_mmap"], 6)

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
        df.to_csv(out_file, index=False, sep="\t", na_rep="NULL")
    print("summary:")
    print(df.to_string(index=False))
    print()
    return df


# Modify memtest_df to add two columns: cumul_mmap_bytes and cumul_munmap_bytes.
# These are the cumulative number of bytes mmap'd and munmap'd, respectively, up to
# and including the given round. We need this because if the user frees a bunch 
# of memory in user space, not all of it may be unmapped by kernel.
def calc_frag_cols(strace_df, memtest_df, out_file=None):
    # assert strace_df's timestamps are monotonically increasing
    assert(np.all(np.diff(strace_df["timestamp_ns"]) >= 0))

    memtest_df["kernel_secs"] = 0
    memtest_df["cumul_mmap_bytes"] = 0
    memtest_df["cumul_munmap_bytes"] = 0
    mrow_i = 0
    for run in memtest_df["run"].unique():
        sdf = strace_df[strace_df["run"] == run]
        for row in memtest_df[memtest_df["run"] == run].itertuples():
            start_ts = row.alloc_start_ns
            end_ts = row.alloc_end_ns
            mmap_mask = (sdf["call"] == "mmap") & (sdf["timestamp_ns"] <= end_ts)
            munmap_mask = (sdf["call"] == "munmap") & (sdf["timestamp_ns"] <= start_ts)
            et_mask = (sdf["timestamp_ns"] >= start_ts) & (sdf["timestamp_ns"] <= end_ts)
            mmap_sum = sdf[mmap_mask]["size"].sum()
            munmap_sum = sdf[munmap_mask]["size"].sum()
            kernel_secs_sum = sdf[et_mask]["elapsed"].sum()
            
            # now set this row's kernel_secs, cumul_mmap_bytes, and cumul_munmap_bytes
            memtest_df.at[row.Index, "kernel_secs"] = kernel_secs_sum
            memtest_df.at[row.Index, "cumul_mmap_bytes"] = mmap_sum
            memtest_df.at[row.Index, "cumul_munmap_bytes"] = munmap_sum

    # calculate fragmentation
    numer = memtest_df["cumul_mmap_bytes"] - memtest_df["cumul_munmap_bytes"]
    denom = memtest_df["total_bytes"]
    memtest_df["frag"] = numer / denom
    
    print("detailed user-side stats with fragmentation:")
    print(memtest_df.to_string(index=False))
    print()
    if out_file is not None:
        memtest_df.to_csv(out_file, index=False, sep="\t", na_rep="NULL")


# Plot fragmentation over time for each run.
# Fragmentation is defined as (mmap'd bytes - munmap'd bytes) / malloc'd bytes.
def plot_frag(strace_df, memtest_df, out_path):    
    plt.figure()
    for run in memtest_df["run"].unique():
        mdf = memtest_df[memtest_df["run"] == run]
        plt.plot(mdf["round"], mdf["frag"], label=f"run {run}")
    plt.xlabel("round")
    plt.ylabel("fragmentation (mmap'd bytes / malloc'd bytes)")
    plt.grid(True, which="both")
    plt.title("Fragmentation over time")
    # plt.ylim(0, 4)
    plt.savefig(out_path)
    plt.close()


# Plot the cumulative number of bytes mmap'd and munmap'd over time.
# This is distinct from fragmentation, which is the ratio of mmap'd to malloc'd bytes.
# This just gives a sense of the kernel-side activity of the allocator.
def plot_net_mmap(strace_df, out_path):
    plt.figure()
    for run in strace_df["run"].unique()[:2]:
        sdf = strace_df[strace_df["run"] == run].copy()
        first_ts = sdf["timestamp_ns"].min()
        sdf["elapsed_ns"] = sdf["timestamp_ns"] - first_ts
        
        y = [0]  # net mmap
        x = [0]  # elapsed time
        for row in sdf.itertuples(index=False):
            if row.call == "mmap":
                y.append(y[-1] + row.size)
                x.append(row.elapsed_ns / NS_PER_SEC)
            elif row.call == "munmap":
                y.append(y[-1] - row.size)
                x.append(row.elapsed_ns / NS_PER_SEC)
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
    parser.add_argument("-u", nargs="?", default=10, type=int, help="mean artificial latency to add in microseconds")
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
    sdata_df = parse_strace(*sfiles, out_file=args.o / "strace_detail.tsv", delay_us=args.u)

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
