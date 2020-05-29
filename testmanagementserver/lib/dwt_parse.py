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

import queue
import sys
import time
import threading
import numpy as np
import pandas as pd
import collections

both_threads_done = False
read_thread_ended = False

logging_on = False

sys.setswitchinterval(5e-3)  # switch threads every 5 ms. This prevents that read thread writes too much into queue

# create the pandas data frame to store the parsed values in
df = pd.DataFrame(columns=['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts'])
df_append = pd.DataFrame(index=["comp0", "comp1", "comp2", "comp3"],
                         columns=['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts'])

# create a series used in the case we only have a timestamp and no packets (local ts overflow)
nan = np.nan
new_row = pd.Series([nan, nan, nan, nan, nan])
index_ = ['global_ts', 'data', 'PC', 'operation', 'local_ts']
new_row.index = index_

# solution w/o global vars would be to define the df and new_row as static variables in parser and then somehow pass
# the current df upwards to the parse_fun every time there could be a program stop.
# parse_fun will then directly create the csv file.


def parse_dwt_output(input_file='swo_read_log', output_file='swo_read_log.csv', threads=False):
    """
    Starts the read and parse thread that will read from the given input_file and parse the content
    It will save the parsed contents in the file specified as second argument

    Parameters:
        input_file (str): name of the file to parse
        output_file (str): name of the file to parse
        threads (bool): if set to true program will run using 2 threads, else first read then parse
    Returns:
        int: True if the program was halted by Key interrupt

    """
    global df
    swo_queue = collections.deque()
    global_ts_queue = collections.deque()
    # df_queue = queue.Queue()

    # Output the information about the program.
    if logging_on:
        sys.stdout.write('configure and read demo\n')
        sys.stdout.write('Press Ctrl-C to Exit\n')

    if threads:
        # Create threads
        read_thread = threading.Thread(target=read_fun, args=(swo_queue, global_ts_queue, input_file))
        read_thread.setDaemon(True)
        parse_thread = threading.Thread(target=parse_fun, args=(swo_queue, global_ts_queue))
        parse_thread.setDaemon(True)

        # Starts threads
        read_thread.start()
        parse_thread.start()

        while True:
            time.sleep(1)
            if both_threads_done:
                break

    else:
        read_fun(swo_queue, global_ts_queue, input_file)
        parse_fun(swo_queue, global_ts_queue)

    # df = df_queue.get()
    # convert the pandas data frame to a csv file
    df.to_csv(output_file, index=False, header=True)

    if threads:
        read_thread.join()  # wait for the threads to end
        parse_thread.join()

    return 0  # exit the program execution


def read_fun(swo_queue, global_ts_queue, input_file):
    """
    Reads from the input file and then puts values into the queue. This runs as a thread.
    It also handles special cases by putting a varying number of global timestamps into the queue
    """

    global read_thread_ended
    # global new_row
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
                data_is_next = False
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
                    swo_queue.appendleft(byte)  # put all the data into the queue that the parsing thread will read from
                # now indicate that this is the end of a line
                # swo_queue.appendleft(LINE_ENDS)
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
    read_thread_ended = True
    if logging_on:
        print("read thread ended")


def parse_fun(swo_queue, global_ts_queue):
    """
    Calls the parse function on packets from the queue in a loop until the program is stopped or queue is empty
    """
    global both_threads_done
    while True:  # if stop_threads this fun will jump to end and stop by join()
        # if not swo_queue.empty():
        if swo_queue:
            swo_byte = swo_queue.pop()
            parser(swo_byte, swo_queue, global_ts_queue)
        else:
            if not read_thread_ended:  # just an empty queue but will be filled again
                time.sleep(0.01)
                continue
            else:  # in this case the queue is emtpy and the read thread has finished so close the program
                both_threads_done = True  # tell the loop in main to stop
                # df_queue.put(df)  # must use a queue to pass the value back to main
                return


def parser(swo_byte, swo_queue, global_ts_queue):
    """
    Parses packets from the queue
    """
    # sync packet, problem: in begin we have don't have 5 zero bytes as specified for a sync pack but there are 9
    # Just read all zeros until get an 0x80, then we are in sync.
    if swo_byte == 0:  # only happens at beginning so no check for stop_threads
        while swo_byte == 0 and swo_queue:
            swo_byte = swo_queue.pop()
        # according to documentation it should be 0x80 but I observe the stream to start with 0x08 in certain cases
        if swo_byte == 0x08:
            if logging_on:
                print("now in sync")
            swo_byte = swo_queue.pop()  # then get next byte

    lower_bytes = swo_byte & 0x0f
    if lower_bytes == 0x00 and not swo_byte & 0x80:  # 1-byte local timestamp has a zero in front (C = 0)
        if logging_on:
            print("one byte local TS")
    elif lower_bytes == 0x00:
        timestamp_parse(swo_queue, global_ts_queue)
    elif lower_bytes == 0x04:
        if logging_on:
            print("reserved")
    elif lower_bytes == 0x08:
        if logging_on:
            print("ITM ext")
    elif lower_bytes == 0x0c:
        if logging_on:
            print("DWT ext")
    else:
        if swo_byte & 0x04:
            pars_hard(swo_byte, swo_queue)
        else:
            if logging_on:
                print("this is a SWIT packet (SW source)")


def pars_hard(header_swo_byte, swo_queue):
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
        if logging_on:
            print("invalid size")
        return

    buf = [0, 0, 0, 0]
    for i in range(0, size):
        # for the case that we stopped exec but this would be hanging on get(), we must first test if not stopped
        if read_thread_ended and not swo_queue:
            return
        buf[i] = swo_queue.pop()
    value = (buf[3] << 24) + (buf[2] << 16) + (buf[1] << 8) + (buf[0] << 0)

    comparator_id = (header_swo_byte & 0x30) >> 4  # id is in bit 4 and 5

    # A data read or write
    if header_swo_byte & 0x80:
        if comparator_id == 0:
            df_append.at['comp0', 'comparator'] = 0
            df_append.at['comp0', 'data'] = value
            if header_swo_byte & 0x04:
                df_append.at['comp0', 'operation'] = 'w'
            else:
                df_append.at['comp0', 'operation'] = 'r'

        elif comparator_id == 1:
            df_append.at['comp1', 'comparator'] = 1
            df_append.at['comp1', 'data'] = value
            if header_swo_byte & 0x04:
                df_append.at['comp1', 'operation'] = 'w'
            else:
                df_append.at['comp1', 'operation'] = 'r'

        elif comparator_id == 2:
            df_append.at['comp2', 'comparator'] = 2
            df_append.at['comp2', 'data'] = value
            if header_swo_byte & 0x04:
                df_append.at['comp2', 'operation'] = 'w'
            else:
                df_append.at['comp2', 'operation'] = 'r'

        else:
            df_append.at['comp3', 'comparator'] = 3
            df_append.at['comp3', 'data'] = value
            if header_swo_byte & 0x04:
                df_append.at['comp3', 'operation'] = 'w'
            else:
                df_append.at['comp3', 'operation'] = 'r'

    # A PC or address packet
    else:
        if comparator_id == 0:
            df_append.at['comp0', 'comparator'] = 0
            df_append.at['comp0', 'PC'] = hex(value)
        elif comparator_id == 1:
            df_append.at['comp1', 'comparator'] = 1
            df_append.at['comp1', 'PC'] = hex(value)
        elif comparator_id == 2:
            df_append.at['comp2', 'comparator'] = 2
            df_append.at['comp2', 'PC'] = hex(value)
        else:
            df_append.at['comp3', 'comparator'] = 3
            df_append.at['comp3', 'PC'] = hex(value)



def timestamp_parse(swo_queue, global_ts_queue):
    """
    Parses timestamp packets and writes a line into output file after every timestamp
    """
    global df_append
    global df
    buf = [0, 0, 0, 0]
    i = 0
    local_ts_delta = 0

    while i < 4:
        if read_thread_ended and not swo_queue:  # to not get blocked on queue.get() first check if should stop
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
        series0 = df_append.loc['comp0']
        df = df.append(series0, ignore_index=True)
    elif not empty['comp1']:
        df_append.at['comp1', 'local_ts'] = local_ts_delta
        df_append.at['comp1', 'global_ts'] = global_ts
        series1 = df_append.loc['comp1']
        df = df.append(series1, ignore_index=True)
    elif not empty['comp2']:
        df_append.at['comp2', 'local_ts'] = local_ts_delta
        df_append.at['comp2', 'global_ts'] = global_ts
        series2 = df_append.loc['comp2']
        df = df.append(series2, ignore_index=True)
    elif not empty['comp3']:
        df_append.at['comp3', 'local_ts'] = local_ts_delta
        df_append.at['comp3', 'global_ts'] = global_ts
        series3 = df_append.loc['comp3']
        df = df.append(series3, ignore_index=True)
    # overflow was received, so no comparator data, only global and local ts
    elif empty['comp0'] and empty['comp1'] and empty['comp2'] and empty['comp3']:
        new_row.at["local_ts"] = local_ts_delta
        new_row.at['global_ts'] = global_ts

        df = df.append(new_row, ignore_index=True)


    # reset the df_append to nan values
    nan = np.nan
    for col in df_append.columns:
        df_append[col].values[:] = nan



def correct_ts_with_regression(input_file='swo_read_log.csv', output_file='swo_read_log_corrected.csv'):
    """
    Calculates a regression based on the values in log_table.csv
    Then projects the global timestamps onto the regression and writes the corrected values in log_table_corrected.csv
    """
    # read data in the file into a pandas data frame
    df = pd.read_csv(input_file)

    # extract the global and local timestamps and put into a numpy array
    x = df['local_ts'].to_numpy(dtype=float)
    y = df['global_ts'].to_numpy(dtype=float)

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
    df['global_ts'] = y
    # convert the pandas data frame to a csv file
    df.to_csv(output_file, index=False, header=True)

    if logging_on:
        print("\n")
        print("The file log_table_corrected.csv now contains the corrected global timestamps together with the DWT packets")


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
