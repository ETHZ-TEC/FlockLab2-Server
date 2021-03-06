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

import sys, os, getopt, errno, time, datetime, subprocess, MySQLdb, logging, __main__, traceback, types, calendar, multiprocessing, signal
import lib.flocklab as flocklab


logger = None
debug  = False


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
def test_startstopabort(testid=None, abort=False, delay=0):
    global logger
    
    if ((type(testid) != int) or (testid <= 0)):
        return -1
    
    if not logger:
        logger = flocklab.get_logger()
    
    # change status of test that the next scheduler will skip this test
    try:
        (conn, cursor) = flocklab.connect_to_db()
    except:
        logger.error("Could not connect to the database.")
    
    flocklab.set_test_dispatched(cursor, conn, testid)

    # wait for the actual start time of the test
    time.sleep(delay)
    
    # Add testid to logger name
    logger.name += " (Test %d)" % testid
    # Call the dispatcher:
    cmd = [flocklab.config.get("dispatcher", "dispatcherscript"), '--testid=%d' % testid]
    if abort:
        cmd.append("--abort")
    # Make sure no other instance of the scheduler is running for the same task:
    cmd2 = ['pgrep', '-o', '-f', ' '.join(cmd)]
    p = subprocess.Popen(cmd2, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    out, err = p.communicate()
    if (p.returncode == 0):
        logger.error("There is already an instance of this task running with PID %s. Nothing will be done." % (str(out)))
        logger.debug("Command executed was: %s"%(str(cmd2)))
        rs = errno.EALREADY
    else:
        cmd.append('--debug')
        p = subprocess.Popen(cmd)
        p.wait()
        rs = p.returncode
    if (rs != flocklab.SUCCESS):
        logger.error("Dispatcher returned with error %d." % (rs))
        logger.debug("Command executed was: %s" % (str(cmd)))
        conn.close()
        return errno.EFAULT
    
    conn.close()
    return flocklab.SUCCESS
### END test_startstopabort()


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print("Usage: %s [--debug] [--help]" % __file__)
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
    
    # Get logger:
    logger = flocklab.get_logger()
    
    # Get the config file:
    flocklab.load_config()
    
    # Get the arguments:
    try:
        opts, args = getopt.getopt(argv, "dh", ["debug", "help"])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warning(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        flocklab.error_logandexit("Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])), errno.EAGAIN)

    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
            logger.setLevel(logging.DEBUG)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        else:
            logger.warning("Wrong API usage")
            sys.exit(errno.EINVAL)
            
    # Connect to the database ---
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        flocklab.error_logandexit("Could not connect to database", errno.EAGAIN)
    
    try:
        flocklab.acquire_db_lock(cur, cn, 'scheduler', 5)
    except:
        flocklab.error_logandexit("Could not acquire db lock", errno.EAGAIN)
    # Get current time ---
    now = time.strftime(flocklab.config.get("database", "timeformat"), time.gmtime())
    
    # schedule link measurement if needed
    flocklab.schedule_linktest(cur, cn, debug)
    
    # Check for work ---
    # Check if a new test is to be started ---
    # Calculate the time frame in which a test can be started: at least the setuptime ahead
    schedinterval = 60 + 10   # add slack time
    setuptime     = flocklab.config.getint("tests", "setuptime")
    earlieststart = (datetime.datetime.now() + datetime.timedelta(seconds=setuptime) - datetime.timedelta(seconds=schedinterval)).strftime(flocklab.config.get("database", "timeformat"))
    lateststart   = (datetime.datetime.now() + datetime.timedelta(seconds=setuptime) + datetime.timedelta(seconds=schedinterval)).strftime(flocklab.config.get("database", "timeformat"))
    # Check if a test is going to start soon:
    sql = """SELECT `serv_tests_key`,`time_start`
             FROM `tbl_serv_tests`
             WHERE (`time_start` >= '%s')
             AND (`time_start` <= '%s')
             AND (`test_status` = 'planned')
             AND (`dispatched` = 0)
          """ % (earlieststart, lateststart)
    #logger.debug("Looking in DB for tests with start time between %s and %s and test status planned..." % (earlieststart, lateststart))
    cur.execute(sql)
    rs = cur.fetchall()
    if rs:
        # start thread for each test to start
        for test in rs:
            testid = int(test[0])
            delay = int(calendar.timegm(time.strptime(str(test[1]), '%Y-%m-%d %H:%M:%S'))) - setuptime - int(time.time())
            if delay < 0:
                delay = 0 
            logger.info("Call process to start test %s with delay %ss." % (testid,delay))
            p = multiprocessing.Process(target=test_startstopabort, args=(testid, False, delay))
            p.start()
    else:
        logger.debug("No test is to be started within the next %d seconds" % (setuptime + schedinterval))
        # Check for test which have been missed ---
        sql1 = """SELECT `serv_tests_key`
                  FROM `tbl_serv_tests`
                  WHERE (`time_start` < '%s')
                  AND (`test_status` = 'planned')
               """ % earlieststart
        sql2 = """UPDATE `tbl_serv_tests`
                  SET `test_status` = 'failed'
                  WHERE (`time_start` < '%s')
                  AND (`test_status` = 'planned')
               """ % earlieststart
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
                        msg = "The test with ID %d could not be started as planned because of the following errors:\n\n" % testid
                        msg += "\t * Scheduler missed start time of test (probably because the previous test took too long to stop). Try re-scheduling your test.\n"
                        flocklab.send_mail(subject="[FlockLab Scheduler] Missed test %d" % (testid), message=msg, recipients=owner_email)
                else:
                    logger.error("Error %s returned when trying to get test owner information" % str(rs))
            logger.warning("Updated test status of %d missed tests to 'failed' and informed users." % nmissed)
        #else:
        #    logger.debug("No missed tests found.")
        rs = errno.ENODATA
    
    # Check if a test needs to be aborted ---
    sql = """SELECT `serv_tests_key`, `test_status`
             FROM `tbl_serv_tests` 
             WHERE (`test_status` = 'aborting')
             AND (`dispatched` = 0)
          """
    cur.execute(sql)
    rs = cur.fetchall()
    if rs:
        for test in rs:
            testid = int(test[0])
            dispatcher_pid = flocklab.get_dispatcher_pid(testid)
            if dispatcher_pid != flocklab.FAILED:
                logger.warning("Telling dispatcher with pid %d to abort test %d (status: %s)." % (dispatcher_pid, testid, test[1]))
                os.kill(dispatcher_pid, signal.SIGTERM)
    
    # Release Lock ---
    flocklab.release_db_lock(cur, cn, 'scheduler')
    cur.close()
    cn.close()
    sys.exit(flocklab.SUCCESS)
### END main()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg, errno.EAGAIN)
