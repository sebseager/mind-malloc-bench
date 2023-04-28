import matplotlib.pyplot as plt
import pandas as pd

# load the data into a pandas dataframe
df = pd.read_csv('frag.csv', sep='\t', header=0)

# create a figure object with three subplots stacked vertically
fig, axs = plt.subplots(nrows=3, ncols=1, figsize=(10, 8))

# loop through each allocator in the dataframe and plot its data in a separate subplot
for i, (allocator, data) in enumerate(df.groupby('allocator')):
    x = data['elapsed_start_time']
    y = data['frag']
    axs[i].plot(x, y)
    axs[i].set_title(allocator)
    if i == 2:
        axs[i].set_xlabel('Elapsed Start Time')
    axs[i].set_ylabel('Fragmentation')
    axs[i].set_ylim([1, 2.5])
    axs[i].grid(True, which='both', axis='both')
    axs[i].minorticks_on()

# set the overall title for the figure
fig.suptitle('Fragmentation vs. Time by Allocator')
fig.tight_layout(pad=2.0)

# save to file
fig.savefig('frag.png')