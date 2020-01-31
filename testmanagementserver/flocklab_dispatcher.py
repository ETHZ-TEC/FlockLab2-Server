#! /usr/bin/env python3

import sys, os, getopt, errno, threading, shutil, time, datetime, subprocess, tempfile, queue, re, logging, traceback, __main__, types, hashlib, lxml.etree, MySQLdb
import lib.flocklab as flocklab


logger = None
debug  = False


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
                    logger.debug("Test stop script on observer ID %s succeeded." %(self._obsdict_key[self._obskey][1]))
                elif (rs == 255):
                    msg = "Observer ID %s is not reachable, thus not able to stop test. Dataloss occurred possibly for this observer." % (self._obsdict_key[self._obskey][1])
                    errors.append((msg, errno.EHOSTUNREACH, self._obsdict_key[self._obskey][1]))
                    logger.error(msg)
                else:
                    errors.append(("Test stop script on observer ID %s failed with error code %d." % (str(self._obsdict_key[self._obskey][1]), rs), rs, self._obsdict_key[self._obskey][1]))
                    logger.error("Test stop script on observer ID %s failed with error code %d and message:\n%s" % (str(self._obsdict_key[self._obskey][1]), rs, str(out)))
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
    def __init__(self, obskey, obsdict_key, xmldict_key, imagedict_key, errors_queue, testid):
        threading.Thread.__init__(self) 
        self._obskey        = obskey
        self._obsdict_key   = obsdict_key
        self._xmldict_key   = xmldict_key
        self._imagedict_key = imagedict_key
        self._errors_queue  = errors_queue
        self._abortEvent    = threading.Event()
        self._testid        = testid
        
    def run(self):
        errors = []
        testconfigfolder = "%s/%d" % (flocklab.config.get("observer", "testconfigfolder"), self._testid)
        obsdataport      = flocklab.config.getint('serialproxy', 'obsdataport')
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
                    remote_cmd = flocklab.config.get("observer", "starttestscript") + " --testid=%d --xml=%s/%s --serialport=%d" % (self._testid, testconfigfolder, os.path.basename(self._xmldict_key[self._obskey][0]), obsdataport)
                    if debug:
                        remote_cmd += " --debug"
                    cmd = ['ssh', '%s' % (self._obsdict_key[self._obskey][2]), remote_cmd]
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                    while p.returncode == None:
                        self._abortEvent.wait(1.0)
                        p.poll()
                    if self._abortEvent.is_set():
                        p.kill()
                        logger.debug("Abort is set, start test process for observer %s killed." % (self._obsdict_key[self._obskey][1]))
                    else:
                        out, err = p.communicate()
                    rs = p.wait()
                    if rs != flocklab.SUCCESS:
                        errors.append(("Test start script on observer ID %s failed with error code %d." % (self._obsdict_key[self._obskey][1], rs), rs, self._obsdict_key[self._obskey][1]))
                        logger.error("Test start script on observer ID %s failed with error code %d and message:\n%s" % (str(self._obsdict_key[self._obskey][1]), rs, str(out)))
                    else:
                        logger.debug("Test start script on observer ID %s succeeded." % (self._obsdict_key[self._obskey][1]))
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
        cmd = [flocklab.config.get('dispatcher','validationscript'), '--testid=%d'%testid]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, err = p.communicate()
        rs = p.returncode
        if rs != 0:
            logger.error("Error %s returned from %s" % (str(rs), flocklab.config.get('dispatcher','validationscript')))
            logger.error("Tried to execute: %s" % (" ".join(cmd)))
            errors.append("Validation of XML failed. Output of script was: %s %s" % (str(out), str(err)))
        
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
            logger.debug("Got start time wish for test from database: %s" %starttime)
            logger.debug("Got end time wish for test from database: %s" %stoptime)
            
            # Image processing ---
            # Get all images from the database:
            imagedict_key = {}
            sql_image =     """    SELECT `t`.`binary`, `m`.`observer_fk`, `m`.`node_id`, LOWER(`a`.`architecture`), LOWER(`o`.`name`) AS `osname`, `t`.`serv_targetimages_key`, LOWER(`p`.`name`) AS `platname`, `a`.`core` AS `core`
                                FROM `tbl_serv_targetimages` AS `t` 
                                LEFT JOIN `tbl_serv_map_test_observer_targetimages` AS `m` 
                                    ON `t`.`serv_targetimages_key` = `m`.`targetimage_fk` 
                                LEFT JOIN `tbl_serv_platforms` AS `p`
                                    ON `t`.`platforms_fk` = `p`.`serv_platforms_key`
                                LEFT JOIN `tbl_serv_operatingsystems` AS `o`
                                    ON `t`.`operatingsystems_fk` = `o`.`serv_operatingsystems_key`
                                LEFT JOIN `tbl_serv_architectures` AS `a`
                                    ON `t`.`core` = `a`.`core` AND `p`.`serv_platforms_key` = `a`.`platforms_fk`
                                WHERE `m`.`test_fk` = %d
                            """    
            cur.execute(sql_image%testid)
            ret = cur.fetchall()
            for r in ret:
                binary      = r[0]
                obs_fk      = r[1]
                obs_id        = obsdict_key[obs_fk][1]
                node_id     = r[2]
                arch        = r[3]
                osname      = r[4].lower()
                tgimage_key = r[5]
                platname    = r[6]
                core        = r[7]
                
                # Prepare image ---
                (fd, imagepath) = tempfile.mkstemp()
                binpath = "%s" %(os.path.splitext(imagepath)[0]) 
                imagefile = os.fdopen(fd, 'w+b')
                imagefile.write(binary)
                imagefile.close()
                removeimage = True
                logger.debug("Got target image ID %s for observer ID %s with node ID %s from database and wrote it to temp file %s (hash %s)" %(str(tgimage_key), str(obs_id), str(node_id), imagepath, hashlib.sha1(binary).hexdigest()))
                
                # Convert image to binary format and, depending on operating system and platform architecture, write the node ID (if specified) to the image:
                logger.debug("Found %s target platform architecture with %s operating system on platform %s for observer ID %s (node ID to be used: %s)." %(arch, osname, platname, str(obs_id), str(node_id)))
                set_symbols_tool = flocklab.config.get('targetimage', 'setsymbolsscript')
                symbol_node_id = "FLOCKLAB_NODE_ID"
                # keep <os> tag for backwards compatibility
                if ((node_id != None) and (osname == 'tinyos')):
                    symbol_node_id = "TOS_NODE_ID"
                elif (osname == 'contiki'):
                    symbol_node_id = None   # don't set node ID for OS Contiki
                if (arch == 'msp430'):
                    binutils_path = flocklab.config.get('targetimage', 'binutils_msp430')
                    binpath = "%s.ihex"%binpath
                    if symbol_node_id:
                        cmd = ['%s' % (set_symbols_tool), '--objcopy', '%s/msp430-objcopy' % (binutils_path), '--objdump', '%s/msp430-objdump' % (binutils_path), '--target', 'ihex', imagepath, binpath, '%s=%s' % (symbol_node_id, node_id), 'ActiveMessageAddressC$addr=%s' % (node_id), 'ActiveMessageAddressC__addr=%s' % (node_id)]
                        try:
                            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            rs = p.wait()
                            if rs != 0:
                                logger.error("Error %d returned from %s" % (rs, set_symbols_tool))
                                logger.error("Tried to execute: %s" % (" ".join(cmd)))
                                errors.append("Could not set node ID %s for target image %s" %(str(node_id), str(tgimage_key)))
                            else:
                                logger.debug("Set symbols and converted file to ihex.")
                                # Remove the temporary exe file
                                os.remove("%s.exe"%imagepath)
                                #logger.debug("Removed intermediate image %s.exe" % (str(imagepath)))
                        except OSError as err:
                            msg = "Error in subprocess: tried calling %s. Error was: %s" % (str(cmd), str(err))
                            logger.error(msg)
                            errors.append(msg)
                            removeimage = False
                    else:
                        cmd = ['%s/msp430-objcopy' % (binutils_path), '--output-target', 'ihex', imagepath, binpath]
                        try:
                            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            rs = p.wait()
                            if rs != 0:
                                logger.error("Error %d returned from msp430-objcopy" %rs)
                                logger.error("Tried to execute: %s" % (" ".join(cmd)))
                                errors.append("Could not convert target image %s to ihex" %str(tgimage_key))
                            else:
                                logger.debug("Converted file to ihex.")
                        except OSError as err:
                            msg = "Error in subprocess: tried calling %s. Error was: %s" % (str(cmd), str(err))
                            logger.error(msg)
                            errors.append(msg)
                            removeimage = False
                elif (arch == 'arm'):
                    if (platname == 'dpp'):
                        imgformat = 'ihex'
                        binpath = "%s.ihex"%binpath
                    else:
                        imgformat = 'binary'
                        binpath = "%s.bin"%binpath
                    # Set library path for arm-binutils:
                    arm_binutils_path = flocklab.config.get('targetimage', 'binutils_arm')
                    arm_env = os.environ
                    if 'LD_LIBRARY_PATH' not in arm_env:
                        arm_env['LD_LIBRARY_PATH'] = ''
                    arm_env['LD_LIBRARY_PATH'] += ':%s/%s' % (arm_binutils_path, "usr/x86_64-linux-gnu/arm-linux-gnu/lib")
                    if symbol_node_id:
                        cmd = ['%s' % (set_symbols_tool), '--objcopy', '%s/%s' % (arm_binutils_path, "usr/bin/arm-linux-gnu-objcopy"), '--objdump', '%s/%s' % (arm_binutils_path, "usr/bin/arm-linux-gnu-objdump"), '--target', imgformat, imagepath, binpath, '%s=%s' % (symbol_node_id, node_id), 'ActiveMessageAddressC$addr=%s' % (node_id), 'ActiveMessageAddressC__addr=%s' % (node_id)]
                        try:
                            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=arm_env)
                            rs = p.wait()
                            if rs != 0:
                                logger.error("Error %d returned from %s" % (rs, set_symbols_tool))
                                logger.error("Tried to execute: %s" % (" ".join(cmd)))
                                errors.append("Could not set node ID %s for target image %s" %(str(node_id), str(tgimage_key)))
                            else:
                                logger.debug("Set symbols and converted file to bin.")
                        except OSError as err:
                            msg = "Error in subprocess: tried calling %s. Error was: %s" % (str(cmd), str(err))
                            logger.error(msg)
                            errors.append(msg)
                            removeimage = False
                    else:
                        cmd = ['%s/%s' % (arm_binutils_path, "usr/bin/arm-linux-gnu-objcopy"), '--output-target', imgformat, imagepath, binpath]
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=arm_env)
                        rs = p.wait()
                        if rs != 0:
                            logger.error("Error %d returned from arm-linux-gnu-objcopy" %rs)
                            logger.error("Tried to execute: %s" % (" ".join(cmd)))
                            errors.append("Could not convert target image %s to bin" %str(tgimage_key))
                        else:
                            logger.debug("Converted file to bin.")
                else:
                    msg = "Unknown architecture %s found. The original target image (ID %s) file will be used without modification." %(arch, str(tgimage_key))
                    errors.append(msg)
                    logger.error(msg)
                    orig = open(imagepath, "r+b")
                    binfile = open(binpath, "w+b")
                    binfile.write(orig.read())
                    orig.close()
                    binfile.close()
                    logger.debug("Copied image to binary file without modification.")
                
                # Remove the original file which is not used anymore:
                if removeimage:
                    os.remove(imagepath)
                    #logger.debug("Removed image %s" % (str(imagepath)))
                else:
                    logger.warn("Image %s has not been removed." % (str(imagepath)))
                
                
                # Slot detection ---
                # Find out which slot number to use on the observer.
                #logger.debug("Detecting adapter for %s on observer ID %s" %(platname, obs_id))
                ret = flocklab.get_slot(cur, int(obs_fk), platname)
                if ret in range(1,5):
                    slot = ret
                    logger.debug("Found adapter for %s on observer ID %s in slot %d" % (platname, obs_id, slot))
                elif ret == 0:
                    slot = None
                    msg = "Could not find an adapter for %s on observer ID %s" %(platname, obs_id)
                    errors.append(msg)
                    logger.error(msg)
                else:
                    slot = None
                    msg = "Error when detecting adapter for %s on observer ID %s: function returned %d" %(platname, obs_id, ret)
                    errors.append(msg)
                    logger.error(msg)
                        
                # Write the dictionary for the image:
                if not obs_fk in imagedict_key:
                    imagedict_key[obs_fk] = []
                imagedict_key[obs_fk].append((binpath, slot, platname, osname, 0.0, core))
                
            logger.info("Processed all target images from database.")
                
            # XML processing ---
            # Get the XML config from the database and generate a separate file for every observer used:
            cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" %testid)
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
                # Create XML files ---
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
                            xmldict_key[obskey][1].write("\t<firmware>%s</firmware>\n" % (imagedict_key[obskey][0][4]))
                            for coreimage in imagedict_key[obskey]:
                                xmldict_key[obskey][1].write("\t<image core=\"%d\">%s/%d/%s</image>\n" % (coreimage[5], flocklab.config.get("observer", "testconfigfolder"),testid, os.path.basename(coreimage[0])))
                            xmldict_key[obskey][1].write("\t<slotnr>%s</slotnr>\n" % (imagedict_key[obskey][0][1]))
                            xmldict_key[obskey][1].write("\t<platform>%s</platform>\n" % (imagedict_key[obskey][0][2]))
                            xmldict_key[obskey][1].write("\t<os>%s</os>\n" % (imagedict_key[obskey][0][3]))
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
                            port = srconf.xpath('d:port', namespaces=ns)[0].text.strip()
                            xmlblock += "\t<port>%s</port>\n" %port
                        baudrate = srconf.xpath('d:baudrate', namespaces=ns)
                        if baudrate:
                            baudrate = srconf.xpath('d:baudrate', namespaces=ns)[0].text.strip()
                            xmlblock += "\t<baudrate>%s</baudrate>\n" %baudrate
                        mode = srconf.xpath('d:mode', namespaces=ns)
                        if mode:
                            mode = srconf.xpath('d:mode', namespaces=ns)[0].text.strip()
                            xmlblock += "\t<mode>%s</mode>\n" %mode
                        xmlblock += "</obsSerialConf>\n\n"
                        for obsid in obsids:
                            obsid = int(obsid)
                            obskey = obsdict_id[obsid][0]
                            xmldict_key[obskey][1].write(xmlblock)
                            #logger.debug("Wrote obsSerialConf XML for observer ID %s" %obsid)
                else:
                    logger.debug("No <serialConf> found, not using serial service.")
                
                # gpioTracingConf ---
                gmconfs = tree.xpath('//d:gpioTracingConf', namespaces=ns)
                if gmconfs:
                    for gmconf in gmconfs:
                        obsids = gmconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                        pinconfs = gmconf.xpath('d:pinConf', namespaces=ns)
                        xmlblock = "<obsGpioMonitorConf>\n"
                        for pinconf in pinconfs:
                            pin  = pinconf.xpath('d:pin', namespaces=ns)[0].text.strip()
                            edge = pinconf.xpath('d:edge', namespaces=ns)[0].text.strip()
                            mode = pinconf.xpath('d:mode', namespaces=ns)[0].text.strip()
                            xmlblock += "\t<pinConf>\n\t\t<pin>%s</pin>\n\t\t<edge>%s</edge>\n\t\t<mode>%s</mode>\n" %(pin, edge, mode)
                            cb_gs_add = pinconf.xpath('d:callbackGpioActAdd', namespaces=ns)
                            if cb_gs_add:
                                pin = cb_gs_add[0].xpath('d:pin', namespaces=ns)[0].text.strip()
                                level = cb_gs_add[0].xpath('d:level', namespaces=ns)[0].text.strip()
                                offsets = cb_gs_add[0].xpath('d:offsetSecs', namespaces=ns)[0].text.strip()
                                offsetms = cb_gs_add[0].xpath('d:offsetMicrosecs', namespaces=ns)[0].text.strip()
                                xmlblock += "\t\t<callbackGpioSetAdd>\n\t\t\t<pin>%s</pin>\n\t\t\t<level>%s</level>\n\t\t\t<offsetSecs>%s</offsetSecs>\n\t\t\t<offsetMicrosecs>%s</offsetMicrosecs>\n\t\t</callbackGpioSetAdd>\n" %(pin, level, offsets, offsetms)
                            cb_pp_add = pinconf.xpath('d:callbackPowerProfAdd', namespaces=ns)
                            if cb_pp_add:
                                duration = cb_pp_add[0].xpath('d:durationMillisecs', namespaces=ns)[0].text.strip()
                                offsets = cb_pp_add[0].xpath('d:offsetSecs', namespaces=ns)[0].text.strip()
                                offsetms = cb_pp_add[0].xpath('d:offsetMicrosecs', namespaces=ns)[0].text.strip()
                                xmlblock += "\t\t<callbackPowerprofAdd>\n\t\t\t<duration>%s</duration>\n\t\t\t<offsetSecs>%s</offsetSecs>\n\t\t\t<offsetMicrosecs>%s</offsetMicrosecs>\n\t\t</callbackPowerprofAdd>\n" %(duration, offsets, offsetms)
                            xmlblock += "\t</pinConf>\n"
                        xmlblock += "</obsGpioMonitorConf>\n\n"
                        for obsid in obsids:
                            obsid = int(obsid)
                            obskey = obsdict_id[obsid][0]
                            xmldict_key[obskey][1].write(xmlblock)
                          #logger.debug("Wrote obsGpioMonitorConf XML for observer ID %s" %obsid)
                else:
                    logger.debug("No <gpioTracingConf> found, not using GPIO tracing service.")
                        
                # gpioActuationConf ---
                # Create 2 pin settings for every observer used in the test: 
                #        1) Pull reset pin of target low when test is to start
                #        2) Pull reset pin of target high when test is to stop
                xmlblock = "<obsGpioSettingConf>\n"
                startdatetime = starttime.strftime(flocklab.config.get("observer", "timeformat"))
                startmicrosecs = starttime.microsecond
                xmlblock += "\t<pinConf>\n\t\t<pin>RST</pin>\n\t\t<level>low</level>\n\t\t<absoluteTime>\n\t\t\t<absoluteDateTime>%s</absoluteDateTime>\n\t\t\t<absoluteMicrosecs>%d</absoluteMicrosecs>\n\t\t</absoluteTime>\n\t\t<intervalMicrosecs>0</intervalMicrosecs>\n\t\t<count>1</count>\n\t</pinConf>\n" %(startdatetime, startmicrosecs)
                stopdatetime = stoptime.strftime(flocklab.config.get("observer", "timeformat"))
                stopmicrosecs = stoptime.microsecond
                xmlblock += "\t<pinConf>\n\t\t<pin>RST</pin>\n\t\t<level>high</level>\n\t\t<absoluteTime>\n\t\t\t<absoluteDateTime>%s</absoluteDateTime>\n\t\t\t<absoluteMicrosecs>%d</absoluteMicrosecs>\n\t\t</absoluteTime>\n\t\t<intervalMicrosecs>0</intervalMicrosecs>\n\t\t<count>1</count>\n\t</pinConf>\n" %(stopdatetime, stopmicrosecs)
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
                        abs_tim = pinconf.xpath('d:absoluteTime', namespaces=ns)
                        if abs_tim:
                            absdatetime = absolute2absoluteUTC_time(abs_tim[0].xpath('d:absoluteDateTime', namespaces=ns)[0].text.strip())
                            ret = abs_tim[0].xpath('d:absoluteMicrosecs', namespaces=ns)
                            if ret:
                                absmicrosec = int(ret[0].text.strip())
                            else:
                                absmicrosec = 0
                        rel_tim = pinconf.xpath('d:relativeTime', namespaces=ns)
                        if rel_tim:
                            relsec = int(rel_tim[0].xpath('d:offsetSecs', namespaces=ns)[0].text.strip())
                            ret = rel_tim[0].xpath('d:offsetMicrosecs', namespaces=ns)
                            if ret:
                                relmicrosec = int(ret[0].text.strip())
                            else:
                                relmicrosec = 0
                            # Relative times need to be converted into absolute times:
                            absmicrosec, absdatetime = relative2absolute_time(starttime, relsec, relmicrosec)    
                        periodic = pinconf.xpath('d:periodic', namespaces=ns)
                        if periodic:
                            interval = int(periodic[0].xpath('d:intervalMicrosecs', namespaces=ns)[0].text.strip())
                            count = int(periodic[0].xpath('d:count', namespaces=ns)[0].text.strip())
                        else:
                            interval = 0
                            count = 1
                        xmlblock += "\t<pinConf>\n\t\t<pin>%s</pin>\n\t\t<level>%s</level>\n\t\t<absoluteTime>\n\t\t\t<absoluteDateTime>%s</absoluteDateTime>\n\t\t\t<absoluteMicrosecs>%s</absoluteMicrosecs>\n\t\t</absoluteTime>\n\t\t<intervalMicrosecs>%i</intervalMicrosecs>\n\t\t<count>%i</count>\n\t</pinConf>\n" %(pin, level, absdatetime, absmicrosec, interval, count)
                    for obsid in obsids:
                        obsid = int(obsid)
                        obskey = obsdict_id[obsid][0]
                        xmldict_key[obskey][1].write(xmlblock)
                        #logger.debug("Wrote obsGpioSettingConf XML for observer ID %s" %obsid)
                xmlblock = "</obsGpioSettingConf>\n\n"
                for obskey in obsdict_key.keys():
                    xmldict_key[obskey][1].write(xmlblock)
                
                # powerProfilingConf ---
                ppconfs = tree.xpath('//d:powerProfilingConf', namespaces=ns)
                if ppconfs:
                    for ppconf in ppconfs:
                        obsids = ppconf.xpath('d:obsIds', namespaces=ns)[0].text.strip().split()
                        profconfs = ppconf.xpath('d:profConf', namespaces=ns)
                        xmlblock = "<obsPowerprofConf>\n"
                        for profconf in profconfs:
                            duration  = profconf.xpath('d:durationMillisecs', namespaces=ns)[0].text.strip()
                            xmlblock += "\t<profConf>\n\t\t<duration>%s</duration>" %duration
                            abs_tim = profconf.xpath('d:absoluteTime', namespaces=ns)
                            if abs_tim:
                                absdatetime = absolute2absoluteUTC_time(abs_tim[0].xpath('d:absoluteDateTime', namespaces=ns)[0].text.strip()) # parse xml date
                                ret = abs_tim[0].xpath('d:absoluteMicrosecs', namespaces=ns)
                                if ret:
                                    absmicrosec = ret[0].text.strip()
                                else: 
                                    absmicrosec = 0
                            rel_tim = profconf.xpath('d:relativeTime', namespaces=ns)
                            if rel_tim:
                                relsec = int(rel_tim[0].xpath('d:offsetSecs', namespaces=ns)[0].text.strip())
                                ret = rel_tim[0].xpath('d:offsetMicrosecs', namespaces=ns)
                                if ret:
                                    relmicrosec = int(ret[0].text.strip())
                                else:
                                    relmicrosec = 0
                                # Relative times need to be converted into absolute times:
                                absmicrosec, absdatetime = relative2absolute_time(starttime, relsec, relmicrosec)
                            xmlblock += "\n\t\t<absoluteTime>\n\t\t\t<absoluteDateTime>%s</absoluteDateTime>\n\t\t\t<absoluteMicrosecs>%s</absoluteMicrosecs>\n\t\t</absoluteTime>" %(absdatetime, absmicrosec)
                            samplingdivider = profconf.xpath('d:samplingDivider', namespaces=ns)
                            if samplingdivider:
                                samplingdivider = samplingdivider[0].text.strip()
                            else:
                                samplingdivider = flocklab.config.get('dispatcher', 'default_sampling_divider') 
                            xmlblock += "\n\t\t<samplingDivider>%s</samplingDivider>"%samplingdivider
                            xmlblock += "\n\t</profConf>\n"
                        xmlblock += "</obsPowerprofConf>\n\n"
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
                thread = StartTestThread(obskey, obsdict_key, xmldict_key, imagedict_key, errors_queue, testid)
                thread_list.append((thread, obskey))
                thread.start()
                #DEBUG logger.debug("Started thread for test start on observer ID %s" %(str(obsdict_key[obskey][1])))
            # Wait for all threads to finish:
            for (thread, obskey) in thread_list:
                # Wait max 75% of the setuptime:
                thread.join(timeout=(flocklab.config.getint('tests','setuptime')*0.75*60))
                if thread.isAlive():
                    # Timeout occurred. Signal the thread to abort:
                    logger.error("Telling thread for test start on observer ID %s to abort..." %(str(obsdict_key[obskey][1])))
                    thread.abort()
            # Wait again for the aborted threads:
            for (thread, obskey) in thread_list:    
                thread.join(timeout=10)
                if thread.isAlive():
                    msg = "Thread for test start on observer ID %s is still alive but should be aborted now." %(str(obsdict_key[obskey][1]))
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
            # Check if there is at least 1 observer which succeeded:
            if len(obs_error) > 0:
                if (len(obsdict_id) == len(set(obs_error))):
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
    
        # Start obsdbfetcher ---
        if len(errors) == 0:
            logger.debug("Starting DB fetcher...")
            cmd = [flocklab.config.get("dispatcher", "fetcherscript"), "--testid=%d"%testid]
            if debug:
                cmd.append("--debug")
            p = subprocess.Popen(cmd)
            rs = p.wait()
            if rs != 0:
                msg = "Could not start database fetcher for test ID %d. Fetcher returned error %d" % (testid, rs)
                errors.append(msg)
                logger.error(msg)
                logger.error("Tried to execute: %s" % (" ".join(cmd)))

        # check if we're still in time
        # 
        now = time.strftime(flocklab.config.get("database", "timeformat"), time.gmtime())
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
        
        # Set a time for the scheduler to check for the test to stop ---
        # This is done using the 'at' command:
        if len(errors) == 0:
            lag = 5
            # avoid scheduling a scheduler around full minute +/- 5s
            if (stoptime.second+lag) % 60 < 5:
                lag = lag + 5 - ((stoptime.second+lag) % 60)
            elif (stoptime.second+lag) % 60 > 55:
                lag = lag + 60 - ((stoptime.second+lag) % 60) + 5
            # Only schedule scheduler if it's the only one at that time
            cmd = ['atq']
            p = subprocess.Popen(cmd,  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            out, err = p.communicate()
            rs = p.returncode
            if rs == 0:
                #logger.debug("Output of atq is: %s" % (out))
                stopTimeString = str(stoptime).split()[1]
                if not out or stopTimeString not in out:
                    logger.debug("Scheduling scheduler for %s +%ds using at command..." % (stoptime, lag))
                    (fd, tmppath) = tempfile.mkstemp()
                    tmpfile = os.fdopen(fd, 'w')
                    # The at command can only schedule with a minute resolution. Thus let the script sleep for the time required and add some slack:
                    tmpfile.write("sleep %d;\n" % (stoptime.second+lag))
                    tmpfile.write("%s " % (flocklab.config.get("dispatcher", "schedulerscript")))
                    if debug:
                        tmpfile.write("--debug ")
                    tmpfile.write(">> /dev/null 2>&1\n")
                    tmpfile.close()
                    # Register the command:
                    cmd = ['at', '-M', '-t', stoptime.strftime('%Y%m%d%H%M'), '-f', tmppath]
                    p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                    rs = p.wait()
                    # Delete the temp script:
                    os.unlink(tmppath)
                    if rs != 0:
                        msg = "Could not schedule scheduler for test ID %d. at command returned error %d" % (testid, rs)
                        warnings.append(msg)
                        logger.error(msg)
                        logger.error("Tried to execute: %s" % (" ".join(cmd)))
                else:
                    logger.debug("Already scheduler scheduled for %s"%stoptime)
            else:
                logger.debug("Could not execute atq, continue")

        return (errors, warnings)
    except Exception:
        msg = "Unexpected error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        print(msg)
        logger.warn(msg)
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
        logger.info("Stopping test %d..."%testid)
        
        # Update DB status --- 
        if abort:
            status = 'aborting'
        else:
            status = 'cleaning up'
        logger.debug("Setting test status in DB to %s..." %status)
        flocklab.set_test_status(cur, cn, testid, status)
        
        # Stop serial proxy ---
        # Get the XML config from the database and check if the serial service was used in the test:
        cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" %testid)
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
            logger.warn(msg)
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
            thread.join(timeout=(flocklab.config.getint('tests','cleanuptime')*0.75*60))
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
        cmd = [flocklab.config.get("dispatcher", "fetcherscript"),"--testid=%d"%testid, "--stop"]
        if debug: 
            cmd.append("--debug")
        p = subprocess.Popen(cmd)
        rs = p.wait()
        if rs not in (flocklab.SUCCESS, errno.ENOPKG): # flocklab.SUCCESS (0) is successful stop, ENOPKG (65) means the service was not running. 
            msg = "Could not stop database fetcher for test ID %d. Fetcher returned error %d" % (testid, rs)
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
        print(msg)
        logger.warn(msg)
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
        
    logger.debug("Preparing testresults...")
    
    # Check if user wants test results as email ---
    logger.debug("Check if user wants testresults as email...")
    emailResults = False
    # Get the XML config from the database:
    cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" %testid)
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
    
    
    # Archive test results ---
    cmd = [flocklab.config.get('dispatcher', 'archiverscript'),"--testid=%d"%testid]
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
            logger.info("Archiver returned EUSERS. Wait for %d s before trying again..."%waittime)
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
        ret = errno.EPERM
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
            sql = 'DELETE FROM tbl_serv_dispatcher_activity WHERE (`time_start` < date_add(NOW(), interval - %d minute))' % (max((flocklab.config.getint('tests','setuptime'),flocklab.config.getint('tests','cleanuptime'))) * 2)
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
    print("Usage: %s --testid=<int> [--start] [--stop] [--abort] [--debug] [--help]" % __file__)
    print("  --testid=<int>\t\tTest ID of test dispatch.")
    print("  --start\t\t\tOptional. Tell dispatcher to start the test. Either --start, --stop or --aborted has to be specified.")
    print("  --stop\t\t\tOptional. Tell dispatcher to stop the test. Either --start, --stop or --aborted has to be specified.")
    print("  --abort\t\t\tOptional. Tell dispatcher to abort the test. Either --start, --stop or --aborted has to be specified.")
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
    global debug
    
    testid = None
    action = None
    errors = []
    warnings = []
    
    # Get logger:
    logger = flocklab.get_logger()
    
    # Get the config file:
    flocklab.load_config()
    
    pidfile = "%s/%s" %(flocklab.config.get("tests", "pidfolder"), "flocklab_dispatcher.pid")
    
    # Get the arguments:
    try:
        opts, args = getopt.getopt(argv, "seadht:", ["start", "stop", "abort", "debug", "help", "testid="])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warn(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN)
    
    for opt, arg in opts:
        if opt in ("-s", "--start"):
            action = 'start'
        elif opt in ("-e", "--stop"):
            action = 'stop'
        elif opt in ("-a", "--abort"):
            action = 'abort'
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
                logger.warn("Wrong API usage: testid has to be a positive number")
                sys.exit(errno.EINVAL)
        else:
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)

    # Check if the necessary parameters are set: testid and either start, stop or abort has to be specified but not all.
    if ((not testid) or (action == None)):
        logger.warn("Wrong API usage")
        sys.exit(errno.EINVAL)

    # Add testid to logger name
    logger.name += " (Test %d)"%testid
        
    # Get PID of process and write it to pid file:
    if not os.path.isdir(os.path.dirname(pidfile)):
        shutil.rmtree(pidfile, ignore_errors=True)
    if not os.path.exists(os.path.dirname(pidfile)):
        os.makedirs(os.path.dirname(pidfile))
    open(pidfile,'w').write("%d" % (os.getpid()))
    #logger.debug("Wrote pid %d into file %s" %(os.getpid(), pidfile))
    
    # Connect to the database:
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        msg = "Could not connect to database"
        flocklab.error_logandexit(msg, errno.EAGAIN)
    #logger.debug("Connected to database")
        
    # Check test ID:
    ret = flocklab.check_test_id(cur, testid)
    if (ret != 0):
        cur.close()
        cn.close()
        try:
            os.remove(pidfile)
        except OSError:
            pass
        if ret == 3:
            msg = "Test ID %d does not exist in database." %testid
            flocklab.error_logandexit(msg, errno.EINVAL)
        else:
            msg = "Error when trying to get test ID from database: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            flocklab.error_logandexit(msg, errno.EIO)
    else:
        logger.debug("Checking test ID %d passed"%testid)
        
    # Build obsdict_key, obsdict_id ---
    # Get all observers which are used in the test and build a dictionary out of them:
    sql =      """    SELECT `a`.serv_observer_key, `a`.observer_id, `a`.ethernet_address
                FROM `tbl_serv_observer` AS `a` 
                LEFT JOIN `tbl_serv_map_test_observer_targetimages` AS `b` 
                    ON `a`.serv_observer_key = `b`.observer_fk 
                WHERE `b`.test_fk = %d;
            """
    cur.execute(sql%testid)
    ret = cur.fetchall()
    if not ret:
        logger.debug("No used observers found in database for test ID %d. Exiting..." %testid)
        logger.debug("Setting test status in DB to 'failed'...")
        status = 'failed'
        flocklab.set_test_status(cur, cn, testid, status)
        cur.close()
        cn.close()
        try:
            os.remove(pidfile)
        except OSError:
            pass
        sys.exit(errno.EINVAL)
    obsdict_key = {}
    obsdict_id = {}
    for obs in ret:
        # Dict searchable by serv_observer_key:
        obsdict_key[obs[0]] = (obs[0], obs[1], obs[2])
        # Dict searchable by observer_id:
        obsdict_id[obs[1]] = (obs[0], obs[1], obs[2])
    
    # Start/stop/abort test ---
    if (action == 'start'):
        # Try to start test:
        starttime = time.time()
        errors, warnings = start_test(testid, cur, cn, obsdict_key, obsdict_id)
        # Record time needed to set up test for statistics in DB:
        time_needed = time.time() - starttime
        sql =      """    UPDATE `tbl_serv_tests`
                    SET `setuptime` = %d
                    WHERE `serv_tests_key` = %d;
                """
        cur.execute(sql%(int(time_needed), testid))
        cn.commit()
        if len(errors) != 0:
            # Test start failed. Make it abort:
            logger.warn("Going to abort test because of errors when trying to start it.")
        # Write errors and warnings to DB:
        for warn in warnings:
            flocklab.write_errorlog(cursor=cur, conn=cn, testid=testid, message=warn)
        for err in errors:
            flocklab.write_errorlog(cursor=cur, conn=cn, testid=testid, message=err)
        # Inform user:
        ret = inform_user(testid, cur, action, errors, warnings)
    
    elif ((action == 'stop') or (action == 'abort')):
        # Stop test:
        if action == 'abort':
            abort = True
        else:
            abort = False
        starttime = time.time()
        errors, warnings = stop_test(testid, cur, cn, obsdict_key, obsdict_id, abort)
        # Record time needed to set up test for statistics in DB:
        time_needed = time.time() - starttime
        sql =      """    UPDATE `tbl_serv_tests`
                    SET `cleanuptime` = %d
                    WHERE `serv_tests_key` = %d;
                """
        cur.execute(sql%(int(time_needed), testid))
        cn.commit()
        # Write errors and warnings to DB:
        for warn in warnings:
            flocklab.write_errorlog(cursor=cur, conn=cn, testid=testid, message=warn)
        for err in errors:
            flocklab.write_errorlog(cursor=cur, conn=cn, testid=testid, message=err)
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
                msg = "Could not connect to database"
                flocklab.error_logandexit(msg, errno.EAGAIN)
                continue # try to connect again in 5s
            status = flocklab.get_test_status(cur, cn, testid)
            if (flocklab.get_fetcher_pid(testid) < 0):
                # no fetcher is running: set test status to failed
                status = 'failed'
                break
        logger.debug("Fetcher has set test status to '%s'."%status)
        
        # Check the actual runtime: if < 0, test failed
        cur.execute("SELECT TIME_TO_SEC(TIMEDIFF(`time_end_act`, `time_start_act`)) FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d" % testid)
        test_runtime = int(cur.fetchone()[0])
        if test_runtime < 0:
            logger.info("Negative runtime detected, marking test as 'failed'.")
        
        # Prepare testresults:
        if (len(errors) == 0) and (test_runtime > 0):
            err = prepare_testresults(testid, cur)
            for e in err:
                errors.append(e)
            # Evaluate link measurement:
            err = evalute_linkmeasurement(testid, cur)
            for e in err:
                errors.append(e)
        # Update DB status and statistics:
        if (len(errors) == 0) and (test_runtime > 0):
            status = 'finished'
        else:
            status = 'failed'
        logger.debug("Setting test status in DB to '%s'..."%status)
        flocklab.set_test_status(cur, cn, testid, status)
        logger.info("Test %d is stopped."%testid)
        
    # Close db connection ---
    try:
        cur.close()
        cn.close()
    except:
        pass
    
    # Inform admins of errors and exit ---
    if ((len(errors) > 0) or (len(warnings) > 0)):
        msg = "The test %s with ID %d reported the following errors/warnings:\n\n" % (action, testid)
        for error in errors:
            msg = msg + "\t * ERROR: %s\n" %(str(error))
        for warn in warnings:
            msg = msg +  "\t * WARNING: %s\n" %(str(warn))
        flocklab.error_logandexit(msg)

    sys.exit(flocklab.SUCCESS)
        
### END main()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg)


