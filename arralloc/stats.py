from argparse import ArgumentParser
from pathlib import Path
import pandas as pd

# Each file is a list of memory-related calls recorded by strace
# for a single run of arralloc. The format per-line is:
# [timestamp] [call]([args]) = [return value] <[elapsed time]>
# The file ends with a message like +++ exited with # +++
# Read the files into a single pandas DataFrame.
def strace_df(*files, out_file=None):
    dicts = []
    for it, fp in enumerate(files):
        with open(fp, "r") as f:
            for line in f:
                line = line.strip()
                if line == "":
                    continue
                if "+++" in line:
                    continue
                elts = line.split(" ")
                n_elts = len(elts)
                try:
                    d = {}
                    d["run"] = it + 1  # match 1-indexed file names in harness.sh
                    for i in range(n_elts):
                        if i == 0:
                            d["timestamp"] = str(elts[i])
                        elif i == 1:
                            d["call"] = elts[i].split("(")[0]
                        elif i == 2:
                            if d["call"] == "mmap":
                                d["size"] = int(elts[i].split(",")[0])
                            elif d["call"] == "munmap":
                                d["size"] = int(elts[i].split(")")[0])
                            else:
                                continue
                        else:
                            if elts[i] == "=":
                                d["return"] = int(elts[i + 1], 16)  # hex to int
                                # drop < and > surrounding elapsed time
                                d["elapsed"] = float(elts[i + 2][1:-1])
                            else:
                                continue
                except:
                    print(f"error parsing line: {line}")
                    continue
                dicts.append(d)
    
    df = pd.DataFrame(dicts)
    if out_file is not None:
        df.to_csv(out_file, index=False, sep="\t")
    
    return df


def parse_args():
    parser = ArgumentParser(description="Test the performance of array allocation")
    parser.add_argument("-f", nargs="+", required=True,
                        help="strace output files (with flags -e trace=memory -ttt -T)")
    parser.add_argument("-o", nargs=1, required=True, help="output directory")
    parser.add_argument("--plot", action="store_true", help="plot the results")
    parser.add_argument("--recalc", action="store_true", help="reread input files")
    args = parser.parse_args()

    # validation and arg processing
    args.o = Path(args.o[0])
    args.o.mkdir(parents=True, exist_ok=True)
    args.f = [Path(f) for f in args.f]

    return args


def print_summary_stats(df):
    # average overhead
    # we find the average number of mmap + munmap calls per run
    import pdb; pdb.set_trace()
    overhead = df.groupby("run").count()["call"].mean()


def main():
    args = parse_args()
    strace_files = [f for f in args.f if f.name.startswith("strace_")]

    # read strace files into df
    strace_out = args.o / "strace.tsv"
    if args.recalc or not (strace_out).exists():
        df = strace_df(*strace_files, out_file=strace_out)
    else:
        try:
            df = pd.read_csv(strace_out, sep="\t")
        except:
            print(f"Error reading {strace_out}, try --recalc")
            exit(1)
    
    # run analyses
    print_summary_stats(df)




if __name__ == "__main__":
    main()
