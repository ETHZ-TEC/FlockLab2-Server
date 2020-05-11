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

import sys, os, getopt, errno, subprocess, time, calendar, MySQLdb, tempfile, base64, syslog, re, configparser, traceback, lxml.etree, logging
import lib.flocklab as flocklab


debug = False


##############################################################################
#
# check_obsids
#    Checks if every observer ID returned by the xpath evaluation is only used
#    once and if every observer ID is in the list provided in obsidlist.
#
##############################################################################
def check_obsids(tree, xpathExpr, namespace, obsidlist=None):
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
    
    if "ALL" in foundObsids:
        return (obsidlist, False, True)
    
    # Check for duplicates:
    if ( (len(foundObsids) != len(set(foundObsids))) ):
        duplicates = True
    
    # Check if all obs ids are in the list:
    for obsid in foundObsids:
        if obsid.lstrip('0') not in obsidlist:
            allInList = False
    
    # Return the values to the caller:
    if (duplicates or not allInList):
        return (None, duplicates, allInList)
    else:
        return (sorted(foundObsids), duplicates, allInList)
### END check_obsids()


##############################################################################
#
# get_sampling_rate
#    Extract sampling rate from a powerProfilingConf element
#
##############################################################################
def get_sampling_rate(elem=None, ns=""):
    if elem is None:
        return None
    
    res = elem.findtext('d:samplingRate', namespaces=ns)
    if res:
        return int(res)
    res = elem.findtext('d:samplingDivider', namespaces=ns)
    if res:
        return int(64000/int(res))
    return 1000     # default sampling rate
### END get_sampling_rate()


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print("Usage: %s [--xml=<path>] [--testid=<int>] [--userid=<int>] [--schema=<path>] [--quiet] [--help]" % sys.argv[0])
    print("Validate an XML testconfiguration. Returns 0 on success, errno on errors.")
    print("Options:")
    print("  --xml\t\t\t\tOptional. Path to the XML file which is to check. Either --xml or --testid are) mandatory. If both are given, --testid will be favoured.")
    print("  --testid\t\t\tOptional. Test ID to validate. If this parameter is set, the XML will be taken from the DB. Either --xml or --testid are mandatory. If both are given, --testid will be favoured.")
    print("  --userid\t\t\tOptional. User ID to which the XML belongs. Mandatory if --xml is specified.")
    print("  --schema\t\t\tOptional. Path to the XML schema to check XML against. If not given, the standard path will be used: %s" %(str(flocklab.config.get('xml', 'schemapath'))))
    print("  --quiet\t\t\tOptional. Do not print on standard out.")
    print("  --help\t\t\tOptional. Print this help.")
### END usage()


##############################################################################
#
# Main
#
##############################################################################
def main(argv):
    quiet        = False
    userid       = None
    xmlpath      = None
    schemapath   = None
    testid       = None
    userrole     = ""
    testDuration = 0
    
    # Open the log and create logger:
    logger = flocklab.get_logger(debug=debug)
    
    # Get the config file:
    flocklab.load_config()
    
    # Get command line parameters.
    try:
        opts, args = getopt.getopt(argv, "hqu:s:x:t:", ["help", "quiet", "userid=", "schema=", "xml=", "testid="])
    except getopt.GetoptError as err:
        logger.warning(str(err))
        usage()
        sys.exit(errno.EINVAL)
    for opt, arg in opts:
        if opt in ("-u", "--userid"):
            try:
                userid = int(arg)
                if userid <= 0:
                    raise
            except:
                logger.warning("Wrong API usage: userid has to be a positive number")
                sys.exit(errno.EINVAL)
        elif opt in ("-t", "--testid"):
            try:
                testid = int(arg)
                if testid <= 0:
                    raise
            except:
                logger.warning("Wrong API usage: testid has to be a positive number")
                sys.exit(errno.EINVAL)
        elif opt in ("-s", "--schema"):
            schemapath = arg
            if (not os.path.exists(schemapath) or not os.path.isfile(schemapath)):
                logger.warning("Wrong API usage: schema file '%s' does not exist" % schemapath)
                sys.exit(errno.EINVAL)
        elif opt in ("-x", "--xml"):
            xmlpath = arg
            if (not os.path.exists(xmlpath) or not os.path.isfile(xmlpath)):
                logger.warning("Wrong API usage: XML file '%s' does not exist" % xmlpath)
                sys.exit(errno.EINVAL)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(SUCCESS)
        elif opt in ("-q", "--quiet"):
            quiet = True
        else:
            if not quiet:
                print("Wrong API usage")
                usage()
            logger.warning("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Check mandatory arguments:
    if ( ((not testid) and (not xmlpath)) or ((xmlpath) and (not userid)) ):
        if not quiet:
            print("Wrong API usage")
            usage()
        logger.warning("Wrong API usage")
        sys.exit(errno.EINVAL)
    
    # Set the schemapath:
    if not schemapath:
        schemapath = flocklab.config.get('xml', 'schemapath')
    
    # check if xmllint is installed
    try:
        subprocess.check_call(['which', 'xmllint'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if check_call doesn't raise an exception, then return code was zero (success)
    except:
        if not quiet:
            print("xmllint not found!")
        logger.warning("xmllint not found!")
        sys.exit(errno.EINVAL)
    
    # Connect to the DB:
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        flocklab.error_logandexit("Could not connect to database", errno.EAGAIN)
    
    # Check if the user is admin:
    if userid is None:
        userid = flocklab.get_test_owner(cur, testid)[0]
    userrole = flocklab.get_user_role(cur, userid)
    if userrole is None:
        logger.warning("Could not determine role for user ID %d." % userid)
        sys.exit(errno.EAGAIN)
    
    # Valid stati for observers based on used permissions
    stati = "'online'"
    if "admin" in userrole:
        stati += ", 'develop', 'internal'"
    elif "internal" in userrole:
        stati += ", 'internal'"
    
    # Initialize error counter and set timezone to UTC:
    errcnt = 0;
    
    logger.debug("Checking XML config...")
    
    #===========================================================================
    # If a testid was given, get the xml from the database
    #===========================================================================
    if testid:
        # Get the XML from the database, put it into a temp file and set the xmlpath accordingly:
        (fd, xmlpath) = tempfile.mkstemp()
        cur.execute("SELECT `testconfig_xml`, `owner_fk` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" %testid)
        ret = cur.fetchone()
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
        ns = {'d': flocklab.config.get('xml', 'namespace')}
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
        sched      = tree.xpath('//d:generalConf/d:schedule', namespaces=ns)
        if sched_abs:
            # The start date and time have to be in the future:
            rs = tree.xpath('//d:generalConf/d:scheduleAbsolute/d:start', namespaces=ns)
            now = time.time()
            testStart = flocklab.get_xml_timestamp(rs[0].text)
            if (testStart <= now):
                if not quiet:
                    print("Element generalConf: Start time has to be in the future.")
                errcnt = errcnt + 1
            # The end date and time have to be in the future and after the start:
            rs = tree.xpath('//d:generalConf/d:scheduleAbsolute/d:end', namespaces=ns)
            testEnd = flocklab.get_xml_timestamp(rs[0].text)
            if (testEnd <= testStart):
                if not quiet:
                    print("Element generalConf: End time has to be after start time.")
                errcnt = errcnt + 1
            # Calculate the test duration which is needed later on:
            testDuration = testEnd - testStart
        elif sched_asap:
            testDuration = int(tree.xpath('//d:generalConf/d:scheduleAsap/d:durationSecs', namespaces=ns)[0].text)
        elif sched:
            testDuration = int(tree.xpath('//d:generalConf/d:schedule/d:duration', namespaces=ns)[0].text)
        
        # targetConf additional validation -------------------------------------------- 
        #    * DB image ids need to be in the database and binary field must not be empty
        #    * Embedded image ids need to be in elements in the XML and need to be valid and correct type
        #    * Observer ids need to have the correct target adaptor installed and must be unique
        #    * If specified, number of target ids need to be the same as observer ids
        #    * There must be a target image provided for every mandatory core (usually core 0, core 0-3 for DPP)
        
        # Loop through all targetConf elements:
        obsidlist = []
        obsiddict = {}
        platform  = None
        targetconfs = tree.xpath('//d:targetConf', namespaces=ns)
        for targetconf in targetconfs:
            targetids  = None
            dbimageid  = None
            embimageid = None
            # Get elements:
            obsids = targetconf.xpath('d:obsIds', namespaces=ns)[0].text.split()
            ret = targetconf.xpath('d:targetIds', namespaces=ns)
            if ret:
                if "ALL" in obsids:
                    if not quiet:
                        print("Can't set targetIds when 'ALL' is used as observer ID.")
                    errcnt = errcnt + 1
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
            
            # If target ids are present, there need to be as many as observer ids:
            if (targetids and (len(targetids) != len(obsids))):
                if not quiet:
                    print(("Line %d: element targetIds: If element targetIds is used, it needs the same amount of IDs as in the corresponding element obsIds." %(targetids_line)))
                errcnt = errcnt + 1
            
            # If DB image IDs are present, check if they are in the database and belong to the user (if he is not an admin) and get values for later use:
            if dbimageid:
                for dbimg, line in zip(dbimageid, dbimageid_line):
                    sql = """SELECT b.name, a.core
                             FROM `tbl_serv_targetimages` AS a
                             LEFT JOIN `tbl_serv_platforms` AS b
                                 ON a.platforms_fk = b.serv_platforms_key
                             WHERE (a.`serv_targetimages_key` = %s AND a.`binary` IS NOT NULL)
                          """ % (dbimg)
                    if "admin" not in userrole:
                        sql += " AND (a.`owner_fk` = %s)" % (userid)
                    cur.execute(sql)
                    ret = cur.fetchone()
                    if not ret:
                        if not quiet:
                            print(("Line %d: element dbImageId: The image with ID %s does not exist in the database or does not belong to you." %(line, str(dbimg))))
                        errcnt = errcnt + 1
                    else:
                        # Put data into dictionary for later use:
                        pf = ret[0]
                        core = int(ret[1])
                        if platform == None:
                            platform = pf
                        elif platform != pf:
                            if not quiet:
                                print("Line %d: using target images of different platforms is not allowed." % (line))
                            errcnt = errcnt + 1
                        if "ALL" in obsids:
                            obsids.remove("ALL")
                            obsids.extend(flocklab.get_obsids(cur, platform, stati))
                        for obsid in obsids:
                            if obsid not in obsiddict:
                                obsiddict[obsid] = {}
                            if core in obsiddict[obsid]:
                                if not quiet:
                                    print(("Line %d: element dbImageId: There is already an image for core %d (image with ID %s)." % (line, core, str(dbimg))))
                                errcnt = errcnt + 1
                                break
                            else:
                                obsiddict[obsid][core] = platform   # target platform
                                logger.debug("Target image for platform %s (core %d) found." % (platform, core))
            
            # If embedded image IDs are present, check if they have a corresponding <embeddedImageConf> which is valid:
            if embimageid:
                for embimg, line in zip(embimageid, embimageid_line):
                    imageconf = tree.xpath('//d:embeddedImageConf/d:embeddedImageId[text()="%s"]/..' %(embimg), namespaces=ns)
                    if not imageconf:
                        if not quiet:
                            print(("Line %d: element embeddedImageId: There is no corresponding element embeddedImageConf with embeddedImageId %s defined." %(line, embimg)))
                        errcnt = errcnt + 1
                    else:
                        # Get os and platform and put it into dictionary for later use:
                        pf = imageconf[0].xpath('d:platform', namespaces=ns)[0].text
                        if platform == None:
                            platform = pf
                        elif platform != pf:
                            if not quiet:
                                print("Line %d: using target images of different platforms is not allowed." % (line))
                            errcnt = errcnt + 1
                        if "ALL" in obsids:
                            obsids.remove("ALL")
                            obsids.extend(flocklab.get_obsids(cur, platform, stati))
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
                            obsiddict[obsid][core] = platform
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
                        p = subprocess.Popen([flocklab.config.get('targetimage', 'imagevalidator'), '--quiet', '--image', imagefilename, '--platform', platform], stderr=subprocess.PIPE, universal_newlines=True)
                        stdout, stderr = p.communicate()
                        if p.returncode != flocklab.SUCCESS:
                            if not quiet:
                                print(("Line %d: element data: Validation of image data failed. %s" %(image_line, stderr)))
                            errcnt = errcnt + 1
                        # Remove temporary file:
                        os.remove(imagefilename)
        
            # Put obsids into obsidlist:
            for obsid in obsids:
                if obsid == "ALL":   # expand
                    res = flocklab.get_obsids(cur, platform, stati)
                    if res:
                        logger.debug("Found observer IDs %s for platform '%s' and stati '%s'." % (", ".join(rs), platform, stati))
                        obsidlist.extend(res)
                else:
                    obsidlist.append(obsid.lstrip('0'))   # remove leading zeros
        
        if not obsidlist or (len(obsidlist) == 0):
            print("No observer ID found.")
            errcnt = errcnt + 1
        # Remove duplicates and check if every observer has the correct target adapter installed:
        obsidlist = list(set(obsidlist))
        (obsids, duplicates, allInList) = check_obsids(tree, '//d:targetConf/d:obsIds', ns, obsidlist)
        if not allInList:
            if not quiet:
                print("Element targetConf: Not all used observers have a target config assigned.")
            errcnt = errcnt + 1
        elif duplicates:
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
                            WHERE (`a`.`observer_id` = %s)
                            AND (`a`.`status` IN (%s))
                        """
            sql_platf = """SELECT COUNT(*)
                            FROM `tbl_serv_tg_adapt_types` AS `a` 
                            LEFT JOIN `tbl_serv_platforms` AS `b` ON `a`.`platforms_fk` = `b`.`serv_platforms_key`
                            WHERE (`a`.`serv_tg_adapt_types_key` = %s)
                            AND (LOWER(`b`.`name`) = LOWER('%s'))
                        """
            sql_cores = """SELECT core, optional
                            FROM `tbl_serv_platforms` AS `b` 
                            LEFT JOIN `tbl_serv_architectures` AS `a` ON `a`.`platforms_fk` = `b`.`serv_platforms_key`
                            WHERE (LOWER(`b`.`name`) = LOWER('%s'))
                        """
            for obsid in usedObsidsList:
                if obsid in obsiddict:
                    platf = obsiddict[obsid][0].lower()
                    for p in obsiddict[obsid].values():
                        if platf != p.lower():
                            if not quiet:
                                print(("Element targetConf: Observer ID %s has images of several platform types assigned." % (obsid)))
                            errcnt = errcnt + 1
                            break
                else:
                    platf = None
                # Get tg_adapt_types_fk of installed target adaptors on observer:
                cur.execute(sql_adap %(obsid, stati))
                adaptTypesFk = cur.fetchone()
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
                            cur.execute(sql_platf %(adapt, platf))
                            rs = cur.fetchone()
                            if (rs[0] > 0):
                                adaptFound = True
                                break
                    if not adaptFound:
                        if not quiet:
                            print(("Element targetConf: Observer ID %s has currently no target adapter for %s installed." % (obsid, platf)))
                        errcnt = errcnt + 1
                if platf is not None:
                    cur.execute(sql_cores %(platf))
                    core_info = cur.fetchall()
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
        (ids, duplicates, allInList) = check_obsids(tree, '//d:serialConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element serialConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element serialConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
            errcnt = errcnt + 1
        
        # debugConf additional validation
        (debugObsIds, duplicates, allInList) = check_obsids(tree, '//d:debugConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element debugConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element debugConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
            errcnt = errcnt + 1
        if tree.xpath('//d:debugConf/d:dataTraceConf', namespaces=ns) and platform.lower() not in ('nrf5', 'dpp2lora', 'dpp2lorahg'):
            if not quiet:
                print("Element dataTraceConf: data tracing is not supported on the platform %s." % platform)
            errcnt = errcnt + 1
        
        # gpioTracingConf additional validation ---------------------------------------
        #    * observer ids need to have a targetConf associated and must be unique
        #    * Every (pin, edge) combination can only be used once.

        # Check observer ids:
        (ids, duplicates, allInList) = check_obsids(tree, '//d:gpioTracingConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element gpioTracingConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element gpioTracingConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
            errcnt = errcnt + 1
        # Check (pin, edge) combinations:
        gpiomonconfs = tree.xpath('//d:gpioTracingConf', namespaces=ns)
        for gpiomonconf in gpiomonconfs:
            usesDebug = False
            # check if one of the used observers also uses the debug service
            for obs in ids:
                if obs in debugObsIds:
                    usesDebug = True
                    break
            # check offset
            ofs = gpiomonconf.find('d:offset', namespaces=ns)
            if ofs != None and (int(ofs.text) >= testDuration):
                if not quiet:
                    print("Line %d: Offset is larger than test duration." % (ofs.sourceline))
                errcnt = errcnt + 1
            pins = gpiomonconf.find('d:pins', namespaces=ns)
            if ("dpp2lora" in platform.lower()) and ("INT2" in pins.text):
                if not quiet:
                    print("Line %d: Pin INT2 cannot be used with target platform DPP2LoRa." % (pins.sourceline))
                errcnt = errcnt + 1
                break
            if usesDebug and ("LED1" in pins.text or "LED3" in pins.text):
                if not quiet:
                    print("Line %d: Pins LED1 and LED3 cannot be traced on target platform DPP2LoRa in conjunction with the debug service." % (pins.sourceline))
                errcnt = errcnt + 1
                break
        
        # gpioActuationConf additional validation ---------------------------
        #    * observer ids need to have a targetConf associated and must be unique
        #    * relative timing commands cannot be after the test end
        #    * absolute timing commands need to be between test start and end and are not allowed for ASAP test scheduling
        
        # Check observer ids:
        (ids, duplicates, allInList) = check_obsids(tree, '//d:gpioActuationConf/d:obsIds', ns, obsidlist)
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
                eventTime = flocklab.get_xml_timestamp(elem.text)
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
        (ids, duplicates, allInList) = check_obsids(tree, '//d:powerProfilingConf/d:obsIds', ns, obsidlist)
        if duplicates:
            if not quiet:
                print("Element powerProfilingConf: Some observer IDs have been used more than once.")
            errcnt = errcnt + 1
        if not allInList:
            if not quiet:
                print("Element powerProfilingConf: Some observer IDs have been used but do not have a targetConf element associated with them.")
                print("List: %s, used IDs: %s" % (str(obsidlist), str(ids)))
            errcnt = errcnt + 1
        # Check offset tag (mandatory element)
        rs = tree.xpath('//d:powerProfilingConf/d:offset', namespaces=ns)
        total_samples = 0
        for elem in rs:
            ppOffset = int(elem.text)
            elem2 = elem.getparent().find('d:duration', namespaces=ns)
            if elem2 != None:
                ppDuration = int(elem2.text.strip())
            else:
                # assume sampling duration = test duration
                ppDuration = testDuration - ppOffset
            total_samples = total_samples + ppDuration * get_sampling_rate(elem.getparent(), ns)
            if (ppOffset + ppDuration) > testDuration:
                if not quiet:
                    print(("Line %d: element duration/offset: Profiling lasts longer than test." % (elem2.sourceline)))
                errcnt = errcnt + 1
        
        # check total number of samples (for now, just multiply the total by the number of observers)
        if ids:
            total_samples = total_samples * len(ids)
            if total_samples > flocklab.config.getint('tests', 'powerprofilinglimit'):
                if not quiet:
                    print(("Invalid combination of power profiling duration and sampling rate: the total amount of data to collect is too large (%d samples requested, limit is %d)." % (total_samples, flocklab.config.getint('tests', 'powerprofilinglimit'))))
                errcnt = errcnt + 1
        
    #===========================================================================
    # All additional tests finished. Clean up and exit.
    #===========================================================================
    if cn.open:
        cn.close()
    
    # If there is a temp XML file, delete it:
    if testid:
        os.remove(xmlpath)
    
    logger.debug("Validation finished (%u errors)." % errcnt)
    
    if errcnt == 0:
        ret = flocklab.SUCCESS
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
