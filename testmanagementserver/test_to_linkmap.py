#! /usr/bin/env python3

import sys, os, getopt, tempfile, shutil, re, time, errno, io, logging, traceback, __main__, csv, tarfile, struct, datetime
import lib.flocklab as flocklab


### Global variables ###
###
scriptname = os.path.basename(__main__.__file__)
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
name = "test_to_linkmap"
###

logger = None
config = None


##############################################################################
#
# Error classes
#
##############################################################################
class Error(Exception):
    """ Base class for exception. """
    pass
### END Error classes


##############################################################################
#
# Node class
#
##############################################################################
class Node():
    def __init__(self, obsid, id):
        self.nodeid = id
        self.obsid = obsid
        self.stat = {}
        self.rssi = {}
        
    def addStats(self, sender_id, num_messages, num_received):
        if not sender_id in self.stat:
            self.stat[sender_id] = []
        self.stat[sender_id].append((sender_id, num_messages, num_received))
    
    def getPRR(self):
        prr = []
        for sender,statlist in self.stat.items():
            prr_rec = 0
            prr_tot = 0
            for (sender_id, num_messages, num_received) in statlist:
                prr_rec = prr_rec + num_received
                prr_tot = prr_tot + num_messages
            prr.append((self.obsid, sender, float(prr_rec) / prr_tot, prr_tot))
        return prr
        
    def addRssi(self, channel, level, ouccurences):
        if not channel in self.rssi:
            self.rssi[channel] = {}
        self.rssi[channel][level] = ouccurences
        
    def getRssi(self):
        return self.rssi
### END Node class


##############################################################################
#
# TestToLinkmap
#
##############################################################################
def TestToLinkmap(testid=None, cn=None, cur=None):
    
    errors = []
    _serial_service_file = None
    nodes = {}
    starttime = None
    stoptime = None
    channels = []
    
    logger.debug("Starting to create linkmap for test ID %s..."%testid)
    
    # Get test results from archive --- 
    archive_path = "%s/%s%s"%(config.get('archiver','archive_dir'), testid, config.get('archiver','archive_ext'))
    if not os.path.exists(archive_path):
        msg = "Archive path %s does not exist, removing link measurement." % archive_path
        cur.execute("DELETE FROM `tbl_serv_web_link_measurements` WHERE `test_fk` = %s" % testid)
        logger.error(msg)
        errors.append(msg)
        return errors
    
    # Extract serial service results file ---
    logger.debug("Extracting serial service file from archive...")
    tempdir = tempfile.mkdtemp()
    archive = tarfile.open(archive_path, 'r:gz')
    for f in archive.getmembers():
        if re.search("serial[_]?", f.name) is not None:
            archive.extract(f, tempdir)
            _serial_service_file = "%s/%s" % (tempdir, f.name)
            logger.debug("Found serial service file in test archive.")
            break
    archive.close()
    if _serial_service_file is None:
        msg =  "Serial service file could not be found in archive %s."%(archive_path)
        logger.error(msg)
        errors.append(msg)
        return errors
    
    # Process CSV file ---
    logger.debug("Processing CSV file...")
    packetreader = csv.reader(open(_serial_service_file, 'r'), delimiter=',')
    for packetinfo in packetreader:
        if re.search("^observer_id", packetinfo[1]):
            continue
        # nx_uint16_t num_messages;
        # nx_uint16_t sender_id;
        # nx_uint16_t num_received;
        packet = bytes.fromhex(packetinfo[4])
        data = struct.unpack(">7xB%dx" % (len(packet) - 8), packet)
        if data[0] == 7:
            # link measurement
            data = struct.unpack(">8xHHH",packet)
            #print "%s: src:%d dst:%s %d/%d" % (packetinfo[1], data[1], packetinfo[2], data[2], data[0])
            if not int(packetinfo[2]) in nodes:
                nodes[int(packetinfo[2])] = Node(int(packetinfo[1]), int(packetinfo[2]))
            nodes[int(packetinfo[2])].addStats(data[1], data[0], data[2])
            if starttime is None or starttime > float(packetinfo[0]):
                starttime = float(packetinfo[0])
            if stoptime is None or stoptime < float(packetinfo[0]):
                stoptime = float(packetinfo[0])
        elif data[0] == 8:
            # RSSI scan
            data = struct.unpack(">8xBHH",packet)
            # print "RSSI scan: %d %d %d" % (data[0], data[1] - 127 - 45, data[2])
            if not int(packetinfo[2]) in nodes:
                nodes[int(packetinfo[2])] = Node(int(packetinfo[1]), int(packetinfo[2]))
            nodes[int(packetinfo[2])].addRssi(data[0], data[1], data[2])
            if not data[0] in channels:
                channels.append(data[0])
    logger.debug("Processed CSV file.")
    
    # Determine start/stop time ---
    if (starttime is None) or (stoptime is None):
        msg = "Could not determine start or stop time of link test ID %s." % testid
        filesize = os.path.getsize(_serial_service_file)
        if filesize < 100:
            # file size is less than 100 bytes (empty file) -> test failed
            ret = flocklab.set_test_status(cur, cn, testid, 'failed')
            if ret != 0:
                msg += " Could not set test status to failed.\n"
            else:
                msg += " File size is %u bytes, test status set to failed.\n" % filesize
        logger.error(msg)
        errors.append(msg)
        return errors
    # structure: list, [[sum(received packets from node i at j)],[],[]...]
    # structure: list, [[sum(stat packets node j about i)],[],[]...]
    
    # Get platform info ---
    logger.debug("Getting platform info...")
    sql = """    SELECT `c`.`platforms_fk`, `d`.`name`, `a`.`description`
            FROM 
                `tbl_serv_tests` as `a`
                LEFT JOIN `tbl_serv_map_test_observer_targetimages` as `b` ON (`a`.serv_tests_key = `b`.test_fk) 
                LEFT JOIN `tbl_serv_targetimages` AS `c` ON (`b`.`targetimage_fk` = `c`.`serv_targetimages_key`)
                LEFT JOIN `tbl_serv_platforms` AS `d` ON (`c`.`platforms_fk` = `d`.`serv_platforms_key`)
            WHERE `a`.serv_tests_key = %s
            LIMIT 1
        """
    cur.execute(sql % str(testid))
    ret = cur.fetchall()
    platform_fk = ret[0][0]
    platform_name = ret[0][1]
    # search for structure (Radio:*) in description
    platform_radio = re.search('\(Radio:([^)]*)\)', ret[0][2])
    if platform_radio is not None:
        platform_radio = platform_radio.group(1)
        
    # Write XML file ---
    logger.debug("Writing XML file...")
    linkmap = io.StringIO()
    linkmap.write('<?xml version="1.0" encoding="UTF-8" ?>\n<network platform="%s"' % platform_name)
    if platform_radio is not None:
        linkmap.write(' radio="%s"' % platform_radio)
    linkmap.write('>')
    for receiver, node in nodes.items():
        nodeprr = node.getPRR()
        for (obsid, sender, prr, numpkt) in nodeprr:
            if prr > 0:
                if sender in nodes:
                    sender_obs_id = str(nodes[sender].obsid)
                else:
                    sender_obs_id = "?"
                linkmap.write('<link src="%s" dest="%d" prr="%0.4f" numpackets="%d" />' % (sender_obs_id, obsid, prr, numpkt))
    for ch in channels:
        linkmap.write('<rssiscan channel="%d">' % ch)
        for receiver, node in nodes.items():
            rssi = node.getRssi()
            if ch in rssi:
                linkmap.write('<rssi nodeid="%s" frq="' % (node.obsid))
                linkmap.write(','.join(map(str, iter(rssi[ch].values()))))
                linkmap.write('" />')    
        linkmap.write('</rssiscan>')
    linkmap.write('</network>')
    
    # Store XML file in  DB ---
    logger.debug("Storing XML file in DB...")
    cur.execute("DELETE FROM `tbl_serv_web_link_measurements` WHERE `test_fk`=%s" % str(testid))
    if platform_radio is None:
        cur.execute("INSERT INTO `tbl_serv_web_link_measurements` (`test_fk`, `platform_fk`, `links`, `begin`, `end`) VALUES (%s,%s,'%s','%s','%s')" % ((str(testid), platform_fk, linkmap.getvalue(), datetime.datetime.fromtimestamp(starttime), datetime.datetime.fromtimestamp(stoptime))))
    else:
        cur.execute("INSERT INTO `tbl_serv_web_link_measurements` (`test_fk`, `platform_fk`, `links`, `begin`, `end`, `radio`) VALUES (%s,%s,'%s','%s','%s',%s)" % (str(testid), platform_fk, linkmap.getvalue(), datetime.datetime.fromtimestamp(starttime), datetime.datetime.fromtimestamp(stoptime), platform_radio))
    cn.commit()    

    # Remove temp dir ---
    logger.debug("Removing %s..."%tempdir)
    shutil.rmtree(tempdir)
    
    logger.debug("Created linkmap for test ID %s"%testid)
    return errors
### END TestToLinkmap()


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print("Usage: %s [--debug] [--help]" %scriptname)
    print("Options:")
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
    global config
    global name
    
    errors = []
    _serial_service_file = None
    
    # Set timezone to UTC:
    os.environ['TZ'] = 'UTC'
    time.tzset()
    
    # Get logger:
    logger = flocklab.get_logger(loggername=scriptname, loggerpath=scriptpath)
    
    # Get the config file:
    config = flocklab.get_config(configpath=scriptpath)
    if not config:
        msg = "Could not read configuration file. Exiting..."
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
    #logger.debug("Read configuration file.")
    
    # Get the arguments:
    try:
        opts, args = getopt.getopt(argv, "hd", ["help", "debug"])
    except getopt.GetoptError as err:
        logger.warn(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-d", "--debug"):
            logger.setLevel(logging.DEBUG)
        else:
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Connect to the DB ---
    try:
        (cn, cur) = flocklab.connect_to_db(config, logger)
    except:
        msg = "Could not connect to database"
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
    #logger.debug("Connected to database")
    
    # Query database for pending link measurements ---
    testids = []
    cur.execute("SELECT `test_fk` FROM `tbl_serv_web_link_measurements` LEFT JOIN `tbl_serv_tests` ON (`test_fk` = `serv_tests_key`) WHERE `links` is NULL AND `test_status` IN ('synced', 'finished')")
    ret = cur.fetchall()
    for row in ret:
        testids.append(int(row[0]))
    if (len(testids) == 0):
        logger.debug("No pending test for evaluation")
    else:
        logger.debug("Test IDs to process: %s\n"%str(testids))
        for testid in testids:
            try:
                ret = TestToLinkmap(testid=testid, cn=cn, cur=cur)
                if len(ret) == 0:
                    # No errors occurred, thus mark the test for deletion:
                    logger.debug("Mark test %s for deletion."%str(testid))
                    flocklab.set_test_status(cur, cn, testid, 'todelete')
                else:
                    logger.debug("Errors detected while processing test %s."%str(testid))
                    for err in ret:
                        errors.append(err)
            except:
                msg = "Encountered error for test ID %d: %s: %s" % (testid, str(sys.exc_info()[0]), str(sys.exc_info()[1]))
                errors.append(msg)
                logger.error(msg)
                continue
    if (len(errors)):
        msg = ""
        for err in errors:
            msg += err    
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
        
    logger.debug("Finished. Exit program.")
    cn.close()
    sys.exit(flocklab.SUCCESS)
### END main()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
    
