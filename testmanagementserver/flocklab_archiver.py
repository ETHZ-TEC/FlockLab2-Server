#!/usr/bin/env python3

__author__        = "Christoph Walser <walserc@tik.ee.ethz.ch>, Adnan Mlika"
__copyright__    = "Copyright 2010, ETH Zurich, Switzerland"
__license__        = "GPL"


import sys, os, getopt, errno, traceback, time, shutil, logging, subprocess, __main__, types
# Import local libraries
from lib.flocklab import SUCCESS
import lib.flocklab as flocklab


### Global variables ###
###
scriptname = os.path.basename(__main__.__file__)
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
name = "Archiver"
###

logger = None
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
# Usage
#
##############################################################################
def usage():
    print("Usage: %s --testid=<int> [--email] [--debug] [--help]" %scriptname)
    print("Options:")
    print("  --testid=<int>\t\tTest ID of test whose results should be archived.")
    print("  --email\t\t\tOptional. Send the data to the test owner by email.")
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
    global config
    
    send_email = False
    testid = -1
    
    # Set timezone to UTC ---
    os.environ['TZ'] = 'UTC'
    time.tzset()
    
    # Get logger ---
    logger = flocklab.get_logger(loggername=scriptname, loggerpath=scriptpath)
        
    # Get config ---
    config = flocklab.get_config(configpath=scriptpath)
    if not config:
        msg = "Could not read configuration file. Exiting..."
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
    #logger.debug("Read configuration file.")
            
    # Get arguments ---
    try:
        opts, args = getopt.getopt(argv, "ehdt:", ["email", "help", "debug", "testid=" ])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warn(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(SUCCESS)
        elif opt in ("-e", "--email"):
            send_email = True
        elif opt in ("-d", "--debug"):
            logger.debug("Detected debug flag.")
            logger.setLevel(logging.DEBUG)
        elif opt in ("-t", "--testid"):
            try:
                testid = int(arg)
                if testid <= 0:
                    raise Error
            except:
                logger.warn("Wrong API usage: testid has to be a positive number")
                sys.exit(errno.EINVAL)
        else:
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)

    # Check if necessary parameters are set ---
    if ((testid == -1)):
        logger.warn("Wrong API usage")
        sys.exit(errno.EINVAL)
        
    # Add Test ID to logger name ---
    logger.name += " (Test %d)"%testid
    
    # Connect to the DB ---
    try:
        (cn, cur) = flocklab.connect_to_db(config, logger)
    except:
        msg = "Could not connect to database"
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
    
    # Check if max number of instances is not reached ---
    rs = flocklab.count_running_instances(scriptname)
    if (rs >= 0):
        maxinscount = config.getint('archiver', 'max_instances')
        if rs > maxinscount:
            msg = "Maximum number of instances (%d) for script %s with currently %d instances running exceeded. Aborting..."%(maxinscount, scriptname, rs)
            flocklab.error_logandexit(msg, errno.EUSERS, name, logger, config)
        #else:
            #logger.debug("Maximum number of instances (%d) for script %s with currently %d instances running not exceeded."%(maxinscount, scriptname, rs))
    else:
        msg = "Error when trying to count running instances of %s. Function returned with %d"%(scriptname, rs)
        flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
        
    # Check if the Test ID exists in the database ---
    rs = flocklab.check_test_id(cur, testid)
    if rs != 0:
        if rs == 3:
            msg = "Test ID %d does not exist in database." %testid
            flocklab.error_logandexit(msg, errno.EINVAL, name, logger, config)
        else:
            msg = "Error when trying to get test ID from database: %s: %s"%(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            flocklab.error_logandexit(msg, errno.EIO, name, logger, config)
    
    # Check directories needed ---
    archivedir    = config.get('archiver', 'archive_dir')
    archivename    = "%d%s"%(testid, config.get('archiver','archive_ext'))
    archivepath    = "%s/%s"%(archivedir, archivename)
    if ((not os.path.exists(archivedir)) or (not os.path.isdir(archivedir))):
        if not os.path.exists(archivedir):
            os.makedirs(archivedir)
            logger.debug("Directory '%s' created." % (archivedir))
        else:
            msg = "The path %s does either not exist or is not a directory. Aborting..."%(archivedir)
            flocklab.error_logandexit(msg, errno.EINVAL, name, logger, config)
    
    # Generate archive ---
    if ((os.path.exists(archivepath)) and (os.path.isfile(archivepath))):
        logger.debug("Archive %s is already existing." %(archivepath))
    else:
        # Check if testresultsdir directory is existing:
        testresultsdir = "%s/%d" %(config.get('fetcher', 'testresults_dir'), testid)
        if ((not os.path.exists(testresultsdir)) or (not os.path.isdir(testresultsdir))):
            msg = "The path %s does either not exist or is not a directory. Aborting..."%(testresultsdir)
            flocklab.error_logandexit(msg, errno.EINVAL, name, logger, config)
        else:
            logger.debug("Directory %s exists."%(testresultsdir))
        # sort tar file, powerprofiling at the end
        pp_part = []
        resultparts = []
        for part in os.listdir(testresultsdir):
            if part!='powerprofiling.csv':
                resultparts.append(os.path.basename(testresultsdir)+'/'+part)
            else:
                pp_part.append(os.path.basename(testresultsdir)+'/'+part)
        resultparts.extend(pp_part)
        # Archive files:
        max_cpus = config.get('archiver', 'pigz_max_cpus')
        try:
            nice_level = config.getint('archiver', 'nice_level')
        except:
            logger.warn("Could not read nice_level from config file. Setting level to 10.")
            nice_level = 10
        if nice_level not in list(range(0,20)):
            logger.warn("Defined nice_level %d from config file is out of bounds. Setting level to 10."%nice_level)
            nice_level = 10
        tarcmd = ['tar', 'cf', '-', '-C', os.path.dirname(testresultsdir)]
        tarcmd.extend(resultparts)
        # Use pigz instead of gz because pigz makes use of multiple processors.
        gzcmd = ['pigz', '-p', max_cpus]
        outfile = open(archivepath, 'w+')
        logger.debug("Starting to write archive %s using max %s CPUs and level %d for compressing..."%(archivepath, max_cpus, nice_level))
        ptar = subprocess.Popen(tarcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, preexec_fn=lambda : os.nice(nice_level))
        pgz = subprocess.Popen(gzcmd, stdin=ptar.stdout, stdout=outfile, stderr=subprocess.PIPE, universal_newlines=True, preexec_fn=lambda : os.nice(nice_level))
        gzout, gzerr = pgz.communicate()
        tarout, tarerr = ptar.communicate()
        outfile.close()
        if pgz.returncode == 0:
            logger.debug("Created archive")
            # Remove testresultsdir:
            shutil.rmtree(testresultsdir)
            logger.debug("Removed directory %s"%testresultsdir)
        else:
            msg = "Error %d when creating archive %s"%(pgz.returncode, archivepath)
            msg += "Tried to pipe commands %s and %s"%(str(tarcmd), str(gzcmd))
            msg += "Tar command returned: %s, %s"%(str(tarout), str(tarerr))
            msg += "Gz command returned: %s, %s"%(str(gzout), str(gzerr))
            msg += "Error was: %s: %s"%(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            flocklab.error_logandexit(msg, errno.EFAULT, name, logger, config)
    archive_size = os.path.getsize(archivepath)
    archive_size_mb = float(archive_size)/1048576
    logger.debug("Archive has size %dB (%.3fMB)"%(archive_size, archive_size_mb))
    
    # Send results to test owner ---
    if send_email:
        # Get Email of test owner:
        rs = flocklab.get_test_owner(cur, testid)
        if isinstance(rs, tuple):
            usermail = rs[4]
        else:
            usermail = rs
        if ((usermail == 1) or (usermail == 2)):
            msg = "Error when trying to get test owner email address for test id %d from database. Aborting..." %testid
            flocklab.error_logandexit(msg, errno.EINVAL, name, logger, config)
        else:
            logger.debug("Got email of test owner: %s" %(str(usermail)))
    
        # Check the size of the archive and only send it by email if it has a decent size:
        if ( archive_size > int(config.get('archiver','email_maxsize')) ):
            msg = "Dear FlockLab user,\n\n\
Measurement data for test with ID %d has been successfully retrieved from the FlockLab database \
but could not be sent by email as it is too big. Please fetch your test results from the user interface.\n\n\
Yours faithfully,\nthe FlockLab server" %(testid)
            flocklab.send_mail(subject="[FlockLab] Results for Test ID %d" %testid, message=msg, recipients=usermail)
        else:
            msg = "Dear FlockLab user,\n\n\
Measurement data for test with ID %d has been successfully retrieved from the FlockLab database, \
compressed and attached to this email. You can find all test results in the attached archive file %s\n\n\
Yours faithfully,\nthe FlockLab server" %(testid, archivename)
            flocklab.send_mail(subject="[FlockLab] Results for Test ID %d" %testid, message=msg, recipients=usermail, attachments=[archivepath])
        logger.debug("Sent email to test owner")
    
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
