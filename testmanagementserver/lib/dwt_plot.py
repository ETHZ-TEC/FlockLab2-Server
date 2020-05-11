#! /usr/bin/env python3

"""
Copyright (c) 2020, ETH Zurich, Computer Engineering Group
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

Author: Lukas Daschinger
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt


def configure_read_parse(filename='swo_read_log_corrected.csv'):
    # read data in the file ./log_table.csv into a pandas data frame
    df = pd.read_csv(filename)

    # need to forward fill the NaN values.
    # (there are rows with a global ts but no data which would cause problems in plotting)
    df['data'] = df['data'].fillna(method='ffill')

    # at the very beginning there are no values to forward fill so the variable is set to zero to not appear in plot
    df['data'] = df['data'].fillna(0)

    # we need to extract the data values and timestamps  of comp0, comp1, comp2 and comp3 separately
    x = df['global_ts'].to_numpy()
    y = df['data'].to_numpy()

    x0 = df.loc[df['comparator'] == 0, 'global_ts'].to_numpy()
    y0 = df.loc[df['comparator'] == 0, 'data'].to_numpy()

    x1 = df.loc[df['comparator'] == 1, 'global_ts'].to_numpy()
    y1 = df.loc[df['comparator'] == 1, 'data'].to_numpy()

    x2 = df.loc[df['comparator'] == 2, 'global_ts'].to_numpy()
    y2 = df.loc[df['comparator'] == 2, 'data'].to_numpy()

    x3 = df.loc[df['comparator'] == 3, 'global_ts'].to_numpy()
    y3 = df.loc[df['comparator'] == 3, 'data'].to_numpy()

    # draw a graph
    # plt.scatter(x, y, color="g")
    plt.step(x0, y0)
    plt.step(x1, y1)
    plt.step(x2, y2)
    plt.step(x3, y3)
    # putting labels
    plt.xlabel('time [s]')
    plt.ylabel('variable')
    plt.show()



if __name__ == '__main__':
    if len(sys.argv) > 1:
        configure_read_parse(sys.argv[1])
