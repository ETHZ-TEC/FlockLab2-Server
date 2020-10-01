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

class SwoParser():
    def __init__(self):
        self._streamStarted = False
        self._currentPkt = []
        self._ignoreBytes = 0

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
            self._tc = (header >> 4) & 0b11 if not self._format2 else 0b00 ## format 2 can only occur if timestamp is synchronous (i.e. tc=0b00)

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
                raise Exception("ERROR: DatatracePkt with reserved packetType!")

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


    def addSwoByte(self, swoByte):
        """
        Args:
            swoByte: single SWO byte (header or payload) which shall be parsed.
            NOTE: SWO bytes need to be inserted in the correct sequence (as outputted by the SWO port)
        Returns:
            Parsed packet object if provided swoByte leads to the completion of a packet, None otherwise

        """

        # sync to packet in byte stream
        if not self._streamStarted:
            # read all zeros until get an 0x80, then we are in sync (Synchronization packet)
            # NOTE: dpp2lora bytestream does not contain required single-bit in Synchronization packet
            if swoByte == 0:
                return None
            elif swoByte == 0x08:
                return None
            else:
                self._streamStarted = True
                print('>>>>>>>> Stream started!')

        # ignore paylaod bytes of nrecognized packet
        if self._ignoreBytes:
            self._ignoreBytes -= 1
            return None

        # parse packets with content
        if len(self._currentPkt) == 0:
            # we do not currently have a begun packet -> start new one
            if swoByte & 0b11001111 == 0b11000000:
                # Local timestamp packet header
                self._currentPkt.append(type(self).LocalTimestampPkt(header=swoByte))
            elif swoByte & 0b10001111 == 0b0:
                # Local timestamp packet header (single-byte)
                self._currentPkt.append(type(self).LocalTimestampPkt(header=swoByte))
            elif swoByte == 0b01110000:
                self._currentPkt.append(type(self).OverflowPkt(header=swoByte))
            elif swoByte >> 2 & 0b1  == 0b1 and swoByte & 0b11 != 0b00:
                # Hardware source packet header
                discriminator_id = swoByte >> 3 & 0b11111
                plSize = map_size(swoByte & 0b11)
                if discriminator_id in [0, 1, 2]:
                    # 0 Event counter wrapping, 1 Exception tracing, 2 PC sampling
                    self._ignoreBytes = plSize
                    print('WARNING: Hardware source packet with discriminator_id={} ignored!'.format(discriminator_id))
                elif discriminator_id >= 8 and discriminator_id <= 23:
                    # Data tracing
                    self._currentPkt.append(type(self).DatatracePkt(header=swoByte))
                else:
                    # Other undefined header
                    raise Exception("ERROR: Unrecognized discriminator ID in hardware source packet header: {}".format(swoByte)) # packets with undefined discriminator_id appear sporadically -> we cannot throw error here
            else:
                print("ERROR: Unrecognized DWT packet header: {} {:#010b}".format(swoByte, swoByte))
        else:
            # we currently have a begun packet -> add data
            self._currentPkt[0].addByte(swoByte)

        # check whether current packet is complete
        if self._currentPkt[0].isComplete():
            return self._currentPkt.pop()
        else:
            return None



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
    with open(input_file) as open_file_object:
        for i, line in enumerate(open_file_object):
            if i == 0:
                # ignore first line with varnames
                continue

            if data_is_next:
                # Line with data

                numbers = []
                for word in line.split():
                    if not word.isdigit():
                        raise Exception('ERROR: element of line is not digits as expected for a line with data')

                    numbers.append(int(word))
                read_queue.appendleft(('data', numbers))
                data_is_next = False
            else:
                # Line with global timestamp

                # check if line actually contains a float
                if not is_float(line):
                    raise Exception('ERROR: line is not float as expected for a line with global timestamp')

                read_queue.appendleft(('global_ts', float(line)))
                data_is_next = True


def parse_fun(read_queue):
    """
    Parses packets from the queue

    Relevant passage from ARMv7-M Architecture Reference Manual:
    "Local timestamping is differential, meaning each timestamp gives the time since the previous local timestamp.
    When local timestamping is enabled and a DWT or ITM event transfers a packet to the appropriate output FIFO,
    and the timestamp counter is non-zero, the ITM:
    * Generates a Local timestamp packet.
    * Resets the timestamp counter to zero."
    """
    columns = ['global_ts', 'comparator', 'data', 'PC', 'operation', 'local_ts']
    out_list = []

    completedPkts = []
    completedOverflowPkts = []

    # completedDataPkts = []
    # completedLocalTimestampPkts = []

    swoParser = SwoParser()

    while read_queue:
        elem = read_queue.pop()
        elemType, elemData = elem
        if elemType == 'data':
            for swoByte in elemData:
                ret = swoParser.addSwoByte(swoByte)
                if ret:
                    print(ret)
                    if type(ret) == SwoParser.LocalTimestampPkt:
                        completedPkts.append(ret)
                    elif type(ret) == SwoParser.DatatracePkt:
                        completedPkts.append(ret)
                    elif type(ret) == SwoParser.OverflowPkt:
                        completedOverflowPkts.append(ret)
                    else:
                        raise Exception['ERROR: Packet completed but type is unknown!']

        elif elemType == 'global_ts':
            global_ts = elemData

            if not swoParser._streamStarted:
                continue

            # go through list of completed packts and try to create new rows
            overflowPkts = []
            while completedPkts:
                # find next set of packtes for creating one row
                idx = None
                for i, pkt in enumerate(completedPkts):
                    if type(pkt) == SwoParser.DatatracePkt:
                        continue
                    elif type(pkt) == SwoParser.LocalTimestampPkt:
                        idx = i
                        break
                    else:
                        raise Exception('ERROR: Unrecognized packet type!')

                if idx is None:
                    # no (more) complete set found -> wait for more data
                    break
                elif idx == 0:
                    # single LocalTimestampPkt
                    assert type(pkt) == SwoParser.LocalTimestampPkt
                    dataPkt = completedPkts.pop(0)
                    new_row = collections.OrderedDict(zip(columns, [None]*len(columns)))
                    new_row['local_ts'] = dataPkt.ts
                    new_row['global_ts'] = global_ts
                    out_list += [new_row]
                else:
                    # Set with datatrace packets found
                    dataPkts = []
                    ltsPkts = []
                    for i in range(idx+1):
                        pkt = completedPkts.pop(0)
                        if type(pkt) == SwoParser.DatatracePkt:
                            dataPkts.append(pkt)
                        elif type(pkt) == SwoParser.LocalTimestampPkt:
                            ltsPkts.append(pkt)
                        else:
                            raise Exception('ERROR: Unexpected packet type {}'.format(type(pkt)))

                    assert len(dataPkts) >= 1
                    assert len(ltsPkts) == 1
                    # FIXME handle LocalTimestamp pkts with tc!=0 properly
                    # assert ltsPkts[0].tc == 0
                    # FIXME support case where multiple comparators output data!
                    comparators = [e.comparator for e in dataPkts]
                    if len(set(comparators)) > 1:
                        raise Exception('ERROR: More than one comparator in set for creating a row!')
                    else:
                        comparatorId = comparators[0]

                    ltsUsed = False # indicate whether LocalTimestampPkt has been used for logging a row or not (releveant since local timestamp is a delta timestamp and logged value should therefore not always be incremented when LocalTimestampPkt is used multiple times)
                    while dataPkts:
                        # decide whether to process one (data only) or two (data and PC) dataPkts
                        use2Pkts = False
                        if len(dataPkts) >= 2:
                            if (dataPkts[0].comparator == dataPkts[1].comparator) and (dataPkts[0].pktType != dataPkts[1].pktType):
                                use2Pkts = True

                        # create row
                        new_row = collections.OrderedDict(zip(columns, [None]*len(columns)))
                        for i in range(use2Pkts+1):
                            dataPkt = dataPkts.pop(0)
                            if dataPkt.pktType == 1: # data trace pc value pkt
                                if not dataPkt.addressPkt: # we want PC value
                                    new_row['PC'] = hex(dataPkt.value)
                            elif dataPkt.pktType == 2: # data trace data value pkt
                                new_row['operation'] = 'w' if dataPkt.writeAccess else 'r'
                                new_row['data'] = dataPkt.value
                        new_row['comparator'] = int(comparatorId)
                        # only log LocalTimestamp if this is the first row logged for this LocalTimestamp epoch (local timestamps are delta tiestamps!)
                        if not ltsUsed:
                            new_row['local_ts'] = ltsPkts[0].ts
                            ltsUsed = True
                        else:
                            new_row['local_ts'] = 0
                        new_row['global_ts'] = global_ts
                        out_list += [new_row]


            # output overflow packats
            for pkt in completedOverflowPkts:
                new_row = collections.OrderedDict(zip(columns, [None]*len(columns)))
                new_row['global_ts'] = global_ts
                out_list += [new_row]
            completedOverflowPkts.clear()

        else:
            # Unrecognized elemType
            raise Exception('ERROR: Unknown element type!')

    ret = pd.DataFrame(out_list)
    # FIXME: comparator and data should be ints not floats
    # return ret.astype({'comparator': 'int32', 'data': 'int32'})
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
