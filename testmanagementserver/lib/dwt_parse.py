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
import time
import numpy as np
import pandas as pd
import collections

# create the pandas data frame to store the parsed values in
# df = pd.DataFrame(columns=['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts'])
df_append = pd.DataFrame(index=["comp0", "comp1", "comp2", "comp3"],
                         columns=['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts'])

# solution w/o global vars would be to define the df and new_row as static variables in parser and then somehow pass
# the current df upwards to the parse_fun every time there could be a program stop.
# parse_fun will then directly create the csv file.


def parse_dwt_output(input_file):
    """
    Executes the read and parse functions which will read from the given input_file and parse the content
    It will save the parsed contents in the file specified as second argument

    Parameters:
        input_file (str): name of the file to parse
    Returns:
        df: dataframe containing the parsed data

    """
    swo_queue = collections.deque()
    global_ts_queue = collections.deque()

    # read raw file into queues
    read_fun(swo_queue, global_ts_queue, input_file)

    # parse data in queues and generate dataframe
    df = parse_fun(swo_queue, global_ts_queue)

    return df


def read_fun(swo_queue, global_ts_queue, input_file):
    """
    Reads from the input file and then puts values into the queue.
    It also handles special cases by putting a varying number of global timestamps into the queue
    """

    data_is_next = True  # we start with data
    local_ts_count = 0
    global_ts_count = 0
    currently_hw_packet = False  # we start with zeros so next is header
    currently_ts_packet = False  # we start with zeros so next is header
    next_is_header = True  # we start with zeros so next is header
    current_packet_size = 0
    with open(input_file) as open_file_object:
        for line in open_file_object:
            if data_is_next:  # Test if this is a line with data
                numbers = []  # initialise again, else has the numbers from previous line also

                for word in line.split():  # extract the numbers in the line into a python list
                    if word.isdigit():
                        numbers.append(int(word))

                        if currently_hw_packet:
                            if current_packet_size:  # still bytes left
                                current_packet_size -= 1
                            else:  # no more bytes in the hw packet => next is header
                                currently_hw_packet = False
                                next_is_header = True

                        if currently_ts_packet:
                            if not (int(word) & 0x80):  # means this is the last byte of ts, next byte is header
                                currently_ts_packet = False
                                next_is_header = True

                        if next_is_header:
                            if word == '192' or word == '208' or word == '224' or word == '240':
                                local_ts_count += 1  # need to find the local ts
                                currently_ts_packet = True
                                next_is_header = False
                            if word == '71' or word == '135' or word == '143':
                                currently_hw_packet = True
                                next_is_header = False
                                current_packet_size = int(word) & 0x03

                for byte in numbers:  # data line
                    swo_queue.appendleft(byte)  # put all the data into the queue that the parsing function will read from
                # now indicate that this is the end of a line
                # swo_queue.appendleft(LINE_ENDS)
                if numbers:
                    data_is_next = False

            else:  # If not it is a line with a global timestamp
                data_is_next = True
                global_ts_count += 1
                if global_ts_count > local_ts_count:  # case where had a global ts in middle of packet
                    global_ts_count -= 1  # need to put back to normal s.t. not again true in next round
                elif local_ts_count > global_ts_count:  # case where had several local ts in one packet
                    for _ in range(local_ts_count - global_ts_count):
                        global_ts_queue.appendleft(float(line))  # put the global ts several times (for every l ts once)
                        global_ts_count += 1
                    global_ts_queue.appendleft(float(line))  # plus the "normal" append to dequeue
                else:  # normal case, put the global timestamp in queue
                    global_ts_queue.appendleft(float(line))

    # finished reading all lines
    open_file_object.close()

    # # debug
    # print("read function ended (timestamp queue size: %d, swo queue size: %d)" % (len(global_ts_queue), len(swo_queue)))


def parse_fun(swo_queue, global_ts_queue):
    """
    Parses packets from the queue
    """
    df_out = pd.DataFrame(columns=['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts'])

    while swo_queue:
        swo_byte = swo_queue.pop()

        # sync packet, problem: in begin we have don't have 5 zero bytes as specified for a sync pack but there are 9
        # Just read all zeros until get an 0x80, then we are in sync.
        if swo_byte == 0:
            while swo_byte == 0 and swo_queue:
                swo_byte = swo_queue.pop()
            # according to documentation it should be 0x80 but I observe the stream to start with 0x08 in certain cases
            if swo_byte == 0x08:
                # now in sync
                swo_byte = swo_queue.pop()  # then get next byte

        lower_bytes = swo_byte & 0x0f
        if lower_bytes == 0x00 and not swo_byte & 0x80:  # 1-byte local timestamp has a zero in front (C = 0)
            # one byte local TS
            pass # do not comment, returning if detected is required!
        elif lower_bytes == 0x00:
            new_row = parse_timestamp(swo_queue, global_ts_queue)
            df_out = df_out.append(new_row, ignore_index=True)
        elif lower_bytes == 0x04:
            # reserved
            pass # do not comment, returning if detected is required!
        elif lower_bytes == 0x08:
            # ITM ext
            pass # do not comment, returning if detected is required!
        elif lower_bytes == 0x0c:
            # DWT ext
            pass # do not comment, returning if detected is required!
        else:
            if swo_byte & 0x04:
                parse_hard(swo_byte, swo_queue)
            else:
                raise Exception("ERROR: unrecognized SWO byte: {}".format(swo_byte))

    return df_out


def parse_hard(header_swo_byte, swo_queue):
    """
    Parses a DWT hardware packet
    """
    global df_append
    # the given swo_byte is a header for a PC, an address, data read or data write packet
    size_bytes = header_swo_byte & 0x03
    if size_bytes == 3:
        size = 4
    elif size_bytes == 2:
        size = 2
    elif size_bytes == 1:
        size = 1
    else:
        raise Exception("invalid packet size in swo header byte")

    buf = [0, 0, 0, 0]
    for i in range(0, size):
        # for the case that we stopped exec but this would be hanging on get(), we must first test if not stopped
        if not swo_queue:
            return
        buf[i] = swo_queue.pop()
    value = (buf[3] << 24) + (buf[2] << 16) + (buf[1] << 8) + (buf[0] << 0)

    comparator_id = (header_swo_byte >> 4) & 0b11 # id is in bit 4 and 5
    comparator_label = 'comp{}'.format(comparator_id)

    # debug
    # with open('/home/flocklab/tmp/log2.txt', 'a') as f_debug:
    #     f_debug.write('{}\n'.format(comparator_id))

    # data value packet
    if header_swo_byte >> 6 == 0b10:
        df_append.at[comparator_label, 'comparator'] = comparator_id
        df_append.at[comparator_label, 'data'] = value
        df_append.at[comparator_label, 'operation'] = 'w' if (header_swo_byte & 0b1000) else 'r'
    # PC value or address packet
    elif header_swo_byte >> 6 == 0b01:
        df_append.at[comparator_label, 'comparator'] = comparator_id
        df_append.at[comparator_label, 'PC'] = hex(value)
    # unknown packet
    else:
        raise Exception('ERROR: Unknown data trace packet type observed!')


def parse_timestamp(swo_queue, global_ts_queue):
    """
    Parses timestamp packets and writes a line into output file after every timestamp
    """
    global df_append
    buf = [0, 0, 0, 0]
    i = 0
    local_ts_delta = 0

    while i < 4:
        if not swo_queue:  # to not get blocked on queue.get() first check if should stop
            return
        buf[i] = swo_queue.pop()
        local_ts_delta |= (buf[i] & 0x7f) << i * 7  # remove the first bit and shift by 0,7,14,21 depending on value

        if buf[i] & 0x80:         # if more payload the first bit of payload is = 1 (Continuation bit)
            i += 1
            continue
        else:
            break  # if the first bit was 0 then no more payload

    # now we want to complete all the half filled rows in the df_append (contain only data, PC, operation, comparator)
    # there can be several data (in several rows) but we only have 1 local ts and 1 global ts to use for all of them
    empty = df_append[:].isnull().apply(lambda x: all(x), axis=1)

    # we only have one global timestamp for one local timestamp so need to pop and reuse
    global_ts = global_ts_queue.pop()
    if not empty['comp0']:
        df_append.at['comp0', 'local_ts'] = local_ts_delta
        df_append.at['comp0', 'global_ts'] = global_ts
        new_row = df_append.loc['comp0'].copy()
    elif not empty['comp1']:
        df_append.at['comp1', 'local_ts'] = local_ts_delta
        df_append.at['comp1', 'global_ts'] = global_ts
        new_row = df_append.loc['comp1'].copy()
    elif not empty['comp2']:
        df_append.at['comp2', 'local_ts'] = local_ts_delta
        df_append.at['comp2', 'global_ts'] = global_ts
        new_row = df_append.loc['comp2'].copy()
    elif not empty['comp3']:
        df_append.at['comp3', 'local_ts'] = local_ts_delta
        df_append.at['comp3', 'global_ts'] = global_ts
        new_row = df_append.loc['comp3'].copy()
    # overflow was received, so no comparator data, only global and local ts
    elif empty['comp0'] and empty['comp1'] and empty['comp2'] and empty['comp3']:
        # create a series used in the case we only have a timestamp and no packets (local ts overflow)
        new_row = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan])
        new_row.index = ['global_ts', 'data', 'PC', 'operation', 'local_ts']

        new_row.at["local_ts"] = local_ts_delta
        new_row.at['global_ts'] = global_ts

    # reset the df_append to nan values
    for col in df_append.columns:
        df_append[col].values[:] = np.nan

    return new_row



def correct_ts_with_regression(df_in):
    """
    Calculates a regression based on the values in log_table.csv
    Then projects the global timestamps onto the regression and writes the corrected values in log_table_corrected.csv

    Params:
        df_in: dataframe containing parsed data
    Returns:
        df_out: dataframe containing time corrected data
    """
    df_out = df_in.copy()

    # extract the global and local timestamps and put into a numpy array
    x = df_out['local_ts'].to_numpy(dtype=float)
    y = df_out['global_ts'].to_numpy(dtype=float)

    # add up the local timestamps and calculate the global timestamp relative to the first global timestamp
    sum_local_ts = 0

    for local_ts in np.nditer(x, op_flags=['readwrite']):
        sum_local_ts = local_ts[...] = sum_local_ts + local_ts

    # use the data from the arrays to calculate the regression
    b = estimate_coef(x, y)

    # correct the global timestamp in the data frame
    for local_ts, global_ts in np.nditer([x, y], op_flags=['readwrite']):
        global_ts[...] = b[0] + b[1] * local_ts

    # write the array back into the pandas df to replace the global timestamps
    df_out['global_ts'] = y

    # The file log_table_corrected.csv now contains the corrected global timestamps together with the DWT packets

    return df_out



def estimate_coef(x, y):
    """
    Calculates coefficient b_0 and b_1 of the regression.

    Parameters:
      x (numpy array): the local timestamps received from target
      y (numpy array): the global timestamps taken on the observer

    Returns:
      int: b_0 offset of linear regression
      int: b_1 slope of linear regression
    """
    # number of observations/points
    n = np.size(x)

    # mean of x and y vector
    m_x, m_y = np.mean(x), np.mean(y)

    # calculating cross-deviation and deviation about x
    SS_xy = np.sum(y * x) - n * m_y * m_x
    SS_xx = np.sum(x * x) - n * m_x * m_x

    # calculating regression coefficients
    b_1 = SS_xy / SS_xx
    b_0 = m_y - b_1 * m_x

    return b_0, b_1



if __name__ == '__main__':
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        parse_dwt_output(filename, filename + ".csv")
        correct_ts_with_regression(filename + ".csv", filename + "_corrected.csv")
