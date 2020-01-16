#!/usr/bin/env python3

import sys, os, smtplib, MySQLdb, configparser, time, re, errno, random, subprocess, string, logging, traceback, numpy, calendar
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from struct import *
import syslog
import logging.config
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders
from email.utils import formatdate, make_msgid
from lxml import etree
import tempfile
from MySQLdb.constants import ER as MySQLErrors
import MySQLdb.cursors

### Global variables ###
# Error code to return if there was no error:
SUCCESS = 0
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
scriptname = "flocklab.py"

# Set timezone to UTC ---
os.environ['TZ'] = 'UTC'
time.tzset()

LOW    = 0
HIGH   = 1
TOGGLE = 2


##############################################################################
#
# get_config - read user.ini and return it to caller.
#
##############################################################################
def get_config(configpath=None):
    global scriptpath
    global scriptname
    """Arguments: 
            configpath
       Return value:
            The configuration object on success
            none otherwise
    """
    if not configpath:
        configpath = scriptpath
    try: 
        config = configparser.SafeConfigParser(comment_prefixes=('#', ';'), inline_comment_prefixes=(';'))
        config.read(configpath + '/config.ini')
    except:
        logger = get_logger()
        logger.error("Could not read %s/config.ini because: %s: %s" %(str(configpath), str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        config = None
    return config
### END get_config()


##############################################################################
#
# get_logger - Open a logger for the caller.
#
##############################################################################
def get_logger(loggername=None, loggerpath=None):
    global scriptpath
    global scriptname
    """Arguments: 
            loggername
            loggerpath
       Return value:
            The logger object on success
            none otherwise
    """
    if not loggerpath:
        loggerpath = scriptpath
    if not loggername:
        loggername = scriptname
    try:
        logging.config.fileConfig(loggerpath + '/logging.conf')
        logger = logging.getLogger(loggername)
        if not logger:
            print("no valid logger received")
    except:
        syslog.syslog(syslog.LOG_ERR, "flocklab.py: error in get_logger(): %s: Could not open logger because: %s: %s" %(str(loggername), str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        logger = None
    return logger
### END get_logger()


##############################################################################
#
# connect_to_db - Connect to the FlockLab database
#
##############################################################################
def connect_to_db(config=None, logger=None):
    # Check the arguments:
    if (not isinstance(config, configparser.SafeConfigParser)):
        return (None, None)
    try:
        cn = MySQLdb.connect(host=config.get('database','host'), user=config.get('database','user'), passwd=config.get('database','password'), db=config.get('database','database'), charset='utf8', use_unicode=True) 
        cur = cn.cursor()
        #cur.execute("SET sql_mode=''")     # TODO check whether this is needed
    except:
        if logger and isinstance(logger, logging.Logger):
            logger.error("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        raise
    return (cn, cur)
### END connect_to_db()


##############################################################################
#
# send_mail - send a mail to the specified user(s)
#
##############################################################################
def send_mail(subject="[FlockLab]", message="", recipients="", attachments=[]):
    """Arguments: 
            subject:     the subject of the message
            message:     the message to be sent
            recipients:  tuple with recipient(s) of the message
            attachments: list of files to attach. Each file has to be an absolute path
       Return value:
            0 on success
            1 if there is an error in the arguments passed to the function
            2 if there was an error processing the function
       """
    
    # Local variables:
    from_address = "flocklab@tik.ee.ethz.ch"
    
    # Check the arguments:
    if ((type(message) != str) or ((type(recipients) != str) and (type(recipients) != list) and (type(recipients) != tuple)) or (type(attachments) != list)):
        return(1)
    # Check if attachments exist in file system:
    if (len(attachments) > 0):
        for path in attachments:
            if not os.path.isfile(path):
                return(1)

    # Create the email:
    mail = MIMEMultipart()
    
    # Attach the message text:
    mail.attach(MIMEText(str(message)))
    
    # Set header fields:
    mail['Subject'] = str(subject)
    mail['From'] = "FlockLab <%s>" % from_address
    mail['Date'] = formatdate(localtime=True)
    mail['Message-ID'] = make_msgid()
    if ((type(recipients) == tuple) or (type(recipients) == list)):
        mail['To'] = ', '.join(recipients)
    elif (type(recipients) == str):
        mail['To'] = recipients
    else:
        return(1)
    
    # If there are attachments, attach them to the email:
    for path in attachments:
        fp = open(path, 'rb')
        fil = MIMEBase('application', 'octet-stream')
        fil.set_payload(fp.read())
        fp.close()
        encoders.encode_base64(fil)
        fil.add_header('Content-Disposition', 'attachment', filename=os.path.basename(path))
        mail.attach(fil)

    # Establish an SMTP object and connect to your mail server
    try:
        s = smtplib.SMTP()
        s.connect("smtp.ee.ethz.ch")
        # Send the email - real from, real to, extra headers and content ...
        s.sendmail(from_address, recipients, mail.as_string())
        s.close()
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    
    return (0)
### END send_mail()



##############################################################################
#
# check_test_id - Check if a test id is present in the flocklab database.
#
##############################################################################
def check_test_id(cursor=None, testid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            testid: test ID which should be checked
       Return value:
            0 if test ID exists in database
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
            3 if test ID does not exist in the database
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(testid) != int) or (testid <= 0)):
        return(1)

    # Check if the test ID is in the database:            
    try:
        # Check if the test ID exists in tbl_serv_tests.serv_tests_key
        cursor.execute("SELECT COUNT(serv_tests_key) FROM `tbl_serv_tests` WHERE serv_tests_key = %d" %testid)
        rs = cursor.fetchone()[0]
        
        if (rs == 0):
            return(3)
        else: 
            return(0)
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
### END check_test_id()


##############################################################################
#
# get_test_obs - Get all observer IDs, keys and node IDs which are used in a test.
#
##############################################################################
def get_test_obs(cursor=None, testid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            testid: test ID
       Return value:
            Dictionary with observer IDs, keys and node IDs
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
    """
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(testid) != int) or (testid <= 0) or (check_test_id(cursor, testid) != 0)):
        return 1

    try:
        cursor.execute("SELECT `a`.serv_observer_key, `a`.observer_id, `b`.node_id \
FROM tbl_serv_observer AS `a` \
LEFT JOIN tbl_serv_map_test_observer_targetimages AS `b` \
ON `a`.serv_observer_key = `b`.observer_fk \
WHERE `b`.test_fk = %d \
ORDER BY `a`.observer_id" %testid)
        rs = cursor.fetchall()
        
        obsdict_bykey = {}
        obsdict_byid = {}
        for row in rs:
            obsdict_bykey[row[0]] = (row[1], row[2])
            obsdict_byid[row[1]] = (row[0], row[2])
        return (obsdict_bykey, obsdict_byid)
            
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return 2
### END get_test_obs()


##############################################################################
#
# get_fetcher_pid - Returns the process ID of the oldest running fetcher.
#
##############################################################################
def get_fetcher_pid(testid):
    try:
        searchterm = "flocklab_fetcher.py (.)*-(-)?t(estid=)?%d"%(testid)
        cmd = ['pgrep', '-o', '-f', searchterm]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, err = p.communicate()
        if (p.returncode == 0):
            return int(out)
        else:
            return -1
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return -2


##############################################################################
#
# get_test_owner - Get information about the owner of a test
#
##############################################################################
def get_test_owner(cursor=None, testid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            testid: test ID
       Return value:
            On success, tuple with information
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """

    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(testid) != int) or (testid <= 0)):
        return(1)
    
    try:
        sql = "    SELECT `a`.serv_users_key, `a`.lastname, `a`.firstname, `a`.username, `a`.email, `a`.disable_infomails \
                FROM tbl_serv_users AS `a` \
                LEFT JOIN tbl_serv_tests AS `b` \
                    ON `a`.serv_users_key = `b`.owner_fk WHERE `b`.serv_tests_key=%d;"
        cursor.execute(sql %testid)
        rs = cursor.fetchone()
        
        return (rs[0], rs[1], rs[2], rs[3], rs[4], rs[5])    
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return (2)
### END get_test_owner()



##############################################################################
#
# get_pinmappings - Get all pin mappings from the database
#
##############################################################################
def get_pinmappings(cursor=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
       Return value:
            Dictionary with pin number, pin_name
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request

       """
    if ((type(cursor) != MySQLdb.cursors.Cursor)):
        return 1
            
    try:
        cursor.execute("SELECT `a`.`pin_number`, `a`.`pin_name` , `b`.`service` \
                        FROM `tbl_serv_pinmappings` AS `a` \
                            LEFT JOIN `tbl_serv_services` AS `b` \
                            ON `a`.`services_fk` = `b`.`serv_services_key` \
                        ")
        rs = cursor.fetchall()
        
        pindict = {}
        for row in rs:
            pindict[row[0]] = (row[1], row[2])
        if len(pindict) == 0:
            raise
        return pindict
            
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return 2
### END get_pinmappings()



##############################################################################
#
# get_servicemappings - Get all service mappings from the database
#
##############################################################################
def get_servicemappings(cursor=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
       Return value:
            Dictionary with mappings
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request

       """
    if ((type(cursor) != MySQLdb.cursors.Cursor)):
        return 1
        
    try:
        cursor.execute("SELECT `serv_services_key`, `service`, `abbreviation` FROM `tbl_serv_services`")
        rs = cursor.fetchall()
        
        servicedict = {}
        for row in rs:
            servicedict[row[0]] = (row[1], row[2])
        return servicedict
            
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return 2
### END get_servicemappings()


##############################################################################
#
# get_slot - Get slot for specific observer and platform from the database
#
##############################################################################
def get_slot(cursor=None, obs_fk=None, platname=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            obs_fk: key of the observer which has to be queried
            platname: name of the platform which the slot has to host  
       Return value:
            slot number on success
            0 if no suitable slot was found
            -1 if there is an error in the arguments passed to the function
            -2 if there was an error in processing the request

       """
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(obs_fk) != int) or (type(platname) != str)):
        return -1
        
    try:
        # First, get a list of all possible adapt_list keys:
        sql =    """    SELECT `l`.`serv_tg_adapt_list_key` FROM `tbl_serv_tg_adapt_types` AS `t` 
                    LEFT JOIN `tbl_serv_platforms` AS `p` 
                        ON `t`.`platforms_fk` = `p`.`serv_platforms_key` 
                    LEFT JOIN `tbl_serv_tg_adapt_list` AS `l` 
                        ON `l`.`tg_adapt_types_fk` = `t`.`serv_tg_adapt_types_key` 
                    WHERE LOWER(p.name) = '%s' 
                """ 
        cursor.execute(sql%(platname))
        ret = cursor.fetchall()
        al_keys = []
        for r in ret:
            al_keys.append(r[0])
        # Now get all adapt_list FK's used on the particular observer and see if there is a match:
        sql =    """    SELECT `slot_1_tg_adapt_list_fk`, `slot_2_tg_adapt_list_fk`, `slot_3_tg_adapt_list_fk`, `slot_4_tg_adapt_list_fk` 
                    FROM `tbl_serv_observer`
                    WHERE `serv_observer_key` = %d
                """ 
        cursor.execute(sql%(obs_fk))
        slotlist = cursor.fetchone()
        slot = None
        if (slotlist[0] in al_keys):
            slot = 1
        elif (slotlist[1] in al_keys):
            slot = 2
        elif (slotlist[2] in al_keys):
            slot = 3
        elif (slotlist[3] in al_keys):
            slot = 4
        if not slot:
            slot = 0
        return slot
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return -2
### END get_slot()



##############################################################################
#
# get_slot_calib - Get calibration values for a slot
#
##############################################################################
def get_slot_calib(cursor=None, obsfk=None, testid=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            obsfk: observer key
            testid: Test key  
       Return value:
            tuple with calibration values on success (0,1) if none were found
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(obsfk) != int) or (type(testid) != int)):
        return 1
        
    try:
        # First, get a list of all possible adapt_list keys:
        sql =    """    SELECT 1000*`c`.`offset`, `c`.`factor` 
                    FROM tbl_serv_map_test_observer_targetimages AS `b` 
                    LEFT JOIN tbl_serv_observer_slot_calibration AS `c` 
                        ON (`b`.slot = `c`.slot) AND (`b`.observer_fk = `c`.observer_fk)
                    WHERE (`b`.test_fk = %d) AND (`b`.observer_fk = %d);
                """ 
        cursor.execute(sql%(testid, obsfk))
        offset, factor = cursor.fetchone()
        if (offset == None):
            offset = 0.0
        if (factor== None):
            factor = 1.0
        return (float(offset), float(factor))
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return -2
### END get_slot_calib()


##############################################################################
#
# get_obs_from_id - Get information about an observer from its ID
#
##############################################################################
def get_obs_from_id(cursor=None, obsid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            testid: observer ID
       Return value:
            On success, tuple with information
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """

    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(obsid) != int) or (obsid <= 0)):
        return(1)
    
    try:
        sql = "    SELECT `ethernet_address`, `status` \
                FROM `tbl_serv_observer` \
                WHERE `observer_id`=%d;"
        cursor.execute(sql %obsid)
        rs = cursor.fetchone()
        
        return (rs[0], rs[1])
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return (2)
### END get_obs_from_id()



##############################################################################
#
# check_observer_id - Check if an observer id is present in the flocklab 
#     database and return its key if present.
#
##############################################################################
def check_observer_id(cursor=None, obsid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            obsid:  observer ID which should be checked
       Return value:
            key if observer ID exists in database
            -1 if there is an error in the arguments passed to the function
            -2 if there was an error in processing the request
            -3 if observer ID does not exist in the database
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(obsid) != int) or (obsid <= 0)):
        return(1)

    # Check if the test ID is in the database:            
    try:
        # Check if the test ID exists in tbl_serv_tests.serv_tests_key
        cursor.execute("SELECT serv_observer_key FROM `tbl_serv_observer` WHERE observer_id = %d" %obsid)
        rs = cursor.fetchone()
        
        if (rs == None):
            return(-3)
        else: 
            return(rs[0])
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(-2)
### END check_observer_id()


##############################################################################
#
# set_test_status - Set the status of a test in the flocklab database.
#
##############################################################################
def set_test_status(cursor=None, conn=None, testid=0, status=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            conn:   database connection
            testid: test ID for which the status is to be set
       Return value:
            0 on success
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(conn) != MySQLdb.connections.Connection) or (type(testid) != int) or (testid <= 0)):
        return(1)
    # Get all possible test stati and check the status argument:
    try:
        cursor.execute("SHOW COLUMNS FROM `tbl_serv_tests` WHERE Field = 'test_status'")
        possible_stati = cursor.fetchone()[1][5:-1].split(",")
        if ("'%s'"%status not in possible_stati):
            return(1)
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)

    # Set the status in the database            
    try:
        cursor.execute("UPDATE `tbl_serv_tests` SET `test_status` = '%s', `dispatched` = 0 WHERE `serv_tests_key` = %d;" %(status, testid))
        conn.commit()
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    return(0)
### END set_test_status()


##############################################################################
#
# get_test_status - Get the status of a test in the flocklab database.
#
##############################################################################
def get_test_status(cursor=None, conn=None, testid=0):
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(conn) != MySQLdb.connections.Connection) or (type(testid) != int) or (testid <= 0)):
        return -1

    # Get the status in the database
    try:
        # To read changed values directly, one needs to change the isolation level to "READ UNCOMMITTED"
        cursor.execute("SELECT @@session.tx_isolation")
        isolation_old = cursor.fetchone()[0]
        if isolation_old != 'READ-UNCOMMITTED':
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            conn.commit()
        # Now get the value:
        cursor.execute("SELECT `test_status` FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d;" %testid)
        status = cursor.fetchone()[0]
        # Reset the isolation level:
        if isolation_old != 'READ-UNCOMMITTED':
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL %s"%(str.replace(isolation_old, '-', ' ')))
            conn.commit()
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return -2
    return status
### END get_test_status()

##############################################################################
#
# set_test_dispatched - Set the dispatched flag of a test in the flocklab database.
#
##############################################################################
def set_test_dispatched(cursor=None, conn=None, testid=0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            conn:   database connection
            testid: test ID for which the status is to be set
       Return value:
            0 on success
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(conn) != MySQLdb.connections.Connection) or (type(testid) != int) or (testid <= 0)):
        return(1)

    # Set the flag in the database            
    try:
        cursor.execute("UPDATE `tbl_serv_tests` SET `dispatched` = 1 WHERE `serv_tests_key` = %d;" %(testid))
        conn.commit()
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    return(0)
### END set_test_dispatched()

##############################################################################
#
# acquire_db_lock - try to get db lock on the specified key
# this is a blocking operation.
#
##############################################################################
def acquire_db_lock(cursor, conn, key, expiry_time=10):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            conn:   database connection
            key: key to lock
       """
    try:
        spin = True
        while spin:
            spin = False
            try:
                cursor.execute("DELETE FROM `tbl_serv_locks` WHERE (`name`='%s' AND `expiry_time` < now());" %(key))
                conn.commit() # this is needed to release a potential shared lock on the table
                cursor.execute("INSERT INTO `tbl_serv_locks` (`name`, `expiry_time`) values ('%s', now() + %d);" %(key, expiry_time))
                conn.commit()
            except MySQLdb.IntegrityError:
                time.sleep(1)
                spin = True
            except MySQLdb.OperationalError as e: # retry if deadlock
                if e.args[0] == MySQLErrors.LOCK_DEADLOCK:
                    time.sleep(1)
                    spin = True
                else:
                    raise
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        raise
    return(0)
### END acquire_db_lock()

##############################################################################
#
# release_db_lock - release db lock on the specified key
#
##############################################################################
def release_db_lock(cursor, conn, key, expiry_time=10):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            conn:   database connection
            key: key to lock
       """
    spin = True
    try:
        while spin:
            spin = False
            try:
                cursor.execute("DELETE FROM `tbl_serv_locks` WHERE (`name`='%s');" %(key))
                conn.commit()
            except MySQLdb.OperationalError as e: # retry if deadlock
                if e.args[0] == MySQLErrors.LOCK_DEADLOCK:
                    time.sleep(1)
                    spin = True
                else:
                    raise
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    return(0)
### END release_db_lock()

##############################################################################
#
# write_errorlog - Writes a message to the errorlog table tbl_serv_errorlog.
#
##############################################################################
def write_errorlog(cursor=None, conn=None, testid=0, obsid=0, message="", timestamp=0.0):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
            conn:   database connection
            testid: test ID
            obsid: observer ID
            message: message to write to the database
       Return value:
            0 on success
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(conn) != MySQLdb.connections.Connection) or (type(testid) != int) or (type(obsid) != int) or (type(message) != str) or (len(message) <= 0) or (type(timestamp) != float) or (timestamp < 0.0)):
        return(1)
    if ((testid != 0) and (check_test_id(cursor, testid) != 0)):
        return(1)
    if ((obsid != 0) and (check_observer_id(cursor, obsid) <= 0)):
        return(1)
    else: 
        obskey = check_observer_id(cursor, obsid)
    
    # Prepare timestamp:
    if (timestamp <= 0.0):
        timestamp = time.time()

    # Set the status in the database
    sql = "INSERT INTO `tbl_serv_errorlog` (`errormessage`, `timestamp`, `test_fk`, `observer_fk`) VALUES ('%s', %f" %(re.escape(message), timestamp)
    if testid != 0:
        sql += ", %d"%testid
    else:
        sql += ", NULL"
    if obsid != 0:
        sql += ", %d"%obskey
    else:
        sql += ", NULL"
    sql += ");"
    try:
        cursor.execute(sql)
        conn.commit()
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("Error when executing %s: %s: %s" %(sql, str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return(2)
    return(0)
### END write_errorlog()



##############################################################################
#
# error_logandexit - Logs an error (to log and email to admins) and exits the script
#
##############################################################################
def error_logandexit(message=None, exitcode=SUCCESS, scriptname="", logger=None, config=None):
    """Arguments: 
            message:    error message to log
            exitcode:    code to exit with
            scriptname:    name of script which calls the function
            logger:        logger instance to log to
            config:        config instance
       Return value:
            none on success
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(message) != str) or (type(exitcode) != int) or (type(scriptname) != str) or ((logger != None) and (not isinstance(logger, logging.Logger))) or ((config != None) and (not isinstance(config, configparser.SafeConfigParser)))):
        return(1)
    # Required arguments:
    if (message == ""):
        return(1)

    # Log error - if available, use logger, otherwise get it first:
    if logger:
        logger.error(message)
    else:
        logger = get_logger(loggername=scriptname)
        logger.error(message)
    
    
    # Send email to admin:
    try:
        cn, cur = connect_to_db(config, logger)
        admin_emails = get_admin_emails(cur, config)
        cur.close()
        cn.close()
        if ((admin_emails == 1) or (admin_emails == 2)):
            msg = "Error when getting admin emails from database"
            if logger:
                logger.error(msg)
            else:
                logger = get_logger()
                logger.error(msg)
            raise
    except:
        # Use backup email address:
        admin_emails = "flocklab@tik.ee.ethz.ch"
    finally:
        send_mail(subject="[FlockLab %s]"%(scriptname.capitalize()), message=message, recipients=admin_emails)
        
    # Exit program
    logger.debug("Exiting with error code %u." % exitcode)
    sys.exit(exitcode)
### END error_logandexit()



##############################################################################
#
# count_running_instances - Check how many instances of a script are running  
#
##############################################################################
def count_running_instances(scriptname=None):
    """Arguments: 
            scriptname:    name of script to check
       Return value:
            Count on success
            -1 if there is an error in the arguments passed to the function
            -2 if there was an error in processing the request
       """
    # Check the arguments:
    if ((type(scriptname) != str) or (len(scriptname) <= 0)):
        return(-1)

    cmd = ['pgrep', '-l', '-f', scriptname]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    out, err = p.communicate()
    if (p.returncode == 0):
        # If a script is called from a cronjob, this will add an additional line in pgrep which needs to be filtered.
        count = 0
        for line in out.split('\n'):
            if ((len(line) > 0) and (line.find('python') != -1)):
                count += 1
        # Return the total instance count (including the instance which called this function):
        return count
    else:
        return(-2)
### END count_running_instances()



##############################################################################
#
# get_admin_emails - Get the email addresses of all admins from the FlockLab 
#    database
#
##############################################################################
def get_admin_emails(cursor=None, config=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
       Return value:
            On success, a list with all admin email addresses if successful, an empty list if no addresses were found
            1 if there is an error in the arguments passed to the function
            2 if there was an error in processing the request
       """
    # Local variables:   
    email_list = []
    
    if (not isinstance(config, configparser.SafeConfigParser)) or (not config.has_option('general', 'admin_email')):
    
        # Check the arguments:
        if (type(cursor) != MySQLdb.cursors.Cursor):
            return(1)

        # Get the addresses from the database:            
        try:
            cursor.execute("SELECT `email` FROM `tbl_serv_users` WHERE `role` = 'admin'")
            rs = cursor.fetchall()
            for mail in rs:
                email_list.append(mail[0])
        except:
            # There was an error in the database connection:
            logger = get_logger()
            logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
            return(2)
            
    else:
            email_list.append(config.get('general','admin_email'))
    
    return(email_list)
### END get_admin_emails()



##############################################################################
#
# is_test_running - Check in the FlockLab database if a test is running or
#                    not. This also includes other test states such as 
#                    preparing, cleaning up, aborting...
#
##############################################################################
def is_test_running(cursor=None):
    """Arguments: 
            cursor: cursor of the database connection to be used for the query
       Return value:
            True if a test is running
            False if no test is running
            None otherwise
       """
    if not cursor:
        return None
    
    try:
        cursor.execute("SELECT COUNT(serv_tests_key) FROM tbl_serv_tests WHERE test_status IN('preparing', 'running', 'aborting', 'cleaning up');")
        rs = cursor.fetchone()
        if rs[0] != 0:
            return True
        else:
            return False
    except:
        logger = get_logger()
        logger.error("%s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return None
### is_test_running())

            
def viz_plot(t, d, testdir, obsid, imgdir):
    fig = Figure(figsize=(2*(t[len(t)-1] - t[0]), 1))
    ax = fig.add_axes([0., 0., 1., 1.])
    ax.patch.set_facecolor(None)
    fig.patch.set_alpha(0.)
    ax.set_frame_on(False)
    ax.axes.get_yaxis().set_visible(False)
    ax.axes.get_xaxis().set_visible(False)
    canvas = FigureCanvasAgg(fig)    
    ax.plot(t, d, '-', color = '#001050', linewidth=2)
    ax.axis((t[0], t[len(t)-1], -1, 40))
    canvas.get_renderer().clear() 
    canvas.draw()
    try:
        os.makedirs('%s/%s' % (imgdir, testdir))
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    canvas.print_figure('%s/%s/power_%d_%d.png' % (imgdir, testdir, obsid, t[0]*1e3), pad_inches=0, dpi=50, transparent=True)

def viz_powerprofiling(testid, owner_fk, values, obsid, imgdir, logger):
    #logger.debug("Viz %i values" % len(values[0]))
    # samples, count, start, end
    t=[]
    d=[]
    try:
        if len(values[0]) != len(values[1]):
            raise Exception("Could not process data, timestamp count and value count must be equal.")
        for i in range(len(values[0])): # packets
            start = time.time()
            t.extend(values[0][i])
            d.extend(values[1][i])
            if t[0] is None:
                logger.warn("first timestamp in list is none.")
            if t[-1] is None:
                logger.warn("last timestamp in list is none.")
            if t[-1] < t[0]:
                logger.warn("timestamps are not propperly ordered. t[0]: %f, t[-1]: %f." % (t[0], t[-1]))
            if (t[-1]-t[0] >= 2) | (i==len(values[0])-1):
                try:
                    viz_plot(t, d, "%d_%d"%(testid, owner_fk), obsid, imgdir)
                except:
                    msg = "Viz error: %s: %s, data t: %f .. %f size(t)=%d" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]),t[0],t[-1],len(t))
                    msg = msg.join(traceback.format_list(traceback.extract_tb(sys.exc_info()[2])))
                    logger.error(msg)
                t=[]
                d=[]
            #logger.debug("Viz time spent %f" % (time.time() - start))
    except: 
        logger.error("Error in viz_powerprofiling: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))

def viz_gpio_monitor(testid, owner_fk, values, obsid, imgdir, logger):
    # gpio; edge; timestamp;
    # print max time int values per file to gpiom_<obsid>_<starttime>.json
    try:
        os.makedirs('%s/%d_%d' % (imgdir, testid, owner_fk))
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    starttime = 0
    try:
        for i in range(len(values)):
            e = values[i]
            if starttime == 0:
                starttime = float(e[2])
                f = open('%s/%d_%d/gpiom_%d_%d.json' % (imgdir, testid, owner_fk, obsid, 1e3 * starttime), 'w')
                f.write('{"e":[')
            if (float(e[2]) - starttime > 5) or (i==len(values)-1):
                f.write('{"t":%d,"p":%s,"l":%s}\n' % (int(round((float(e[2]) - starttime) * 1e3)), e[0], e[1]))
                f.write(']}\n')
                f.close()
                starttime = 0
            else:
                f.write('{"t":%d,"p":%s,"l":%s},\n' % (int(round((float(e[2]) - starttime) * 1e3)), e[0], e[1]))
    except: 
        logger.error("Error in viz_gpio_monitor: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
    


##############################################################################
#
# scheduleLinkTest - try to schedule a link test for every platform, according to config file
#
##############################################################################
        
def scheduleLinkTest(logger, config, cur, cn, debug=False):
    # Check the arguments:
    if ((type(cur) != MySQLdb.cursors.Cursor) or (type(cn) != MySQLdb.connections.Connection)):
        return(1)
    
    sql = "SELECT TIMESTAMPDIFF(MINUTE, `begin`, NOW()) AS `last` FROM `tbl_serv_web_link_measurements` ORDER BY `last` ASC LIMIT 1"
    cur.execute(sql)
    rs = cur.fetchone()
    if rs:
        lasttest = int(rs[0])
        logger.debug("Last link measurement was %s minutes ago."%(lasttest))
        nexttest = 60 * config.getint("linktests", "interval_hours") + random.randint(-config.getint("linktests", "interval_random_minutes"), config.getint("linktests", "interval_random_minutes"))
        
        if lasttest >= nexttest:
            # Schedule new tests
            # Check if the lockfile is present:
            lockfile = config.get("linktests", "lockfile")
            if os.path.exists(lockfile):
                logger.debug("Lockfile %s exists already. Skip adding new linktests.")
                # If the last scheduled link tests are a long time ago, generate a warning since it may be that the lockfile was not deleted for whatever reason:
                if lasttest > 2*nexttest:
                    logger.error("Lockfile %s exists and the last linktest was %d min ago (interval is %d min)"%(lockfile, lasttest, config.getint("linktests", "interval_hours")))
            else:
                # Create the lockfile:
                basedir = os.path.dirname(lockfile)
                if not os.path.exists(basedir):
                    os.makedirs(basedir)
                open(lockfile, 'a').close()
                logger.debug("Touched lockfile %s"%lockfile)
                
                # Schedule new tests
                logger.debug("Schedule new link measurements")
                listing = os.listdir(config.get("linktests", "testfolder"))
                for linktestfile in listing:
                    if re.search("\.xml$", os.path.basename(linktestfile)) is not None:
                        # read platform
                        parser = etree.XMLParser(remove_comments=True)
                        tree = etree.parse("%s/%s" % (config.get("linktests", "testfolder"),linktestfile), parser)
                        ns = {'d': config.get('xml', 'namespace')}
                        pl = tree.xpath('//d:platform', namespaces=ns)
                        platform = pl[0].text.strip()
                        # get available observers with that platform from DB
                        sql = """SELECT LPAD(obs.observer_id, 3, '0') as obsid
                                FROM `flocklab`.`tbl_serv_observer` AS obs 
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS a ON obs.slot_1_tg_adapt_list_fk = a.serv_tg_adapt_list_key 
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot1 ON a.tg_adapt_types_fk = slot1.serv_tg_adapt_types_key
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS b ON obs.slot_2_tg_adapt_list_fk = b.serv_tg_adapt_list_key 
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot2 ON b.tg_adapt_types_fk = slot2.serv_tg_adapt_types_key
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS c ON obs.slot_3_tg_adapt_list_fk = c.serv_tg_adapt_list_key 
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot3 ON c.tg_adapt_types_fk = slot3.serv_tg_adapt_types_key
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS d ON obs.slot_4_tg_adapt_list_fk = d.serv_tg_adapt_list_key 
                                LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot4 ON d.tg_adapt_types_fk = slot4.serv_tg_adapt_types_key
                                WHERE
                                obs.status = 'online' AND (
                                LOWER(slot1.name) = LOWER('%s') OR
                                LOWER(slot2.name) = LOWER('%s') OR
                                LOWER(slot3.name) = LOWER('%s') OR
                                LOWER(slot4.name) = LOWER('%s'))
                                ORDER BY obs.observer_id""" % (platform,platform,platform,platform)
                        cur.execute(sql)
                        ret = cur.fetchall()
                        if not ret:
                            logger.info("Target platform %s not available, skipping link test." % platform)
                            continue
                        logger.debug("Observers with platform %s: %s" %(platform,' '.join([x[0] for x in ret])))
                        obsIdTags = tree.xpath('//d:obsIds', namespaces=ns)
                        for o in obsIdTags:
                            o.text = ' '.join([x[0] for x in ret])
                        targetIdTags = tree.xpath('//d:targetIds', namespaces=ns)
                        for o in targetIdTags:
                            o.text = ' '.join(map(str,list(range(len(ret)))))
                        # generate temporary test config
                        (fd, xmlpath) = tempfile.mkstemp(suffix='.xml')
                        tree.write(xmlpath, xml_declaration=True, encoding="UTF-8")
                        logger.info("add link test: %s" % linktestfile)
                        cmd = [config.get("linktests", "starttest_script"), '-c', "%s" % xmlpath]
                        
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, cwd=os.path.dirname(config.get("linktests", "starttest_script")))
                        out, err = p.communicate()
                        rs = p.wait()
                        testid = re.search("Test ID: ([0-9]*)",out)
                        if (testid is None) | (rs != SUCCESS):
                            logger.error("Could not register link test %s (%s)" % (linktestfile,err))
                        else:
                            # flag in db
                            sql = "INSERT INTO `tbl_serv_web_link_measurements` (test_fk, begin, end, platform_fk, links) \
                                SELECT %s, NOW(), NOW(), serv_platforms_key, NULL from tbl_serv_platforms WHERE serv_platforms_key = (SELECT `b`.platforms_fk FROM \
                                flocklab.tbl_serv_map_test_observer_targetimages as `a` left join \
                                flocklab.tbl_serv_targetimages as `b` ON (a.targetimage_fk = b.serv_targetimages_key) WHERE `a`.test_fk=%s ORDER BY serv_platforms_key LIMIT 1)"% (testid.group(1), testid.group(1))
                            cur.execute(sql)
                            cn.commit()
                        os.remove(xmlpath)
                # Delete the lockfile:
                os.remove(lockfile)
                logger.debug("Removed lockfile %s"%lockfile)
    
##############################################################################
#
# getXmlTimestamp
# Converts XML timestamps to python taking timezone into account.
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
      timestamp = timestamp + offset
    else:
      timestamp = timestamp - offset
  return timestamp
### END getXmlTimestamp()

