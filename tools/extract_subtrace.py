#! /usr/bin/env python3

"""
Copyright (c) 2010 - 2020, ETH Zurich, Computer Engineering Group
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

"""

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
