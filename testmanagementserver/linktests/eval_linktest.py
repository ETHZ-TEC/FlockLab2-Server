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

import sys
import os
import numpy as np
import pandas as pd
import json
from collections import OrderedDict
import pickle

from flocklab import Flocklab
from flocklab import *

fl = Flocklab()

assertionOverride = False
outputdir         = "./data"


################################################################################

# check arguments (either at least one test ID or the path to test results must be specified)
if len(sys.argv) < 2:
    print("no test number or path specified!")
    sys.exit(1)


################################################################################
def getJson(text):
    '''Find an convert json in a single line from serial output. Returns None if no valid json could be found.
    '''
    ret = None
    # find index
    idx = 0
    if not '{' in text:
        return ret
    for i in range(len(text)):
        if text[i] == '{':
            idx = i
            break

    try:
        ret =  json.loads(text[idx:], strict=False)
    except json.JSONDecodeError:
        print('WARNING: json could not be parsed: {}'.format(text[idx:]))
    return ret

def getRows(roundNo, gDf):
    '''Extract rows for requested round from gDf
    '''
    inRange = False
    ret = []
    for d in gDf.data.to_list():
        if d['type'] == 'StartOfRound':
            if d['node'] == roundNo:
                inRange = True
        elif d['type'] == 'EndOfRound':
            if d['node'] == roundNo:
                break
        elif inRange:
            ret.append(d)
    return ret

################################################################################

for arg in sys.argv[1:]:
    seriallog = ""
    testid    = None
    if os.path.isfile(arg) and "serial" in arg:
        seriallog = arg
    elif os.path.isdir(arg):
        seriallog = os.path.join(arg, "serial.csv")
    else:
        try:
            testid = int(arg)
            print('testid: {}'.format(testid))
            seriallog = os.getcwd() + "/{}/serial.csv".format(testid)
        except:
            print("invalid argument %s" % arg)

    if testid:
        # download test results if directory does not exist
        if not os.path.isfile(seriallog):
            fl.getResults(testid)

    if not os.path.isfile(seriallog):
        print("file %s not found" % seriallog)
        continue

    df = fl.serial2Df(seriallog, error='ignore')
    df.sort_values(by=['timestamp', 'observer_id'], inplace=True, ignore_index=True)

    # convert output with valid json to dict and remove other rows
    keepMask = []
    resList = []
    for idx, row in df.iterrows():
        jsonDict = getJson(row['output'])
        keepMask.append(1 if jsonDict else 0)
        if jsonDict:
            resList.append(jsonDict)
    dfd = df[np.asarray(keepMask).astype(bool)].copy()
    dfd['data'] = resList

    # figure our list of nodes available in the serial trace
    nodeList = list(set(dfd.observer_id))
    numNodes = len(nodeList)

    # prepare
    groups = dfd.groupby('observer_id')
    prrMatrix = np.empty( (numNodes, numNodes,) ) * np.nan       # packet reception ratio (PRR)
    crcErrorMatrix = np.empty( (numNodes, numNodes,) ) * np.nan  # ratio of packets with CRC error
    pathlossMatrix = np.empty( (numNodes, numNodes,) ) * np.nan  # path loss

    # Get TestConfig and RadioConfig & check for consistency
    testConfigDict = OrderedDict()
    radioConfigDict = OrderedDict()
    for node in nodeList:
        testConfigFound = False
        radioConfigFound = False
        testConfigDict[node] = None
        radioConfigDict[node] = None
        gDf = groups.get_group(node)
        for d in gDf.data.to_list():
            if d['type'] == 'TestConfig':
                testConfigDict[node] = d
                testConfigFound = True
            if d['type'] == 'RadioConfig':
                radioConfigDict[node] = d
                radioConfigFound = True
            if testConfigFound and radioConfigFound:
                break

    for node in nodeList:
        assert testConfigDict[nodeList[0]] == testConfigDict[node]
        assert radioConfigDict[nodeList[0]] == radioConfigDict[node]

    testConfig = testConfigDict[nodeList[0]]
    radioConfig = radioConfigDict[nodeList[0]]

    # Make sure that round boundaries do not overlap
    if not assertionOverride:
        currentSlot = -1
        for d in dfd.data.to_list():
            if d['type'] == 'StartOfRound':
                node = d['node']
                # print('Start: {}'.format(node))
                assert node >= currentSlot
                if node > currentSlot:
                    currentSlot = node
            elif d['type'] == 'EndOfRound':
                node = d['node']
                # print('End: {}'.format(node))
                assert node >= currentSlot

    # extract statistics (PRR, path loss, ...)
    # iterate over rounds
    for roundIdx, roundNo in enumerate(nodeList):
    # for roundNo in [nodeList[0]]:
        # print('Round: {}'.format(roundNo))
        txNode = roundNo
        txNodeIdx = roundIdx
        numTx = 0
        numRxDict = OrderedDict()
        numCrcErrorDict = OrderedDict()
        rssiAvgDict = OrderedDict()
        # iterate over nodes
        for nodeIdx, node in enumerate(nodeList):
            rows = getRows(roundNo, groups.get_group(node))
            if node == txNode:
    #            print(node)
                txDoneList = [elem for elem in rows if (elem['type']=='TxDone')]
                numTx = len(txDoneList)
    #            print(numTx, testConfig['numTx'])
                assert numTx == testConfig['numTx']
            else:
                rxDoneList = [elem for elem in rows if (elem['type']=='RxDone' and elem['key']==testConfig['key'] and elem['crc_error']==0)]
                crcErrorList = [elem for elem in rows if (elem['type']=='RxDone' and elem['crc_error']==1)]
                numRxDict[node] = len(rxDoneList)
                numCrcErrorDict[node] = len(crcErrorList)
                rssiAvgDict[node] = np.mean([elem['rssi'] for elem in rxDoneList]) if len(rxDoneList) else np.nan

        # fill PRR matrix
        for rxNode, numRx in numRxDict.items():
            rxNodeIdx = nodeList.index(rxNode)
            prrMatrix[txNodeIdx][rxNodeIdx] = numRx/numTx

        # fill CRC error matrix
        for rxNode, numCrcError in numCrcErrorDict.items():
            rxNodeIdx = nodeList.index(rxNode)
            crcErrorMatrix[txNodeIdx][rxNodeIdx] = numCrcError/numTx
        # NOTE: some CRC error cases are ignored while getting the rows (getRows()) because the json parser cannot parse the RxDone output

        # fill path loss matrix
        for rxNode, rssi in rssiAvgDict.items():
            rxNodeIdx = nodeList.index(rxNode)
            pathlossMatrix[txNodeIdx][rxNodeIdx] = -(rssi - radioConfig['txPower'])

    prrMatrixDf = pd.DataFrame(data=prrMatrix, index=nodeList, columns=nodeList)
    crcErrorMatrixDf = pd.DataFrame(data=crcErrorMatrix, index=nodeList, columns=nodeList)
    pathlossMatrixDf = pd.DataFrame(data=pathlossMatrix, index=nodeList, columns=nodeList)

    # save obtained data to file (including nodeList to resolve idx <-> node ID relations)
    if testid:
        pklPath = '{}/linktest_data_{}.pkl'.format(outputdir, testid)
    else:
        pklPath = '{}/linktest_data.pkl'.format(outputdir)
    os.makedirs(os.path.split(pklPath)[0], exist_ok=True)
    with open(pklPath, 'wb' ) as f:
        d = {
            'testConfig': testConfig,
            'radioConfig': radioConfig,
            'nodeList': nodeList,
            'prrMatrix': prrMatrix,
            'crcErrorMatrix': crcErrorMatrix,
            'pathlossMatrix': pathlossMatrix,
        }
        pickle.dump(d, f)

    # save colored tables to html
    html_template = '''
    <table>
      <tr>
        <th><br />Radio Config</th>
      </tr>
      <tr>
        <td>{config}</td>
      </tr>
      <tr>
        <th><br />Pathloss Matrix [dB]</th>
      </tr>
      <tr>
        <td>{pathloss_html}</td>
      </tr>
      <tr>
        <td> </td>
      </tr>
      <tr>
        <th><br />PRR Matrix</th>
      </tr>
      <tr>
        <td>{prr_html}</td>
      </tr>
      <tr>
        <th><br />CRC Error Matrix</th>
      </tr>
      <tr>
        <td>{crc_error_html}</td>
      </tr>
    </table>
    '''

    pathlossMatrixDf_styled = (pathlossMatrixDf.style
      .background_gradient(cmap='summer', axis=None)
      .applymap(lambda x: 'background: white' if pd.isnull(x) else '')
      .format("{:.0f}")
    )
    pathloss_html = pathlossMatrixDf_styled.render().replace('nan','')

    prrMatrixDf_styled = (prrMatrixDf.style
      .background_gradient(cmap='inferno', axis=None)
      .format("{:.1f}")
    )
    prr_html = prrMatrixDf_styled.render()

    crcErrorMatrixDf_styled = (crcErrorMatrixDf.style
      .background_gradient(cmap='YlGnBu', axis=None)
      .format("{:.1f}")
    )
    crc_error_html = crcErrorMatrixDf_styled.render()

    if testid:
        htmlPath = '{}/linktest_map_{}.html'.format(outputdir, testid)
    else:
        htmlPath = '{}/linktest_map.html'.format(outputdir)
    os.makedirs(os.path.split(htmlPath)[0], exist_ok=True)
    with open(htmlPath,"w") as fp:
       fp.write(html_template.format(
               pathloss_html=pathloss_html,
               prr_html=prr_html,
               crc_error_html=crc_error_html,
               config='Frequency: %.3fMHz, TX power: %ddBm, modulation: %d, datarate: %d, bandwidth: %d, coderate: %d' % (radioConfig['frequency'] / 1000000.0, radioConfig['txPower'], radioConfig['modulation'], radioConfig['datarate'], radioConfig['bandwidth'], radioConfig['coderate'])
           )
       )

    print("results saved in %s" % os.path.realpath(outputdir))
