#! /usr/bin/env python3

import sys, os, getopt, errno, traceback, logging, time, __main__, shutil, glob
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
        maxinscount = flocklab.config.getint('retentioncleaner', 'max_instances')
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
    
    # Check for work ---
    expiration_leadtime = flocklab.config.get('retentioncleaner', 'expiration_leadtime')
    logger.debug("Expiration lead time is %s days"%expiration_leadtime)
    try:
        # Get all users that have ran tests:
        sql =    """ SELECT DISTINCT `owner_fk` 
                    FROM `tbl_serv_tests`
                    WHERE (`test_status` IN ('not schedulable','finished','failed', 'retention expiring'))
                """
        if ( cur.execute(sql) <= 0 ):
            logger.info("No users found which ran tests.")
        else:
            rs = cur.fetchall()
            ownerids = [str(i[0]) for i in rs]
            for ownerid in ownerids:
                sql =     """    SELECT `retention_time`, `email`, `username`, `is_active`
                            FROM `tbl_serv_users` 
                            WHERE (`serv_users_key` = %s)
                        """ % (ownerid)
                cur.execute(sql)
                rs = cur.fetchone()
                retention_time_user = rs[0]
                owneremail = rs[1]
                ownerusername = rs[2]
                is_active = rs[3]
                logger.debug("Checking tests of user %s (users retention time is %d days)."%(ownerusername, retention_time_user))
                # Check for each user (taking into account her individual retention time [-1 means saving data forever]) if there are tests to be cleaned soon and inform the user about these tests. 
                if retention_time_user != -1:
                    sql =    """    SELECT `serv_tests_key`, `title`, DATE(`time_end_act`), `test_status`
                                FROM `tbl_serv_tests` 
                                WHERE ((`owner_fk` = %s) AND (`time_end_act` < ADDDATE(NOW(), -(%s + %s))) AND (`test_status` IN ('not schedulable','finished','failed'))) 
                                ORDER BY `time_end_act` DESC
                            """ % (ownerid, retention_time_user, expiration_leadtime)
                    if(cur.execute(sql) > 0):
                        rs = cur.fetchall()
                        msg_expiring = """Dear FlockLab user,\n\n\
FlockLab can not save your test data forever and thus your tests have a retention time of %s days before they are deleted.\n\
According to this policy, the following tests will be deleted in %s days. If you want to keep the test data, please download it before \
it is deleted. \n\n\
Test ID\tEnd of test\tTest state\tTest Title\n\
===============================================================\n\
%s\n\
Yours faithfully,\nthe FlockLab server"""
                        testlist = ""
                        testids = ", ".join([str(i[0]) for i in rs])
                        logger.debug("Found tests whose retention time expires soon: %s"%testids)
                        for testid, title, enddate, teststatus in rs:
                            testlist = testlist + "%s\t%s\t%s\t%s\n"%(testid, enddate, teststatus, title)
                        msg = msg_expiring%(retention_time_user, expiration_leadtime, testlist)
                        if is_active == 1:
                            ret = flocklab.send_mail(subject="[FlockLab %s] %s"%(name, "Retention time expiring soon") , message=msg, recipients=owneremail)
                        else:
                            ret = 0
                        if ret != 0:
                            msg = "Could not send Email to %s. Function returned %d"%(owneremail, ret)
                            logger.error(msg)
                            emails = flocklab.get_admin_emails(cur)
                            msg = "%s on server %s encountered error:\n\n%s" % (__file__, os.uname()[1], msg)
                            flocklab.send_mail(subject="[FlockLab %s]" % name, message=msg, recipients=emails)
                            continue
                        else:
                            # Mark the tests in the database:
                            sql =    """    UPDATE `tbl_serv_tests`
                                        SET `test_status` = 'retention expiring', `retention_expiration_warned` = NOW()
                                        WHERE `serv_tests_key` IN (%s)
                                    """
                            cur.execute(sql%(testids))
                            cn.commit()
                            logger.debug("Set test status to 'retention expiring' for tests.")
                    else:
                        logger.debug("Found no tests whose retention time expires soon.")
                
                # Check for each user if there are tests which are to be marked for deletion as their retention time expired:
                sql =    """    SELECT `serv_tests_key`, `title`, DATE(`time_end_act`)
                            FROM `tbl_serv_tests` 
                            WHERE ((`owner_fk` = %s) AND (`time_end_act` < ADDDATE(NOW(), -(%s))) AND (`test_status` = 'retention expiring') AND (`retention_expiration_warned` < ADDDATE(NOW(), -(%s+1)))) 
                            ORDER BY `time_end_act` DESC
                        """
                if(cur.execute(sql % (ownerid, retention_time_user, expiration_leadtime)) > 0):
                    rs = cur.fetchall()
                    msg_deleted = """Dear FlockLab user,\n\n\
FlockLab can not save your test data forever and thus your tests have a retention time of %s days before they are deleted.\n\
According to this policy, the following tests have been deleted. \n\n\
Test ID\tEnd of test\tTest title\n\
===============================================================\n\
%s\n\
Yours faithfully,\nthe FlockLab server"""
                    testlist = ""
                    testids = ", ".join([str(i[0]) for i in rs])
                    logger.debug("Found tests whose retention time expired: %s"%testids)
                    for testid, title, enddate in rs:
                        testlist = testlist + "%s\t%s\t%s\n"%(testid, enddate, title)
                    msg = msg_deleted%(retention_time_user, testlist)
                    if is_active == 1:
                        ret = flocklab.send_mail(subject="[FlockLab %s] %s"%(name, "Retention time expired") , message=msg, recipients=owneremail)
                    else:
                        ret = 0
                    if ret != 0:
                        msg = "Could not send Email to %s. Function returned %d"%(owneremail, ret)
                        logger.error(msg)
                        emails = flocklab.get_admin_emails(cur)
                        msg = "%s on server %s encountered error:\n\n%s" % (__file__, os.uname()[1], msg)
                        flocklab.send_mail(subject="[FlockLab %s]"%name, message=msg, recipients=emails)
                        continue
                    else:
                        # Mark the tests in the database:
                        sql =    """    UPDATE `tbl_serv_tests`
                                    SET `test_status` = 'todelete'
                                    WHERE `serv_tests_key` IN (%s)
                                """
                        cur.execute(sql%(testids))
                        cn.commit()
                        logger.debug("Set test status to 'todelete' for tests.")
                else:
                    logger.debug("Found no tests whose retention time expired.")
    except:
        msg = "Encountered error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        logger.error(msg)
        emails = flocklab.get_admin_emails(cur)
        msg = "%s on server %s encountered error:\n\n%s" % (__file__, os.uname()[1], msg)
        flocklab.send_mail(subject="[FlockLab RetentionCleaner]", message=msg, recipients=emails)
    finally:
        cur.close()
        cn.close()
    
    logger.debug("Finished. Exit program.")
    sys.exit(flocklab.SUCCESS)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg, errno.EAGAIN)
        
