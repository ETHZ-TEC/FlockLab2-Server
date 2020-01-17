#!/usr/bin/env python3

import sys, os, getopt, errno, subprocess, time, calendar, MySQLdb, tempfile, base64, syslog, re, configparser, traceback, xml
import lib.flocklab as flocklab


debug = False


##############################################################################
#
# checkObsids
#    Checks if every observer ID returned by the xpath evaluation is only used
#    once and if every observer ID is in the list provided in obsidlist.
#
##############################################################################
def checkObsids(tree, xpathExpr, namespace, obsidlist=None):
    duplicates = False
    allInList  = True
    
    # Get the observer IDs from the xpath expression:
    rs = tree.xpath(xpathExpr, namespaces=namespace)
    
    # Build a list with all used observer IDs in it:
    foundObsids = []
    tmp = []
    for ids in rs:
        tmp.append(ids.text.split())
    list(map(foundObsids.extend, tmp))
    
    # Check for duplicates:
    if ( (len(foundObsids) != len(set(foundObsids))) ):
        duplicates = True
    
    # Check if all obs ids are in the list:
    for obsid in foundObsids:
        if obsid not in obsidlist:
            allInList = False
    
    # Return the values to the caller:
    if (duplicates or not allInList):
        return(None, duplicates, allInList)
    else:
        return(sorted(foundObsids), duplicates, allInList)
### END checkObsids()



##############################################################################
#
# getXmlTimestamp
#    Converts XML timestamps to python taking timezone into account.
#
##############################################################################
def getXmlTimestamp(datetimestring):
    #is there a timezone?
    m = re.match('([0-9]{4,4}-[0-9]{1,2}-[0-9]{1,2}T[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2})([+-])([0-9]{2,2}):([0-9]{2,2})',datetimestring)
    if m == None:
        timestamp = calendar.timegm(time.strptime(datetimestring, "%Y-%m-%dT%H:%M:%SZ"))
    else:
        timestamp = calendar.timegm(time.strptime('%s' % (m.group(1)), "%Y-%m-%dT%H:%M:%S"))
        offset = int(m.group(3))*3600 + int(m.group(4)) * 60
        if m.group(2)=='-':
            timestamp = timestamp + offset;
        else:
            timestamp = timestamp - offset;
    return timestamp
### END getXmlTimestamp()



##############################################################################
#
# Usage
#
##############################################################################
def usage(config):
    print("Usage: %s [--xml=<path>] [--testid=<int>] [--userid=<int>] [--schema=<path>] [--quiet] [--help]" % sys.argv[0])
    print("Validate an XML testconfiguration. Returns 0 on success, errno on errors.")
    print("Options:")
    print("  --xml\t\t\t\tOptional. Path to the XML file which is to check. Either --xml or --testid are) mandatory. If both are given, --testid will be favoured.")
    print("  --testid\t\t\tOptional. Test ID to validate. If this parameter is set, the XML will be taken from the DB. Either --xml or --testid are mandatory. If both are given, --testid will be favoured.")
    print("  --userid\t\t\tOptional. User ID to which the XML belongs. Mandatory if --xml is specified.")
    print("  --schema\t\t\tOptional. Path to the XML schema to check XML against. If not given, the standard path will be used: %s" %(str(config.get('xml', 'schemapath'))))
    print("  --quiet\t\t\tOptional. Do not print on standard out.")
    print("  --help\t\t\tOptional. Print this help.")
### END usage()


##############################################################################
#
# get_config - read user.ini and return it to caller.
#
##############################################################################
def get_config():
    global scriptpath
    """Arguments: 
            none
       Return value:
            The configuration object on success
            none otherwise
    """
    try: 
        config = configparser.SafeConfigParser(comment_prefixes=('#', ';'), inline_comment_prefixes=(';'))
        config.read(scriptpath + '/user.ini')
    except:
        syslog(LOG_WARNING, "Could not read %s/user.ini because: %s: %s" %(scriptpath, str(sys.exc_info()[0]), str(sys.exc_info()[1])))
    return config
### END get_config()


##############################################################################
#
# is_admin - Check if a user ID belongs to an admin.
#
##############################################################################
def is_admin(cursor=None, userid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            userid: user ID to test
       Return value:
            On success, True or False
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(userid) != int) or (userid <= 0)):
        return(1)

    # Get the addresses from the database:            
    try:
        cursor.execute("SELECT `role` FROM `tbl_serv_users` WHERE `serv_users_key` = %d" %userid)
        rs = cursor.fetchone()
        ret = False
        if ((rs != None) and (rs[0] == 'admin')):
            ret = True
    except:
        # There was an error in the database connection:
        syslog(LOG_WARNING, "FlockLab is_admin() error: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    
    return ret
### END is_admin()


##############################################################################
#
# is_internal - Check if an ID belongs to an internal user.
#
##############################################################################
def is_internal(cursor=None, userid=0):
    """Arguments:
            cursor: cursor of the database connection to be used for the query
            userid: user ID to test
       Return value:
            On success, True or False
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(userid) != int) or (userid <= 0)):
        return(1)

    # Get the addresses from the database:
    try:
        cursor.execute("SELECT `role` FROM `tbl_serv_users` WHERE `serv_users_key` = %d" %userid)
        rs = cursor.fetchone()
        ret = False
        if ((rs != None) and (rs[0] == 'internal')):
            ret = True
    except:
        # There was an error in the database connection:
        syslog(LOG_WARNING, "FlockLab is_internal() error: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    
    return ret
### END is_internal()


##############################################################################
#
# get_obsids - Get a list of currently available observer IDs of a certain platform.
#
##############################################################################
def get_obsids(cursor=None, platform=None, status=None):
    if not cursor or not platform or not status:
        return None
    rs = cursor.execute("""SELECT obs.observer_id AS obsid FROM flocklab.tbl_serv_observer AS obs
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS a ON obs.slot_1_tg_adapt_list_fk = a.serv_tg_adapt_list_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot1 ON a.tg_adapt_types_fk = slot1.serv_tg_adapt_types_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS b ON obs.slot_2_tg_adapt_list_fk = b.serv_tg_adapt_list_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot2 ON b.tg_adapt_types_fk = slot2.serv_tg_adapt_types_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS c ON obs.slot_3_tg_adapt_list_fk = c.serv_tg_adapt_list_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot3 ON c.tg_adapt_types_fk = slot3.serv_tg_adapt_types_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS d ON obs.slot_4_tg_adapt_list_fk = d.serv_tg_adapt_list_key
                        LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot4 ON d.tg_adapt_types_fk = slot4.serv_tg_adapt_types_key
                        WHERE obs.status IN (%s) AND '%s' IN (slot1.name, slot2.name, slot3.name, slot4.name)
                        ORDER BY obs.observer_id;
                        """ % (status, platform))
    obslist = []
    for r in rs.fetchall():
        obslist.append(r[obsid])
    return obslist
### END get_obsids()


##############################################################################
#
# Main
#
##############################################################################
def main(argv):
    quiet      = False
    userid     = None
    xmlpath    = None
    schemapath = None
    testid     = None
    isadmin    = False
    isinternal = False
    
    # Open the log and create logger:
    try:
        logger = flocklab.get_logger(os.path.basename(__file__))
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    except:
        syslog.syslog(syslog.LOG_ERR, "%s: Could not open logger because: %s: %s" % (os.path.basename(__file__), str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        print("Failed to open logger because: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        sys.exit(errno.EAGAIN)
    
    # Get the config file:
    config = get_config()
    if not config:
        logger.warn("Could not read configuration file. Exiting...")
        sys.exit(errno.EAGAIN)
    
    # Get command line parameters.
    try:
        opts, args = getopt.getopt(argv, "hqu:s:x:t:", ["help", "quiet", "userid=", "schema=", "xml=", "testid="])
    except getopt.GetoptError as err:
        logger.warn(str(err))
        usage(config)
        sys.exit(errno.EINVAL)
    for opt, arg in opts:
        if opt in ("-u", "--userid"):
            try:
                userid = int(arg)
                if userid <= 0:
                    raise
            except:
                logger.warn("Wrong API usage: userid has to be a positive number")
                sys.exit(errno.EINVAL)
        elif opt in ("-t", "--testid"):
            try:
                testid = int(arg)
                if testid <= 0:
                    raise
            except:
                logger.warn("Wrong API usage: testid has to be a positive number")
                sys.exit(errno.EINVAL)
        elif opt in ("-s", "--schema"):
            schemapath = arg
            if (not os.path.exists(schemapath) or not os.path.isfile(schemapath)):
                logger.warn("Wrong API usage: schema file '%s' does not exist" % schemapath)
                sys.exit(errno.EINVAL)
        elif opt in ("-x", "--xml"):
            xmlpath = arg
            if (not os.path.exists(xmlpath) or not os.path.isfile(xmlpath)):
                logger.warn("Wrong API usage: XML file '%s' does not exist" % xmlpath)
                sys.exit(errno.EINVAL)
        elif opt in ("-h", "--help"):
            usage(config)
            sys.exit(SUCCESS)
        elif opt in ("-q", "--quiet"):
            quiet = True
        else:
            if not quiet:
                print("Wrong API usage")
                usage(config)
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Check mandatory arguments:
    if ( ((not testid) and (not xmlpath)) or ((xmlpath) and (not userid)) ):
        if not quiet:
            print("Wrong API usage")
            usage(config)
        logger.warn("Wrong API usage")
        sys.exit(errno.EINVAL)
    
    # Set the schemapath:
    if not schemapath:
        schemapath = config.get('xml', 'schemapath')
    
    # check if xmllint is installed
    try:
        subprocess.check_call(['which', 'xmllint'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if check_call doesn't raise an exception, then return code was zero (success)
    except:
        if not quiet:
            print("xmllint not found!")
        logger.warn("xmllint not found!")
        sys.exit(errno.EINVAL)
    
    # Connect to the DB:
    try:
        db = MySQLdb.connect(host=config.get('database','host'), user=config.get('database','user'), passwd=config.get('database','password'), db=config.get('database','database')) 
        cursor = db.cursor()
    except:
        logger.warn("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        sys.exit(errno.EAGAIN)
        
    # Check if the user is admin:
    isadmin = is_admin(cursor, userid)
    if isadmin not in (True, False):
        logger.warn("Could not determine if user is admin or not. Error %d occurred. Exiting..." %isadmin)
        sys.exit(errno.EAGAIN)
        
    # Check if the user is internal:
    isinternal = is_internal(cursor, userid)
    if isinternal not in (True, False):
        logger.warn("Could not determine if user is internal or not. Error %d occurred. Exiting..." %isinternal)
        sys.exit(errno.EAGAIN)
    
    # Valid stati for observers based on used permissions
    stati = "'online'"
    if isadmin:
        stati += ", 'develop', 'internal'"
    elif isinternal:
        stati += ", 'internal'"
    
    # Initialize error counter and set timezone to UTC:
    errcnt = 0;
    os.environ['TZ'] = 'UTC'
    time.tzset()
    
    logger.debug("Checking xml config...")
    
    #===========================================================================
    # If a testid was given, get the xml from the database
    #===========================================================================
    if testid:
        # Get the XML from the database, put it into a temp file and set the xmlpath accordingly:
        (fd, xmlpath) = tempfile.mkstemp()
        cursor.execute("SELECT `testconfig_xml`, `owner_fk` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" %testid)
        ret = cursor.fetchone()
        if not ret:
            if not quiet:
                print(("No test found in database with testid %d. Exiting..." %testid))
            errcnt = errcnt + 1
        else:
            xmlfile = os.fdopen(fd, 'w+')
            xmlfile.write(ret[0])
            xmlfile.close()
            userid = int(ret[1])
    
    #===========================================================================
    # Validate the XML against the XML schema
    #===========================================================================
    if errcnt == 0:
        try:
            p = subprocess.Popen(['xmllint', '--noout', xmlpath, '--schema', schemapath], stdout=subprocess.PIPE, stderr= subprocess.PIPE, universal_newlines=True)
            stdout, stderr = p.communicate()
            for err in stderr.split('\n'):
                tmp = err.split(':')
                if len(tmp) >= 7:
                    if not quiet:
                        print(("Line " + tmp[1] + ":" + tmp[2] + ":" + ":".join(tmp[6:])))
                    errcnt = errcnt + 1
                elif not ((err.find('fails to validate') != -1) or (err.find('validates') != -1) or (err == '\n') or (err == '')):
                    if not quiet:
                        print(err)
                    errcnt = errcnt + 1
        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(("%s %s, %s %s" % (exc_type, sys.exc_info()[1], fname, exc_tb.tb_lineno)))
            errcnt = errcnt + 1
    
    #===========================================================================
    # If XML is valid, do additional checks on <generalConf> and <targetConf> elements
    #===========================================================================
    if errcnt == 0:
        # generalConf additional validation -------------------------------------------
        #    * If specified, start time has to be in the future
        #    * If specified, end time has to be after start time
        f = open(xmlpath, 'r')
        parser = lxml.etree.XMLParser(remove_comments=True)
        tree = lxml.etree.parse(f, parser)
        f.close()
        ns = {'d': config.get('xml', 'namespace')}
        # additional check for the namespace
        m = re.match('\{.*\}', tree.getroot().tag)
        if not m:
            print("Failed to extract namespace from XML file.")
            errcnt = errcnt + 1
        m = m.group(0)[1:-1]  # remove braces
        if m != ns['d']:
            print("Namespace in XML file does not match: found '%s', expected '%s'." % (m, ns['d']))
            errcnt = errcnt + 1
        # check xs:list items (obsIds, targetIds) for whitespace as separator
        for l in tree.xpath('//d:*/d:obsIds', namespaces=ns) + tree.xpath('//d:*/d:targetIds', namespaces=ns):
            if l.text.find('\t')>=0:
                if not quiet:
                    print("Element obsIds/targetIds: Id lists must not have tabs as separators.")
                errcnt = errcnt + 1
    
    if errcnt == 0:
        sched_abs  = tree.xpath('//d:generalConf/d:scheduleAbsolute', namespaces=ns)
        sched_asap = tree.xpath('//d:generalConf/d:scheduleAsap', namespaces=ns)
        if sched_abs:
            # The start date and time have to be in the future:
            rs = tree.xpath('//d:generalConf/d:scheduleAbsolute/d:start', namespaces=ns)
            now = time.time()
            testStart = getXmlTimestamp(rs[0].text)
            if (testStart <= now):
                if not quiet:
                    print("Element generalConf: Start time has to be in the future.")
                errcnt = errcnt + 1
            # The end date and time have to be in the future and after the start:
            rs = tree.xpath('//d:generalConf/d:scheduleAbsolute/d:end', namespaces=ns)
            testEnd = getXmlTimestamp(rs[0].text)
            if (testEnd <= testStart):
                if not quiet:
                    print("Element generalConf: End time has to be after start time.")
                errcnt = errcnt + 1
            # Calculate the test duration which is needed later on:
            testDuration = testEnd - testStart
        elif sched_asap:
            testDuration = int(tree.xpath('//d:generalConf/d:scheduleAsap/d:durationSecs', namespaces=ns)[0].text)
        
        # targetConf additional validation -------------------------------------------- 
        #    * DB image ids need to be in the database and binary field must not be empty
        #    * Embedded image ids need to be in elements in the XML and need to be valid and correct type
        #    * Observer ids need to have the correct target adaptor installed and must be unique
        #    * If specified, number of target ids need to be the same as observer ids
        #    * There must be a target image provided for every mandatory core (usually core 0, core 0-3 for DPP)
        
        # Loop through all targetConf elements:
        obsidlist = []
        obsiddict = {}
        targetconfs = tree.xpath('//d:targetConf', namespaces=ns)
        platform = None
        for targetconf in targetconfs:
            targetids = None
            dbimageid = None
            embimageid = None
            # Get elements:
            obsids = targetconf.xpath('d:obsIds', namespaces=ns)[0].text.split()
            ret = targetconf.xpath('d:targetIds', namespaces=ns)
            if ret:
                targetids = ret[0].text.split()
                targetids_line = ret[0].sourceline 
            ret = targetconf.xpath('d:dbImageId', namespaces=ns)
            if ret:
                dbimageid = [o.text for o in ret]
                dbimageid_line = [o.sourceline for o in ret]
            ret = targetconf.xpath('d:embeddedImageId', namespaces=ns)
            if ret:
                embimageid = [o.text for o in ret]
                embimageid_line = [o.sourceline for o in ret]
            
            # Put obsids into obsidlist:
            for obsid in obsids:
                if obsid is not "ALL":
                    obsidlist.append(obsid)
                
            # If target ids are present, there need to be as many as observer ids:
            if (targetids and (len(targetids) != len(obsids))):
                if not quiet:
                    print(("Line %d: element targetIds: If element targetIds is used, it needs the same amount of IDs as in the corresponding element obsIds." %(targetids_line)))
                errcnt = errcnt + 1
            
            # If DB image IDs are present, check if they are in the database and belong to the user (if he is not an admin) and get values for later use:
            if dbimageid:
                for dbimg, line in zip(dbimageid, dbimageid_line):
                    sql = """    SELECT b.name, c.name, a.core
                                FROM `tbl_serv_targetimages` AS a 
                                LEFT JOIN `tbl_serv_operatingsystems` AS b 
                                    ON a.operatingsystems_fk = b.serv_operatingsystems_key 
                                LEFT JOIN `tbl_serv_platforms` AS c 
                                    ON a.platforms_fk = c.serv_platforms_key
                                WHERE (a.`serv_targetimages_key` = %s AND a.`binary` IS NOT NULL)""" %(dbimg)
                    if not isadmin:
                        sql += " AND (a.`owner_fk` = %s)"%(userid)
                    cursor.execute(sql)
                    ret = cursor.fetchone()
                    if not ret:
                        if not quiet:
                            print(("Line %d: element dbImageId: The image with ID %s does not exist in the database or does not belong to you." %(line, str(dbimg))))
                        errcnt = errcnt + 1
                    else:
                        # Put data into dictionary for later use:
                        core = int(ret[2])
                        for obsid in obsids:
                            if obsid not in obsiddict:
                                obsiddict[obsid] = {}
                            if core in obsiddict[obsid]:
                                if not quiet:
                                    print(("Line %d: element dbImageId: There is already an image for core %d (image with ID %s)." %(line, core, str(dbimg))))
                                errcnt = errcnt + 1
                            else:
                                obsiddict[obsid][core]=ret[:2]
            
            # If embedded image IDs are present, check if they have a corresponding <imageConf> which is valid:
            if embimageid:
                for embimg, line in zip(embimageid, embimageid_line):
                    imageconf = tree.xpath('//d:imageConf/d:embeddedImageId[text()="%s"]/..' %(embimg), namespaces=ns)
                    if not imageconf:
                        if not quiet:
                            print(("Line %d: element embeddedImageId: There is no corresponding element imageConf with embeddedImageId %s defined." %(line, embimg)))
                        errcnt = errcnt + 1
                    else:
                        # Get os and platform and put it into dictionary for later use:
                        if imageconf[0].xpath('d:os', namespaces=ns):
                            opersys = imageconf[0].xpath('d:os', namespaces=ns)[0].text
                        else:
                            opersys = 'other'
                        platform = imageconf[0].xpath('d:platform', namespaces=ns)[0].text
                        try:
                            core = int(imageconf[0].xpath('d:core', namespaces=ns)[0].text)
                        except:
                            # not a mandatory field, use the default value
                            core = 0
                        logger.debug("Target image for platform %s (core %d) found." % (platform, core))
                        for obsid in obsids:
                            if obsid not in obsiddict:
                                obsiddict[obsid] = {}
                            if core in obsiddict[obsid]:
                                if not quiet:
                                    print(("Line %d: element dbImageId: There is already an image for core %d (image with ID %s)." %(line, core, str(embimg))))
                                errcnt = errcnt + 1
                            obsiddict[obsid][core]=(opersys, platform)
                        # Get the image and save it to a temporary file:
                        image = imageconf[0].xpath('d:data', namespaces=ns)[0].text
                        # For target platform DPP2LoRa, the <data> tag may be empty
                        if len(image.strip()) == 0 and (platform.lower() == "dpp2lora" or platform.lower() == "dpp2lorahg"):
                            continue   # skip image validation
                        image_line = imageconf[0].xpath('d:data', namespaces=ns)[0].sourceline
                        (fd, imagefilename) = tempfile.mkstemp()
                        imagefile = os.fdopen(fd, 'w+b')
                        if not imagefile:
                            print("Failed to create file %s." % (imagefilename))
                        imagefile.write(base64.b64decode(image, None))
                        imagefile.close()
                        # Validate image:
                        p = subprocess.Popen([config.get('targetimage', 'imagevalidator'), '--quiet', '--image', imagefilename, '--platform', platform], stderr=subprocess.PIPE, universal_newlines=True)
                        stdout, stderr = p.communicate()
                        if p.returncode != SUCCESS:
                            if not quiet:
                                print(("Line %d: element data: Validation of image data failed. %s" %(image_line, stderr)))
                            errcnt = errcnt + 1
                        # Remove temporary file:
                        os.remove(imagefilename)
        
        # if there is just one target config and a list of observers is not provided, then fetch a list of all observers from the database
        if (len(obsidlist) == 0) and len(targetconfs) == 1:
            obsidlist = get_obsids(cursor, platform, stati)
        # Check if no observers are in the list multiple times and if every observer has the correct target adapter installed:
        obsidlist = list(set(obsidlist))
        (obsids, duplicates, allInList) = checkObsids(tree, '//d:targetConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element targetConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        else:
            usedObsidsList = sorted(obsids)
            # Now that we have the list, check the observer types:
            sql_adap = """SELECT `b`.`tg_adapt_types_fk`, `c`.`tg_adapt_types_fk`, `d`.`tg_adapt_types_fk`, `e`.`tg_adapt_types_fk`
                            FROM `tbl_serv_observer` AS `a` 
                            LEFT JOIN `tbl_serv_tg_adapt_list` AS `b` ON `a`.`slot_1_tg_adapt_list_fk` = `b`.`serv_tg_adapt_list_key`
                            LEFT JOIN `tbl_serv_tg_adapt_list` AS `c` ON `a`.`slot_2_tg_adapt_list_fk` = `c`.`serv_tg_adapt_list_key`
                            LEFT JOIN `tbl_serv_tg_adapt_list` AS `d` ON `a`.`slot_3_tg_adapt_list_fk` = `d`.`serv_tg_adapt_list_key`
                            LEFT JOIN `tbl_serv_tg_adapt_list` AS `e` ON `a`.`slot_4_tg_adapt_list_fk` = `e`.`serv_tg_adapt_list_key`
                            WHERE 
                                (`a`.`observer_id` = %s)
                                AND (`a`.`status` IN (%s))
                        """
            sql_platf = """SELECT COUNT(*)
                            FROM `tbl_serv_tg_adapt_types` AS `a` 
                            LEFT JOIN `tbl_serv_platforms` AS `b` ON `a`.`platforms_fk` = `b`.`serv_platforms_key`
                            WHERE 
                                (`a`.`serv_tg_adapt_types_key` = %s)
                                AND (LOWER(`b`.`name`) = LOWER('%s'))
                        """
            sql_cores = """SELECT core, optional
                            FROM `tbl_serv_platforms` AS `b` 
                            LEFT JOIN `tbl_serv_architectures` AS `a` ON `a`.`platforms_fk` = `b`.`serv_platforms_key`
                            WHERE (LOWER(`b`.`name`) = LOWER('%s'))
                        """
            for obsid in usedObsidsList:
                if obsid in obsiddict:
                    platf = next(iter(obsiddict[obsid].values()))[1].lower()
                    opersys = next(iter(obsiddict[obsid].values()))[0].lower()
                    for p in obsiddict[obsid].values():
                        if platf!=p[1].lower():
                            if not quiet:
                                print(("Element targetConf: Observer ID %s has images of several platform types assigned." %(obsid)))
                            errcnt = errcnt + 1
                            break
                        #if opersys!=p[0].lower():
                        #    if not quiet:
                        #        print(("Element targetConf: Observer ID %s has images of several operating system types assigned." %(obsid)))
                        #    errcnt = errcnt + 1
                        #    break
                else:
                    platf = None
                # Get tg_adapt_types_fk of installed target adaptors on observer:
                cursor.execute(sql_adap %(obsid, stati))
                adaptTypesFk = cursor.fetchone()
                # If no results are returned, it most probably means that the observer is not active at the moment.
                if not adaptTypesFk:
                    if not quiet:
                        print(("Element targetConf: Observer ID %s cannot be used at the moment." %(obsid)))
                    # If the test ID has been provided, the test has already been scheduled and should run despite a node that is not available.
                    if not testid:
                        errcnt = errcnt + 1
                elif adaptTypesFk and platf:
                    # Cycle through the adaptors which are attached to the observer and try to find one that can be used with the requested platform:
                    adaptFound = False
                    for adapt in adaptTypesFk:
                        # Only check for entries which are not null:
                        if adapt:
                            cursor.execute(sql_platf %(adapt, platf))
                            rs = cursor.fetchone()
                            if (rs[0] > 0):
                                adaptFound = True
                                break
                    if not adaptFound:
                        if not quiet:
                            print(("Element targetConf: Observer ID %s has currently no target adapter for %s installed." %(obsid, platf)))
                        errcnt = errcnt + 1
                if platf is not None:
                    cursor.execute(sql_cores %(platf))
                    core_info = cursor.fetchall()
                    all_cores = [row[0] for row in core_info]
                    required_cores = [row[0] for row in [row for row in core_info if row[1]==0]]
                    provided_cores = list(obsiddict[obsid].keys())
                    if not set(required_cores).issubset(set(provided_cores)):
                        if not quiet:
                            print(("Element targetConf: Not enough target images provided for Observer ID %s. Platform %s requires images for cores %s." %(obsid, platf, ','.join(map(str,required_cores)))))
                        errcnt = errcnt + 1
                    if not set(provided_cores).issubset(set(all_cores)):
                        if not quiet:
                            print(("Element targetConf: Excess target images specified on Observer ID %s. Platform %s requires images for cores %s." %(obsid, platf, ','.join(map(str,required_cores)))))
                        errcnt = errcnt + 1
    
    #===========================================================================
    # If there are still no errors, do additional test on the remaining elements
    #===========================================================================
    if errcnt == 0:
        # serialConf additional validation --------------------------------------
        #    * observer ids need to have a targetConf associated and must be unique
        #    * check port depending on platform 
        
        # Check observer ids:
        (ids, duplicates, allInList) = checkObsids(tree, '//d:serialConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element serialConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element serialConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
            errcnt = errcnt + 1
        
        # gpioTracingConf additional validation ---------------------------------------
        #    * observer ids need to have a targetConf associated and must be unique
        #    * Every (pin, edge) combination can only be used once.

        # Check observer ids:
        (ids, duplicates, allInList) = checkObsids(tree, '//d:gpioTracingConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element gpioTracingConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element gpioTracingConf: Some observer IDs have been used but do not have a) targetConf element associated with them.")
            errcnt = errcnt + 1
        # Check (pin, edge) combinations:
        gpiomonconfs = tree.xpath('//d:gpioTracingConf', namespaces=ns)
        for gpiomonconf in gpiomonconfs:
            combList = []
            pinconfs = gpiomonconf.xpath('d:pinConf', namespaces=ns)
            for pinconf in pinconfs:
                pin  = pinconf.xpath('d:pin', namespaces=ns)[0].text
                edge = pinconf.xpath('d:edge', namespaces=ns)[0].text
                combList.append((pin, edge))
            if (len(combList) != len(set(combList))):
                if not quiet:
                    print(("Line %d: element gpioTracingConf: Every (pin, edge) combination can only be used once per observer configuration." %(gpiomonconf.sourceline)))
                errcnt = errcnt + 1
                            
                            
        # gpioActuationConf additional validation ---------------------------
        #    * observer ids need to have a targetConf associated and must be unique
        #    * relative timing commands cannot be after the test end
        #    * absolute timing commands need to be between test start and end and are not allowed for ASAP test scheduling
        
        # Check observer ids:
        (ids, duplicates, allInList) = checkObsids(tree, '//d:gpioActuationConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element gpioActuationConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element gpioActuationConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
            errcnt = errcnt + 1
        # Check relative timings:
        rs = tree.xpath('//d:gpioActuationConf/d:pinConf/d:relativeTime/d:offsetSecs', namespaces=ns)
        for elem in rs:
            if (int(elem.text) > testDuration):
                if not quiet:
                    print(("Line %d: element offsetSecs: The offset is bigger than the test duration, thus the action will never take place." %(elem.sourceline)))
                errcnt = errcnt + 1
        # Check absolute timings:
        rs = tree.xpath('//d:gpioActuationConf/d:pinConf/d:absoluteTime/d:absoluteDateTime', namespaces=ns)
        for elem in rs:
            if sched_asap:
                if not quiet:
                    print(("Line %d: element absoluteDateTime: For test scheduling method ASAP, only relative timed actions are allowed." %(elem.sourceline)))
                errcnt = errcnt + 1
            else:
                eventTime = getXmlTimestamp(elem.text)
                if (eventTime > testEnd):
                    if not quiet:
                        print(("Line %d: element absoluteDateTime: The action is scheduled after the test ends, thus the action will never take place." %(elem.sourceline)))
                    errcnt = errcnt + 1
                elif (eventTime < testStart):
                    if not quiet:
                        print(("Line %d: element absoluteDateTime: The action is scheduled before the test starts, thus the action will never take place." %(elem.sourceline)))
                    errcnt = errcnt + 1
        

        # powerProfilingConf additional validation -----------------------------------------
        #    * observer ids need to have a targetConf associated and must be unique
        #    * relative timing commands cannot be after the test end
        #    * absolute timing commands need to be between test start and end and are not allowed for ASAP test scheduling

        # Check observer ids:
        (ids, duplicates, allInList) = checkObsids(tree, '//d:powerProfilingConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element powerProfilingConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element powerProfilingConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
            errcnt = errcnt + 1
        # Check relative timings:
        rs = tree.xpath('//d:powerProfilingConf/d:profConf/d:relativeTime/d:offsetSecs', namespaces=ns)
        for elem in rs:
            ppMicroSecs = elem.getparent().find('d:offsetMicrosecs', namespaces=ns)
            if ppMicroSecs is not None:
                ppStart = float(ppMicroSecs.text) / 1000000 + int(elem.text)
            else:
                ppStart = int(elem.text)
            elem2 = elem.getparent().getparent().find('d:durationMillisecs', namespaces=ns)
            if (ppStart > testDuration):
                if not quiet:
                    print(("Line %d: element offsetSecs: The offset is bigger than the test duration, thus the action will never take place." %(elem.sourceline)))
                errcnt = errcnt + 1
            elif (ppStart + int(elem2.text)/1000 > testDuration):
                if not quiet:
                    print(("Line %d: element durationMillisecs: Profiling lasts longer than test." %(elem2.sourceline)))
                errcnt = errcnt + 1
        # Check absolute timings:
        rs = tree.xpath('//d:powerProfilingConf/d:profConf/d:absoluteTime/d:absoluteDateTime', namespaces=ns)
        for elem in rs:
            if sched_asap:
                if not quiet:
                    print(("Line %d: element absoluteDateTime: For test scheduling method ASAP, only relative timed actions are allowed." %(elem.sourceline)))
                errcnt = errcnt + 1
            else:
                ppMicroSecs = elem.getparent().find('d:absoluteMicrosecs', namespaces=ns)
                eventTime = getXmlTimestamp(elem.text)
                if ppMicroSecs is not None:
                    ppStart = float(ppMicroSecs.text) / 1000000 + eventTime
                else:
                    ppStart = eventTime
                elem2 = elem.getparent().getparent().find('d:durationMillisecs', namespaces=ns)
                if (ppStart > testEnd):
                    if not quiet:
                        print(("Line %d: element absoluteDateTime: The action is scheduled after the test ends, thus the action will never take place." %(elem.sourceline)))
                    errcnt = errcnt + 1
                elif (ppStart < testStart):
                    if not quiet:
                        print(("Line %d: element absoluteDateTime: The action is scheduled before the test starts, thus the action will never take place." %(elem.sourceline)))
                    errcnt = errcnt + 1
                elif (ppStart + int(elem2.text)/1000 > testEnd):
                    if not quiet:
                        print(("Line %d: element durationMillisecs: Profiling lasts longer than test." %(elem2.sourceline)))
                    errcnt = errcnt + 1
    
    #===========================================================================
    # All additional tests finished. Clean up and exit.
    #===========================================================================
    if db.open:
        db.close()
    
    # If there is a temp XML file, delete it:
    if testid:
        os.remove(xmlpath)
    
    logger.debug("Validation finished (%u errors)." % errcnt)
    
    if errcnt == 0:
        ret = SUCCESS
    else:
        err_str = "Number of errors: %d. It is possible that there are more errors which could not be detected due to dependencies from above listed errors."%errcnt
        logger.debug(err_str)
        if not quiet:
            print(err_str)
        ret = errno.EBADMSG
    sys.exit(ret)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        print("testconfig validator encountered an error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc()))
        sys.exit(errno.EBADMSG)
