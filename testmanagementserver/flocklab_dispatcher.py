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

import sys, os, getopt, errno, threading, shutil, time, datetime, subprocess, tempfile, queue, re, logging, traceback, __main__, types, hashlib, lxml.etree, MySQLdb, signal
import lib.flocklab as flocklab
import flocklab as fltools


logger = None
debug  = False
abort  = False


##############################################################################
#
# sigterm_handler
#
##############################################################################
def sigterm_handler(signum, frame):
    global abort
    logger.info("Process received SIGTERM signal.")
    abort = True
### END sigterm_handler


##############################################################################
#
# StopTestThread
#
##############################################################################
class StopTestThread(threading.Thread):
    """    Thread which calls the test stop script on an observer. 
    """ 
    def __init__(self, obskey, obsdict_key, errors_queue, testid):
        threading.Thread.__init__(self) 
        self._obskey        = obskey
        self._obsdict_key   = obsdict_key
        self._errors_queue  = errors_queue
        self._abortEvent    = threading.Event()
        self._testid        = testid
        
    def run(self):
        try:
            logger.debug("Start StopTestThread for observer ID %d" % (self._obsdict_key[self._obskey][1]))
            errors = []
            starttime = time.time()
            # First test if the observer is online and if the SD card is mounted: 
            cmd = ['ssh', '%s' % (self._obsdict_key[self._obskey][2]), "mount | grep /dev/mmcblk0p1"]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            while p.returncode == None:
                self._abortEvent.wait(1.0)
                p.poll()
            if self._abortEvent.is_set():
                p.kill()
            else:
                out, err = p.communicate()
            rs = p.returncode
            if (rs != 0):
                if (rs == 1):
                    if ("No such file or directory" in err):
                        msg = "SD card on observer ID %s is not mounted, observer will thus be omitted for this test." % (self._obsdict_key[self._obskey][1])
                    else:
                        msg = "Observer ID %s is not reachable (returned %d: %s, %s)." % (self._obsdict_key[self._obskey][1], rs, out, err)
                else:
                    msg = "Observer ID %s is not responsive (SSH returned %d)." % (self._obsdict_key[self._obskey][1], rs)
                errors.append((msg, errno.EHOSTUNREACH, self._obsdict_key[self._obskey][1]))
                logger.error(msg)
            else:
                # Call the script on the observer which stops the test:
                remote_cmd = flocklab.config.get("observer", "stoptestscript") + " --testid=%d" % self._testid
                if debug:
                    remote_cmd += " --debug"
                cmd = ['ssh' ,'%s' % (self._obsdict_key[self._obskey][2]), remote_cmd]
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                while p.returncode == None:
                    self._abortEvent.wait(1.0)
                    p.poll()
                if self._abortEvent.is_set():
                    p.kill()
                else:
                    out, err = p.communicate()
                rs = p.returncode
                if (rs == flocklab.SUCCESS):
                    logger.debug("Test stop script on observer ID %s succeeded (took %us)." % (self._obsdict_key[self._obskey][1], int(time.time() - starttime)))
                elif (rs == 255):
                    msg = "Observer ID %s is not reachable, thus not able to stop test. Dataloss occurred possibly for this observer." % (self._obsdict_key[self._obskey][1])
                    errors.append((msg, errno.EHOSTUNREACH, self._obsdict_key[self._obskey][1]))
                    logger.error(msg)
                else:
                    errors.append(("Test stop script on observer ID %s failed with error code %d." % (str(self._obsdict_key[self._obskey][1]), rs), rs, self._obsdict_key[self._obskey][1]))
                    logger.error("Test stop script on observer ID %s failed with error code %d:\n%s" % (str(self._obsdict_key[self._obskey][1]), rs, str(err).strip()))
                    logger.error("Tried to execute: %s" % (" ".join(cmd)))
        except:
            logger.debug("Exception: %s, %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
            # Main thread requested abort.
            # Close a possibly still running subprocess:
            if (p is not None) and (p.poll() is not None):
                p.kill()
            msg = "StopTestThread for observer ID %d aborted." % (self._obsdict_key[self._obskey][1])
            errors.append((msg, errno.ECOMM, self._obsdict_key[self._obskey][1]))
            logger.error(msg)
        finally:
            if (len(errors) > 0):
                self._errors_queue.put((self._obskey, errors))
            
    def abort(self):
        self._abortEvent.set()
### END StopTestThread



##############################################################################
#
# StartTestThread
#
##############################################################################
class StartTestThread(threading.Thread):
    """    Thread which uploads all config files to an observer and
        starts the test on the observer. 
    """ 
    def __init__(self, obskey, obsdict_key, xmldict_key, imagedict_key, errors_queue, testid, serialproxy):
        threading.Thread.__init__(self) 
        self._obskey        = obskey
        self._obsdict_key   = obsdict_key
        self._xmldict_key   = xmldict_key
        self._imagedict_key = imagedict_key
        self._errors_queue  = errors_queue
        self._abortEvent    = threading.Event()
        self._testid        = testid
        self._serialproxy   = serialproxy
        
    def run(self):
        errors = []
        testconfigfolder = "%s/%d" % (flocklab.config.get("observer", "testconfigfolder"), self._testid)
        obsdataport      = flocklab.config.getint('serialproxy', 'obsdataport')
        starttime        = time.time()
        try:
            logger.debug("Start StartTestThread for observer ID %d" % (self._obsdict_key[self._obskey][1]))
            # First test if the observer is online and if the SD card is mounted: 
            cmd = ['ssh', '%s' % (self._obsdict_key[self._obskey][2]), "ls ~/data/ && mkdir %s" % testconfigfolder]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            while p.returncode == None:
                self._abortEvent.wait(1.0)
                p.poll()
            if self._abortEvent.is_set():
                p.kill()
            else:
                out, err = p.communicate()
            rs = p.returncode
            if (rs != 0):
                if (rs == 1):
                    if ("No such file or directory" in err):
                        msg = "SD card on observer ID %s is not mounted, observer will thus be omitted for this test." % (self._obsdict_key[self._obskey][1])
                    else:
                        msg = "Observer ID %s is not reachable, it will thus be omitted for this test (returned: %d: %s, %s)." % (self._obsdict_key[self._obskey][1], rs, out, err)
                else:
                    msg = "Observer ID %s is not responsive, it will thus be omitted for this test (SSH returned %d). Command: %s" % (self._obsdict_key[self._obskey][1], rs, " ".join(cmd))
                errors.append((msg, errno.EHOSTUNREACH, self._obsdict_key[self._obskey][1]))
                logger.error(msg)
            else:
                fileuploadlist = [self._xmldict_key[self._obskey][0]]
                if self._obskey in list(self._imagedict_key.keys()):
                    for image in self._imagedict_key[self._obskey]:
                        fileuploadlist.append(image[0])
                # Now upload the image and XML config file:
                cmd = ['scp', '-q']
                cmd.extend(fileuploadlist)
                cmd.append('%s:%s/.' % (self._obsdict_key[self._obskey][2], testconfigfolder))
                p = subprocess.Popen(cmd)
                while p.returncode == None:
                    self._abortEvent.wait(1.0)
                    p.poll()
                if self._abortEvent.is_set():
                    p.kill()
                rs = p.returncode
                if (rs != flocklab.SUCCESS):
                    msg = "Upload of target image and config XML to observer ID %s failed with error number %d\nTried to execute: %s" % (self._obsdict_key[self._obskey][1], rs, (" ".join(cmd)))
                    errors.append((msg, rs, self._obsdict_key[self._obskey][1]))
                    logger.error(msg)
                else:
                    logger.debug("Upload of target image and config XML to observer ID %s succeeded." % (self._obsdict_key[self._obskey][1]))
                    # Run the script on the observer which starts the test:
                    remote_cmd = flocklab.config.get("observer", "starttestscript") + " --testid=%d --xml=%s/%s" % (self._testid, testconfigfolder, os.path.basename(self._xmldict_key[self._obskey][0]))
                    if self._serialproxy:
                        remote_cmd += " --serialport=%d" % (obsdataport)
                    if debug:
                        remote_cmd += " --debug"
                    cmd = ['ssh', '%s' % (self._obsdict_key[self._obskey][2]), remote_cmd]
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                    while p.returncode == None:
                        self._abortEvent.wait(1.0)
                        p.poll()
                    out = ""
                    if self._abortEvent.is_set():
                        p.kill()
                        logger.debug("Abort is set, start test process for observer %s killed." % (self._obsdict_key[self._obskey][1]))
                    else:
                        out, err = p.communicate()
                    rs = p.wait()
                    if rs != flocklab.SUCCESS:
                        errors.append(("Test start script on observer ID %s failed with error code %d." % (self._obsdict_key[self._obskey][1], rs), rs, self._obsdict_key[self._obskey][1]))
                        logger.error("Test start script on observer ID %s failed with error code %d:\n%s" % (str(self._obsdict_key[self._obskey][1]), rs, str(err)))
                    else:
                        logger.debug("Test start script on observer ID %s succeeded (took %us)." % (self._obsdict_key[self._obskey][1], int(time.time() - starttime)))
                    # Remove image file and xml on server:
                    os.remove(self._xmldict_key[self._obskey][0])
                    logger.debug("Removed XML config %s for observer ID %s" % (self._xmldict_key[self._obskey][0], self._obsdict_key[self._obskey][1]))
                    if self._obskey in list(self._imagedict_key.keys()):
                        for image in self._imagedict_key[self._obskey]:
                            os.remove(image[0])
                            logger.debug("Removed target image %s for observer ID %s" % (self._imagedict_key[self._obskey][0], self._obsdict_key[self._obskey][1]))
            
        except:
            logger.debug("Exception: %s, %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
            # Main thread requested abort.
            # Close a possibly still running subprocess:
            if (p is not None) and (p.poll() is not None):
                p.kill()
            msg = "StartTestThread for observer ID %d aborted." % (self._obsdict_key[self._obskey][1])
            errors.append((msg, errno.ECOMM, self._obsdict_key[self._obskey][1]))
            logger.error(msg)
        finally:
            if (len(errors) > 0):
                self._errors_queue.put((self._obskey, errors))
        
    def abort(self):
        self._abortEvent.set()
    
### END StartTestThread



##############################################################################
#
# start_test
#
##############################################################################
def start_test(testid, cur, cn, obsdict_key, obsdict_id):
    errors = []
    warnings = []
    
    try:    
        logger.debug("Entering start_test() function...")
        # First, validate the XML file again. If validation fails, return immediately:
        cmd = [flocklab.config.get('dispatcher','validationscript'), '--testid=%d' % testid]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, err = p.communicate()
        rs = p.returncode
        if rs != 0:
            logger.error("Error %s returned from %s" % (str(rs), flocklab.config.get('dispatcher','validationscript')))
            logger.error("Tried to execute: %s" % (" ".join(cmd)))
            msg = "Validation of XML failed. Output of script was: %s %s" % (str(out), str(err))
            logger.error(msg)
            errors.append(msg)
        
        if len(errors) == 0:
            # Update DB status ---
            # Update the status of the test in the db:
            flocklab.set_test_status(cur, cn, testid, 'preparing')
            
            # Get start/stop time ---
            cur.execute("SELECT `time_start_wish`, `time_end_wish`, `owner_fk` FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d" %testid)
            # Times are going to be of datetime type:
            ret = cur.fetchone()
            starttime = ret[0]
            stoptime  = ret[1]
            owner_fk = ret[2]
            logger.debug("Got start time wish for test from database: %s" % starttime)
            logger.debug("Got end time wish for test from database: %s" % stoptime)
            
            # Check whether datatrace debug feature is used
            datatrace_used = False
            cur.execute("SELECT serv_tests_key FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s) AND (`testconfig_xml` LIKE '%%<dataTraceConf>%%')" % testid)
            ret = cur.fetchone()
            if ret:
                datatrace_used = True
                logger.debug("Use of data trace detected.")
            
            # Image processing ---
            # Get all images from the database:
            imagedict_key = {}
            symtable = {}
            sql_image =     """ SELECT `t`.`binary`, `m`.`observer_fk`, `m`.`node_id`, LOWER(`a`.`architecture`), `t`.`serv_targetimages_key`, LOWER(`p`.`name`) AS `platname`, `a`.`core` AS `core`
                                FROM `tbl_serv_targetimages` AS `t` 
                                LEFT JOIN `tbl_serv_map_test_observer_targetimages` AS `m` 
                                    ON `t`.`serv_targetimages_key` = `m`.`targetimage_fk` 
                                LEFT JOIN `tbl_serv_platforms` AS `p`
                                    ON `t`.`platforms_fk` = `p`.`serv_platforms_key`
                                LEFT JOIN `tbl_serv_architectures` AS `a`
                                    ON `t`.`core` = `a`.`core` AND `p`.`serv_platforms_key` = `a`.`platforms_fk`
                                WHERE `m`.`test_fk` = %d
                            """
            cur.execute(sql_image%testid)
            ret = cur.fetchall()
            for r in ret:
                binary      = r[0]
                obs_fk      = r[1]
                obs_id      = obsdict_key[obs_fk][1]
                node_id     = r[2]
                arch        = r[3]
                tgimage_key = r[4]
                platname    = r[5]
                core        = r[6]
                
                # Prepare image ---
                (fd, imagepath) = tempfile.mkstemp()
                binpath = "%s.hex" % (os.path.splitext(imagepath)[0])
                
                # First, check if image is already in hex format ---
                if flocklab.is_hex_file(data=binary):
                    f = open(binpath, "wb")
                    f.write(binary)
                    f.close()
                else:
                    imagefile = os.fdopen(fd, 'w+b')
                    imagefile.write(binary)
                    imagefile.close()
                    logger.debug("Got target image ID %s for observer ID %s with node ID %s from database and wrote it to temp file %s (hash %s)" % (str(tgimage_key), str(obs_id), str(node_id), imagepath, hashlib.sha1(binary).hexdigest()))
                    
                    logger.debug("Found %s target architecture on platform %s for observer ID %s (node ID to be used: %s)." % (arch, platname, str(obs_id), str(node_id)))
                    
                    # get symbols table if necessary
                    if datatrace_used and not obs_id in symtable:    # allow only one entry per observer
                        symtable[obs_id] = flocklab.extract_variables_from_symtable(flocklab.get_symtable_from_binary(imagepath))
                    
                    # binary patching
                    if (node_id != None):
                        # set node ID
                        if flocklab.patch_binary("FLOCKLAB_NODE_ID", node_id, imagepath, arch) != flocklab.SUCCESS:
                            msg = "Failed to patch symbol FLOCKLAB_NODE_ID in binary file %s." % (imagepath)
                            errors.append(msg)
                            logger.error(msg)
                        if flocklab.patch_binary("TOS_NODE_ID", node_id, imagepath, arch) != flocklab.SUCCESS:
                            msg = "Failed to patch symbol TOS_NODE_ID in binary file %s." % (imagepath)
                            errors.append(msg)
                            logger.error(msg)
                    # convert elf to intel hex
                    if flocklab.bin_to_hex(imagepath, arch, binpath) != flocklab.SUCCESS:
                        msg = "Failed to convert image file %s to Intel hex format." % (imagepath)
                        errors.append(msg)
                        logger.error(msg)
                        shutil.move(imagepath, binpath)
                        logger.debug("Copied binary file without modification.")
                
                # Remove the original file which is not used anymore:
                if os.path.exists(imagepath):
                    os.remove(imagepath)
                
                # Slot detection ---
                # Find out which slot number to use on the observer.
                #logger.debug("Detecting adapter for %s on observer ID %s" %(platname, obs_id))
                ret = flocklab.get_slot(cur, int(obs_fk), platname)
                if ret in range(1,5):
                    slot = ret
                    logger.debug("Found adapter for %s on observer ID %s in slot %d" % (platname, obs_id, slot))
                elif ret == 0:
                    slot = None
                    msg = "Could not find an adapter for %s on observer ID %s" % (platname, obs_id)
                    errors.append(msg)
                    logger.error(msg)
                else:
                    slot = None
                    msg = "Error when detecting adapter for %s on observer ID %s: function returned %d" % (platname, obs_id, ret)
                    errors.append(msg)
                    logger.error(msg)
                
                # Write the dictionary for the image:
                if not obs_fk in imagedict_key:
                    imagedict_key[obs_fk] = []
                imagedict_key[obs_fk].append((binpath, slot, platname, core))
                
            logger.info("Processed all target images from database.")
                
            # XML processing ---
            # Get the XML config from the database and generate a separate file for every observer used:
            cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" % testid)
            ret = cur.fetchone()
            if not ret:
                msg = "No XML found in database for testid %d." %testid
                errors.append(msg)
                logger.error(msg)
            else:
                parser = lxml.etree.XMLParser(remove_comments=True)
                tree = lxml.etree.fromstring(bytes(bytearray(ret[0], encoding = 'utf-8')), parser)
                ns = {'d': flocklab.config.get('xml', 'namespace')}
                logger.debug("Got XML from database.")
                # Create XML files for observers ---
                # Create an empty XML config file for every observer used and organize them in a dictionary:
                xmldict_key = {}
                for obs_key, obs_id, obs_ether in obsdict_key.values():
                    (fd, xmlpath) = tempfile.mkstemp()
                    xmlfhand = os.fdopen(fd, 'w+')
                    xmldict_key[obs_key] = (xmlpath, xmlfhand)
                    xmlfhand.write('<?xml version="1.0" encoding="UTF-8"?>\n\n<obsConf>\n\n')
                # Go through the blocks of the XML file and write the configs to the affected observer XML configs:
                # targetConf ---
                targetconfs = tree.xpath('//d:targetConf', namespaces=ns)
                if not targetconfs:
                    msg = "no <targetConf> element found in XML config (wrong namespace?)"
                    errors.append(msg)
                    logger.error(msg)
                for targetconf in targetconfs:
                    obsids = targetconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                    ret = targetconf.xpath('d:voltage', namespaces=ns)
                    if ret:
                        voltage = ret[0].text.strip()
                    else:
                        voltage = str(flocklab.config.get("dispatcher", "default_tg_voltage"))
                    ret = targetconf.xpath('d:noImage', namespaces=ns)
                    if ret:
                        noImageSlot = ret[0].text.strip()
                    else:
                        noImageSlot = None
                    for obsid in obsids:
                        obsid = int(obsid)
                        obskey = obsdict_id[obsid][0]
                        xmldict_key[obskey][1].write("<obsTargetConf>\n")
                        xmldict_key[obskey][1].write("\t<voltage>%s</voltage>\n"%voltage)
                        if noImageSlot:
                            slot = noImageSlot
                            xmldict_key[obskey][1].write("\t<slotnr>%s</slotnr>\n" % (slot))
                        else:
                            for coreimage in imagedict_key[obskey]:
                                xmldict_key[obskey][1].write("\t<image core=\"%d\">%s/%d/%s</image>\n" % (coreimage[3], flocklab.config.get("observer", "testconfigfolder"),testid, os.path.basename(coreimage[0])))
                            xmldict_key[obskey][1].write("\t<slotnr>%s</slotnr>\n" % (imagedict_key[obskey][0][1]))
                            xmldict_key[obskey][1].write("\t<platform>%s</platform>\n" % (imagedict_key[obskey][0][2]))
                            xmldict_key[obskey][1].write("\t<os>%s</os>\n" % (imagedict_key[obskey][0][2]))
                            slot = imagedict_key[obskey][0][1]
                        xmldict_key[obskey][1].write("</obsTargetConf>\n\n")
                        #logger.debug("Wrote obsTargetConf XML for observer ID %s" %obsid)
                        # update test_image mapping with slot information
                        cur.execute("UPDATE `tbl_serv_map_test_observer_targetimages` SET `slot` = %s WHERE `observer_fk` = %d AND `test_fk`=%d" % (slot, obskey, testid))
                        cn.commit()
                
                # serialConf ---
                srconfs = tree.xpath('//d:serialConf', namespaces=ns)
                serialProxyUsed = False
                if srconfs:
                    # only use serialproxy if remote IP specified in xml
                    if tree.xpath('//d:serialConf/d:remoteIp', namespaces=ns):
                        serialProxyUsed = True
                    for srconf in srconfs:
                        obsids = srconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                        xmlblock = "<obsSerialConf>\n"
                        port = srconf.xpath('d:port', namespaces=ns)
                        if port:
                            port = port[0].text.strip()
                            xmlblock += "\t<port>%s</port>\n" % port
                        baudrate = srconf.xpath('d:baudrate', namespaces=ns)
                        if baudrate:
                            baudrate = baudrate[0].text.strip()
                            xmlblock += "\t<baudrate>%s</baudrate>\n" % baudrate
                        cpuspeed = srconf.xpath('d:cpuSpeed', namespaces=ns)
                        if cpuspeed:
                            cpuspeed = cpuspeed[0].text.strip()
                            xmlblock += "\t<cpuSpeed>%s</cpuSpeed>\n" % cpuspeed
                        xmlblock += "</obsSerialConf>\n\n"
                        for obsid in obsids:
                            obsid = int(obsid)
                            obskey = obsdict_id[obsid][0]
                            xmldict_key[obskey][1].write(xmlblock)
                else:
                    logger.debug("No <serialConf> found, not using serial service.")
                
                # debugConf ---
                dbgconfs = tree.xpath('//d:debugConf', namespaces=ns)
                if dbgconfs:
                    for dbgconf in dbgconfs:
                        obsids = dbgconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                        xmlblock = "<obsDebugConf>\n"
                        remoteIp = dbgconf.xpath('d:remoteIp', namespaces=ns)
                        if remoteIp:
                            remoteIp = remoteIp[0].text.strip()
                            xmlblock += "\t<remoteIp>%s</remoteIp>\n" % (remoteIp)
                        cpuSpeed = dbgconf.xpath('d:cpuSpeed', namespaces=ns)
                        if cpuSpeed:
                            cpuSpeed = cpuSpeed[0].text.strip()
                            xmlblock += "\t<cpuSpeed>%s</cpuSpeed>\n" % (cpuSpeed)
                        gdbPort = dbgconf.xpath('d:gdbPort', namespaces=ns)
                        if gdbPort:
                            gdbPort = gdbPort[0].text.strip()
                            xmlblock += "\t<gdbPort>%s</gdbPort>\n" % (gdbPort)
                        dwtconfs = dbgconf.xpath('d:dataTraceConf', namespaces=ns)
                        for dwtconf in dwtconfs:
                            var  = dwtconf.xpath('d:variable', namespaces=ns)[0].text.strip()
                            # check if variable field already contains an address
                            if var.startswith("0x"):
                                varaddr = var
                            else:
                                # convert variable name to address
                                obskey = int(float(obsids[0]))
                                if obskey in symtable:
                                    if var in symtable[obskey]:
                                        logger.debug("Variable %s replaced by address 0x%x." % (var, symtable[obskey][var][0]))
                                        varaddr = "0x%x" % symtable[obskey][var][0]
                                    else:
                                        logger.warning("Variable %s not found in symbol table." % var)
                                        continue
                                else:
                                    logger.warning("Key %u not found in symbol table." % (obskey))
                                    continue
                            mode = dwtconf.xpath('d:mode', namespaces=ns)
                            if mode:
                                mode = mode[0].text.strip()
                            else:
                                mode = 'W'    # use default
                            size = dwtconf.xpath('d:size', namespaces=ns)
                            if size:
                                size = size[0].text.strip()
                            else:
                                size = 4
                            xmlblock += "\t<dataTraceConf>\n\t\t<variable>%s</variable>\n\t\t<varName>%s</varName>\n\t\t<mode>%s</mode>\n\t\t<size>%d</size>\n\t</dataTraceConf>\n" % (varaddr, var, mode, size)
                        xmlblock += "</obsDebugConf>\n\n"
                        for obsid in obsids:
                            obsid = int(obsid)
                            obskey = obsdict_id[obsid][0]
                            xmldict_key[obskey][1].write(xmlblock)
                else:
                    logger.debug("No <debugConf> found, not using debug service.")
                
                # gpioTracingConf ---
                gmconfs = tree.xpath('//d:gpioTracingConf', namespaces=ns)
                if gmconfs:
                    for gmconf in gmconfs:
                        obsids = gmconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                        pinlist = gmconf.xpath('d:pins', namespaces=ns)
                        offset = gmconf.xpath('d:offset', namespaces=ns)
                        xmlblock = "<obsGpioMonitorConf>\n"
                        if pinlist:
                            xmlblock += "\t<pins>" + pinlist[0].text.strip() + "</pins>\n"
                        if offset:
                            xmlblock += "\t<offset>" + offset[0].text.strip() + "</offset>\n"
                        xmlblock += "</obsGpioMonitorConf>\n\n"
                        for obsid in obsids:
                            obsid = int(obsid)
                            obskey = obsdict_id[obsid][0]
                            xmldict_key[obskey][1].write(xmlblock)
                else:
                    logger.debug("No <gpioTracingConf> found, not using GPIO tracing service.")
                
                # gpioActuationConf ---
                # Create 2 pin settings for every observer used in the test:
                #   1) Pull reset pin of target high when test is to start
                #   2) Pull reset pin of target low when test is to stop
                xmlblock = "<obsGpioSettingConf>\n"
                startdatetime = starttime.replace(tzinfo=datetime.timezone.utc).timestamp()      #.strftime(flocklab.config.get("observer", "timeformat"))
                xmlblock += "\t<pinConf>\n\t\t<pin>RST</pin>\n\t\t<level>high</level>\n\t\t<timestamp>%s</timestamp>\n\t</pinConf>\n" % (startdatetime)
                stopdatetime = stoptime.replace(tzinfo=datetime.timezone.utc).timestamp()        #.strftime(flocklab.config.get("observer", "timeformat"))
                xmlblock += "\t<pinConf>\n\t\t<pin>RST</pin>\n\t\t<level>low</level>\n\t\t<timestamp>%s</timestamp>\n\t</pinConf>\n" % (stopdatetime)
                for obskey in obsdict_key.keys():
                    xmldict_key[obskey][1].write(xmlblock)
                # Now write the per-observer config:
                gsconfs = tree.xpath('//d:gpioActuationConf', namespaces=ns)
                for gsconf in gsconfs:
                    xmlblock = ""
                    obsids = gsconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                    pinconfs = gsconf.xpath('d:pinConf', namespaces=ns)
                    for pinconf in pinconfs:
                        pin  = pinconf.xpath('d:pin', namespaces=ns)[0].text.strip()
                        level = pinconf.xpath('d:level', namespaces=ns)[0].text.strip()
                        ofs = pinconf.xpath('d:offset', namespaces=ns)[0].text.strip()
                        count = pinconf.xpath('d:count', namespaces=ns)
                        if count:
                            count = int(count[0].text.strip())
                        else:
                            count = 1
                        period = pinconf.xpath('d:period', namespaces=ns)
                        if period:
                            period = float(period[0].text.strip())
                            # periodic toggling
                            xmlblock += "\t<pinConf>\n\t\t<pin>%s</pin>\n\t\t<level>toggle</level>\n\t\t<offset>%s</offset>\n\t\t<period>%f</period>\n\t\t<count>%d</count>\n\t</pinConf>\n" % (pin, ofs, period, count)
                        else:
                            xmlblock += "\t<pinConf>\n\t\t<pin>%s</pin>\n\t\t<level>%s</level>\n\t\t<offset>%s</offset>\n\t</pinConf>\n" % (pin, level, ofs)
                    for obsid in obsids:
                        obsid = int(obsid)
                        obskey = obsdict_id[obsid][0]
                        xmldict_key[obskey][1].write(xmlblock)
                xmlblock = "</obsGpioSettingConf>\n\n"
                for obskey in obsdict_key.keys():
                    xmldict_key[obskey][1].write(xmlblock)
                
                # powerProfilingConf ---
                ppconfs = tree.xpath('//d:powerProfilingConf', namespaces=ns)
                if ppconfs:
                    for ppconf in ppconfs:
                        obsids = ppconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                        xmlblock = "<obsPowerprofConf>\n"
                        duration = ppconf.xpath('d:duration', namespaces=ns)
                        if duration:
                            duration = duration[0].text.strip()
                        else:
                            # if duration not given, run power profiling for the duration of the test
                            duration = (stoptime - starttime).total_seconds()
                            logger.debug("Power profiling duration set to %ds." % (duration))
                        xmlblock += "\t<duration>%s</duration>" % duration
                        # calculate the sampling start
                        offset  = ppconf.xpath('d:offset', namespaces=ns)
                        if offset:
                            offset = int(offset[0].text.strip())
                            tstart = datetime.datetime.timestamp(starttime + datetime.timedelta(seconds=offset))
                        else:
                            tstart = datetime.datetime.timestamp(starttime)
                        xmlblock += "\n\t<starttime>%s</starttime>" % (tstart)
                        # check if config contains samplingRate:
                        samplingrate    = ppconf.xpath('d:samplingRate', namespaces=ns)
                        if samplingrate:
                            samplingrate = samplingrate[0].text.strip()
                            xmlblock += "\n\t<samplingRate>%s</samplingRate>" % samplingrate
                        xmlblock += "\n</obsPowerprofConf>\n\n"
                        for obsid in obsids:
                            obsid = int(obsid)
                            obskey = obsdict_id[obsid][0]
                            xmldict_key[obskey][1].write(xmlblock)
                            #logger.debug("Wrote obsPowerprofConf XML for observer ID %s" %obsid)
                else:
                    logger.debug("No <powerProfilingConf> found, not using power profiling service.")
                 
                logger.debug("Wrote all observer XML configs.")
                
                # Close XML files ---
                for xmlpath, xmlfhand in xmldict_key.values():
                    xmlfhand.write("</obsConf>\n")
                    xmlfhand.close()
                    #logger.debug("Closed observer XML config %s"%xmlpath)
                #logger.debug("Closed all observer XML configs.")
                
        # Upload configs to observers and start test ---
        if len(errors) == 0:
            if not db_register_activity(testid, cur, cn, 'start', iter(obsdict_key.keys())):
                msg = "Could not access all needed observers for testid %d." %testid
                errors.append(msg)
                logger.error(msg)
        if len(errors) == 0:
            # -- START OF CRITICAL SECTION where dispatcher accesses used observers
            # Start a thread for each observer which uploads the config and calls the test start script on the observer
            thread_list = []
            errors_queue = queue.Queue()
            for obskey in obsdict_key.keys():
                thread = StartTestThread(obskey, obsdict_key, xmldict_key, imagedict_key, errors_queue, testid, serialProxyUsed)
                thread_list.append((thread, obskey))
                thread.start()
                #DEBUG logger.debug("Started thread for test start on observer ID %s" %(str(obsdict_key[obskey][1])))
            # Wait for all threads to finish:
            for (thread, obskey) in thread_list:
                # Wait max 75% of the setuptime:
                thread.join(timeout=(flocklab.config.getint('tests','setuptime')*0.75))
                if thread.isAlive():
                    # Timeout occurred. Signal the thread to abort:
                    logger.error("Telling thread for test start on observer ID %s to abort..." % (str(obsdict_key[obskey][1])))
                    thread.abort()
            # Wait again for the aborted threads:
            for (thread, obskey) in thread_list:
                thread.join(timeout=10)
                if thread.isAlive():
                    msg = "Thread for test start on observer ID %s timed out and will be aborted now." % (str(obsdict_key[obskey][1]))
                    errors.append(msg)
                    logger.error(msg)
            # -- END OF CRITICAL SECTION where dispatcher accesses used observers
            db_unregister_activity(testid, cur, cn, 'start')
            
            # Get all errors (if any). Observers which return errors are not regarded as a general error. In this
            # case, the test is just started without the faulty observers if there is at least 1 observer that succeeded:
            obs_error = []
            #if not errors_queue.empty():
                #logger.error("Queue with errors from test start thread is not empty. Getting errors...")
            while not errors_queue.empty():
                errs = errors_queue.get()
                for err in errs[1]:
                    #logger.error("Error from test start thread for observer %s: %s" %(str(err[2]), str(err[0])))
                    obs_error.append(err[2])
                    warnings.append(err[0])
            if len(obs_error) > 0:
                # Abort or continue?
                if not flocklab.config.get("dispatcher", "continue_on_error"):
                    msg = "At least one observer failed to start the test, going to abort..."
                    errors.append(msg)
                    logger.error(msg)
                # Check if there is at least 1 observer which succeeded:
                elif (len(obsdict_id) == len(set(obs_error))):
                    msg = "None of the requested observers could successfully start the test."
                    errors.append(msg)
                    logger.error(msg)
        
        # Start proxy for serial service ---
        if len(errors) == 0:
            if serialProxyUsed:
                # Start serial proxy:
                logger.debug("Starting serial proxy...")
                cmd = [flocklab.config.get("dispatcher", "serialproxyscript"), "--notify"]
                if debug: 
                    cmd.append("--debug")
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                rs = p.wait()
                if (rs != 0):
                    msg = "Serial proxy for test ID %d could not be started (error code %d)." % (testid, rs)
                    errors.append(msg)
                    logger.error(msg)
                    logger.debug("Executed command was: %s" % (str(cmd)))
                else:
                    logger.debug("Started serial proxy.")
    
        # Start fetcher ---
        if len(errors) == 0:
            logger.debug("Starting fetcher...")
            cmd = [flocklab.config.get("dispatcher", "fetcherscript"), "--testid=%d" % testid]
            if debug:
                cmd.append("--debug")
            p = subprocess.Popen(cmd)
            rs = p.wait()
            if rs != 0:
                msg = "Could not start fetcher for test ID %d. Fetcher returned error %d" % (testid, rs)
                errors.append(msg)
                logger.error(msg)
                logger.error("Tried to execute: %s" % (" ".join(cmd)))

        # check if we're still in time ---
        if len(errors) == 0:
            now = time.strftime(flocklab.config.get("database", "timeformat"), time.gmtime(time.time() - 10))     # allow 10s tolerance
            cur.execute("SELECT `serv_tests_key` FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d AND `time_start_wish` <= '%s'" % (testid, now))
            if cur.fetchone() is not None:
                msg = "Setup for test ID %d took too much time." % (testid)
                errors.append(msg)
                logger.error(msg)

        # Update DB status, set start time ---
        if len(errors) == 0:
            logger.debug("Setting test status in DB to running...")
            flocklab.set_test_status(cur, cn, testid, 'running')
            cur.execute("UPDATE `tbl_serv_tests` SET `time_start_act` = `time_start_wish` WHERE `serv_tests_key` = %d" %testid)
            cn.commit()
        else:
            logger.debug("Setting test status in DB to aborting...")
            flocklab.set_test_status(cur, cn, testid, 'aborting')
            cur.execute("UPDATE `tbl_serv_tests` SET `time_start_act` = `time_start_wish`, `time_end_act` = UTC_TIMESTAMP() WHERE `serv_tests_key` = %d" %testid)
            cn.commit()
        logger.debug("At end of start_test(). Returning...")

        return (errors, warnings)
    except Exception:
        msg = "Unexpected error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        logger.error(msg)
        raise
### END start_test()



##############################################################################
#
# stop_test
#
##############################################################################
def stop_test(testid, cur, cn, obsdict_key, obsdict_id, abort=False):
    errors = []
    warnings = []
    
    try:
        logger.info("Stopping test %d..." % testid)
        
        # Update DB status --- 
        if abort:
            status = 'aborting'
        else:
            status = 'cleaning up'
        logger.debug("Setting test status in DB to %s..." % status)
        if flocklab.set_test_status(cur, cn, testid, status) != flocklab.SUCCESS:
            msg = "Failed to set test status in DB."
            errors.append(msg)
            logger.error(msg)
        
        # Stop serial proxy ---
        # Get the XML config from the database and check if the serial service was used in the test:
        cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" % testid)
        ret = cur.fetchone()
        if not ret:
            msg = "No XML found in database for testid %d." % testid
            errors.append(msg)
            logger.error(msg)
        else:
            parser = lxml.etree.XMLParser(remove_comments=True)
            tree = lxml.etree.fromstring(bytes(bytearray(ret[0], encoding = 'utf-8')), parser)
            ns = {'d': flocklab.config.get('xml', 'namespace')}
            logger.debug("Got XML from database.")
            # only stop serialproxy if remote IP specified in xml
            if tree.xpath('//d:serialConf/d:remoteIp', namespaces=ns):
                # Serial service was used. Thus stop the serial proxy:
                logger.debug("Usage of serial service detected. Stopping serial proxy...")
                cmd = [flocklab.config.get("dispatcher", "serialproxyscript"), "--notify"]
                if debug: 
                    cmd.append("--debug")
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                rs = p.wait()
                if (rs != 0):
                    msg = "Serial proxy for test ID %d could not be stopped. Serial proxy returned %d." % (testid, rs)
                    errors.append(msg)
                    logger.error(msg)
                    logger.debug("Executed command was: %s" % (str(cmd)))
                else:
                    logger.debug("Stopped serial proxy.")
        
        # Stop test on observers ---
        if not db_register_activity(testid, cur, cn, 'stop', iter(obsdict_key.keys())):
            msg = "Some observers were occupied while stopping test."
            logger.warning(msg)
            warnings.append(msg)
        # Start a thread for each observer which calls the test stop script on the observer
        logger.info("Stopping test on observers...")
        thread_list = []
        errors_queue = queue.Queue()
        for obskey in obsdict_key.keys():
            thread = StopTestThread(obskey, obsdict_key, errors_queue,testid)
            thread_list.append((thread, obskey))
            thread.start()
            logger.debug("Started thread for test stop on observer ID %s" %(str(obsdict_key[obskey][1])))
        # Wait for all threads to finish:
        for (thread, obskey) in thread_list:
            thread.join(timeout=(flocklab.config.getint('tests','cleanuptime') * 0.75))
            if thread.isAlive():
                # Timeout occurred. Signal the thread to abort:
                msg = "Telling thread for test stop on observer ID %s to abort..." %(str(obsdict_key[obskey][1]))
                logger.error(msg)
                warnings.append(msg)
                thread.abort()
        # Wait again for the aborted threads:
        for (thread, obskey) in thread_list:
            thread.join(timeout=10)
            if thread.isAlive():
                msg = "Thread for test stop on observer ID %s is still alive but should be aborted now." %(str(obsdict_key[obskey][1]))
                errors.append(msg)
                logger.error(msg)
        db_unregister_activity(testid, cur, cn, 'stop')
        # cleanup resource allocation
        now = time.strftime(flocklab.config.get("database", "timeformat"), time.gmtime())
        cur.execute("DELETE FROM tbl_serv_resource_allocation where `time_end` < '%s' OR `test_fk` = %d" % (now, testid))
        cn.commit()
        # Stop fetcher ---
        # This has to be done regardless of previous errors.
        logger.info("Stopping fetcher...")
        cmd = [flocklab.config.get("dispatcher", "fetcherscript"),"--testid=%d" % testid, "--stop"]
        if debug: 
            cmd.append("--debug")
        p = subprocess.Popen(cmd)
        rs = p.wait()
        if rs not in (flocklab.SUCCESS, errno.ENOPKG): # flocklab.SUCCESS (0) is successful stop, ENOPKG (65) means the service was not running. 
            msg = "Could not stop fetcher for test ID %d. Fetcher returned error %d" % (testid, rs)
            errors.append(msg)
            logger.error(msg)
            logger.error("Tried to execute: %s" % (" ".join(cmd)))
    
        # Get all errors (if any). Observers which return errors are not regarded as a general error.
        #if not errors_queue.empty():
            #logger.error("Queue with errors from test stop thread is not empty. Getting errors...")
        while not errors_queue.empty():
            errs = errors_queue.get()
            for err in errs[1]:
                #logger.error("Error from test stop thread: %s" %(str(err[0])))
                warnings.append(err[0])
        
        # Set stop time in DB ---
        cur.execute("UPDATE `tbl_serv_tests` SET `time_end_act` = UTC_TIMESTAMP() WHERE `serv_tests_key` = %d" %testid)
        cn.commit()
        
        return (errors, warnings)
    except Exception:
        msg = "Unexpected error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        logger.error(msg)
        raise
### END stop_test()


##############################################################################
#
# prepare_testresults
#
##############################################################################
def prepare_testresults(testid, cur):
    """    This function prepares testresults for the user. It calls the archiver.
        If several instances of the archiver
        are running, it may take a long time for this function to finish as it will wait
        for these functions to succeed.
    """
    errors = []
    tree = None
    
    # Check if results directory exists
    testresultsdir = "%s/%d" % (flocklab.config.get('fetcher', 'testresults_dir'), testid)
    if not os.path.isdir(testresultsdir):
        errors.append("Test results directory does not exist.")
        return errors
    
    logger.debug("Preparing testresults...")
    
    # Check if user wants test results as email ---
    logger.debug("Check if user wants testresults as email...")
    emailResults = False
    # Get the XML config from the database:
    cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" % testid)
    ret = cur.fetchone()
    if ret:
        parser = lxml.etree.XMLParser(remove_comments=True)
        tree = lxml.etree.fromstring(bytes(bytearray(ret[0], encoding = 'utf-8')), parser)
        ns = {'d': flocklab.config.get('xml', 'namespace')}
        logger.debug("Got XML from database.")
        # Check if user wants results as email
        ret = tree.xpath('//d:generalConf/d:emailResults', namespaces=ns)
        if not ret:
            logger.debug("Could not get relevant XML value <emailResults>, thus not emailing results to user.")
        else:
            if (ret[0].text.lower() == 'yes'):
                emailResults = True
    if not emailResults:
        logger.debug("User does not want test results as email.")
    else:
        logger.debug("User wants test results as email. Will trigger the email.")
    
    # Add config XML to results directory
    if flocklab.config.get('archiver', 'include_xmlconfig'):
        if tree:
            et = lxml.etree.ElementTree(tree)
            et.write("%s/testconfig.xml" % testresultsdir, pretty_print=True)
            logger.debug("XML config copied to results folder.")
        else:
            logger.warning("Could not copy XML config to test results directory.")
    
    # Generate plot ---
    if flocklab.config.getint('viz', 'generate_plots'):
        owner = flocklab.get_test_owner(cur, testid)
        if not os.path.isdir(flocklab.config.get('viz', 'dir')):
            os.mkdir(flocklab.config.get('viz', 'dir'))
        logger.debug("Generating plots...")
        try:
            showRSTandPPS = False
            if owner != flocklab.FAILED and owner[6] == "admin":
                showRSTandPPS = True
            fltools.visualizeFlocklabTrace(testresultsdir, outputDir=flocklab.config.get('viz', 'dir'), interactive=False, showPps=showRSTandPPS, showRst=showRSTandPPS)
            logger.debug("Plots generated.")
        except Exception:
            logger.error("Failed to generate results plot for test %d. %s: %s" % (testid, str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        except SystemExit:
            pass
    
    # Archive test results ---
    cmd = [flocklab.config.get('dispatcher', 'archiverscript'),"--testid=%d" % testid]
    if emailResults:
        cmd.append("--email")
    if debug: 
        cmd.append("--debug")
    # Call the script until it succeeds:
    waittime = flocklab.config.getint('dispatcher', 'archiver_waittime')
    rs = errno.EUSERS
    while rs == errno.EUSERS:
        p = subprocess.Popen(cmd)
        rs = p.wait()
        if rs not in (flocklab.SUCCESS, errno.EUSERS): # flocklab.SUCCESS (0) is successful stop, EUSERS (87) means the maximum number of allowed instances is reached. 
            msg = "Could not trigger archiver. Archiver returned error %d" % (rs)
            logger.error(msg)
            logger.error("Tried to execute: %s" % (" ".join(cmd)))
            errors.append(msg)
            return errors
        if rs == errno.EUSERS:
            # Maximum number of instances is reached. Wait some time before calling again.
            logger.info("Archiver returned EUSERS. Wait for %d s before trying again..." % waittime)
            time.sleep(waittime)
    logger.debug("Call to archiver successful.")
    
    logger.debug("Prepared testresults.")
    return errors
### END prepare_testresults()


##############################################################################
#
# evalute_linkmeasurement
#
##############################################################################
def evalute_linkmeasurement(testid, cur):
    errors = []
    # if link measurement, evaluate data
    cur.execute("SELECT `username` FROM `tbl_serv_tests` LEFT JOIN `tbl_serv_users` ON (`serv_users_key`=`owner_fk`) WHERE (`serv_tests_key` = %s)" %testid)
    ret = cur.fetchone()
    if ret and ret[0]==flocklab.config.get('linktests', 'user'):
        logger.debug("Evaluating link measurements.")
        cmd = [flocklab.config.get('dispatcher', 'testtolinkmapscript')]
        p = subprocess.Popen(cmd)
        rs = p.wait()
        if rs != flocklab.SUCCESS:
            msg = "Error %s returned from testtolinkmap script" % str(rs)
            logger.error(msg)
            errors.append(msg)
        else:
            logger.debug("Link measurement evaluations finished.")
    return errors
### END evalute_linkmeasurement()


##############################################################################
#
# inform_user
#
##############################################################################
def inform_user(testid, cur, job, errors, warnings):
    if len(errors) != 0:
        subj = "Error notification"
        if job == 'start':
            msg = "The test with ID %d could not be started as planned because of the following errors:\n\n" %testid
        elif job == 'stop':
            msg = "The test with ID %d could not be stopped as planned because of the following errors:\n\n" %testid
        elif job == 'abort':
            msg = "The test with ID %d could not be aborted as requested because of the following errors:\n\n" %testid
        for error in errors:
            msg += "\t * %s\n" %error
        for warn in warnings:
            msg += "\t * %s\n" %warn
        ret = flocklab.FAILED
    elif len(warnings) != 0:
        if job == 'start':
            subj = "Test %d starting with warnings" %testid
            msg  = "Your test has been prepared and is going to start as planned, but consider the following warnings:\n\n" 
        elif job == 'stop':
            subj = "Test %d stopped with warnings" %testid
            msg = "Your test has been stopped as planned and the results will be available on the website soon.\nTest results are also accessible using webdav: webdavs://www.flocklab.ethz.ch/user/webdav/\nConsider the following warnings:\n\n"
        elif job == 'abort':
            subj = "Test %d aborted with warnings" %testid
            msg = "Your test has been aborted as requested and the results (if any) will be available on the website soon\nTest results are also accessible using webdav: webdavs://www.flocklab.ethz.ch/user/webdav/\nConsider the following warnings:\n\n"
        for warn in warnings:
            msg += "\t * %s\n" %warn
        ret = flocklab.SUCCESS
    else:
        if job == 'start':
            subj = "Test %d starting as planned" %testid
            msg  = "Your test has been prepared and is going to start as planned." 
        elif job == 'stop':
            subj = "Test %d stopped as planned" %testid
            msg = "Your test has been stopped as planned. The results will be available on the website soon.\nTest results are also accessible using webdav: webdavs://www.flocklab.ethz.ch/user/webdav/"
        elif job == 'abort':
            subj = "Test %d aborted as requested" %testid
            msg = "Your test has been aborted as requested. The results (if any) will be available on the website soon.\nTest results are also accessible using webdav: webdavs://www.flocklab.ethz.ch/user/webdav/"
        ret = flocklab.SUCCESS

    rs = flocklab.get_test_owner(cur, testid)
    if isinstance(rs, tuple):
        owner_email = rs[4]
        disable_infomails = int(rs[5])
        # Only send email to test owner if she didn't disable reception of info mails or if there were warnings/errors:
        if ((len(warnings) != 0) or (len(errors) != 0) or (disable_infomails != 1)):
            flocklab.send_mail(subject="[FlockLab Dispatcher] %s" % (subj), message=msg, recipients=owner_email)
    else:
        msg = "Error %s returned when trying to get test owner information" % str(rs)
        logger.error(msg)
        errors.append(msg)
    
    return ret
### END inform_user()


##############################################################################
#
# relative2absolute_time -  Convert a relative time from the XML config into 
#        an absolute time by adding it to the starttime of the test
#
##############################################################################
def relative2absolute_time(starttime, relative_secs, relative_microsecs):
    tempdatetime = starttime + datetime.timedelta(seconds=relative_secs, microseconds=relative_microsecs)
    absolute_microsecs = tempdatetime.microsecond
    absolute_datetime = tempdatetime.strftime(flocklab.config.get("observer", "timeformat"))
    
    return (absolute_microsecs, absolute_datetime)
### END relative2absolute_time()


##############################################################################
#
# absolute2absoluteUTC_time -  Convert a absolute time string with time zone from the XML config into 
#   an absolute time in UTC time zone
#
##############################################################################
def absolute2absoluteUTC_time(timestring):
  tempdatetime = flocklab.get_xml_timestamp(timestring)
  absolute_datetime = time.strftime(flocklab.config.get("observer", "timeformat"), time.gmtime(tempdatetime))
  return absolute_datetime
### END relative2absolute_time()


def db_register_activity(testid, cur, cn, action, obskeys):
    pid = os.getpid()
    register_ok = True
    spin = True
    while spin:
        spin = False
        try:
            # remove obsolete values, just in case there was something going wrong..
            sql = 'DELETE FROM tbl_serv_dispatcher_activity WHERE (`time_start` < date_add(NOW(), interval - %d second))' % (max((flocklab.config.getint('tests','setuptime'),flocklab.config.getint('tests','cleanuptime'))) * 2)
            cur.execute(sql)
            for obskey in obskeys:
                sql = 'INSERT INTO tbl_serv_dispatcher_activity (`pid`,`action`,`observer_fk`,`test_fk`,`time_start`) VALUES (%d,"%s",%d,%d,NOW())' % (pid,action,obskey,testid)
                cur.execute(sql)
            cn.commit()
        except MySQLdb.IntegrityError:
            sql = 'DELETE FROM tbl_serv_dispatcher_activity WHERE (`pid` = %d AND `action`="%s" AND `test_fk` = %d)' % (pid,action,testid)
            cur.execute(sql)
            cn.commit()
            register_ok = False
        except MySQLdb.OperationalError as e: # retry if deadlock
            if e.args[0] == MySQLdb.constants.ER.LOCK_DEADLOCK:
                time.sleep(1)
                spin = True
            else:
                raise
    return register_ok
    
def db_unregister_activity(testid, cur, cn, action):
    pid = os.getpid()
    sql = 'DELETE FROM tbl_serv_dispatcher_activity WHERE (`pid` = %d AND `action`="%s" AND `test_fk` = %d)' % (pid,action,testid)
    cur.execute(sql)
    cn.commit()

##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print("Usage: %s --testid=<int> [--abort] [--debug] [--help]" % __file__)
    print("  --testid=<int>\t\tTest ID of test dispatch.")
    print("  --abort\t\t\tOptional. Tell dispatcher to abort the test.")
    print("  --debug\t\t\tOptional. Print debug messages to log.")
    print("  --help\t\t\tOptional. Print this help.")
### END usage()


##############################################################################
#
# Main
#
##############################################################################
def main(argv):
    global logger
    global abort
    global debug
    
    testid = None
    action = None
    errors = []
    warnings = []
    
    # Get logger:
    logger = flocklab.get_logger()
    
    # Get the config file:
    flocklab.load_config()
    
    # Get the arguments:
    try:
        opts, args = getopt.getopt(argv, "adht:", ["abort", "debug", "help", "testid="])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warning(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN)
    
    for opt, arg in opts:
        if opt in ("-a", "--abort"):
            abort = True
        elif opt in ("-d", "--debug"):
            debug = True
            logger.setLevel(logging.DEBUG)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-t", "--testid"):
            try:
                testid = int(arg)
            except:
                testid = 0
            if testid <= 0:
                logger.warning("Wrong API usage: testid has to be a positive number")
                sys.exit(errno.EINVAL)
        else:
            logger.warning("Wrong API usage")
            sys.exit(errno.EINVAL)

    # Check if the necessary parameters are set: testid and either start, stop or abort has to be specified but not all.
    if not testid:
        logger.warning("Wrong API usage")
        sys.exit(errno.EINVAL)

    # Add testid to logger name
    logger.name += " (Test %d)" % testid
    
    # Connect to the database:
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        flocklab.error_logandexit("Could not connect to database", errno.EAGAIN)
    
    # Check test ID:
    ret = flocklab.check_test_id(cur, testid)
    if (ret != 0):
        cur.close()
        cn.close()
        if ret == 3:
            msg = "Test ID %d does not exist in database." % testid
            flocklab.error_logandexit(msg, errno.EINVAL)
        else:
            msg = "Error when trying to get test ID from database: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            flocklab.error_logandexit(msg, errno.EIO)
    else:
        logger.debug("Checking test ID %d passed" % testid)
    
    # Register signal handler
    signal.signal(signal.SIGTERM,  sigterm_handler)
    
    # Build obsdict_key, obsdict_id ---
    # Get all observers which are used in the test and build a dictionary out of them:
    sql = """ SELECT `a`.serv_observer_key, `a`.observer_id, `a`.ethernet_address
              FROM `tbl_serv_observer` AS `a` 
              LEFT JOIN `tbl_serv_map_test_observer_targetimages` AS `b` 
                ON `a`.serv_observer_key = `b`.observer_fk 
              WHERE `b`.test_fk = %d;
          """
    cur.execute(sql % testid)
    ret = cur.fetchall()
    if not ret:
        logger.debug("No used observers found in database for test ID %d. Exiting..." % testid)
        logger.debug("Setting test status in DB to 'failed'...")
        status = 'failed'
        flocklab.set_test_status(cur, cn, testid, status)
        cur.close()
        cn.close()
        sys.exit(errno.EINVAL)
    obsdict_key = {}
    obsdict_id = {}
    for obs in ret:
        # Dict searchable by serv_observer_key:
        obsdict_key[obs[0]] = (obs[0], obs[1], obs[2])
        # Dict searchable by observer_id:
        obsdict_id[obs[1]] = (obs[0], obs[1], obs[2])
    
    if not abort:
        # Start the test ---
        action = "start"
        starttime = time.time()
        errors, warnings = start_test(testid, cur, cn, obsdict_key, obsdict_id)
        # Record time needed to set up test for statistics in DB:
        time_needed = time.time() - starttime
        sql = """ UPDATE `tbl_serv_tests`
                  SET `setuptime` = %d
                  WHERE `serv_tests_key` = %d;
              """
        cur.execute(sql % (int(time_needed), testid))
        cn.commit()
        if len(errors) != 0:
            # Test start failed. Make it abort:
            logger.warning("Going to abort test because of errors when trying to start it.")
            abort = True
        # Inform user:
        ret = inform_user(testid, cur, action, errors, warnings)
        
        # Inform admins of errors ---
        if len(errors) > 0 or len(warnings) > 0:
            msg = "The test %s with ID %d reported the following errors/warnings:\n\n" % (action, testid)
            for error in errors:
                msg = msg + "\t * ERROR: %s\n" % (str(error))
            for warn in warnings:
                msg = msg + "\t * WARNING: %s\n" % (str(warn))
            flocklab.send_mail_to_admin(msg)
        
        # Get the stop time from the database
        cur.execute("SELECT `time_end_wish` FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d" % testid)
        ret = cur.fetchone()
        stoptimestamp = datetime.datetime.timestamp(ret[0])
        if not stoptimestamp or stoptimestamp < time.time():
            logger.error("Something went wrong, stop time is in the past (%s)." % (str(stoptimestamp)))
            abort = True
            stoptimestamp = time.time()
        
        # close MySQL connection, otherwise it will time out
        try:
            cur.close()
            cn.close()
        except:
            pass
        
        # Wait for the test to stop ---
        if not abort:
            logger.info("Waiting for the test to stop... (%ds left)" % (int(stoptimestamp - time.time())))
            while not abort and time.time() < stoptimestamp:
                time.sleep(0.1)
            logger.debug("Stopping test now...")
        
        # Reconnect to the database:
        try:
            (cn, cur) = flocklab.connect_to_db()
        except:
            flocklab.error_logandexit("Could not connect to database", errno.EAGAIN)
    
    # Stop or abort the test ---
    if abort:
        action = "abort"
    else:
        action = "stop"
    starttime = time.time()
    errors, warnings = stop_test(testid, cur, cn, obsdict_key, obsdict_id, abort)
    # Record time needed to set up test for statistics in DB:
    time_needed = time.time() - starttime
    sql =   """ UPDATE `tbl_serv_tests`
                SET `cleanuptime` = %d
                WHERE `serv_tests_key` = %d;
            """
    cur.execute(sql % (int(time_needed), testid))
    cn.commit()
    
    # Inform user:
    ret = inform_user(testid, cur, action, errors, warnings)
    
    # Wait until test has status synced or no more fetcher is running:
    status = flocklab.get_test_status(cur, cn, testid)
    while (status not in ('synced', 'finished', 'failed')):
        logger.debug("Fetcher has not yet set test status to 'synced', 'finished' or 'failed' (currently in status '%s'). Going to sleep 5s..." % (status))
        # Disconnect from database (important to avoid timeout for longer processing)
        try:
            cur.close()
            cn.close()
        except:
            pass
        time.sleep(5)
        # Reconnect to the database:
        try:
            (cn, cur) = flocklab.connect_to_db()
        except:
            flocklab.error_logandexit("Could not connect to database", errno.EAGAIN)
        status = flocklab.get_test_status(cur, cn, testid)
        if (flocklab.get_fetcher_pid(testid) < 0):
            # no fetcher is running: set test status to failed
            status = 'failed'
            break
    logger.debug("Fetcher has set test status to '%s'." % status)
    
    # Check the actual runtime: if < 0, test failed
    cur.execute("SELECT TIME_TO_SEC(TIMEDIFF(`time_end_act`, `time_start_act`)) FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d" % testid)
    test_runtime = cur.fetchone()[0]
    if not test_runtime or int(test_runtime) < 0:
        logger.info("Negative runtime detected, marking test as 'failed'.")
        test_runtime = 0
    else:
        test_runtime = int(test_runtime)
    
    # Prepare testresults:
    status = 'failed'
    if not abort and test_runtime > 0 and len(errors) == 0:
        err = prepare_testresults(testid, cur)
        for e in err:
            errors.append(e)
        # Evaluate link measurement:
        #err = evalute_linkmeasurement(testid, cur)
        #for e in err:
        #    errors.append(e)
        if len(errors) == 0:
            status = 'finished'
    
    # Inform admins of errors ---
    if len(errors) > 0 or len(warnings) > 0:
        msg = "The test %s with ID %d reported the following errors/warnings:\n\n" % (action, testid)
        for error in errors:
            msg = msg + "\t * ERROR: %s\n" % (str(error))
        for warn in warnings:
            msg = msg + "\t * WARNING: %s\n" % (str(warn))
        flocklab.send_mail_to_admin(msg)
    
    # Update status (note: always treat 'abort' as 'failed' due to potentially incomplete / invalid results)
    logger.debug("Setting test status in DB to '%s'..." % status)
    flocklab.set_test_status(cur, cn, testid, status)
    logger.info("Test %d is stopped." % testid)

    # Close db connection ---
    try:
        cur.close()
        cn.close()
    except:
        pass
    
    sys.exit(flocklab.SUCCESS)
        
### END main()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg)


