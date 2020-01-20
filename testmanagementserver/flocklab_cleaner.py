#! /usr/bin/env python3

import sys, os, getopt, errno, traceback, logging, time, __main__, shutil, glob, datetime
import lib.flocklab as flocklab


logger = None


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

    # Set timezone to UTC:
    os.environ['TZ'] = 'UTC'
    time.tzset()
    
    # Get logger:
    logger = flocklab.get_logger()
    
    # Get config ---
    if flocklab.load_config() != flocklab.SUCCESS:
        msg = "Could not read configuration file. Exiting..."
        flocklab.error_logandexit(msg, errno.EAGAIN)
    #logger.debug("Read configuration file.")
    
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
        flocklab.error_logandexit(msg, errno.EAGAIN)

    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            logger.setLevel(logging.DEBUG)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        else:
            logger.warn("Wrong API usage")
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
    #logger.debug("Connected to database")
    
    # Check for running tests ---
    testisrunning = flocklab.is_test_running(cur)
    
    # Check for work ---
    if testisrunning:
        logger.debug("A test is running, thus exiting...")
    else:
        try:
            # Check for tests to delete ---
            sql =     """    SELECT `serv_tests_key`, `time_start_wish`
                        FROM `tbl_serv_tests` 
                        WHERE (`test_status` = 'todelete')
                    """
            #logger.info("Looking in DB for tests which are marked to be deleted...")
            if ( cur.execute(sql) <= 0 ):
                logger.info("No tests found which are marked to be deleted.")
            else:
                rs = cur.fetchall()
                for (testid, starttime) in rs:
                    testid = str(testid)
                    logger.debug("Found test ID %s to delete."%testid)
                    # If a test is to be deleted which has not run yet, delete it completely. Otherwise, keep the metadata of the test for statistics:
                    if (starttime > datetime.datetime.today()):
                        delete_all = True
                        logger.debug("Test ID %s did not run yet, thus all data (including the test metadata) will be deleted."%testid)
                    else:
                        delete_all = False 
                    # Clean through all relevant tables ---
                    relevant_tables = ['tbl_serv_errorlog']
                    if delete_all:
                        relevant_tables.append('tbl_serv_map_test_observer_targetimages')
                    for table in relevant_tables:
                        sql =    """    DELETE FROM %s
                                    WHERE (`test_fk` = %s)
                                """
                        starttime = time.time()
                        num_deleted_rows = cur.execute(sql%(table, testid))
                        cn.commit()
                        logger.debug("Deleted %i rows of data in table %s for test ID %s in %f seconds" %(num_deleted_rows, table, testid, (time.time()-starttime)))
                    
                    # Delete cached test results ---
                    archive_path = "%s/%s%s"%(flocklab.config.get('archiver','archive_dir'), testid, flocklab.config.get('archiver','archive_ext'))
                    viz_pathes = glob.glob("%s/%s_*"%(flocklab.config.get('viz','imgdir'), testid))
                    pathes = [archive_path]
                    pathes.extend(viz_pathes)
                    for path in pathes:
                        if os.path.exists(path):
                            if os.path.isfile(path):
                                os.remove(path)
                            else:
                                shutil.rmtree(path)
                            logger.debug("Removed path %s for test %s."%(path, testid))
                            
                    # Delete test itself ---
                    if delete_all:
                        # Delete test itself:
                        sql =    """    DELETE FROM `tbl_serv_tests` 
                                WHERE (`serv_tests_key` = %s)
                            """
                        starttime = time.time()
                        num_deleted_rows = cur.execute(sql%(testid))
                        cn.commit()
                        logger.debug("Deleted %i rows of data in table tbl_serv_tests for test ID %s in %f seconds" %(num_deleted_rows, testid, (time.time()-starttime)))
                    else:
                        # Set test status to deleted but keep metadata ---
                        flocklab.set_test_status(cur, cn, int(testid), "deleted")
                        logger.debug("Set status for test ID %s to 'deleted'" %(testid))
                    
            # Delete old entries in viz cache ---
            keeptime = flocklab.config.getint('cleaner', 'keeptime_viz')
            earliest_keeptime = time.time() - (keeptime*86400)
            imgdir_path = flocklab.config.get('viz','imgdir')
            if not os.path.isdir(imgdir_path):
                os.mkdir(imgdir_path)
            for f in os.listdir(imgdir_path):
                path = os.path.join(imgdir_path, f)
                if os.stat(path).st_mtime < earliest_keeptime:
                    logger.debug("Removing viz cache %s..."%path)
                    shutil.rmtree(path)
            
        except:
            msg = "Encountered error: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            logger.error(msg)
            emails = flocklab.get_admin_emails(cur, config)
            msg = "%s on server %s encountered error:\n\n%s" % (__file__, os.uname()[1], msg)
            flocklab.send_mail(subject="[FlockLab %s]"%name, message=msg, recipients=emails)
        finally:
            cur.close()
            cn.close()
    
    #logger.debug("Finished. Exit program.")
    sys.exit(flocklab.SUCCESS)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg, errno.EAGAIN)
        
