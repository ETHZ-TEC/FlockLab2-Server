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

##############################################################################
#
# FlockLab library, runs on the test management server
#
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
        logger.warning("Logger already initialized.")
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
    logger.warning(msg)
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
        cur.execute("SET sql_mode=''")
    except:
        logger = get_logger()
        logger.error("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        raise Exception
    return (cn, cur)
### END connect_to_db()


##############################################################################
#
# check_db_connection - check connection to the database and reconnect if necessary
#
##############################################################################
def check_db_connection(conn, cursor):
    try:
        # arbitrary dummy request
        cur.execute("SELECT * FROM `tbl_serv_observers` LIMIT 1")
    except:
        # reconnect
        return connect_to_db()
    return (conn, cursor)
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
    config = get_config()
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
    
    if logger:
        logger.debug("Sending mail to %s..." % (mail['To']))
    
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
        if logger:
            logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
    
    return SUCCESS
### END send_mail()


##############################################################################
#
# batch_send_mail - send a mail to several users (if recipient list empty, mail will be sent to all active users) with 10s delay, can be aborted with ctrl+c
#
##############################################################################
def batch_send_mail(subject="[FlockLab]", message="", recipients=[], attachments=[]):
    if not message or (type(recipients) != list):
        return FAILED
    if not recipients:
        # no email provided -> extract all addresses from the database
        try:
          config = get_config()
          (cn, cur) = connect_to_db()
          cur.execute("""SELECT email FROM `tbl_serv_users` WHERE is_active=1;""")
          ret = cur.fetchall()
          if not ret:
              if logger:
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
            if logger:
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
        for usermail in recipients:
            if send_mail(subject=subject, message=message, recipients=usermail) != SUCCESS:
                print("failed to send email to %s" % usermail)
            else:
                print("email sent to %s" % usermail)
    except KeyboardInterrupt:
        print("\naborted")
    return SUCCESS
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
        logger.error("%s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
### END get_fetcher_pid()


##############################################################################
#
# get_dispatcher_pid - Returns the process ID of the dispatcher for a test.
#
##############################################################################
def get_dispatcher_pid(testid):
    try:
        searchterm = "flocklab_dispatcher.py (.)*-(-)?t(estid=)?%d" % (testid)
        cmd = ['pgrep', '-o', '-f', searchterm]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, err = p.communicate()
        if (p.returncode == 0):
            return int(out)
        else:
            return FAILED
    except:
        logger = get_logger()
        logger.error("%s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
### END get_dispatcher_pid()


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
        sql = "SELECT `a`.serv_users_key, `a`.lastname, `a`.firstname, `a`.username, `a`.email, `a`.disable_infomails, `a`.role \
               FROM tbl_serv_users AS `a` \
               LEFT JOIN tbl_serv_tests AS `b` \
               ON `a`.serv_users_key = `b`.owner_fk WHERE `b`.serv_tests_key=%d;"
        cursor.execute(sql % testid)
        rs = cursor.fetchone()
        return (rs[0], rs[1], rs[2], rs[3], rs[4], rs[5], rs[6])
    except:
        logger = get_logger()
        logger.error("%s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        return FAILED
### END get_test_owner()


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
        sql = "SELECT `ethernet_address`, `status` \
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
    if not cursor:
        return None
    if status == None:
        status = "online"
    if platform == None:
        cursor.execute("""
                       SELECT observer_id FROM flocklab.tbl_serv_observer
                       WHERE status IN (%s)
                       ORDER BY observer_id;
                       """ % (status))
    else:
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
                       WHERE obs.status IN (%s) AND '%s' IN (LOWER(slot1.name), LOWER(slot2.name), LOWER(slot3.name), LOWER(slot4.name))
                       ORDER BY obs.observer_id;
                       """ % (status, platform.lower()))
    obslist = []
    for rs in cursor.fetchall():
        obslist.append(str(rs[0]).lstrip('0'))   # remove leading zeros
    return map(str, obslist)    # return as list of strings
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
    return SUCCESS
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
# error_logandexit - Logs an error (to log and email to admins) and exits the script
#
##############################################################################
def send_mail_to_admin(message):
    if message is None:
        return FAILED
    # Send email to admin:
    try:
        admin_emails = get_admin_emails()
        if admin_emails == FAILED:
            if logger:
                logger.error("Error when getting admin emails from database")
            return FAILED
        else:
            send_mail(subject="[FlockLab %s]" % (scriptname.replace('.', '_').split('_')[1].capitalize()), message=message, recipients=admin_emails)
    except:
        if logger:
            logger.error("error_logandexit(): Failed to send email to admin.")
        return FAILED
    return SUCCESS
### END send_mail_to_admin()


##############################################################################
#
# error_logandexit - Logs an error (to log and email to admins) and exits the script
#
##############################################################################
def error_logandexit(message=None, exitcode=FAILED):
    # Check the arguments:
    if (type(message) != str) or (message == "") or (type(exitcode) != int):
        return FAILED
    # Log error - if available, use logger, otherwise get it first:
    logger = get_logger()
    if logger:
        logger.error(message)
    else:
        log_fallback(message)
    send_mail_to_admin(message)
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
    if not cursor or not config:
        return None
    try:
        maxcleanuptime = config.getint('cleaner', 'max_test_cleanuptime')
        now = time.strftime(config.get("database", "timeformat"), time.gmtime())
        cursor.execute("""
                       SELECT COUNT(serv_tests_key) FROM tbl_serv_tests
                       WHERE test_status IN('preparing', 'running', 'aborting', 'cleaning up')
                       AND TIMESTAMPDIFF(MINUTE, time_end, '%s') <= %d
                       """ % (now, maxcleanuptime))
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
# scheduleLinkTest - try to schedule a link test for every platform, according to config file
#
##############################################################################
def schedule_linktest(cur, cn, debug=False):
    # Check the arguments:
    if not config or not logger or ((type(cur) != MySQLdb.cursors.Cursor) or (type(cn) != MySQLdb.connections.Connection)):
        return FAILED
    
    linktest_interval_min = config.getint("linktests", "interval_hours") * 60
    if linktest_interval_min == 0:
        return SUCCESS    # nothing to do
    
    sql = "SELECT TIMESTAMPDIFF(MINUTE, `begin`, NOW()) AS `last` FROM `tbl_serv_link_measurements` ORDER BY `last` ASC LIMIT 1"
    cur.execute(sql)
    rs = cur.fetchone()
    if not rs:
        logger.debug("No link measurements found.")
        lasttest = linktest_interval_min * 2    # any number > (interval_hours + interval_random_minutes) will do
    else:
        lasttest = int(rs[0])
        #logger.debug("Last link measurement was %s minutes ago." % (lasttest))
    
    nexttest = linktest_interval_min + random.randint(-config.getint("linktests", "interval_random_minutes"), config.getint("linktests", "interval_random_minutes"))
    if lasttest >= nexttest:
        # Schedule new tests
        # Check if the lockfile is present:
        lockfile = config.get("linktests", "lockfile")
        if os.path.exists(lockfile):
            logger.debug("Lockfile %s exists already. Skip adding new linktests." % lockfile)
            # If the last scheduled link tests are a long time ago, generate a warning since it may be that the lockfile was not deleted for whatever reason:
            if lasttest > 2 * nexttest:
                logger.error("Lockfile %s exists and the last linktest was %d min ago (interval is %d min)." % (lockfile, lasttest, linktest_interval_min))
        else:
            # Create the lockfile:
            basedir = os.path.dirname(lockfile)
            if not os.path.exists(basedir):
                os.makedirs(basedir)
            open(lockfile, 'a').close()
            logger.debug("Touched lockfile %s" % lockfile)
            
            # Schedule new tests
            logger.debug("Schedule new link measurements")
            listing = os.listdir(config.get("linktests", "testfolder"))
            for linktestfile in listing:
                if re.search("\.xml$", os.path.basename(linktestfile)) is not None:
                    logger.info("Adding link test '%s'." % linktestfile)
                    cmd = [config.get("linktests", "starttest_script"), '-c', "%s" % os.path.join(config.get("linktests", "testfolder"), linktestfile)]
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, cwd=os.path.dirname(config.get("linktests", "starttest_script")))
                    out, err = p.communicate()
                    rs = p.wait()
                    testid = re.search("Test ID: ([0-9]*)",out)
                    if (testid is None) | (rs != SUCCESS):
                        logger.error("Could not register link test %s (%s)" % (linktestfile, err.strip()))
                    else:
                        # flag in db
                        sql = """
                              INSERT INTO `tbl_serv_link_measurements` (test_fk, begin, platform_fk, radio_cfg)
                              SELECT %s, NOW(), serv_platforms_key, '' from tbl_serv_platforms WHERE serv_platforms_key = (SELECT `b`.platforms_fk FROM
                              flocklab.tbl_serv_map_test_observer_targetimages as `a` left join
                              flocklab.tbl_serv_targetimages as `b` ON (a.targetimage_fk = b.serv_targetimages_key) WHERE `a`.test_fk=%s ORDER BY serv_platforms_key LIMIT 1)
                              """ % (testid.group(1), testid.group(1))
                        cur.execute(sql)
                        cn.commit()
            # Delete the lockfile:
            os.remove(lockfile)
            logger.debug("Removed lockfile %s" % lockfile)
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


##############################################################################
#
# parse_int()   parses a string to int
#
##############################################################################
def parse_int(s):
    res = 0
    if s:
        try:
            res = int(float(s.strip())) # higher success rate if first parsed to float
        except ValueError:
            if logger:
                logger.warning("Could not parse %s to int." % (str(s)))
    return res
### END parse_int()


##############################################################################
#
# binary_get_symbol_section()   returns the section name if a symbol exists in a binary file (ELF), None otherwise
#
##############################################################################
def binary_get_symbol_section(symbol=None, binaryfile=None):
    if symbol is None or binaryfile is None or not os.path.isfile(binaryfile):
        return None
    p = subprocess.Popen(['objdump', '-t', binaryfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    (out, err) = p.communicate()
    if p.returncode == 0:
        # objdump output is in the following format: [address] [flags] [section] [size] [name]
        section = re.search('(\.[^\s]*)\s[0-9]+\s' + symbol, out)
        if section:
            section = section.group(1)
            logger = get_logger()
            logger.debug("Found symbol %s in section %s of binary file %s." % (symbol, section, binaryfile))
            return section
    return None
### END binary_has_symbol()


##############################################################################
#
# patch_binary()   set / overwrite symbols in a binary file (ELF), input file = output file
#
##############################################################################
def patch_binary(symbol=None, value=None, binaryfile=None, arch=None):
    
    if symbol is None or value is None or binaryfile is None or not os.path.isfile(binaryfile) or arch is None:
        return FAILED
    
    set_symbols_tool = config.get('targetimage', 'setsymbolsscript')
    
    if arch == 'msp430':
        binutils_path = config.get('targetimage', 'binutils_msp430')
        binutils_objcopy = "msp430-objcopy"
        binutils_objdump = "msp430-objdump"
    elif arch == 'arm':
        binutils_path = config.get('targetimage', 'binutils_arm')
        binutils_objcopy = "arm-none-eabi-objcopy"
        binutils_objdump = "arm-none-eabi-objdump"

    # check whether the symbol exists in the binary file and get the section name
    section = binary_get_symbol_section(symbol, binaryfile)
    if section is None:
        logger = get_logger()
        logger.debug("Symbol %s not found in file %s." % (symbol, binaryfile))
        return SUCCESS    # no error, symbol just doesn't exist

    cmd = ['%s' % (set_symbols_tool), '--section', section, '--objcopy', '%s/%s' % (binutils_path, binutils_objcopy), '--objdump', '%s/%s' % (binutils_path, binutils_objdump), '--target', 'elf', binaryfile, binaryfile, '%s=%s' % (symbol, value)]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rs = p.wait()
        if rs != 0:
            logger = get_logger()
            logger.error("Error %d returned from %s. Command was: %s" % (rs, set_symbols_tool, " ".join(cmd)))
            return FAILED
    except OSError as err:
        msg = "Error in subprocess: tried calling %s. Error was: %s" % (str(cmd), str(err))
        logger = get_logger()
        logger.error(msg)
        return FAILED

    return SUCCESS
### END patch_binary()


##############################################################################
#
# bin_to_hex()   converts a binary (ELF) file to Intel hex format
#                -> as alternative, use intelhex python module
#
##############################################################################
def bin_to_hex(binaryfile=None, arch=None, outputfile=None):
    
    if arch is None or binaryfile is None or outputfile is None:
        return FAILED
    
    if arch == 'msp430':
        binutils_path = config.get('targetimage', 'binutils_msp430')
        binutils_objcopy = "msp430-objcopy"
        binutils_objdump = "msp430-objdump"
    elif arch == 'arm':
        binutils_path = config.get('targetimage', 'binutils_arm')
        binutils_objcopy = "arm-none-eabi-objcopy"
        binutils_objdump = "arm-none-eabi-objdump"

    cmd = ['%s/%s' % (binutils_path, binutils_objcopy), '--output-target', 'ihex', binaryfile, outputfile]
    try:
        logger = get_logger()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        if p.returncode != 0:
            logger.error("Command %s returned with error code %d (%s)." % (" ".join(cmd), p.returncode, err.decode("utf-8").strip()))
            return FAILED
        else:
            logger.debug("Converted file %s to Intel hex." % (binaryfile))
    except OSError as err:
        msg = "Error in subprocess: tried calling %s. Error was: %s" % (str(cmd), str(err))
        if logger:
            logger.error(msg)
        return FAILED

    return SUCCESS
### END bin_to_hex()


##############################################################################
#
# is_hex_file()   checks whether the file is an intel hex file (basic checks only!)
#
##############################################################################
def is_hex_file(filename=None, data=None):
    if filename == None and data == None:
        return FAILED
    if (filename != None and not os.path.isfile(filename)):
        return FAILED
    try:
        if filename != None:
            f = open(filename, 'rb')
            data = f.read()
            f.close()
        # try to decode as ASCII, if it fails then this is not a hex file
        decoded_data = data.decode('ascii')
        lines = decoded_data.split('\n')
        for line in lines:
            line = line.strip()
            if line == "":
                continue
            if len(line.strip()) > 44 or line[0] != ':':
                return False
        return True
    except:
        pass   # not a valid hex file
    return False
### END is_hex_file()


##############################################################################
#
# get_symtable_from_binary()   retrieves the symbol table from a target image (elf file)
#
##############################################################################
def get_symtable_from_binary(binaryfile=None):
    if binaryfile == None:
        return ""
    # either use readelf -s or objdump -t
    p = subprocess.Popen(['readelf', '-s', binaryfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    (out, err) = p.communicate()
    if p.returncode == 0:
        return out
    return ""
### END get_symtable_from_binary()


##############################################################################
#
# extract_variables_from_symtable()   extracts all global variables from a symbol table and returns them as a dictionary
#
##############################################################################
def extract_variables_from_symtable(symtable=""):
    if not symtable:
        return symtable
    symbols = {}
    for line in symtable.split('\n'):
        if not "OBJECT" in line:
            continue
        parts = line.split()
        if len(parts) >= 8:      # at least 8 parts required
            try:
                symname = parts[-1]
                symbols[symname] = [ int(parts[1], 16), int(parts[-2]) ]
                print("found symbol: %s, 0x%x, %d" % (symname, symbols[symname][0], symbols[symname][1]))
            except ValueError:
                pass
    return symbols
### END extract_variables_from_symtable()

