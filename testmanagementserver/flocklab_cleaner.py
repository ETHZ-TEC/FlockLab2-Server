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

import sys, os, getopt, errno, traceback, logging, time, __main__, shutil, glob, datetime, subprocess, signal, multiprocessing
import lib.flocklab as flocklab
import flocklab_scheduler as scheduler


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

    # Get logger:
    logger = flocklab.get_logger()
    
    # Get config ---
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
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN)

    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            logger.setLevel(logging.DEBUG)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        else:
            logger.warning("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Allow only x instances ---
    rs = flocklab.count_running_instances(__file__)
    if (rs >= 0):
        maxinscount = flocklab.config.getint('cleaner', 'max_instances')
        if rs > maxinscount:
            msg = "Maximum number of instances (%d) for script %s with currently %d instances running exceeded. Aborting..." % (maxinscount, __file__, rs)
            flocklab.error_logandexit(msg, errno.EUSERS)
    else:
        msg = "Error when trying to count running instances of %s. Function returned with %d" % (__file__, rs)
        flocklab.error_logandexit(msg, errno.EAGAIN)
    
    # Connect to the database ---
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        msg = "Could not connect to database"
        flocklab.error_logandexit(msg, errno.EAGAIN)
    
    # Check for running tests ---
    testisrunning = flocklab.is_test_running(cur)
    
    # Check for work ---
    if testisrunning:
        logger.debug("A test is running, thus exiting...")
    else:
        try:
            # Check for tests to delete ---
            sql = """SELECT `serv_tests_key`, `time_start`
                     FROM `tbl_serv_tests`
                     WHERE (`test_status` = 'todelete')
                  """
            if ( cur.execute(sql) <= 0 ):
                logger.debug("No tests found which are marked to be deleted.")
            else:
                rs = cur.fetchall()
                for (testid, starttime) in rs:
                    testid = str(testid)
                    logger.info("Found test ID %s to delete." % testid)
                    # If a test is to be deleted which has not run yet, delete it completely. Otherwise, keep the metadata of the test for statistics:
                    if (starttime > datetime.datetime.today()):
                        delete_all = True
                        logger.warning("Test ID %s did not run yet, thus all data (including the test metadata) will be deleted." % testid)
                    else:
                        delete_all = False 
                    # Clean through all relevant tables ---
                    relevant_tables = []
                    if delete_all:
                        relevant_tables.append('tbl_serv_map_test_observer_targetimages')
                    for table in relevant_tables:
                        sql = """DELETE FROM %s
                                 WHERE (`test_fk` = %s)
                              """
                        starttime = time.time()
                        num_deleted_rows = cur.execute(sql%(table, testid))
                        cn.commit()
                        logger.debug("Deleted %i rows of data in table %s for test ID %s in %f seconds." % (num_deleted_rows, table, testid, (time.time()-starttime)))
                    
                    # Delete cached test results ---
                    archive_path = "%s/%s%s" % (flocklab.config.get('archiver','archive_dir'), testid, flocklab.config.get('archiver','archive_ext'))
                    pathes = [archive_path]
                    for path in pathes:
                        if os.path.exists(path):
                            if os.path.isfile(path):
                                os.remove(path)
                            else:
                                shutil.rmtree(path)
                            logger.info("Removed path %s for test %s." % (path, testid))
                    
                    # Delete test itself ---
                    if delete_all:
                        # Delete test itself:
                        sql =    """DELETE FROM `tbl_serv_tests` 
                                    WHERE (`serv_tests_key` = %s)
                                 """
                        starttime = time.time()
                        num_deleted_rows = cur.execute(sql % (testid))
                        cn.commit()
                        logger.debug("Deleted %i rows of data in table tbl_serv_tests for test ID %s in %f seconds." % (num_deleted_rows, testid, (time.time()-starttime)))
                    else:
                        # Set test status to deleted but keep metadata ---
                        flocklab.set_test_status(cur, cn, int(testid), "deleted")
                        logger.debug("Set status for test ID %s to 'deleted'" %(testid))
            
            # Delete old entries in viz cache ---
            keeptime = flocklab.config.getint('cleaner', 'keeptime_viz')
            maxfilesize = flocklab.config.getint('viz', 'filesizelimit')
            earliest_keeptime = time.time() - (keeptime * 86400)
            vizdir = flocklab.config.get('viz','dir')
            if os.path.isdir(vizdir):
                for f in os.listdir(vizdir):
                    path = os.path.join(vizdir, f)
                    # either an old plot or a large file (which cannot be displayed anyways)
                    if os.stat(path).st_mtime < earliest_keeptime or os.path.getsize(path) > maxfilesize:
                        logger.info("Removing plots %s..." % path)
                        os.remove(path)
            else:
                logger.warning("Directory '%s' does not exist." % vizdir)
            
            # Get parameters ---
            now = time.strftime(flocklab.config.get("database", "timeformat"), time.gmtime())
            maxtestcleanuptime = flocklab.config.getint('cleaner', 'max_test_cleanuptime')
            
            # Check for tests that are stuck ---
            sql = """SELECT `serv_tests_key` FROM `tbl_serv_tests`
                     WHERE ((`test_status` IN ('preparing', 'aborting', 'cleaning up', 'syncing', 'synced')) OR (`test_status` = 'running' AND `dispatched` = 1))
                     AND (TIMESTAMPDIFF(MINUTE, `time_end`, '%s') > %d)
                  """
            if cur.execute(sql % (now, maxtestcleanuptime)) <= 0:
                logger.debug("No stuck tests found.")
            else:
                rs = cur.fetchall()
                testids = []
                for testid in rs:
                    testids.append(str(testid[0]))
                # set test status to failed
                sql = "UPDATE `tbl_serv_tests` SET `test_status`='failed' WHERE `serv_tests_key` IN (%s)" % (", ".join(testids))
                cur.execute(sql)
                cn.commit()
                msg = "Found %d stuck tests in the database (IDs: %s). Test status set to 'failed'." % (len(rs), ", ".join(testids))
                logger.info(msg)
                emails = flocklab.get_admin_emails()
                if emails != flocklab.FAILED:
                    flocklab.send_mail(subject="[FlockLab Cleaner]", message=msg, recipients=emails)
            
            # Check for tests that are still running, but should have been stopped (NOTE: needs to be AFTER the checking for stuck tests!) ---
            sql = """SELECT `serv_tests_key`, `test_status` FROM `tbl_serv_tests` 
                     WHERE (`test_status` = 'running') AND (`time_end` <= '%s') AND (`dispatched` = 0)
                  """
            cur.execute(sql % (now))
            rs = cur.fetchall()
            if rs:
                # start process for each test which has to be stopped
                for test in rs:
                    testid = int(test[0])
                    logger.debug("Call process to stop test %d (status: %s)." %  (testid, test[1]))
                    p = multiprocessing.Process(target=scheduler.test_startstopabort, args=(testid, True))
                    p.start()
            else:
                logger.debug("No tests found that need to be aborted.")
            
            # Check for stuck threads
            cmd = ["ps", "-U", "flocklab", "-o", "pid:9=,cmd:100=,etime="]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            out, err = p.communicate()
            lines = out.split("\n")
            pids = []
            for line in lines:
                if len(line) > 0:
                    try:
                        pid = int(line[0:10].strip())
                        command = line[10:110].strip()
                        runtime = line[110:].strip()
                        #logger.debug("pid: %d, command: '%s', runtime: %s" % (pid, command, runtime))
                    except:
                        logger.warning("Failed to parse output of 'ps'. Line was: '%s'" % line)
                        break
                    if "testid=" in command:
                        testid = int(command.split('testid=', 1)[1].split()[0])
                        # check stop time of this test
                        sql = """SELECT `serv_tests_key` FROM `tbl_serv_tests`
                                  WHERE `serv_tests_key`=%d AND TIMESTAMPDIFF(MINUTE, `time_end`, '%s') > %d
                              """
                        if cur.execute(sql % (testid, now, maxtestcleanuptime)) > 0:
                            # thread is stuck -> add to list and kill
                            pids.append(str(pid))
                            try:
                                os.kill(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                logger.warning("Could not kill process with ID %s (does not exist)" % (str(pid)))
            if len(pids) > 0:
                msg = "%d stuck threads terminated (PIDs: %s)" % (len(pids), ", ".join(pids))
                logger.info(msg)
                emails = flocklab.get_admin_emails()
                if emails != flocklab.FAILED:
                    flocklab.send_mail(subject="[FlockLab Cleaner]", message=msg, recipients=emails)
            else:
                logger.debug("No stuck threads found.")
            
            # Check for offline observers and mark them accordingly in the database
            sql = """SELECT `observer_id`, `ethernet_address`, `status` FROM `tbl_serv_observer`
                     WHERE `status` = 'offline' OR `status` = 'online'
                  """
            cur.execute(sql)
            rs = cur.fetchall()
            if rs:
                for obs in rs:
                    cmd = ["timeout", "1", "ping", "-c", "1", obs[1]]
                    #logger.debug("pinging observer fl-%02d with command %s" % (int(obs[0]), " ".join(cmd)))
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    ret = p.wait()
                    if ret != 0:
                        logger.warning("Observer %d (%s) appears to be offline." % (int(obs[0]), obs[1]))
                        if obs[2] == 'online':
                            cur.execute("UPDATE `tbl_serv_observer` SET status='offline' WHERE observer_id=%d" % int(obs[0]))
                            cn.commit()
                            logger.info("Observer %d (%s) marked as 'offline' in the database." % (int(obs[0]), obs[1]))
                    else:
                        #logger.debug("Observer %d (%s) is online." % (int(obs[0]), obs[1]))
                        if obs[2] == 'offline':
                            cur.execute("UPDATE `tbl_serv_observer` SET status='online' WHERE observer_id=%d" % int(obs[0]))
                            cn.commit()
                            logger.info("Observer %d (%s) marked as 'online' in the database." % (int(obs[0]), obs[1]))
        except:
            msg = "Encountered error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
            logger.error(msg)
            emails = flocklab.get_admin_emails()
            msg = "%s on server %s encountered error:\n\n%s" % (__file__, os.uname()[1], msg)
            flocklab.send_mail(subject="[FlockLab Cleaner]", message=msg, recipients=emails)
        finally:
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
        
