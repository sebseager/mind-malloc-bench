import matplotlib.pyplot as plt
import pandas as pd

# load the data into a pandas dataframe
df = pd.read_csv('netmmap_fin.csv', sep='\t', header=0)

# create a figure and axis object
fig, ax = plt.subplots(figsize=(10, 4))

# loop through each allocator in the dataframe and plot its data
for allocator, data in df.groupby('allocator'):
    x = data['elapsed_ns']
    y = data['net_mmap_bytes']
    ax.plot(x, y, label=allocator)

# set the title, x/y axis labels, and legend
ax.set_title("Net mmap'd bytes over time")
ax.set_xlabel("Elapsed Time (ns)")
ax.set_ylabel("Net mmap'd bytes")

# add grid
ax.grid(True, which='both', axis='both')

ax.legend()

plt.savefig('net_mmap_bytes.png')