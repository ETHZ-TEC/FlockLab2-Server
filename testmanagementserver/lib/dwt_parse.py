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

Author:  Lukas Daschinger
Adapted: Roman Trub
"""

import sys
import time
import numpy as np
import pandas as pd
from scipy import stats
import collections

################################################################################
# Constants
################################################################################
FULL_TIMESTAMP = 1999999        # timestamp in LocalTimestampPkt when overflow happened
                                # see ARM CoreSight Components Technical Reference Manual

PRESCALER = 16                  # prescaler configured in Trace Control Register (ITM_TCR)
                                # NOTE: needs to match the settings on the observer!

# time offset between datatrace and GPIO service (ts_datatrace + offset = ts_gpio)
DT_FIXED_OFFSET = -5.0e-3  # shift half of loop delay
# DT_FIXED_OFFSET_RESET = +11.65e-3 # time correction based on reset is disabled, see comment at end of timeCorrection()

FILTER_THRESHOLD = 0.15 # Threshold for percentage of filtered messages to produce an error
RESIDUAL_UNFILTERED_THRESHOLD = 0.300 # Threshold for residuals magnitude to producing error (in seconds)
PLATFORM_CORRECTION_OFFSET = -1.3e-3 # offset for platforms (Linux version) with larger overhead


################################################################################
# SwoParser Class
################################################################################
class SwoParser():
    def __init__(self):
        self._ignoreBytes = 0
        self._processingSyncPkt = True # we assume that SWO stream starts with sync packet
        self._currentPkt = []

    class SwoPkt():
        def __init__(self, header, globalTs=None):
            self._header = header
            self._plBytes = []
            self._globalTs = globalTs

        @property
        def globalTs(self):
            return self._globalTs

        @globalTs.setter
        def globalTs(self, globalTs):
            self._globalTs = globalTs

        def addByte(self, byteVal):
            raise Exception('ERROR: This function is a prototype and should not directly be called!')

        def isComplete(self):
            raise Exception('ERROR: This function is a prototype and should not directly be called!')

        def __str__(self):
            raise Exception('ERROR: This function is a prototype and should not directly be called!')

        def __repr__(self):
            return str(self)


    class LocalTimestampPkt(SwoPkt):
        def __init__(self, header, globalTs=None):
            super().__init__(header, globalTs)
            self._complete = False
            self._format2 = (self._header & 0b10001111 == 0) # format 2 (single-byte packet)
            self._tc = (header >> 4) & 0b11 if not self._format2 else 0b00 ## format 2 can only occur if timestamp is synchronous (i.e. tc=0b00)

        def addByte(self, byteVal):
            if len(self._plBytes) >= 4:
                raise Exception('ERROR: Payload of LocalTimestampPkt cannot be longer than 4 bytes! MCU probably not properly initialized...')
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
            ret += "\n  globalTs: {}".format(self.globalTs)
            ret += "\n  format: {}".format(2 if self._format2 else 1)
            if self.isComplete():
                ret += "\n  ts: {}".format(self.ts)
                ret += "\n  tc: {}".format(self.tc)
            return ret

    class DatatracePkt(SwoPkt):
        def __init__(self, header, globalTs=None):
            super().__init__(header, globalTs)
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
            ret = 0
            for i, byte in enumerate(self._plBytes):
                ret |= byte << i * 8
            return ret

        def __str__(self):
            ret = "DatatracePkt {} {:#010b}{}:".format(self._header, self._header, "" if self.isComplete() else " (incomplete)")
            ret += "\n  bytes: {}".format(self._plBytes)
            ret += "\n  globalTs: {}".format(self.globalTs)
            ret += "\n  pktType: {} ({})".format(self.pktType, 'PC value or address' if self.pktType == 1 else 'data value')
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
        def __init__(self, header, globalTs=None):
            super().__init__(header, globalTs)

        def isComplete(self):
            # overflow packet consists of a single header byte
            return True

        def __str__(self):
            ret = "OverflowPkt"
            ret += "\n  globalTs: {}".format(self.globalTs)
            return ret


    def addSwoByte(self, swoByte, globalTs=None):
        """
        Args:
            swoByte: single SWO byte (header or payload) which shall be parsed.
            NOTE: SWO bytes need to be inserted in the correct sequence (as outputted by the SWO port)
        Returns: (packet, newSyncEpoch)
            packet: Parsed packet object if provided swoByte leads to the completion of a packet, None otherwise
            newSyncEpoch: True if a new sync epoch started (i.e. sync packet received and first non-zero byte added), False otherwise
        """
        retPkt = None
        newSyncEpoch = False

        # ignore payload bytes of unrecognized packet
        if self._ignoreBytes:
            self._ignoreBytes -= 1
            return retPkt, newSyncEpoch

        # process sync packet (to sync to packet in byte stream)
        if self._processingSyncPkt:
            # read all zeros until get an 0x80, then we are in sync (Synchronization packet)
            # NOTE: dpp2lora bytestream does not contain required single-bit in Synchronization packet
            if swoByte == 0:
                return retPkt, newSyncEpoch
            # elif swoByte == 0x08:
            #     return retPkt, newSyncEpoch
            else:
                # got a non-0 byte -> sync pkt finished, current byte is processed and interpreted as header
                self._processingSyncPkt = False
                newSyncEpoch = True

        # parse packets with content
        if len(self._currentPkt) == 0:
            # HEADER: we do not currently have a begun packet -> start new sync packet
            if swoByte == 0b0:
                # we expect a new header, got 0 byte -> interpreted as start of sync packet
                self._processingSyncPkt = True
            elif swoByte & 0b11001111 == 0b11000000:
                # Local timestamp packet header
                self._currentPkt.append(type(self).LocalTimestampPkt(header=swoByte, globalTs=globalTs))
            elif (swoByte & 0b10001111 == 0b0) and not (swoByte == 0b01110000):
                # Local timestamp packet header (single-byte)
                self._currentPkt.append(type(self).LocalTimestampPkt(header=swoByte, globalTs=globalTs))
            elif swoByte == 0b01110000:
                self._currentPkt.append(type(self).OverflowPkt(header=swoByte, globalTs=globalTs))
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
                    self._currentPkt.append(type(self).DatatracePkt(header=swoByte, globalTs=globalTs))
                else:
                    # Other undefined header
                    raise Exception("ERROR: Unrecognized discriminator ID ({}) in hardware source packet header: {}".format(discriminator_id, swoByte))
            else:
                print("ERROR: Unrecognized DWT packet header: {} {:#010b}".format(swoByte, swoByte))
        else:
            # PAYLOAD: we currently have a begun packet -> add data
            self._currentPkt[0].addByte(swoByte)

        # check whether current packet is complete
        if len(self._currentPkt) != 0 and self._currentPkt[0].isComplete():
            retPkt = self._currentPkt.pop()

        return retPkt, newSyncEpoch

################################################################################
# METHODS
################################################################################
def processDatatraceOutput(input_file):
    """
    Executes the read, parse, timestamp adding, and time correction functions to
    parse a raw datatrace file into a dataframe of results.

    Parameters:
        input_file (str): path to the raw data trace file
    Returns:
        df: dataframe containing the processed data
    """

    # # DEBUG
    # import matplotlib.pyplot as plt
    # plt.close('all')

    # read raw file into list
    dataTsList, sleepOverhead = readRaw(input_file)

    # parse data/globalTs stream from list (returns packet list split into different sync packet epochs)
    syncEpochList = parseDataTs(dataTsList)

    # process packet list of each sync epoch separately
    dfDataCorrList = []
    dfLocalTsCorrList = []
    dfOverflowList = []
    for i, pktList in enumerate(syncEpochList):
        # # DEBUG
        print('INFO: Sync Epoch {}'.format(i))
        # with open('pktList_{}.txt'.format(i), 'w') as f:
        #     for i, pkt in enumerate(pktList):
        #         f.write('{}\n{}\n'.format(i, pkt))

        # split localTs epochs
        batchList = splitEpochs(pktList)

        # # DEBUG
        # for batch in batchList:
        #     print([type(e).__name__ for e in batch])

        # combine data packets and add localTs
        dfData, dfLocalTs, dfOverflow = combinePkts(batchList)

        if len(dfLocalTs) < 2:
            raise Exception('ERROR: dfLocalTs is empty or does not contain enough pkts -> unable to apply time correction!')

        dfDataCorr, dfLocalTsCorr = timeCorrection(dfData, dfLocalTs, sleepOverhead, firstSyncEpoch=(i==0))

        dfDataCorrList.append(dfDataCorr)
        dfLocalTsCorrList.append(dfLocalTsCorr)
        dfOverflowList.append(dfOverflow)

    # concat results from different sync epochs
    dfData = pd.concat(dfDataCorrList)
    dfLocalTs = pd.concat(dfLocalTsCorrList)
    dfOverflow = pd.concat(dfOverflowList)

    return dfData, dfLocalTs, dfOverflow


def readRaw(input_file):
    """
    Reads from raw data trace file and puts each line into a queue.
    """

    outList = []

    with open(input_file) as f:
        lines = f.readlines()

    # skip first line with varnames but extract sleep_overhead value
    sleepOverhead = float(lines.pop(0).split()[-1:][0])
    # # DEBUG for old trace files without sleepOverhead value
    # lines.pop(0).split()
    # sleepOverhead = 0

    for i in range(int(len(lines)/2)):
        # we expect that raw file starts with data (not with global timestamp)
        data = lines[i*2].strip()
        globalTs = lines[i*2+1].strip()

        # check and convert words in data line
        numbers = []
        for word in data.split():
            if not word.isdigit():
                raise Exception('ERROR: element of line is not digits as expected for a line with data')
            numbers.append(int(word))

        # check if globalTs line actually contains a float
        if not is_float(globalTs):
            raise Exception('ERROR: line is not float as expected for a line with global timestamp')

        # add data and timestamp as tuple
        outList.append((numbers, globalTs))

    return outList, sleepOverhead


def parseDataTs(inList):
    """
    Parses data/globalTs stream from list and batches optained pkts into sync packet epochs.
    """
    syncEpochList = []
    completedPkts = []
    firstSyncEpoch = True # we assume that SWO byte stream starts with sync pkt => first sync epoch is expected to be empty
    swoParser = SwoParser()

    while inList:
        data, globalTs = inList.pop(0)

        for swoByte in data:
            ret, newSyncEpoch = swoParser.addSwoByte(swoByte, globalTs)
            if newSyncEpoch:
                # print('INFO: new sync epoch started!')
                if firstSyncEpoch:
                    # ignore packets from first sync epoch (we assume that SWO stream starts with sync pkt -> completedPkts should be empty anyway)
                    firstSyncEpoch = False
                else:
                    syncEpochList.append(completedPkts)
                completedPkts = [] # NOTE: do not use completedPkts.clear() since this would also clear the list just appended to syncEpochList (as both variables point to the same list object)
            if ret:
                completedPkts.append(ret)

    # append last sync epoch to syncEpochList
    syncEpochList.append(completedPkts)

    # # DEBUG
    # for i, syncEpoch in enumerate(syncEpochList):
    #     print('=== Sync Epoch {} ==='.format(i))
    #     for i, pkt in enumerate(completedPkts):
    #         print(i)
    #         print(pkt)

    return syncEpochList


def splitEpochs(pktList):
    """
    Splits stream of packets into epochs. Each epoch contains exactly one reference packet (either LocalTsPkt or OverflowPkt).
    """
    batchList = []
    startIdx = 0
    stopIdx = 0

    while startIdx < len(pktList):
        if type(pktList[startIdx]) == SwoParser.LocalTimestampPkt and pktList[startIdx].ts == FULL_TIMESTAMP:
            # next packet is local timestamp overflow packet -> put it into its own batch
            stopIdx += 1
        elif type(pktList[startIdx]) == SwoParser.OverflowPkt:
            # next packet is overflow packet -> put it into its own batch
            stopIdx += 1
        else:
            # next packet is NOT local timestamp overflow packet and NOT OverflowPkt

            ## search start of following localTs epoch

            # find current and next reference packet
            currentRefpktIdx = None
            followingRefpktIdx = None
            for i in range(startIdx, len(pktList)):
                if type(pktList[i]) in (SwoParser.LocalTimestampPkt, SwoParser.OverflowPkt):
                    if not currentRefpktIdx:
                        currentRefpktIdx = i
                    else:
                        followingRefpktIdx = i
                        break

            # we expect that there is at least 1 ref packet
            assert currentRefpktIdx
            # ref pkt should not be local timestamp overflow packet
            if type(pktList[currentRefpktIdx]) == SwoParser.LocalTimestampPkt:
                assert pktList[currentRefpktIdx].ts != FULL_TIMESTAMP

            # based on following reference packet, determine stopIdx
            if not followingRefpktIdx:
                # no following localTs found -> rest of list is single epoch
                stopIdx = len(pktList)
            else:
                # following reference packet found
                if type(pktList[followingRefpktIdx]) == SwoParser.LocalTimestampPkt and pktList[followingRefpktIdx].ts == FULL_TIMESTAMP:
                    stopIdx = followingRefpktIdx
                elif type(pktList[followingRefpktIdx]) == SwoParser.OverflowPkt:
                    stopIdx = followingRefpktIdx
                else:
                    ## go back to data packet that caused the reference packet
                    ## based on sample traces, up to 2 datatrace packet can precede a LocalTsPkt (PC and data)
                    ## it is not clear if other packets (e.g. overflow packet) could be between datatrace and localTsPkt
                    # find data packet preceding the reference pkt
                    data2Idx = followingRefpktIdx
                    while type(pktList[data2Idx]) != SwoParser.DatatracePkt:
                        data2Idx -= 1
                        assert data2Idx >= currentRefpktIdx # at least packets up to the found reference packet should be in the in the current epoch
                    # find data packet preceding the data2 data pkt
                    data1Idx = data2Idx - 1
                    while True:
                        if type(pktList[data1Idx]) == SwoParser.DatatracePkt:
                            break
                        elif data1Idx <= currentRefpktIdx:
                            data1Idx = None
                            break
                        else:
                            data1Idx -= 1

                    if data1Idx is None:
                        stopIdx = data2Idx
                    else:
                        if ((pktList[data1Idx].comparator == pktList[data2Idx].comparator) and
                            (pktList[data1Idx].pktType != pktList[data2Idx].pktType)):
                            stopIdx = data1Idx
                        else:
                            stopIdx = data2Idx

        # # DEBUG
        # print('({},{})'.format(startIdx, stopIdx))
        # print('[')
        # for pkt in pktList[startIdx:stopIdx]:
        #     print(pkt)
        # print(']')

        # add found epoch
        batchList.append(pktList[startIdx:stopIdx])
        startIdx = stopIdx

    return batchList


def combinePkts(batchList):
    """
    Combines data packets and adds localTs
    """
    dataColumns = ['global_ts_uncorrected', 'comparator', 'data', 'PC', 'operation', 'local_ts']
    localTsColumns = ['global_ts_uncorrected', 'local_ts', 'tc', 'full_ts']
    overflowColumns = ['global_ts_uncorrected']

    dataOut = []
    localTsOut = []
    overflowOut = []
    localTsCum = 0

    for batch in batchList:
        # sort packets
        dataPkts = []
        localTsPkts = []
        overflowPkts = []
        for pkt in batch:
            if type(pkt) == SwoParser.DatatracePkt:
                dataPkts.append(pkt)
            elif type(pkt) == SwoParser.LocalTimestampPkt:
                localTsPkts.append(pkt)
            elif type(pkt) == SwoParser.OverflowPkt:
                overflowPkts.append(pkt)
            else:
                raise Exception('ERROR: Unknown packet type {}'.format(type(pkt)))

        if not ( (len(localTsPkts) == 1 and len(overflowPkts) == 0) or (len(localTsPkts) == 0 and len(overflowPkts) == 1)) :
            raise Exception('ERROR: batch does not contain exactly 1 reference packet (contains {} LocalTimestampPkt and {} OverflowPkt)!'.format(len(localTsPkts), len(overflowPkts)))

        if localTsPkts:
            localTsCum += localTsPkts[0].ts + 1/PRESCALER # +1 cycle (scaled by prescaler) because transition from last sent value to 0 takes one clock cycle (see ARM CoreSight Components Technical Reference Manual, p. 302)

        # process data pkts
        while dataPkts:
            # decide whether to process one (data only) or two (data and PC) dataPkts
            use2Pkts = False
            if len(dataPkts) >= 2:
                if (dataPkts[0].comparator == dataPkts[1].comparator) and (dataPkts[0].pktType != dataPkts[1].pktType):
                    use2Pkts = True

            # create row
            newRow = collections.OrderedDict(zip(dataColumns, [None]*len(dataColumns)))
            minGlobalTs = None
            for i in range(use2Pkts+1):
                dataPkt = dataPkts.pop(0)
                minGlobalTs = dataPkt.globalTs if (minGlobalTs is None) else min(minGlobalTs, dataPkt.globalTs)
                if dataPkt.pktType == 1: # data trace pc value pkt
                    if not dataPkt.addressPkt: # we want PC value
                        newRow['PC'] = hex(dataPkt.value)
                elif dataPkt.pktType == 2: # data trace data value pkt
                    newRow['operation'] = 'w' if dataPkt.writeAccess else 'r'
                    newRow['data'] = dataPkt.value
            newRow['comparator'] = int(dataPkt.comparator)
            if localTsPkts:
                newRow['local_ts'] = localTsCum
                newRow['local_ts_tc'] = localTsPkts[0].tc
            newRow['global_ts_uncorrected'] = minGlobalTs
            dataOut += [newRow]

        # process local ts packets (note: there should be 0 or 1 LocalTimestampPkt)
        if localTsPkts:
            newRow = collections.OrderedDict(zip(localTsColumns, [None]*len(localTsColumns)))
            newRow['local_ts'] = localTsCum
            # newRow['local_ts_diff'] = localTsPkts[0].ts # DEBUG
            newRow['global_ts_uncorrected'] = localTsPkts[0].globalTs
            newRow['tc'] = localTsPkts[0].tc
            newRow['full_ts'] = int(localTsPkts[0].ts == FULL_TIMESTAMP) # indicate wheter LocalTimestampPkt is overflow pkt or not
            localTsOut += [newRow]

        # process overflow packets (note: there should be 0 or 1 OverflowPkt)
        if overflowPkts:
            newRow = collections.OrderedDict(zip(overflowColumns, [None]*len(overflowColumns)))
            newRow['global_ts_uncorrected'] = overflowPkts[0].globalTs
            overflowOut += [newRow]

    # prepare to return DataFrames
    dfData = pd.DataFrame(dataOut) if dataOut else pd.DataFrame(columns=dataColumns)
    dfLocalTs = pd.DataFrame(localTsOut) if localTsOut else pd.DataFrame(columns=localTsColumns)
    dfOverflow = pd.DataFrame(overflowOut) if overflowOut else pd.DataFrame(columns=overflowColumns)

    return dfData, dfLocalTs, dfOverflow


def timeCorrection(dfData, dfLocalTs, sleepOverhead, firstSyncEpoch):
    """
    Calculates a regression based on the values in dfLocalTs and adds corrected global timestamps.

    Params:
        dfData: dataframe containing data trace data
        dfLocalTs: dataframe containing local timestamp data
        dfOverflow: dataframe containing overflow data
    Returns:
        dfDataCorr: dataframe with added corrected global timestamps
        dfLocalTsCorr: dataframe with added corrected global timestamps
        dfOverflowCorr: dataframe with added corrected global timestamps
    """
    dfDataCorr = dfData.copy()
    dfLocalTsCorr = dfLocalTs.copy()

    # make sure only local timestamp of which are synchronized are used for regression
    df = dfLocalTsCorr[dfLocalTsCorr.tc == 0]

    x = df['local_ts'].to_numpy(dtype=float)
    y = df['global_ts_uncorrected'].to_numpy(dtype=float) + DT_FIXED_OFFSET

    # calculate intial linear regression
    # FIXME: try out more elaborate regressions (piecewise linear, regression splines), would mainly be useful for high-ppm-clock sources
    slopeUnfiltered, interceptUnfiltered, r_valueUnfiltered, p_valueUnfiltered, std_errUnfiltered = stats.linregress(x, y)
    # print('interceptUnfiltered: {}'.format(interceptUnfiltered))

    residualsUnfiltered = y - (slopeUnfiltered*x + interceptUnfiltered)

    # produce error if residuals are unusually large
    if np.max(np.abs(residualsUnfiltered)) > RESIDUAL_UNFILTERED_THRESHOLD:
        raise Exception('ERROR: time correction: residuals are unusually large ({:.6f}s)! Most likely there is a gap/jump in the datatrace data.'.format(np.max(np.abs(residualsUnfiltered))))

    ## filter outliers (since they have a negative impact on slope of reconstructed globalTs)
    # determine mask of time sync points to keep
    maskFiltered = np.abs(residualsUnfiltered) < 2*np.std(residualsUnfiltered)
    xFiltered = x[maskFiltered]
    yFiltered = y[maskFiltered]
    ratioFiltered = (len(maskFiltered) - np.sum(maskFiltered))/len(maskFiltered)
    # calcualte new regression
    slopeFiltered, interceptFiltered, r_valueFiltered, p_valueFiltered, std_errFiltered = stats.linregress(xFiltered, yFiltered)
    residualsFiltered = yFiltered - (slopeFiltered*xFiltered + interceptFiltered)
    # print('interceptFiltered: {}'.format(interceptFiltered))


    print('INFO: Outlier filtering removed {:0.2f}%'.format(ratioFiltered*100.))
    # print('INFO: Regression before filtering: slope={:0.20f}, intercept={:0.7f}'.format(slopeUnfiltered, interceptUnfiltered))
    # print('INFO: Regression  after filtering: slope={:0.20f}, intercept={:0.7f}'.format(slopeFiltered, interceptFiltered))
    if ratioFiltered > FILTER_THRESHOLD:
        raise Exception('ERROR: Outlier filter filtered away more than {:.0f}% of all time sync points: filtered {:0.2f}%'.format(FILTER_THRESHOLD*100., ratioFiltered*100.))

    # shift regression line to compensate offset (since global timestamps can only be positive)
    offset = 0
    # offset = -2*np.std(residualsFiltered)
    # offset = np.min(residualsFiltered)
    slopeFinal = slopeFiltered
    interceptFinal = interceptFiltered + offset
    residualsFinal = yFiltered - (slopeFinal*xFiltered + interceptFinal)

    # # DEBUG visualize
    # import matplotlib.pyplot as plt
    # plt.close('all')
    # ## regression
    # fig, ax = plt.subplots()
    # ax.scatter(x, y, marker='.', label='Data (uncorrected)', c='r')
    # ax.plot(x, slopeUnfiltered*x + interceptUnfiltered, label='Regression (x->y)', c='b', marker='.')
    # ax.set_title('Regression (unfiltered)')
    # ax.set_xlabel('LocalTs')
    # ax.set_ylabel('GlobalTs')
    # ax.legend()
    # ## residuals (before outlier filtering)
    # fig, ax = plt.subplots()
    # ax.plot(x, residualsUnfiltered, label='Residual', c='b', marker='.')
    # ax.axhline(y=0, xmin=0, xmax=x[-1], linestyle='--', c='k')
    # # ax.plot(x, pd.DataFrame(residualsUnfiltered).rolling(100, center=True, min_periods=1).mean().to_numpy(), label='Residual (moving avg)', c='orange', marker='.')
    # ax.set_title('Residuals (before outlier filtering)')
    # ax.set_xlabel('LocalTs')
    # ax.set_ylabel('Diff [s]')
    # ax.legend()
    # ## residuals (after outlier filtering)
    # fig, ax = plt.subplots()
    # ax.plot(xFiltered, residualsFiltered, label='Residual', c='b', marker='.')
    # ax.axhline(y=0, xmin=0, xmax=x[-1], linestyle='--', c='k')
    # # ax.plot(x, pd.DataFrame(residualsFiltered).rolling(100, center=True, min_periods=1).mean().to_numpy(), label='Residual (moving avg)', c='orange', marker='.')
    # ax.set_title('Residuals (after outlier filtering)')
    # ax.set_xlabel('LocalTs')
    # ax.set_ylabel('Diff [s]')
    # ax.legend()
    # ## residuals (after offset correction)
    # fig, ax = plt.subplots()
    # ax.plot(xFiltered, residualsFinal, label='Residual', c='b', marker='.')
    # ax.axhline(y=0, xmin=0, xmax=x[-1], linestyle='--', c='k')
    # # ax.plot(x, pd.DataFrame(residualsFiltered).rolling(100, center=True, min_periods=1).mean().to_numpy(), label='Residual (moving avg)', c='orange', marker='.')
    # ax.set_title('Residuals (after offset correction)')
    # ax.set_xlabel('LocalTs')
    # ax.set_ylabel('Diff')
    # ax.legend()
    # # residuals hist (before outlier filtering)
    # fig, ax = plt.subplots()
    # ax.hist(residualsUnfiltered, 50)
    # # ax.axvline(y=0, xmin=0, xmax=x[-1], linestyle='--', c='k')
    # # ax.plot(x, pd.DataFrame(residualsFiltered).rolling(100, center=True, min_periods=1).mean().to_numpy(), label='Residual (moving avg)', c='orange', marker='.')
    # ax.set_title('Residuals Histogram (before outlier filtering)')
    # ax.set_xlabel('Diff [s]')
    # ax.set_ylabel('Count')
    # # residuals hist (after offset correction)
    # fig, ax = plt.subplots()
    # ax.hist(residualsFinal, 50)
    # # ax.axvline(y=0, xmin=0, xmax=x[-1], linestyle='--', c='k')
    # # ax.plot(x, pd.DataFrame(residualsFiltered).rolling(100, center=True, min_periods=1).mean().to_numpy(), label='Residual (moving avg)', c='orange', marker='.')
    # ax.set_title('Residuals Histogram (after offset correction)')
    # ax.set_xlabel('Diff [s]')
    # ax.set_ylabel('Count')

    # add platform (linux version) dependent correction offset
    # measured sleepOverhead is used to identify platform
    platformCorrection = PLATFORM_CORRECTION_OFFSET if sleepOverhead > 0.263e-3 else 0

    # add corrected timestamps to dataframe
    dfDataCorr['global_ts'] = dfDataCorr.local_ts * slopeFinal + interceptFinal + platformCorrection
    dfLocalTsCorr['global_ts'] = dfLocalTsCorr.local_ts * slopeFinal + interceptFinal + platformCorrection

    # NOTE: Disabled offset correction based on reset again as it seemed that duration between release of reset pin and start of local timestamp counter is application dependent, i.e. not constant
    # # correct offset of global timestamp using the synchronized release from reset at start of the test on FlockLab 2
    # # NOTE: this only works for the first syncEpoch (epoch begins with start of test on FlockLab 2)
    # if firstSyncEpoch:
    #   df = dfLocalTsCorr[dfLocalTsCorr.tc == 0]
    #   firstSyncPoint = df.iloc[0] # first sync point without delay indicated
    #   startCorr = firstSyncPoint.global_ts - firstSyncPoint.local_ts*slopeFinal
    #   startActual = int(startCorr) # FlockLab 2 makes sure that test is started (i.e. reset is released) exactly when new second starts
    #   offsetReset = startCorr - startActual
    #   # DEBUG
    #   print('INFO: offset (based on initial reset): {}'.format(offsetReset))

    #   dfDataCorr['global_ts'] = dfDataCorr.global_ts - offsetReset + DT_FIXED_OFFSET_RESET
    #   dfLocalTsCorr['global_ts'] = dfLocalTsCorr.global_ts - offsetReset + DT_FIXED_OFFSET_RESET

    return dfDataCorr, dfLocalTsCorr


################################################################################
# UTILS
################################################################################
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

################################################################################
# MAIN
################################################################################
if __name__ == '__main__':
    obsid = 7
    nodeid = 7

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        # parse the file
        # first line of the log file contains the variable names
        varnames = ""
        with open(filename, "r") as f:
            varnames = f.readline().strip().split()

        dfData, dfLocalTs, dfOverflow = processDatatraceOutput(filename)

        dfData['obsid'] = obsid
        dfData['nodeid'] = nodeid
        # convert comparator ID to variable name
        dfData['varname'] = dfData.comparator.apply(lambda x: (varnames[x] if x < len(varnames) else str(x)))
        # df_corrected.sort_values(by=['global_ts'], inplace=True)
        with open(filename + '.csv', "w") as outfile:
            dfData.to_csv(
                outfile,
                columns=['global_ts', 'obsid', 'nodeid', 'varname', 'data', 'operation', 'PC', 'local_ts_tc'],
                index=False,
                header=True,
            )
