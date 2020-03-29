#! /usr/bin/env python3

import os, sys, getopt, MySQLdb, errno, threading, subprocess, time, traceback, queue, logging
import lib.flocklab as flocklab


debug = False


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print(("Usage: %s [--searchtime <float>] [--maxretries <int>] [--debug] [--help] [--obs <id>] [--email] [--develop]" % sys.argv[0]))
    print("Options:")
    print("  --searchtime\t\tOptional. If set, standard time for waiting for the ID search is overwritten.")
    print("  --maxretries\t\tOptional. If set, standard number of retries for reading an ID is overwritten.")
    print("  --debug\t\tOptional. Print debug messages to log.")
    print("  --observer\t\tOptional. Update only observer with ID <id>.")
    print("  --develop\t\tOptional. Update only observers with status 'develop'.")
    print("  --email\t\tOptional. Send report via email.")
    print("  --help\t\tOptional. Print this help.")
### END usage()


##############################################################################
#
# UpdateSlotAssignThread
#
##############################################################################
class UpdateSlotAssignThread(threading.Thread):
    def __init__(self, observerdata, logger, searchtime, maxretries, queue):
        threading.Thread.__init__(self)
        self.ObsKey        = observerdata[0]
        self.ObsHostname   = observerdata[1]
        self.ObsSerialList = observerdata[2:]
        self.Logger        = logger
        self.Searchtime    = searchtime
        self.Maxretries    = maxretries
        self.Queue         = queue

    def run(self):
        # Get list of ID's for every slot from observer over SSH:
        cmd = flocklab.config.get("observer", "serialidscript")
        if self.Searchtime:
            cmd = "%s -s%.1f" %(cmd, self.Searchtime)
        if self.Maxretries:
            cmd = "%s -m%d" %(cmd, self.Maxretries)
        self.Logger.debug("Observer %s: calling %s" %(self.ObsHostname, cmd))
        p = subprocess.Popen(['ssh', '%s' % (self.ObsHostname), cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        rs = p.communicate()
        self.Logger.debug("Observer %s response: %s" % (self.ObsHostname, str(rs)))

        # Compare list against values stored on database if ssh command was successful
        if (rs[1] != ''):
            self.Logger.debug("Observer %s returned error: %s" % (self.ObsHostname, str(rs[1])))
        slots = rs[0].split('\n')
        if ((rs[1] == '') and (len(slots) > 1)):
            cmds = []
            changes = []
            for i, slot in enumerate(slots[0:4]):
                s = slot.split(' ')
                slotnr = s[0][0]
                serialid = s[1]

                # If a serial ID was found and if it differs in the database and on the observer, update the database:
                if serialid == 'not':
                    serialid = None
                if (serialid != self.ObsSerialList[i]):
                    msg = "Observer %s: serial IDs for slot %s differ. Value database: %s, value observer slot: %s" % (self.ObsHostname, slotnr, self.ObsSerialList[i], serialid)
                    self.Logger.debug(msg)
                    changes.append((self.ObsHostname, slotnr, self.ObsSerialList[i], serialid))
                    cmds.append(""" UPDATE `tbl_serv_observer`
                                    SET slot_%s_tg_adapt_list_fk = (
                                        SELECT `serv_tg_adapt_list_key`
                                        FROM `tbl_serv_tg_adapt_list`
                                        WHERE `serialid` = '%s')
                                    WHERE `serv_observer_key` = %s;
                            """ % (i+1, serialid, self.ObsKey))

            # If any changes need to be done to the database, do so:
            if len(cmds) > 0:
                try:
                    (cn, cur) = flocklab.connect_to_db()
                except:
                    self.Logger.error("Could not connect to database")
                    raise
                try:
                    for cmd in cmds:
                        #self.Logger.debug("Observer %s: executing SQL: %s" % (self.ObsHostname, cmd))
                        cur.execute(cmd)
                    cn.commit()

                    # Finally prepare message to send to admins about the change(s):
                    msg = ""
                    sql = """ SELECT `name`
                              FROM `tbl_serv_tg_adapt_types`
                              WHERE `serv_tg_adapt_types_key` = (
                                  SELECT `tg_adapt_types_fk`
                                  FROM `tbl_serv_tg_adapt_list`
                                  WHERE `serialid` = '%s');
                          """
                    for change in changes:
                        old = None
                        new = None
                        # Get the type of the old adapter from the DB:
                        if (change[2] == None):
                            old = 'None'
                        else:
                            cmd = sql % (change[2])
                            cur.execute(cmd)
                            #self.Logger.debug("Observer %s: executing SQL: %s" % (self.ObsHostname, cmd))
                            rs = cur.fetchone()
                            if rs:
                                old = rs[0]
                        # Get the type of the new adapter from the DB:
                        if (change[3] == None):
                            new = 'None'
                        else:
                            cmd = sql % (change[3])
                            cur.execute(cmd)
                            #self.Logger.debug("Observer %s: executing SQL: %s" % (self.ObsHostname, cmd))
                            rs = cur.fetchone()
                            if rs:
                                new = rs[0]
                        # If the serial id was not found in the database, inform the admin about it:
                        if not old:
                            msg = msg + "Observer %s: serial ID %s in slot %s not found in database. Has it not been registered yet?\n"  % (str(change[0]), str(change[2]), str(change[1]))
                        elif not new:
                            msg = msg + "Observer %s: serial ID %s in slot %s not found in database. Has it not been registered yet?\n"  % (str(change[0]), str(change[3]), str(change[1]))
                        else:
                            msg = msg + "Observer %s: serial IDs for slot %s differ. Old adapter according to database was %s (%s) but detected %s (%s) in slot. Database has been updated accordingly.\n" % (str(change[0]), str(change[1]), str(old), str(change[2]), str(new), str(change[3]))
                    self.Queue.put(msg)

                except MySQLdb.Error as err:
                    self.Logger.warning(str(err))
                    sys.exit(errno.EIO)
                except:
                    self.Logger.warning("Error updating serial ID: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
                finally:
                    cur.close()
                    cn.close()
            else:
                msg = "Observer %s: No change detected!\n" % (self.ObsHostname)
                self.Queue.put(msg)

        else:
            msg = "Observer %s: ssh invalid return!\n" % (self.ObsHostname)
            self.Queue.put(msg)

        return(flocklab.SUCCESS)
### END UpdateSlotAssignThread


##############################################################################
#
# Main
#
##############################################################################
def main(argv):

    ### Get global variables ###
    global debug
    threadlist = []
    searchtime = None
    maxretries = None
    email = False
    force = False
    observer = ""
    status = "'online', 'internal', 'develop'"

    # Get logger:
    logger = flocklab.get_logger()

    # Get command line parameters.
    try:
        opts, args = getopt.getopt(argv, "hds:m:fo:de", ["help", "debug", "searchtime", "maxretries", "force", "observer", "develop", "email"])
    except getopt.GetoptError as err:
        print((str(err)))
        logger.warning(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        logger.warning("Error %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        sys.exit(errno.EINVAL)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-d", "--debug"):
            debug = True
            logger.setLevel(logging.DEBUG)
        elif opt in ("-s", "--searchtime"):
            try:
                searchtime = float(arg)
                if (searchtime <= 0.0):
                    raise ValueError
            except:
                logger.warning("Wrong API usage: %s" %str(arg))
                usage()
                sys.exit(errno.EINVAL)
        elif opt in ("-f", "--force"):
            force = True
        elif opt in ("-o", "--observer"):
            try:
                observer = " AND observer_id=%u" % int(arg)
                print(("will only update observer %u" % int(arg)))
            except:
                print(("invalid argument '%s'" % arg))
                sys.exit(errno.EINVAL)
        elif opt in ("-d", "--develop"):
            print("will only update observers with status 'develop'")
            status = "'develop'"
        elif opt in ("-m", "--maxretries"):
            try:
                maxretries = int(arg)
                if (maxretries < 0):
                    raise ValueError
            except:
                logger.warning("Wrong API usage: %s" %str(arg))
                usage()
                sys.exit(errno.EINVAL)
        elif opt in ("-e", "--email"):
            email = True
        else:
            print("Wrong API usage")
            logger.warning("Wrong API usage")
            usage()
            sys.exit(errno.EINVAL)

    # Get the config file:
    flocklab.load_config()

    # Check if a test is preparing, running or cleaning up. If yes, exit program.
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        logger.error("Could not connect to database")
        raise
    if flocklab.is_test_running(cur) and not force:
        print("Test is running! You can force the target slot update on a specific observer with the flags '-f -o=<id>'.");
        logger.debug("A test is running, thus exit...")
        cur.close()
        cn.close()
    else:
        logger.info("Started slot assignment updater.")
        # Get all active observers from the database:
        logger.debug("Going to fetch current database status for active observers...")
        try:
            sql = """ SELECT a.serv_observer_key, a.ethernet_address, b.serialid AS serialid_1, c.serialid AS serialid_2, d.serialid AS serialid_3, e.serialid AS serialid_4
                      FROM `tbl_serv_observer` AS a
                      LEFT JOIN `tbl_serv_tg_adapt_list` AS b
                      ON a.slot_1_tg_adapt_list_fk = b.serv_tg_adapt_list_key
                      LEFT JOIN `tbl_serv_tg_adapt_list` AS c
                      ON a.slot_2_tg_adapt_list_fk = c.serv_tg_adapt_list_key
                      LEFT JOIN `tbl_serv_tg_adapt_list` AS d
                      ON a.slot_3_tg_adapt_list_fk = d.serv_tg_adapt_list_key
                      LEFT JOIN `tbl_serv_tg_adapt_list` AS e
                      ON a.slot_4_tg_adapt_list_fk = e.serv_tg_adapt_list_key
                      WHERE a.status IN (%s) %s
                """ % (status, observer)
            cur.execute(sql)
        except MySQLdb.Error as err:
            logger.warning(str(err))
            sys.exit(errno.EIO)
        except:
            logger.warning("Error %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        rs = cur.fetchall()
        cur.close()
        cn.close()
        # Prepare queue which is going to hold the messages returned from the threads:
        q = queue.Queue()
        # Start one update thread per observer:
        for observerdata in rs:
            logger.debug("Starting thread for %s" % (observerdata[1]))
            try:
                t = UpdateSlotAssignThread(observerdata, logger, searchtime, maxretries, q)
                threadlist.append(t)
                t.start()
            except:
                logger.warning("Error when starting thread for observer %s: %s: %s" % (observerdata[1], str(sys.exc_info()[0]), str(sys.exc_info()[1])))
                continue
        # Wait for threads to finish:
        logger.debug("Joining threads")
        for t in threadlist:
            try:
                if (maxretries and searchtime):
                    thread_timeoutadd = int(4*maxretries*searchtime)
                else:
                    thread_timeoutadd = 0
                t.join(timeout=(10 + thread_timeoutadd))
                if t.isAlive():
                    logger.warning("Timeout when joining thread - is still alive...")
            except:
                logger.warning("Error when joining threads...")
                continue
        # Get all messages from the threads which are now in the queue and send them to the admin:
        try:
            msg = ""
            while not q.empty():
                msg = msg + q.get_nowait()
            if not msg == "":
                if email:
                    try:
                        (cn, cur) = flocklab.connect_to_db()
                    except:
                        logger.error("Could not connect to database")
                        raise
                    emails = flocklab.get_admin_emails(cur)
                    flocklab.send_mail(subject="[FlockLab Slot Updater]", message=msg, recipients=emails)
                    cur.close()
                    cn.close()
                else:
                    print(msg)
        except:
            logger.warning("Error when sending change notifications to admin. %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))

    logger.debug("Slot assignment updater finished.")


    sys.exit(flocklab.SUCCESS)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Error %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        flocklab.error_logandexit(msg)
