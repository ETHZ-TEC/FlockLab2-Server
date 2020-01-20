#!/usr/bin/env python3

import sys, os, getopt, errno, subprocess, MySQLdb, syslog, configparser, traceback
import lib.flocklab as flocklab


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print(("Usage: %s --image=<path> --platform=<string> --os=<string> [--core=<int>] [--quiet] [--help]" % sys.argv[0]))
    print("Validate a target image binary. Returns 0 on success, errno on errors.")
    print("Options:")
    print("  --image\t\t\tPath to the image binary which is to check.")
    print("  --platform\t\t\tPlatform for which the image is intended. Must be registered in FlockLab database, table tbl_serv_platforms.")
    print("  --core\t\t\tOptional. Core to use on platforms with several cores, defaults to 0.")
    print("  --quiet\t\t\tOptional. Do not print on standard out.")
    print("  --help\t\t\tOptional. Print this help.")
### END usage()


##############################################################################
#
# Main
#
##############################################################################
def main(argv):
    quiet = False
    imagepath = None
    platform = None
    core = 0
    
    # Open the log and create logger:
    logger = flocklab.get_logger()
    if not logger:
        print("Failed to init logger.")
        sys.exit(errno.EINVAL)
    
    # Get the config file:
    if flocklab.load_config() != flocklab.SUCCESS:
        logger.warn("Could not read configuration file. Exiting...")
        sys.exit(errno.EAGAIN)
    
    # Get command line parameters.
    try:
        opts, args = getopt.getopt(argv, "hqi:p:c:", ["help", "quiet", "image=", "platform=", "core="])
    except getopt.GetoptError as err:
        logger.warn(str(err))
        usage()
        sys.exit(errno.EINVAL)
    for opt, arg in opts:
        if opt in ("-i", "--image"):
            imagepath = arg
            if (not os.path.exists(imagepath) or not os.path.isfile(imagepath)):
                logger.warn("Wrong API usage: image binary file does not exist")
                sys.exit(errno.EINVAL)
        elif opt in ("-p", "--platform"):
            platform = arg
        elif opt in ("-c", "--core"):
            core = int(arg)
        elif opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-q", "--quiet"):
            quiet = True
        else:
            if not quiet:
                print("Wrong API usage")
                usage()
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)
    # Check mandatory arguments:
    if ((imagepath == None) or (platform == None)):
        if not quiet:
            print("Wrong API usage")
            usage()
        logger.warn("Wrong API usage")
        sys.exit(errno.EINVAL)
    
    # Connect to the DB:
    try:
        db = MySQLdb.connect(host=flocklab.config.get('database','host'), user=flocklab.config.get('database','user'), passwd=flocklab.config.get('database','password'), db=flocklab.config.get('database','database')) 
        cursor = db.cursor()
    except:
        logger.warn("Could not connect to the database because: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        sys.exit(errno.EAGAIN)
    
    # Check if platform is registered in database and get platform architecture:
    sql = """SELECT `a`.`architecture` FROM `tbl_serv_platforms` LEFT JOIN `tbl_serv_architectures` `a` ON `tbl_serv_platforms`.`serv_platforms_key` = `a`.`platforms_fk`  WHERE LOWER(name) = '%s' and `core`=%d;"""
    cursor.execute(sql %(str(platform).lower(), core))
    ret = cursor.fetchone()
    if not ret:
        err_str = "Could not find platform %s in database. Exiting..." % (str(platform)) 
        logger.warn(err_str)
        if not quiet:
            print(err_str)
        db.close()
        sys.exit(errno.EINVAL)
    else:
        arch = ret[0]
        arch = arch.lower()
    
    # Validate the image. This is dependent on the architecture of the target platform:
    errcnt = 0
    if arch == 'msp430':
        p = subprocess.Popen([flocklab.config.get('targetimage', 'binutils_msp430') + "/msp430-readelf", '-a', imagepath], stdout=open(os.devnull), stderr=open(os.devnull))
        if p.wait() != 0:
            errcnt += 1
    elif arch == 'arm':
        p = subprocess.Popen([flocklab.config.get('targetimage', 'binutils_arm') + "/arm-angstrom-linux-gnueabi-readelf", '-a', imagepath], stdout=open(os.devnull), stderr=open(os.devnull))
        if p.wait() != 0:
            errcnt += 1
    else:
        err_str = "No image validation test specified for architecture %s, thus defaulting to passed validation." %arch
        logger.info(err_str)
        if not quiet:
            print(err_str)
        
    if errcnt == 0:
        if not quiet:
            print("Target image validation successful.")
        ret = flocklab.SUCCESS
    else:
        err_str = "Target image validation failed. Please check your target image."
        logger.debug(err_str)
        if not quiet:
            print(err_str)
        ret = errno.EBADMSG
    sys.exit(ret)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        print("targetimage validator encountered an error: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc()))
        sys.exit(errno.EBADMSG)
