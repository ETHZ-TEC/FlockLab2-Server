#! /usr/bin/env python3

"""
Copyright (c) 2010 - 2022, ETH Zurich, Computer Engineering Group
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


# extract data from test results directory
def extract_data(results_dir, start, end, output_dir):
    filenames    = [ 'gpiotracing.csv', 'powerprofiling.csv' ]    # first file must be GPIO tracing
    output       = []
    teststart    = None
    gpiotracing  = True
    line_cnt     = 0

    for filename in filenames:
        line_cnt = 0
        filepath = "%s/%s" % (results_dir, filename)
        if not os.path.isfile(filepath):
            continue
        print("extracting data from %s..." % filepath)

        with open(filepath, 'r') as f:
            for line in f.readlines():
                parts     = line.split(",")
                timestamp = parts[0]
                if gpiotracing:
                    pin = parts[3]
                if "timestamp" in timestamp:  # first line?
                    output.append(line)
                    continue
                if not teststart:
                    teststart = float(timestamp)
                ofs = float(timestamp) - teststart
                if (ofs >= start) and (ofs <= end) or (gpiotracing and "nRST" in pin):
                    output.append(line)

        if len(output) > 0:
            line_cnt += len(output)
            with open("%s/%s" % (output_dir, filename), 'w') as f:
                f.write("".join(output))

        gpiotracing = False
        output.clear()

    return line_cnt



if __name__ == "__main__":

    # check arguments
    if len(sys.argv) < 4:
        print("no enough arguments provided")
        print("usage: %s [results_dir] [start_time] [end_time]" % (__file__))
        sys.exit(1)

    results_dir = sys.argv[1].rstrip("/")
    start_time  = float(sys.argv[2])
    end_time    = float(sys.argv[3])

    if not os.path.isdir(results_dir):
        print("directory %s not found" % results_dir)
        sys.exit(1)

    if (start_time < 0) or (end_time <= start_time) or (end_time > 86400):
        print("invalid start and/or end time")
        sys.exit(1)

    # check if output directory exists
    out_dir = results_dir + "_part"
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    # GPIO tracing
    line_cnt = extract_data(results_dir, start_time, end_time, out_dir)
    print("%d lines written to %s" % (line_cnt, out_dir))
