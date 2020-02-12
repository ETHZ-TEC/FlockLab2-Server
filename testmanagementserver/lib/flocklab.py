#!/usr/bin/env python3

##############################################################################
# FlockLab library, runs on the test management server
##############################################################################

import sys, os, smtplib, MySQLdb, MySQLdb.cursors, configparser, time, re, errno, random, subprocess, string, logging, logging.config, traceback, numpy, calendar, matplotlib.figure, matplotlib.backends.backend_agg, tempfile, lxml.etree
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders
from email.utils import formatdate, make_msgid

### Global variables ###
SUCCESS = 0
FAILED  = -2    # note: must be negative, and -1 (= 255) is reserved for SSH error
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
scriptname = os.path.basename(os.path.abspath(sys.argv[0]))   # name of caller script
configfile = "/home/flocklab/flocklab_config.ini"
loggerconf = scriptpath + '/logging.conf'
config = None
logger = None
debug = True

# Set timezone to UTC ---
os.environ['TZ'] = 'UTC'
time.tzset()


##############################################################################
#
# log_fallback - a way to log errors if the regular log file is unavailable
#
##############################################################################
def log_fallback(msg):
    #syslog.syslog(syslog.LOG_ERR, msg)    # -> requires 'import syslog'
    #print(msg, file=sys.stderr)
    print(msg)
### END log_fallback()


##############################################################################
#
# load_config - loads the config from the ini file and stores it in a global variable
#
##############################################################################
def load_config():
    global config
    if config:
        if logger:
            logger.warn("Config already loaded")
        return SUCCESS
    config = get_config()
    if not config:
        error_logandexit("Could not load config file.")
### END load_config()


##############################################################################
#
# get_config - read config file and return it to caller.
#
##############################################################################
def get_config():
    global config
    # if already loaded, return
    if config:
        return config
    try:
        config = configparser.SafeConfigParser(comment_prefixes=('#', ';'), inline_comment_prefixes=(';'))
        config.read(configfile)
    except:
        logger = get_logger()
        logger.error("Could not read '%s' because: %s, %s" % (configfile, str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        config = None
    return config
### END get_config()


##############################################################################
#
# init_logger - Open a logger and keep it in a global variable.
#
##############################################################################
def init_logger(loggername=scriptname):
    global logger
    if logger:
        logger.warn("Logger already initialized.")
        return SUCCESS        # already initialized
    logger = get_logger(loggername)
    if not logger:
        error_logandexit("Failed to init logger.")
### END init_logger()


##############################################################################
#
# get_logger - Open a logger for the caller.
#
##############################################################################
def get_logger(loggername=scriptname, debug=False):
    global logger
    # if it already exists, return logger
    if logger:
        return logger
    if not os.path.isfile(loggerconf):
        log_fallback("[FlockLab] File '%s' not found." % (loggerconf))
        return None
    try:
        logging.config.fileConfig(loggerconf)
        logger = logging.getLogger(loggername)
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    except:
        log_fallback("[FlockLab %s] Could not open logger because: %s, %s" %(str(loggername), str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        logger = None
    return logger
### END get_logger()


##############################################################################
#
# logging helpers
#
##############################################################################
def log_info(msg=""):
    global logger
    logger.info(msg)
### END log_info()

def log_error(msg=""):
    global logger
    logger.error(msg)
### END log_error()

def log_warning(msg=""):
    global logger
    logger.warn(msg)
### END log_warning()

def log_debug(msg=""):
    global logger
    logger.debug(msg)
### END log_debug()


##############################################################################
#
# connect_to_db - Connect to the FlockLab database
#
##############################################################################
def connect_to_db():
    global config
    # if config not yet available, then load it
    if not config or not isinstance(config, configparser.SafeConfigParser):
        load_config()
    try:
        cn = MySQLdb.connect(host=config.get('database','host'), user=config.get('database','user'), passwd=config.get('database','password'), db=config.get('database','database'), charset='utf8', use_unicode=True) 
        cur = cn.cursor()
        #cur.execute("SET sql_mode=''")     # TODO check whether this is needed
    except:
        logger = get_logger()
        logger.error("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        raise Exception
    return (cn, cur)
### END connect_to_db()


##############################################################################
#
# is_user_admin - Check if a user ID belongs to an admin.
#
##############################################################################
def is_user_admin(cursor=None, userid=0):
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(userid) != int) or (userid <= 0)):
        return False
    # Get the addresses from the database:
    try:
        cursor.execute("SELECT `role` FROM `tbl_serv_users` WHERE `serv_users_key` = %d" %userid)
        rs = cursor.fetchone()
        if ((rs != None) and (rs[0] == 'admin')):
            return True
    except:
        logger = get_logger()
        logger.error("Failed to fetch user role from database: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return False
    return False
### END is_user_admin()


##############################################################################
#
# is_user_internal - Check if an ID belongs to an internal user.
#
##############################################################################
def is_user_internal(cursor=None, userid=0):
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(userid) != int) or (userid <= 0)):
        return False
    # Get the addresses from the database:
    try:
        cursor.execute("SELECT `role` FROM `tbl_serv_users` WHERE `serv_users_key` = %d" %userid)
        rs = cursor.fetchone()
        if ((rs != None) and (rs[0] == 'internal')):
            return True
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("Failed to fetch user role from database: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return False
    return False
### END is_user_internal()


##############################################################################
#
# get_user_role - Get the user role (user, admin or internal).
#
##############################################################################
def get_user_role(cursor=None, userid=0):
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(userid) != int) or (userid <= 0)):
        return None
    # Get the addresses from the database:
    try:
        cursor.execute("SELECT `role` FROM `tbl_serv_users` WHERE `serv_users_key` = %d" % userid)
        rs = cursor.fetchone()
        if rs:
            return rs[0]
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("Failed to fetch user role from database: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return None
    return None
### END get_user_role()


##############################################################################
#
# send_mail - send a mail to the specified user(s)
#
##############################################################################
def send_mail(subject="[FlockLab]", message="", recipients="", attachments=[]):
    if not config:
        return FAILED
    # Check the arguments:
    if ((type(message) != str) or ((type(recipients) != str) and (type(recipients) != list) and (type(recipients) != tuple)) or (type(attachments) != list)):
        return FAILED
    # Check if attachments exist in file system:
    if (len(attachments) > 0):
        for path in attachments:
            if not os.path.isfile(path):
                return FAILED

    # Create the email:
    mail = MIMEMultipart()
    
    # Attach the message text:
    mail.attach(MIMEText(str(message)))
    
    # Set header fields:
    mail['Subject'] = str(subject)
    mail['From'] = "FlockLab <%s>" % config.get('email', 'flocklab_email')
    mail['Date'] = formatdate(localtime=True)
    mail['Message-ID'] = make_msgid()
    if ((type(recipients) == tuple) or (type(recipients) == list)):
        mail['To'] = ', '.join(recipients)
    elif (type(recipients) == str):
        mail['To'] = recipients
    else:
        return FAILED
    
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
        s.connect(config.get('email', 'mailserver'))
        # Send the email - real from, real to, extra headers and content ...
        s.sendmail(config.get('email', 'flocklab_email'), recipients, mail.as_string())
        s.close()
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
    
    return (0)
### END send_mail()


##############################################################################
#
# batch_send_mail - send a mail to several users (if recipient list empty, mail will be sent to all active users) with 10s delay, can be aborted with ctrl+c
#
##############################################################################
def batch_send_mail(subject="[FlockLab]", message="", recipients=[], attachments=[]):
    if not message:
        return
    if not recipients:
        # no email provided -> extract all addresses from the database
        try:
          config = flocklab.get_config()
          logger = flocklab.get_logger()
          (cn, cur) = flocklab.connect_to_db()
          cur.execute("""SELECT email FROM `tbl_serv_users` WHERE is_active=1;""")
          ret = cur.fetchall()
          if not ret:
              logger.error("failed to get user emails from database")
              cur.close()
              cn.close()
              return FAILED
          recipients = []
          for elem in ret:
              recipients.append(elem[0])
          cur.close()
          cn.close()
        except Exception as e:
            logger.error("could not connect to database: " + sys.exc_info()[1][0])
            return FAILED
    # interactive, user can abort this process at any time
    print("mail content:\n" + message)
    sys.stdout.write("sending mail with subject '" + subject + "' to " + str(len(recipients)) + " recipient(s) in  ")
    sys.stdout.flush()
    try:
        for x in range(9, 0, -1):
            sys.stdout.write('\b' + str(x))
            sys.stdout.flush()
            time.sleep(1)
        print(" ")
        for usermail in r:
            send_mail(subject=s, message=msg, recipients=usermail)
            print("email sent to " + usermail)
    except KeyboardInterrupt:
        print("\naborted")
### END batch_send_mail()


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
        return FAILED

    # Check if the test ID is in the database:            
    try:
        # Check if the test ID exists in tbl_serv_tests.serv_tests_key
        cursor.execute("SELECT COUNT(serv_tests_key) FROM `tbl_serv_tests` WHERE serv_tests_key = %d" %testid)
        rs = cursor.fetchone()[0]
        
        if (rs == 0):
            return FAILED
        else: 
            return(0)
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
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
        return FAILED

    try:
        cursor.execute("SELECT `a`.serv_observer_key, `a`.observer_id, `b`.node_id \
                        FROM tbl_serv_observer AS `a` \
                        LEFT JOIN tbl_serv_map_test_observer_targetimages AS `b` \
                        ON `a`.serv_observer_key = `b`.observer_fk \
                        WHERE `b`.test_fk = %d \
                        ORDER BY `a`.observer_id" % testid)
        rs = cursor.fetchall()
        obsdict_bykey = {}
        obsdict_byid = {}
        for row in rs:
            obsdict_bykey[row[0]] = (row[1], row[2])
            obsdict_byid[row[1]] = (row[0], row[2])
        return (obsdict_bykey, obsdict_byid)
            
    except:
        logger = get_logger()
        logger.error("%s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
### END get_test_obs()


##############################################################################
#
# get_fetcher_pid - Returns the process ID of the oldest running fetcher.
#
##############################################################################
def get_fetcher_pid(testid):
    try:
        searchterm = "flocklab_fetcher.py (.)*-(-)?t(estid=)?%d" % (testid)
        cmd = ['pgrep', '-o', '-f', searchterm]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, err = p.communicate()
        if (p.returncode == 0):
            return int(out)
        else:
            return FAILED
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
### END get_fetcher_pid()


##############################################################################
#
# get_test_owner - Get information about the owner of a test
#
##############################################################################
def get_test_owner(cursor=None, testid=0):
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(testid) != int) or (testid <= 0)):
        return FAILED
    try:
        sql = "SELECT `a`.serv_users_key, `a`.lastname, `a`.firstname, `a`.username, `a`.email, `a`.disable_infomails \
               FROM tbl_serv_users AS `a` \
               LEFT JOIN tbl_serv_tests AS `b` \
               ON `a`.serv_users_key = `b`.owner_fk WHERE `b`.serv_tests_key=%d;"
        cursor.execute(sql % testid)
        rs = cursor.fetchone()
        return (rs[0], rs[1], rs[2], rs[3], rs[4], rs[5])
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
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
        return FAILED
    
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
# get_obsids - Get a list of currently available observer IDs of a certain platform.
#
##############################################################################
def get_obsids(cursor=None, platform=None, status=None):
    if not cursor or not platform or not status:
        return None
    cursor.execute("""
                   SELECT obs.observer_id AS obsid FROM flocklab.tbl_serv_observer AS obs
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
    for rs in cursor.fetchall():
        obslist.append(rs[0])
    return obslist
### END get_obsids()


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
        return FAILED

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
        return FAILED
    # Get all possible test stati and check the status argument:
    try:
        cursor.execute("SHOW COLUMNS FROM `tbl_serv_tests` WHERE Field = 'test_status'")
        possible_stati = cursor.fetchone()[1][5:-1].split(",")
        if ("'%s'"%status not in possible_stati):
            return FAILED
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED

    # Set the status in the database            
    try:
        cursor.execute("UPDATE `tbl_serv_tests` SET `test_status` = '%s', `dispatched` = 0 WHERE `serv_tests_key` = %d;" %(status, testid))
        conn.commit()
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
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
        return FAILED

    # Set the flag in the database            
    try:
        cursor.execute("UPDATE `tbl_serv_tests` SET `dispatched` = 1 WHERE `serv_tests_key` = %d;" %(testid))
        conn.commit()
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
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
                if e.args[0] == MySQLdb.constants.ER.LOCK_DEADLOCK:
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
                if e.args[0] == MySQLdb.constants.ER.LOCK_DEADLOCK:
                    time.sleep(1)
                    spin = True
                else:
                    raise
    except:
        # There was an error in the database connection:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
    return(0)
### END release_db_lock()


##############################################################################
#
# write_errorlog - Writes a message to the errorlog table tbl_serv_errorlog.
#
##############################################################################
def write_errorlog(cursor=None, conn=None, testid=0, obsid=0, message="", timestamp=0.0):
    # Check the arguments:
    if ((type(cursor) != MySQLdb.cursors.Cursor) or (type(conn) != MySQLdb.connections.Connection) or (type(testid) != int) or (type(obsid) != int) or (type(message) != str) or (len(message) <= 0) or (type(timestamp) != float) or (timestamp < 0.0)):
        return FAILED
    if ((testid != 0) and (check_test_id(cursor, testid) != 0)):
        return FAILED
    if ((obsid != 0) and (check_observer_id(cursor, obsid) <= 0)):
        return FAILED
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
        return FAILED
    return(0)
### END write_errorlog()


##############################################################################
#
# error_logandexit - Logs an error (to log and email to admins) and exits the script
#
##############################################################################
def error_logandexit(message=None, exitcode=FAILED):
    global logger, config
    # Check the arguments:
    if (type(message) != str) or (message == "") or (type(exitcode) != int):
        return FAILED
    # Log error - if available, use logger, otherwise get it first:
    if logger:
        logger.error(message)
    else:
        log_fallback(message)
    # Send email to admin:
    try:
        admin_emails = get_admin_emails()
        if admin_emails == FAILED:
            msg = "Error when getting admin emails from database"
            if logger:
                logger.error(msg)
            else:
                logger.error(msg)
            raise Exception
        send_mail(subject="[FlockLab %s]" % (scriptname.replace('.', '_').split('_')[1].capitalize()), message=message, recipients=admin_emails)
    except:
        if logger:
            logger.error("error_logandexit(): Failed to send email to admin.")
        else:
            log_fallback("error_logandexit(): Failed to send email to admin.")
    # Exit program
    if logger:
        logger.debug("Exiting with error code %u." % exitcode)
    sys.exit(exitcode)
### END error_logandexit()


##############################################################################
#
# count_running_instances - Check how many instances of a script are running  
#
##############################################################################
def count_running_instances(scriptname=None):
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
# get_admin_emails - Get the email addresses of all admins from the FlockLab database or the config file if admin_email is present.
#
##############################################################################
def get_admin_emails(cursor=None):
    email_list = []
    if cursor and type(cursor) == MySQLdb.cursors.Cursor:
        # Get the addresses from the database:
        try:
            cursor.execute("SELECT `email` FROM `tbl_serv_users` WHERE `role` = 'admin'")
            rs = cursor.fetchall()
            for mail in rs:
                email_list.append(mail[0])
        except:
            # There was an error in the database connection:
            if logger:
                logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
            return FAILED
    elif config and isinstance(config, configparser.SafeConfigParser) and config.has_option('email', 'admin_email'):
        email_list.append(config.get('email','admin_email'))
    else:
        if logger:
            logger.error("Failed to get admin email.")
        return FAILED
    return email_list
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


##############################################################################
#
# VIZ stuff
#
##############################################################################
def viz_plot(t, d, testdir, obsid, imgdir):
    fig = matplotlib.figure.Figure(figsize=(2*(t[len(t)-1] - t[0]), 1))
    ax = fig.add_axes([0., 0., 1., 1.])
    ax.patch.set_facecolor(None)
    fig.patch.set_alpha(0.)
    ax.set_frame_on(False)
    ax.axes.get_yaxis().set_visible(False)
    ax.axes.get_xaxis().set_visible(False)
    canvas = matplotlib.backends.backend_agg.FigureCanvasAgg(fig)
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
### END viz_plot()


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
### END viz_powerprofiling()


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
### END viz_gpio_monitor()


##############################################################################
#
# scheduleLinkTest - try to schedule a link test for every platform, according to config file
#
##############################################################################
def schedule_linktest(cur, cn, debug=False):
    global config, logger
    # Check the arguments:
    if not config or not logger or ((type(cur) != MySQLdb.cursors.Cursor) or (type(cn) != MySQLdb.connections.Connection)):
        return FAILED
    
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
                        parser = lxml.etree.XMLParser(remove_comments=True)
                        tree = lxml.etree.parse("%s/%s" % (config.get("linktests", "testfolder"),linktestfile), parser)
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
### END schedule_linktest()


##############################################################################
#
# get_xml_timestamp
# Converts XML timestamps to python taking timezone into account.
#
##############################################################################
def get_xml_timestamp(datetimestring):
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
### END get_xml_timestamp()
