#!/usr/bin/env python3

# extracts a specified part of a GPIO tracing file for easier plotting with the FlockLab tools

import sys
import os


if len(sys.argv) < 4:
    print("no enough arguments provided")
    print("usage: %s [results_dir] [start_time] [end_time]" % (__file__))
    sys.exit(1)

results_dir = sys.argv[1]
start_time  = float(sys.argv[2])
end_time    = float(sys.argv[3])

if not os.path.isdir(results_dir):
    print("directory %s not found" % results_dir)
    sys.exit(1)

if (start_time < 0) or (end_time <= start_time) or (end_time > 86400):
    print("invalid start and/or end time")
    sys.exit(1)

# check if output directory exists
outdir = results_dir.rstrip("/") + "_part"
if not os.path.isdir(outdir):
    os.mkdir(outdir)

processed_lines = 0
output_lines    = 0
output          = []

with open("%s/gpiotracing.csv" % results_dir, 'r') as f_in:
    lines          = f_in.readlines()
    teststart_time = 0
    for line in lines:
        (timestamp, obsid, node_id, pin, state) = line.split(",", 5)
        if "timestamp" in timestamp:    # first line?
            output.append(line)
            continue
        if teststart_time == 0:
            teststart_time = float(timestamp)
        relative_time = float(timestamp) - teststart_time
        if (relative_time >= start_time) and (relative_time <= end_time) or ("nRST" in pin):
            output.append(line)
            output_lines += 1
        processed_lines += 1

if len(output) > 0:
    with open("%s/gpiotracing.csv" % outdir, 'w') as f_out:
        f_out.write("".join(output))

print("%d lines processed, %d lines written to %s" % (processed_lines, output_lines, outdir))
