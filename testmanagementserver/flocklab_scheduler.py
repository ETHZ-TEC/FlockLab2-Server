#! /usr/bin/env python3

__author__          = "Christoph Walser <walserc@tik.ee.ethz.ch>"
__copyright__   = "Copyright 2010, ETH Zurich, Switzerland"
__license__         = "GPL"


import sys, os, getopt, errno, time, datetime, subprocess, MySQLdb, logging, __main__, traceback, types, calendar, multiprocessing
# Import local libraries
from lib.flocklab import SUCCESS
import lib.flocklab as flocklab


### Global variables ###
###
scriptname = os.path.basename(__main__.__file__)
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
name = "Scheduler"
###

logger = None
debug  = False
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
# Start/stop/abort a test
#
##############################################################################
def test_startstopabort(testid=None, mode='stop',delay=0):
    if ((type(testid) != int) or (testid <= 0) or (mode not in ('start', 'stop', 'abort'))):
        return -1
    
    # change status of test that the next scheduler will skip this test
    try:
        conn = MySQLdb.connect(host=config.get('database','host'), user=config.get('database','user'), passwd=config.get('database','password'), db=config.get('database','database')) 
        cursor = conn.cursor()
    except:
        logger.error("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
    
    flocklab.set_test_dispatched(cursor, conn, testid)

    # wait for the actual start time of the test
    time.sleep(delay)
    
    logger.info("Found test ID %d which should be %sed."%(testid, mode))
    # Add testid to logger name
    logger.name += " (Test %d)"%testid
    # Call the dispatcher:
    cmd = [config.get("dispatcher", "dispatcherscript"), '--testid=%d'%testid, '--%s'%mode]
    # Make sure no other instance of the scheduler is running for the same task:
    cmd2 = ['pgrep', '-o', '-f', ' '.join(cmd)]
    p = subprocess.Popen(cmd2, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    out, err = p.communicate()
    if (p.returncode == 0):
        logger.error("There is already an instance of this task running with PID %s. Nothing will be done." % (str(out)))
        logger.debug("Command executed was: %s"%(str(cmd2)))
        rs = errno.EALREADY
    else:
        if debug:
            cmd.append('--debug')
        p = subprocess.Popen(cmd)
        p.wait()
        rs = p.returncode
    if (rs != SUCCESS):
        logger.error("Dispatcher to %s test returned with error %d" %(mode, rs))
        logger.debug("Command executed was: %s"%(str(cmd)))
        conn.close()
        return errno.EFAULT
    else:
        logger.info("Test %d %s done." % (testid, mode))
        conn.close()
        return SUCCESS
### END test_startstopabort()


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

    ### Global Variables ###
    global logger
    global debug
    global config

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
    
    # Get the arguments:
    try:
        opts, args = getopt.getopt(argv, "dh", ["debug", "help"])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warn(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)

    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
            logger.setLevel(logging.DEBUG)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(SUCCESS)
        else:
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)
            
    # Connect to the database ---
    try:
        (cn, cur) = flocklab.connect_to_db(config, logger)
    except:
        msg = "Could not connect to database"
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
    #logger.debug("Connected to database")
    
    try:
        flocklab.acquire_db_lock(cur, cn, 'scheduler', 5)
    except:
        msg = "Could not acquire db lock"
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)    
    # Get current time ---
    now = time.strftime(config.get("database", "timeformat"), time.gmtime())
    
    # schedule link measurement if needed
    flocklab.scheduleLinkTest(logger, config, cur, cn, debug)
    
    # Check for work ---
    # Check if a new test is to be started ---
    # Calculate the time frame in which a test can be started: at least the setuptime ahead, at most 5 minutes more ahead
    earlieststart = (datetime.datetime.now() + datetime.timedelta(minutes=float(config.get("tests", "setuptime"))) - datetime.timedelta(seconds=10)).strftime(config.get("database", "timeformat"))
    lateststart = (datetime.datetime.now() + datetime.timedelta(minutes=int(config.get("tests", "setuptime")))  + datetime.timedelta(minutes=2)).strftime(config.get("database", "timeformat"))
    # Check if a test is going to start soon:
    sql = """    SELECT `serv_tests_key`,`time_start_wish`
                FROM `tbl_serv_tests` 
                WHERE 
                    (`time_start_wish` >= '%s') 
                    AND (`time_start_wish` <= '%s')
                    AND (`test_status` = 'planned')
                    AND (`dispatched` = 0)
                ;"""%(earlieststart, lateststart)
    logger.debug("Looking in DB for tests with start time between %s and %s and test status planned..."%(now, lateststart))
    cur.execute(sql)
    
    # start thread for each test to start
    rs = cur.fetchall()
    if rs:
        for test in rs:
            testid = int(test[0])
            delay = int(calendar.timegm(time.strptime(str(test[1]), '%Y-%m-%d %H:%M:%S'))) - (int(config.get("tests", "setuptime"))*60) - int(time.time())
            if delay < 0:
                delay = 0 
            logger.info("Call process to start test %s with delay %s"%(testid,delay))
            p = multiprocessing.Process(target=test_startstopabort,args=(testid, 'start', delay))
            p.start()
    else:
        logger.debug("No test is to be started within the next %s minutes"%(config.get("tests", "setuptime")))
            #logger.debug("Looking in DB for missed tests...")
        # Check for test which have been missed ---
        sql1 = """    SELECT `serv_tests_key`
                    FROM `tbl_serv_tests`
                    WHERE 
                        (`time_start_wish` < '%s')
                        AND (`test_status` = 'planned')
                    """%earlieststart
        sql2 = """    UPDATE `tbl_serv_tests`
                    SET `test_status` = 'failed'
                    WHERE 
                        (`time_start_wish` < '%s')
                        AND (`test_status` = 'planned')
                    """%earlieststart
        nmissed = cur.execute(sql1)
        if nmissed > 0:
            tests = cur.fetchall()
            cur.execute(sql2)
            cn.commit()
            # Inform users that test has been missed:
            for testid in tests:
                testid=int(testid[0])
                rs = flocklab.get_test_owner(cur, testid)
                if isinstance(rs, tuple):
                    disable_infomails = int(rs[5])
                    # Only send email to test owner if she didn't disable reception of info mails:
                    if disable_infomails != 1:
                        owner_email = rs[4]
                        msg = "The test with ID %d could not be started as planned because of the following errors:\n\n" %testid
                        msg += "\t * Scheduler missed start time of test (probably because the previous test took too long to stop). Try re-scheduling your test.\n"
                        flocklab.send_mail(subject="[FlockLab Scheduler] Missed test %d"%(testid), message=msg, recipients=owner_email)
                else:
                    logger.error("Error %s returned when trying to get test owner information"%str(rs))
            logger.debug("Updated test status of %d missed tests to 'failed' and informed users."%nmissed)
        else:
            logger.debug("No missed tests found.")
        rs = errno.ENODATA
        
    # Check if a test has to be stopped ---
    # Check if there is a running test which is to be stopped:
    sql = """    SELECT `serv_tests_key`, `test_status`
                FROM `tbl_serv_tests` 
                WHERE 
                    ((`test_status` = 'aborting')
                    OR ((`test_status` = 'running') AND (`time_end_wish` <= '%s')))
                    AND (`dispatched` = 0)
                ;"""
    #logger.debug("Looking in DB for running tests with stop time equal or before %s..."%now)
    status2mode = {'running':'stop', 'aborting':'abort'}
    cur.execute(sql%(now))
    # start process for each test which has to be stopped
    rs = cur.fetchall()
    if rs:
        for test in rs:
            testid = int(test[0])
            logger.debug("Call process to stop test %d, status %s"%(testid, test[1]))
            p = multiprocessing.Process(target=test_startstopabort,args=(testid, status2mode[test[1]]))
            p.start()
    
    flocklab.release_db_lock(cur, cn, 'scheduler')
    cur.close()
    cn.close()
    sys.exit(SUCCESS)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
