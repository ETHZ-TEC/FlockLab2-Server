#!/usr/bin/env python

__author__ = "Roman May"


import sys, os, getopt, errno, subprocess, time, calendar, MySQLdb, tempfile, base64, syslog, re, hashlib, calendar, configparser
from lxml import etree
import logging.config


### Global variables ###
###
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
SUCCESS    = 0
###


class TestbedResource():
    def __init__(self, time_start, time_end, obsid, restype):
        self.time_start = time_start
        self.time_end = time_end
        self.obsid = obsid
        self.restype = restype
    
    def __repr__(self):
        return '%d to %d, obs %d, res %s' % (self.time_start,self.time_end,self.obsid,self.restype)

##############################################################################
#
# get_config - read user.ini and return it to caller.
#
##############################################################################
def get_config():
    """Arguments: 
            none
       Return value:
            The configuration object on success
            none otherwise
    """
    try: 
        config = configparser.SafeConfigParser(comment_prefixes=('#', ';'), inline_comment_prefixes=(';'))
        config.read(os.path.dirname(os.path.abspath(sys.argv[0])) + '/user.ini')
    except:
        syslog(LOG_WARNING, "Could not read %s/user.ini because: %s: %s" %(str(os.path.dirname(os.path.abspath(sys.argv[0]))), str(sys.exc_info()[0]), str(sys.exc_info()[1])))
    return config
### END get_config()

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
# getobsids
#    Gets all observer ids including architecture
#
##############################################################################
def getobsids(tree,ns,cursor):
    obsidlist = []
    obsiddict = {}
    ### OBSERVERS
    # Loop through all targetconfs
    targetconfs = tree.xpath('//d:targetConf', namespaces=ns)
    for targetconf in targetconfs:
        dbimageid = None
        embimageid = None
        # Get elements:
        obsids = targetconf.xpath('d:obsIds', namespaces=ns)[0].text.split()
        ret = targetconf.xpath('d:dbImageId', namespaces=ns)
        if ret:
            dbimageid = [o.text for o in ret]
        ret = targetconf.xpath('d:embeddedImageId', namespaces=ns)
        if ret:
            embimageid = [o.text for o in ret]
            embimageid_line = [o.sourceline for o in ret]
        
        # Put obsids into obsidlist:
        for obsid in obsids:
            obsidlist.append(obsid)

        # If DB image IDs are present, check if they are in the database and get values for later use:
        if dbimageid:
            for dbimg in dbimageid:
                if not dbimg:
                    logger.warn("Empty dbimage configuration.")
                    sys.exit(errno.EAGAIN)
                # Get frequency and architecture for each observer
                sql = """SELECT c.name
                            FROM `tbl_serv_targetimages` AS a 
                            LEFT JOIN `tbl_serv_operatingsystems` AS b 
                                ON a.operatingsystems_fk = b.serv_operatingsystems_key 
                            LEFT JOIN `tbl_serv_platforms` AS c 
                                ON a.platforms_fk = c.serv_platforms_key
                            WHERE (a.`serv_targetimages_key` = %s )"""%dbimg #AND a.`binary` IS NOT NULL)

                cursor.execute(sql)
                ret = cursor.fetchone()
                if not ret:
                    logger.warn("The image %s does not exist in the database"%dbimg)
                    sys.exit(errno.EAGAIN)
                else:
                    # Put data into dictionary for later use:
                    for obsid in obsids:
                        if obsid not in obsiddict:
                            obsiddict[obsid] = {}
                        obsiddict[obsid]['architecture']=ret[0]

        # If embedded image IDs are present, check if they have a corresponding <imageConf> which is valid:
        if embimageid:
            for embimg, line in zip(embimageid, embimageid_line):
                imageconf = tree.xpath('//d:imageConf/d:embeddedImageId[text()="%s"]/..' %(embimg), namespaces=ns)
                if not imageconf:
                    logger.warn("The embedded image %s does not exist"%dbimg)
                    sys.exit(errno.EAGAIN)
                else:
                    # Get platform and frequency:
                    platform = imageconf[0].xpath('d:platform', namespaces=ns)[0].text
                    for obsid in obsids:
                        if obsid not in obsiddict:
                            obsiddict[obsid] = {}
                        obsiddict[obsid]['architecture']=platform

    return obsidlist,obsiddict

# END getobids

##############################################################################
#
# gettimeslot
#    Gets start and stop time from a config file
#
##############################################################################
def gettimeslot(tree,ns,config):
    schedASAP = False
    # Start and End time from xml
    sched_abs  = tree.xpath('//d:generalConf/d:scheduleAbsolute', namespaces=ns)
    now = int(time.time())
    testSetup = int(config.get('tests', 'setuptime')) * 60

    if not sched_abs:
        schedASAP =  True
        # Use now + setup time as start time and start time + duration as end time
        testDuration = int(tree.xpath('//d:generalConf/d:scheduleAsap/d:durationSecs', namespaces=ns)[0].text)
        testStart = now + testSetup
        testEnd = testStart + testDuration
        
    else:
        ### TIMES
        # The start date and time have to be more than setup time in the future:
        rs = tree.xpath('//d:generalConf/d:scheduleAbsolute/d:start', namespaces=ns)
        testStart = getXmlTimestamp(rs[0].text)
        if (testStart <= now + testSetup):
            logging.warn("Test starts to soon, exit")
            sys.exit(errno.EAGAIN)

        # The end date and time have to be in the future and after the start:
        rs = tree.xpath('//d:generalConf/d:scheduleAbsolute/d:end', namespaces=ns)
        testEnd = getXmlTimestamp(rs[0].text)
        if (testEnd <= testStart):
            logging.warn("Endtime before start time, exit")
            sys.exit(errno.EAGAIN)

        # Calculate the test duration which is needed later on:
        testDuration = testEnd - testStart

    return testStart,testEnd,testDuration,schedASAP
# END gettimeslot

##############################################################################
#
# resourceSlots
#    generates a list of the slot resources
#
##############################################################################
def resourceSlots(testStart,testEnd,obsidlist,obsiddict,config,cursor):
    ### SLOT NUMBER
    # Get slot number for each observer, slots are used for the whole test plus setup and cleanup time
    obsslotlist = []
    start = int(testStart) - int(config.get('tests', 'setuptime')) * 60
    end = int(testEnd) + int(config.get('tests', 'cleanuptime')) * 60
    for obsid in obsidlist:
        sql_adap = """SELECT `b`.`tg_adapt_types_fk`, `c`.`tg_adapt_types_fk`, `d`.`tg_adapt_types_fk`, `e`.`tg_adapt_types_fk`
                        FROM `tbl_serv_observer` AS `a` 
                        LEFT JOIN `tbl_serv_tg_adapt_list` AS `b` ON `a`.`slot_1_tg_adapt_list_fk` = `b`.`serv_tg_adapt_list_key`
                        LEFT JOIN `tbl_serv_tg_adapt_list` AS `c` ON `a`.`slot_2_tg_adapt_list_fk` = `c`.`serv_tg_adapt_list_key`
                        LEFT JOIN `tbl_serv_tg_adapt_list` AS `d` ON `a`.`slot_3_tg_adapt_list_fk` = `d`.`serv_tg_adapt_list_key`
                        LEFT JOIN `tbl_serv_tg_adapt_list` AS `e` ON `a`.`slot_4_tg_adapt_list_fk` = `e`.`serv_tg_adapt_list_key`
                        WHERE 
                            (`a`.`observer_id` = %s)
                    """
        sql_platf = """SELECT COUNT(*)
                    FROM `tbl_serv_tg_adapt_types` AS `a`
                    WHERE 
                        (`a`.`serv_tg_adapt_types_key` = %s)
                        AND (LOWER(`name`) = LOWER('%s'))
                    """
        cursor.execute(sql_adap %(obsid))
        adaptTypesFk = cursor.fetchone()
        if not adaptTypesFk:
            logger.warn("Could not fetch adapter type fks for the observer %s"%obsid)
            sys.exit(errno.EAGAIN)
        else:
            slotFound = False
            for x in range(0,4):
                if not adaptTypesFk[x]:
                    continue
                cursor.execute(sql_platf %(adaptTypesFk[x],obsiddict[obsid]['architecture']))
                ret = cursor.fetchone()
                if int(ret[0]) == 1:
                    obsslotlist.append(TestbedResource(start,end,int(obsid),'slot_%d'%(x+1)))
                    slotFound = True
                    break
            if not slotFound:
                logger.warn("No Architecture %s on Observer %s"%(obsiddict[obsid]['architecture'],obsid))
                sys.exit(errno.EAGAIN)
     
    return obsslotlist

# END resourceSlots

##############################################################################
#
# resourceFrequency
#    generates a list of the frequency resources
#
##############################################################################
def resourceFrequency(testStart,testEnd,obsidlist,obsiddict,cursor):
    # get frequencies for all observers, frequencies are used for the whole test
    obsfreqlist = []
    for obsid in obsidlist:
        sql = "SELECT freq_2400, freq_868, freq_433 FROM `tbl_serv_platforms` WHERE (LOWER(`name`) = LOWER('%s'))"%obsiddict[obsid]['architecture']
        cursor.execute(sql)
        ret = cursor.fetchone()
        if not ret:
            logger.warn("Could not fetch frequencies for the observer %s"%obsid)
            sys.exit(errno.EAGAIN)
        else:
            if int(ret[0]) == 1:
                obsfreqlist.append(TestbedResource(testStart,testEnd,int(obsid),'freq_2400'))
            if int(ret[1]) == 1:
                obsfreqlist.append(TestbedResource(testStart,testEnd,int(obsid),'freq_868'))
            if int(ret[2]) == 1:
                obsfreqlist.append(TestbedResource(testStart,testEnd,int(obsid),'freq_433'))

    return obsfreqlist
# END resourceFrequency

##############################################################################
#
# resourceMux
#    generates a list of the mux resources
#
##############################################################################
def resourceMux(testStart,testEnd,obsidlist,tree,ns,config):
    
    # first get the services which use the mux for the whole test
    obsmuxdict = {}
    start = int(testStart) - int(config.get('tests', 'setuptime')) * 60
    end = int(testEnd) + int(config.get('tests', 'cleanuptime')) * 60

    # Check serial configuration
    serial  = tree.xpath('//d:serialConf', namespaces=ns)
    if serial:
        port = tree.xpath('//d:serialConf/d:port', namespaces=ns)
        if port and port[0].text == 'serial':
            obsids = tree.xpath('//d:serialConf/d:obsIds', namespaces=ns)[0].text.split()
            for obsid in obsids:
                obsmuxdict[int(obsid)] = TestbedResource(start,end,int(obsid),'mux')

    # Check gpio tracing configuration
    gpiotracing  = tree.xpath('//d:gpioTracingConf', namespaces=ns)
    if gpiotracing:
        obsids = tree.xpath('//d:gpioTracingConf/d:obsIds', namespaces=ns)[0].text.split()
        for obsid in obsids:
            obsmuxdict[int(obsid)] = TestbedResource(start,end,int(obsid),'mux')

    # Check gpio actuation configuration
    gpioactuation  = tree.xpath('//d:gpioActuationConf', namespaces=ns)
    if gpioactuation:
        obsids = tree.xpath('//d:gpioActuationConf/d:obsIds', namespaces=ns)[0].text.split()
        for obsid in obsids:
            obsmuxdict[int(obsid)] = TestbedResource(start,end,int(obsid),'mux')

    # Check power profiling configuration
    powerProfiling  = tree.xpath('//d:powerProfilingConf', namespaces=ns)
    if powerProfiling:
        obsids = tree.xpath('//d:powerProfilingConf/d:obsIds', namespaces=ns)[0].text.split()
        for obsid in obsids:
            obsmuxdict[int(obsid)] = TestbedResource(start,end,int(obsid),'mux')
            
    # TODO: if DAQ is used
    
    muxlist = []

    for obsid in obsidlist:
        # if the mux is not used for the services above it is only used for setup,start,end and cleanup (except duration is smaller than start + stop time)
        if (not int(obsid) in obsmuxdict):
            duration = testEnd - testStart
            if duration > (int(config.get('tests','guard_starttime')) * 60) + (int(config.get('tests', 'guard_stoptime')) * 60):
                # set mux for setup and start
                muxlist.append(TestbedResource(testStart - int(config.get('tests', 'setuptime')) * 60,testStart + int(config.get('tests','guard_starttime')) * 60,int(obsid),'mux'))
                # set mux for stop and cleanup
                muxlist.append(TestbedResource(testEnd - int(config.get('tests', 'guard_stoptime')) * 60,testEnd + int(config.get('tests','cleanuptime')) * 60,int(obsid),'mux'))
            else:
                # set mux for whole test plus setup and cleanup
                muxlist.append(TestbedResource(testStart - int(config.get('tests', 'setuptime')) * 60,testEnd + int(config.get('tests','cleanuptime')) * 60,int(obsid),'mux'))
    
    for dictres in list(obsmuxdict.values()):
        muxlist.append(dictres)

    return muxlist
# END resourceMux

##############################################################################
#
# schedule
#    returns if the test is schedulable and the start and stop time
#
##############################################################################
def schedule(ASAP,resources,cursor,logger):
    timeStart = time.clock()
    isSchedulable = False
    # create lookup dictionary
    resourcesdict = {}
    for r in resources:
        try:
            l = resourcesdict[(r.obsid, r.restype)]
        except KeyError:
            resourcesdict[(r.obsid, r.restype)] = []
            l = resourcesdict[(r.obsid, r.restype)]
        l.append(r)
    # TODO: Consider reservations as well
    
    # Get all tests which overlap in time
    testStartString = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(min([r.time_start for r in resources])))
    sql = "SELECT `time_start`, `time_end`, `observer_fk`, `resource_type` FROM `tbl_serv_resource_allocation` WHERE (`time_end` >= '%s')" % testStartString
    cursor.execute(sql)
    ret = cursor.fetchall()
    # Now check for all resource usage intervals if they overlap in time with an already scheduled test
    testShift = 0
    while not isSchedulable:
        maxShift = 0 # keep track of largest shift needed to resolve dependencies
        isSchedulable = True
        for i in range(len(ret)):
            # for every ret, check for collisions
            allocated_start = int(calendar.timegm(ret[i][0].timetuple()))
            allocated_end = int(calendar.timegm(ret[i][1].timetuple()))
            for res in resourcesdict[(ret[i][2],ret[i][3])]:
                if(allocated_start <= res.time_start + testShift and allocated_end >= res.time_end + testShift):
                    isSchedulable = False
                    # if not ASAP, break
                    if not ASAP:
                        break
                    else:
                        shift = allocated_end - (res.time_start + testShift)
                        if shift > maxShift:
                            maxShift = shift
            if not ASAP and not isSchedulable:
                break
        if not ASAP and not isSchedulable:
            break
        else:
            # else shift by maxShift and repeat
            testShift = testShift + maxShift + 1
    
    if isSchedulable:
        for i in range(len(resources)):
            resources[i].time_start += testShift
            resources[i].time_end += testShift
                    
    dur = time.clock() - timeStart
    return isSchedulable,testShift,[dur]
# END schedule

##############################################################################
#
# modifyConfig
#    returns the modified configuration file
#
##############################################################################
def modifyConfig(tree,ns,userId,testStart,testEnd,config,cursor):
    nstext = config.get('xml', 'namespace')
    
    # 1) Add embedded images to the db and change the config accordingly
    targetconfs = tree.xpath('//d:targetConf', namespaces=ns)
    for targetconf in targetconfs:
        embimageid = None
        # Get elements:
        ret = targetconf.xpath('d:embeddedImageId', namespaces=ns)
        if ret:
            embimageid = [o.text for o in ret]
            embimageid_line = [o.sourceline for o in ret]

            for embimg, line,embIm in zip(embimageid, embimageid_line,ret):
                imageconf = tree.xpath('//d:imageConf/d:embeddedImageId[text()="%s"]/..' %(embimg), namespaces=ns)
                
                # Get Image Data:
                # Name can be used directly
                name = imageconf[0].xpath('d:name', namespaces=ns)[0].text
                # description can be empty
                description = imageconf[0].xpath('d:description', namespaces=ns)
                if description:
                    description = description[0].text
                else:
                    description = ""
                # for the platform we have to get the fk
                platform = imageconf[0].xpath('d:platform', namespaces=ns)[0].text
                sql = "SELECT serv_platforms_key FROM tbl_serv_platforms WHERE (LOWER(name) = LOWER('%s'))"%platform
                cursor.execute(sql)
                ret = cursor.fetchone()
                if not ret:
                    logger.warn("Error in modifyConfig while getting the platform_fk")
                    sys.exit(errno.EAGAIN)
                else:
                    platform = ret[0]
                # same for the os
                if imageconf[0].xpath('d:os', namespaces=ns):
                    os = imageconf[0].xpath('d:os', namespaces=ns)[0].text
                else:
                    os = 'other'   # os tag is optional and deprecated
                sql = "SELECT serv_operatingsystems_key FROM tbl_serv_operatingsystems WHERE (LOWER(name) = LOWER('%s'))"%os
                cursor.execute(sql)
                ret = cursor.fetchone()
                if not ret:
                    logger.warn("Error in modifyConfig while getting the operatingsystem_fk")
                    sys.exit(errno.EAGAIN)
                else:
                    os = ret[0]
                # get core
                sql = "SELECT core FROM tbl_serv_architectures WHERE (platforms_fk = LOWER('%s'))"%platform
                cursor.execute(sql)
                ret = cursor.fetchone()
                if not ret:
                    logger.warn("Error in modifyConfig while getting the core")
                    sys.exit(errno.EAGAIN)
                else:
                    core = ret[0]
                # get data and create hash
                data = base64.b64decode(imageconf[0].xpath('d:data', namespaces=ns)[0].text.strip())
                imgHash = hashlib.sha1(data).hexdigest()
                # Check if there are dublicates
                sql = """SELECT `serv_targetimages_key`, `binary`
                    FROM `tbl_serv_targetimages`
                    WHERE `owner_fk`='%s'
                    AND `binary` IS NOT NULL 
                    AND `binary_hash_sha1`='%s' 
                    AND `operatingsystems_fk`='%s'
                    AND `platforms_fk`='%s'
                    AND `core`='%s'"""%(userId,imgHash,os,platform,core)
                test = cursor.execute(sql)
                ret = cursor.fetchone()
                if not ret:
                    # Add image to db:
                    sql = """INSERT INTO `tbl_serv_targetimages` (`name`,`description`,`owner_fk`,`operatingsystems_fk`,`platforms_fk`,`core`,`binary`,`binary_hash_sha1`) 
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
                    insertData = (name,description,userId,os,platform,core,data,imgHash)
                    cursor.execute(sql,insertData)
                    if not cursor.lastrowid:
                        logger.warn("Error, couldn't insert image in db")
                        sys.exit(errno.EAGAIN)
                    imageId = int(cursor.lastrowid)
                    logger.debug("Added Image with id %s to db."%imageId)
                else:
                    imageId = ret[0]
                    logger.debug("Dublicate Image with id %s detected."%imageId)
                # Replace embedded image with dbimage
                targetconf.remove(embIm)
                dbImageEntry = etree.Element('{%s}dbImageId'%nstext)
                dbImageEntry.text = str(imageId)
                targetconf.append(dbImageEntry)
                root = tree.getroot()
                root.remove(imageconf[0])

    # 2) Change from ASAP to fixed time if necessary
    genConf = tree.xpath('//d:generalConf', namespaces=ns)[0]
    asap = tree.xpath('//d:generalConf/d:scheduleAsap', namespaces=ns)
    if asap:
        genConf.remove(asap[0])
        absEntry = etree.Element('{%s}scheduleAbsolute'%nstext)
        genConf.append(absEntry)
        start = etree.Element('{%s}start'%nstext)
        start.text = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(testStart))
        absEntry.append(start)
        end = etree.Element('{%s}end'%nstext)
        end.text = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(testEnd))
        absEntry.append(end)
    # to keep right order remove and add email if it exists
    email = tree.xpath('//d:generalConf/d:emailResults', namespaces=ns)
    if email:
        genConf.remove(email[0])
        genConf.append(email[0])
    return tree

# END modifyConfig

##############################################################################
#
# addtesttodb
#    adds test to db including mapping and resource table entries
#
##############################################################################

def addtesttodb(tree,ns,resArrayClean,userId,config,cursor):
    # First add the test to the test db
    title = tree.xpath('//d:generalConf/d:name', namespaces=ns)[0].text
    description = tree.xpath('//d:generalConf/d:name', namespaces=ns)
    if description:
        description = description[0].text
    else:
        description = ""
    start = resArrayClean[0][0] + int(config.get('tests', 'setuptime')) * 60
    start = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start))
    end = resArrayClean[-1][1] - int(config.get('tests', 'cleanuptime')) * 60
    end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end))
    root = tree.getroot()
    config_xml = etree.tostring(root, encoding='utf8', method='xml')
    sql =  """INSERT INTO tbl_serv_tests(title, description,owner_fk,testconfig_xml,time_start_wish,time_end_wish,test_status)
                VALUES (%s,%s,%s,%s,%s,%s,%s)"""
    insertData = (title,description,userId,config_xml,start,end,'planned')
    cursor.execute(sql,insertData)
    if not cursor.lastrowid:
        logger.warn("Error, couldn't insert test in db")
        sys.exit(errno.EAGAIN)
    testId = cursor.lastrowid
    logger.debug("Added test with id %s to tbl_srv_tests"%testId)
    
    # add entries for mapping table
    targetconfs = tree.xpath('//d:targetConf', namespaces=ns)
    for targetconf in targetconfs:
        obsids = targetconf.xpath('d:obsIds', namespaces=ns)[0].text.split()
        imgid = targetconf.xpath('d:dbImageId', namespaces=ns)[0].text
        if not imgid:
            print("ERROR")
        
        for obs in obsids:
            # get observer_fk
            sql = """SELECT serv_observer_key
                    FROM tbl_serv_observer
                    WHERE observer_id=%s"""%(obs)
            test = cursor.execute(sql)
            ret = cursor.fetchone()
            if not ret:
                logger.warn("Couldn't fetch observer key for observer id %s"%obs)
                sys.exit(errno.EAGAIN)
            obsKey = ret[0]
            sql =  """INSERT INTO tbl_serv_map_test_observer_targetimages (observer_fk,test_fk,targetimage_fk,node_id) VALUES (%s,%s,%s,%s)"""
            insertData = (int(obsKey),int(testId),int(imgid),int(obs))
            try:
                cursor.execute(sql,insertData)
                db.commit()
            except:
                logger.warn("Couldn't add mapping for observer %s"%obs)
                sys.exit(errno.EAGAIN)
    logger.debug("Added mapping for observers for test %s to db"%(testId))

    # add entries for resource table
    resources = resArrayClean
    # First get all tests which overlap in time and delete them
    testStartString = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(resArrayClean[0][0]))
    testStopString = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(resArrayClean[-1][1]))
    sql = "SELECT * FROM `tbl_serv_test_resources` WHERE (time_start <= '%s') AND (time_end >= '%s')"%(testStopString,testStartString)
    cursor.execute(sql)
    ret = cursor.fetchall()

    sql = "DELETE FROM `tbl_serv_test_resources` WHERE (time_start <= '%s') AND (time_end >= '%s')"%(testStopString,testStartString)
    cursor.execute(sql)
    
    if not cursor.rowcount == len(ret):
        logger.warn("Couldn't delete from resource table")
        sys.exit(errno.EAGAIN)
        
    # Now check for all resource usage intervals if they overlap in time with an already scheduled test
    for old in ret:
        old = list(old[0:-1])
        old[0] = int(calendar.timegm(time.strptime(str(old[0]), '%Y-%m-%d %H:%M:%S')))
        old[1] = int(calendar.timegm(time.strptime(str(old[1]), '%Y-%m-%d %H:%M:%S')))
        resources.append(old)

    resources = cleanuparray(resources)

    for ts in resources:
        ts[0] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts[0]))
        ts[1] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts[1]))
        ts.append(time.strftime('%Y-%m-%d %H:%M:%S'))
        sql =  """INSERT INTO tbl_serv_test_resources VALUES %r"""%(tuple(ts),)
        cursor.execute(sql)
        db.commit()
        if not cursor.rowcount:
            logger.warn("Couldn't add resources timeslot [%s,%s] for test %s to db"%(ts[0],ts[1],testId))
            sys.exit(errno.EAGAIN)
        logger.debug("Added resources timeslot [%s,%s] for test %s to db"%(ts[0],ts[1],testId))

    logger.debug("Successfully added test with starttime %s and testId %s"%(start,testId))
    return start,testId

# END addtesttodb

###############################################################################
#
# Main
#
##############################################################################
def main(argv):
    # Initialize error counter and set timezone to UTC:
    os.environ['TZ'] = 'UTC'
    time.tzset()

    # Open the log and create logger:
    try:
        logging.config.fileConfig(scriptpath + '/logging.conf')
        logger = logging.getLogger(os.path.basename(__file__))
        logger.debug("Start")
    except:
        syslog.syslog(syslog.LOG_ERR, "%s: Could not open logger because: %s: %s" %(os.path.basename(__file__), str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        
    # Get the config file:
    config = get_config()
    if not config:
        logger.warn("Could not read configuration file. Exiting...")
        sys.exit(errno.EAGAIN)
        
    # Get command line parameters.
    if (not len(sys.argv) == 3):
        logger.warn("Wrong API usage, there has to be exacly two parameters: xmlfilepath and userid")
        sys.exit(errno.EAGAIN)
    userId = sys.argv[2]
    xml = sys.argv[1]    
    logger.debug("XML config filepath is: %s" %xml)

    # Parse XML file
    f = open(xml, 'r')
    parser = etree.XMLParser(remove_comments=True)
    tree = etree.parse(f, parser)
    ns = {'d': 'http://www.flocklab.ethz.ch'}

    ### First get information which all "resource-functions" need: time information and observer ids
    # Get test times
    [testStart,testEnd,testDuration,ASAP] = gettimeslot(tree,ns,config)
    logger.debug("Test start,stop,duration: %s,%s,%s" %(testStart,testEnd,testDuration))
    
    # Connect to the DB:
    try:
        db = MySQLdb.connect(host=config.get('database','host'), user=config.get('database','user'), passwd=config.get('database','password'), db=config.get('database','database')) 
        cursor = db.cursor()
    except:
        logger.warn("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        sys.exit(errno.EAGAIN)

    # Get list of observers
    [obsidlist,obsiddict] = getobsids(tree,ns,cursor)
    logger.debug("Obsidlist: %s" %(obsidlist))

    ### List with all timeslots and resource usages
    resources = []

    # get slot numbers
    resources += resourceSlots(testStart,testEnd,obsidlist,obsiddict,config,cursor)
        
    # get frequencies
    resources += resourceFrequency(testStart,testEnd,obsidlist,obsiddict,cursor)

    # get mux usage
    resources += resourceMux(testStart,testEnd,obsidlist,tree,ns,config)

    ### Scheduling
    tmTot = time.clock()
    isSchedulable,timeshift,timeInf = schedule(ASAP,resources, cursor,logger)
    tmTot = time.clock() - tmTot
    logger.debug("Time for scheduling (%s loops): %s, avg: %s, max: %s, min: %s"%(tmTot,len(timeInf),sum(timeInf)/len(timeInf),max(timeInf),min(timeInf)))

    if isSchedulable:
        logger.debug("Test is schedulable with Starttime %s and Endtime %s" %(testStart + timeshift, testEnd + timeshift))
        # modify xml (asap -> absolute, embeddedimage -> dbimage)
        startTime = testStart + timeshift
        endTime = testEnd + timeshift
        tree = modifyConfig(tree,ns,userId,startTime,endTime,config,cursor)
        ## Add test to db and testmapping to db
        #start,testId = addtesttodb(tree,ns,resArrayClean,userId)
        #db.commit()
        #return True,start,testId
        db.close()
        return True,1,1
    else:
        db.close()
        logger.debug("Test is NOT schedulable.")
        return False,0,0


if __name__ == "__main__":
    isSchedulable,start,testId = main(sys.argv)
    retVal = "%s,%s,%s"%(isSchedulable,start,testId)
    print(isSchedulable)
    print(start)
    print(testId)


