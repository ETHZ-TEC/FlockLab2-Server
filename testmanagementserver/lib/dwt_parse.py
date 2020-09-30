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

class SwoPkt():
    def __init__(self, header):
        self._header = header
        self._plBytes = []

    def addByte(self, byteVal):
        raise Exception('ERROR: This function is a prototype and should not directly be called!')

    def isComplete(self):
        raise Exception('ERROR: This function is a prototype and should not directly be called!')

    def __str__(self):
        raise Exception('ERROR: This function is a prototype and should not directly be called!')


class LocalTimestampPkt(SwoPkt):
    def __init__(self, header):
        # TODO: determine from header whether timestamp pkt has payload or not (currently local timestamp packet format 2 (single-byte) is not supported)
        super().__init__(header)
        self._complete = False
        self._format2 = (self._header & 0b10001111 == 0) # format 2 (single-byte packet)
        self._tc = (header >> 4) & 0b11 if not self._format2 else None

    def addByte(self, byteVal):
        self._plBytes.append(byteVal)

    def isComplete(self):
        if self._format2:
            # format 2 (single-byte packet) case
            return True
        else:
            # format 1 (at least one payload byte)
            if not self._plBytes:
                return False
            continuation_bit = self._plBytes[-1] & 0x80
            # continuation_bit==0 indicates that this is the last byte of the local timstamp packet
            return continuation_bit==0

    @property
    def ts(self):
        if not self.isComplete():
            raise Exception('ERROR: Cannot get timestamp from incomplete LocalTimestampPkt')

        if self._format2:
            ret = (self._header & 0b01110000) >> 4
        else:
            ret = 0
            for i, byte in enumerate(self._plBytes):
                ret |= (byte & 0x7f) << i * 7  # remove the first bit and shift by 0,7,14,21 depending on value
        return ret

    @property
    def tc(self):
        return self._tc

    def __str__(self):
        ret = "LocalTimestampPkt {} {:#010b}{}:".format(self._header, self._header, "" if self.isComplete() else " (incomplete)")
        ret += "\n  bytes: {}".format(self._plBytes)
        ret += "\n  format: {}".format(2 if self._format2 else 1)
        if self.isComplete():
            ret += "\n  ts: {}".format(self.ts)
            ret += "\n  tc: {}".format(self.tc)
        return ret

class DatatracePkt(SwoPkt):
    def __init__(self, header):
        super().__init__(header)
        self._payloadSize = map_size(header & 0b11)
        self._pktType = (header >> 6) & 0b11 # 1: PC value or address; 2: data value; otherweise: reserved
        self._comparator = (header >> 4) & 0b11 # comparator that generated the data
        self._addressPkt = None # True if data trace address pkt, False if data trace PC value pkt
        self._writeAccess = None # True if write access, False if read access
        if self._pktType == 1:  # PC value or address
            self._addressPkt = (header >> 3 & 0b1)
        elif self._pktType == 2: # data value
            self._writeAccess = (header >> 3 & 0b1)
        else:
            raise Exception('ERROR: Reserved data trace packet type encountered!')

    def addByte(self, byteVal):
        self._plBytes.append(byteVal)
        # TODO set isComplete var to true if contin==0

    def isComplete(self):
        return len(self._plBytes) == self._payloadSize

    @property
    def pktType(self):
        return self._pktType

    @property
    def comparator(self):
        return self._comparator

    @property
    def addressPkt(self):
        return self._addressPkt

    @property
    def writeAccess(self):
        return self._writeAccess

    @property
    def value(self):
        return (self._plBytes[3] << 24) + (self._plBytes[2] << 16) + (self._plBytes[1] << 8) + (self._plBytes[0] << 0)

    def __str__(self):
        ret = "DatatracePkt {} {:#010b}{}:".format(self._header, self._header, "" if self.isComplete() else " (incomplete)")
        ret += "\n  bytes: {}".format(self._plBytes)
        ret += "\n  pktType: {}".format(self.pktType)
        ret += "\n  comparator: {}".format(self.comparator)
        ret += "\n  payloadSize: {}".format(self._payloadSize)
        if self.pktType == 1:
            # PC value or address;
            ret += "\n  addressPkt: {}".format(self.addressPkt)
        elif self.pktType == 2:
            # data value; otherweise: reserved
            ret += "\n  writeAccess: {}".format(self.writeAccess)
        else:
            raise Exception("ERROR: DataTracePkt with reserved packetType!")

        if self.isComplete():
            ret += "\n  value: {}".format(self.value)

        return ret

class OverflowPkt(SwoPkt):
    def __init__(self, header):
        super().__init__(header)

    def isComplete(self):
        # overflow packet consists of a single header byte
        return True

    def __str__(self):
        return "OverflowPkt"




def parse_dwt_output(input_file):
    """
    Executes the read and parse functions which will read from the given input_file and parse the content.

    Parameters:
        input_file (str): name of the file to parse
    Returns:
        df: dataframe containing the parsed data

    """
    read_queue = collections.deque()

    # read raw file into queue
    read_fun(read_queue, input_file)

    # parse data in queues and generate dataframe
    df = parse_fun(read_queue)

    return df


def map_size(ss):
    if ss == 1:
        return 1
    elif ss == 2:
        return 2
    elif ss == 3:
        return 4
    else:
        raise Exception('ERROR: Invalid ss size: ss should not be ==0 or >3')


def is_float(str):
    try:
        float(str)
        return True
    except ValueError:
        return False


def read_fun(read_queue, input_file):
    """
    Reads from the input file and then puts values into the queue.
    It also handles special cases by putting a varying number of global timestamps into the queue
    """

    data_is_next = True  # we expect that raw file starts with data (not with global timestamp)
    # local_ts_count = 0
    # global_ts_count = 0
    # currently_hw_packet = False  # we start with zeros so next is header
    # currently_ts_packet = False  # we start with zeros so next is header
    # next_is_header = True  # we start with zeros so next is header
    # current_packet_size = 0
    with open(input_file) as open_file_object:
        for i, line in enumerate(open_file_object):
            if i == 0:
                continue # ignore first line with varnames

            if data_is_next:
                # Line with data

                numbers = []
                for word in line.split():
                    if not word.isdigit():
                        raise Exception('ERROR: element of line is not digits as expected for a line with data')

                    numbers.append(int(word))
                read_queue.appendleft(('data', numbers))
                data_is_next = False

                    # if currently_hw_packet:
                    #     if current_packet_size:  # still bytes left
                    #         current_packet_size -= 1
                    #     else:  # no more bytes in the hw packet => next is header
                    #         currently_hw_packet = False
                    #         next_is_header = True
                    #         continue
                    #
                    # if currently_ts_packet:
                    #     continuation_bit = int(word) & 0x80
                    #     if continuation_bit == 0: # continuation_bit==0 indicates that this is the last byte of the local timstamp packet
                    #         currently_ts_packet = False
                    #         next_is_header = True
                    #         continue
                    #
                    # # TODO: handle overflow packets
                    # if next_is_header:
                    #     # if word == '192' or word == '208' or word == '224' or word == '240':
                    #     if int(word) & 0b11001111 == 0b11000000:
                    #         # Local timestamp packet
                    #         local_ts_count += 1  # need to find the local ts
                    #         currently_ts_packet = True
                    #         next_is_header = False
                    #     # elif word == '71' or word == '135' or word == '143':
                    #     elif int(word) >> 2 & 0b1  == 0b1 and int(word) & 0b11 != 0b00:
                    #         # Hardware source packet
                    #         discriminator_id = int(word) >> 3 & 0b11111
                    #         if discriminator_id >= 8 and discriminator_id <= 23:
                    #             # Data tracing
                    #             currently_hw_packet = True
                    #             next_is_header = False
                    #             current_packet_size = map_size(int(word) & 0b11) - 1
                    #         else:
                    #             # Other packet (Event counter wrapping, Exception tracing, PC sampling)
                    #             next_is_header = False
                    #             current_packet_size = map_size(int(word) & 0b11) - 1

            else:
                # Line with global timestamp

                # check if line actually contains a float
                if not is_float(line):
                    raise Exception('ERROR: line is not float as expected for a line with global timestamp')

                read_queue.appendleft(('global_ts', float(line)))
                data_is_next = True

                # data_is_next = True
                # global_ts_count += 1
                # if global_ts_count > local_ts_count:  # case where had a global ts in middle of packet
                #     global_ts_count -= 1  # need to put back to normal s.t. not again true in next round
                # elif local_ts_count > global_ts_count:  # case where had several local ts in one packet
                #     for _ in range(local_ts_count - global_ts_count):
                #         global_ts_queue.appendleft(float(line))  # put the global ts several times (for every l ts once)
                #         global_ts_count += 1
                #     global_ts_queue.appendleft(float(line))  # plus the "normal" append to dequeue
                # else:  # normal case, put the global timestamp in queue

    # # finished reading all lines
    # open_file_object.close()

    # # DEBUG
    # print("read function ended (timestamp queue size: %d, swo queue size: %d)" % (len(global_ts_queue), len(swo_queue)))


def parse_fun(read_queue):
    """
    Parses packets from the queue
    """
    df_out = pd.DataFrame(columns=['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts'])

    streamStarted = False
    nextHeader = False
    completedDataPkts = []
    completedLocalTimestampPkts = []
    completedOverflowPkts = []
    currentPkt = []
    ignoreBytes = 0

    while read_queue:
        elem = read_queue.pop()
        elemType, elemData = elem
        if elemType == 'data':
            for swoByte in elemData:
                # sync to packet in byte stream
                # problem: in begin we have don't have 5 zero bytes as specified for a sync pack but there are 9
                # Just read all zeros until get an 0x80, then we are in sync.
                # FIXME implement according to manual
                if not streamStarted:
                    if swoByte == 0:
                        continue
                    elif swoByte == 0x08:
                        continue
                    else:
                        streamStarted = True
                        print('>>>>>>>> Stream started!')
                        nextHeader = True

                # parse packets with content
                if nextHeader:
                    if swoByte & 0b11001111 == 0b11000000:
                        # Local timestamp packet header
                        currentPkt.append(LocalTimestampPkt(header=swoByte))
                        nextHeader = False
                        # # TODO combine with other isComplete check (this here is necessary since payloadSize could be 0)
                        # # this should not occur since single-byte local timestamp has different header (see blow)
                        # if currentPkt[0].isComplete:
                        #     completedLocalTimestampPkts.append(currentPkt.pop())
                        #     nextHeader = True
                        # new_row_list = parse_timestamp(swo_queue, global_ts_queue, df_append)
                        # df_out = df_out.append(new_row_list, ignore_index=True)
                    elif swoByte & 0b10001111 == 0b0:
                        # Local timestamp packet header (single-byte)
                        currentPkt.append(LocalTimestampPkt(header=swoByte))
                        print(currentPkt[0])
                        completedLocalTimestampPkts.append(currentPkt.pop())
                        nextHeader = True
                        # print('WARNING: local timestamp packet format 2 (single-byte) occurred! {}'.format(swoByte))
                    elif swoByte == 0b01110000:
                        currentPkt.append(OverflowPkt(header=swoByte))
                        print(currentPkt[0])
                        completedOverflowPkts.append(currentPkt.pop())
                        nextHeader = True
                    elif swoByte >> 2 & 0b1  == 0b1 and swoByte & 0b11 != 0b00:
                        # Hardware source packet header
                        discriminator_id = swoByte >> 3 & 0b11111
                        plSize = map_size(swoByte & 0b11)
                        if discriminator_id in [0, 1, 2]:
                            # 0 Event counter wrapping, 1 Exception tracing, 2 PC sampling
                            nextHeader = False
                            ignoreBytes = plSize
                            # raise Exception("ERROR: Unexpected discriminator ID in hardware source packet header: {}".format(swoByte))
                        elif discriminator_id >= 8 and discriminator_id <= 23:
                            # Data tracing
                            currentPkt.append(DatatracePkt(header=swoByte))
                            nextHeader = False
                            # TODO combine with other isComplete check (this here is necessary since payloadSize could be 0)
                            if currentPkt[0].isComplete():
                                print(currentPkt[0])
                                if type(currentPkt[0]) == LocalTimestampPkt:
                                    completedLocalTimestampPkts.append(currentPkt.pop())
                                    nextHeader = True
                                elif type(currentPkt[0]) == DatatracePkt:
                                    completedDataPkts.append(currentPkt.pop())
                                    nextHeader = True
                                else:
                                    raise Exception['ERROR: Packet completed but type is unknown!']
                            # parse_hard(swoByte, swo_queue, df_append)
                        else:
                            # Other undefined header
                            # print("Unknown discriminator ID in hardware source packet header: {}".format(swoByte))
                            raise Exception("ERROR: Unknown discriminator ID in hardware source packet header: {}".format(swoByte)) # packets with undefined discriminator_id appear sporadically -> we cannot throw error here
                    else:
                        print("unrecognized DWT packet header: {} {:#010b}".format(swoByte, swoByte))
                else:
                    if ignoreBytes:
                        ignoreBytes -= 1
                        if ignoreBytes == 0:
                            nextHeader = True
                    else:
                        currentPkt[0].addByte(swoByte)
                        # TODO combine with other isComplete check (implement swoparser object and implement function for isComplete check)
                        if currentPkt[0].isComplete():
                            print(currentPkt[0])
                            if type(currentPkt[0]) == LocalTimestampPkt:
                                completedLocalTimestampPkts.append(currentPkt.pop())
                                nextHeader = True
                            elif type(currentPkt[0]) == DatatracePkt:
                                completedDataPkts.append(currentPkt.pop())
                                nextHeader = True
                            else:
                                raise Exception['ERROR: Packet completed but type is unknown!']
        elif elemType == 'global_ts':
            if not streamStarted:
                continue

            if not completedLocalTimestampPkts:
                print('WARNING: cannot create rows from current data since there is no complete local timestamp pkt')
                continue # cannot create rows from current data since there is no complete local timestamp pkt

            new_row_list = []
            if completedDataPkts:
                for comparatorId in [0, 1, 2, 3]:
                    # create new row and append t143 0 0 0 0o df_out
                    # TODO: handle completedOverflowPkts!
                    new_row = pd.DataFrame([np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
                    new_row.index = ['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts']
                    for dataPkt in completedDataPkts:
                        if dataPkt.comparator == comparatorId:
                            if dataPkt.pktType == 1: # data trace pc value pkt
                                if not dataPkt.addressPkt: # we want PC value
                                    new_row.at["PC"] = hex(dataPkt.value)
                            elif dataPkt.pktType == 2: # data trace data value pkt
                                new_row.at["operation"] = 'w' if dataPkt.writeAccess else 'r'
                                new_row.at["data"] = dataPkt.value
                    if not np.isnan(new_row.at["data", 0]):
                        new_row.at["comparator"] = comparatorId
                        new_row.at["local_ts"] = completedLocalTimestampPkts[-1].ts
                        new_row.at['global_ts'] = elemData
                        new_row_list += [new_row]
            else:
                # no completedDataPkts -> we have overflow timestamp -> add it to use it for regression
                new_row = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan])
                new_row.index = ['global_ts', 'data', 'PC', 'operation', 'local_ts']
                new_row.at["local_ts"] = completedLocalTimestampPkts[-1].ts
                new_row.at['global_ts'] = elemData
                new_row_list += [new_row]
            if completedOverflowPkts:
                for overflowPkt in completedOverflowPkts:
                    new_row = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
                    new_row.index = ['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts']
                    new_row.at['global_ts'] = elemData
                    new_row_list += [new_row]
            df_out = df_out.append(new_row_list, ignore_index=True)
        else:
            raise Exception('ERROR: Unknown element type!')





        # # sync packet, problem: in begin we have don't have 5 zero bytes as specified for a sync pack but there are 9
        # # Just read all zeros until get an 0x80, then we are in sync.
        # if swo_byte == 0:
        #     while swo_byte == 0 and swo_queue:
        #         swo_byte = swo_queue.pop()
        #     # according to documentation it should be 0x80 but I observe the stream to start with 0x08 in certain cases
        #     if swo_byte == 0x08:
        #         # now in sync
        #         swo_byte = swo_queue.pop()  # then get next byte
        #
        # if swo_byte & 0b11001111 == 0b11000000:
        #     # Local timestamp packet
        #     new_row_list = parse_timestamp(swo_queue, global_ts_queue, df_append)
        #     df_out = df_out.append(new_row_list, ignore_index=True)
        # elif swo_byte >> 2 & 0b1  == 0b1 and swo_byte & 0b11 != 0b00:
        #     # Hardware source packet
        #     discriminator_id = swo_byte >> 3 & 0b11111
        #     if discriminator_id in [0, 1, 2]:
        #         # 0 Event counter wrapping, 1 Exception tracing, 2 PC sampling
        #         pass
        #     elif discriminator_id >= 8 and discriminator_id <= 23:
        #         # Data tracing
        #         parse_hard(swo_byte, swo_queue, df_append)
        #     else:
        #         # Other undefined packet
        #         print("Unknown discriminator ID in hardware source packet header: {}".format(swo_byte))
        #         # raise Exception("ERROR: Unknown discriminator ID in hardware source packet header: {}".format(swo_byte)) # packets with undefined discriminator_id appear sporadically -> we cannot throw error here
        # else:
        #     print("unrecognized DWT packet header: {}".format(swo_byte))

    return df_out


def parse_hard(header_swo_byte, swo_queue, df_append):
    """
    Parses a DWT hardware packet
    """
    # the given swo_byte is a header for a PC, an address, data read or data write packet
    size = map_size(header_swo_byte & 0b11)

    buf = [0, 0, 0, 0]
    for i in range(0, size):
        # for the case that we stopped exec but this would be hanging on get(), we must first test if not stopped
        if not swo_queue:
            return
        buf[i] = swo_queue.pop()
    value = (buf[3] << 24) + (buf[2] << 16) + (buf[1] << 8) + (buf[0] << 0)

    comparator_id = (header_swo_byte >> 4) & 0b11 # id is in bit 4 and 5
    comparator_label = 'comp{}'.format(comparator_id)

    # DEBUG
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


def parse_timestamp(swo_queue, global_ts_queue, df_append):
    """
    Parses timestamp packets and writes a line into output file after every timestamp
    """
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
    # DEBUG
    # print('number of non-empty rows in df_append: {}'.format(len(empty) - np.sum(empty)))

    # we only have one global timestamp for one local timestamp so need to pop and reuse
    global_ts = global_ts_queue.pop()
    ret = []
    if not empty['comp0']:
        df_append.at['comp0', 'local_ts'] = local_ts_delta
        df_append.at['comp0', 'global_ts'] = global_ts
        ret += [df_append.loc['comp0'].copy()]
    if not empty['comp1']:
        df_append.at['comp1', 'local_ts'] = local_ts_delta
        df_append.at['comp1', 'global_ts'] = global_ts
        ret += [df_append.loc['comp1'].copy()]
    if not empty['comp2']:
        df_append.at['comp2', 'local_ts'] = local_ts_delta
        df_append.at['comp2', 'global_ts'] = global_ts
        ret += [df_append.loc['comp2'].copy()]
    if not empty['comp3']:
        df_append.at['comp3', 'local_ts'] = local_ts_delta
        df_append.at['comp3', 'global_ts'] = global_ts
        ret += [df_append.loc['comp3'].copy()]
    if empty['comp0'] and empty['comp1'] and empty['comp2'] and empty['comp3']:
        # overflow was received, so no comparator data, only global and local ts
        # create a series used in the case we only have a timestamp and no packets (local ts overflow)
        new_row = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan])
        new_row.index = ['global_ts', 'data', 'PC', 'operation', 'local_ts']

        new_row.at["local_ts"] = local_ts_delta
        new_row.at['global_ts'] = global_ts
        ret += [new_row]

    # reset the df_append to nan values
    for col in df_append.columns:
        df_append[col].values[:] = np.nan

    return ret



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
