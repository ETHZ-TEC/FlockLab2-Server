#! /usr/bin/env python3

# Script to register new target adapter IDs in the database

import os, sys, getopt, MySQLdb, errno, threading, subprocess, time, traceback, queue, logging, traceback
import lib.flocklab as flocklab


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print(("Usage: %s [--id] [--platform] [--help] [--adapterid]" % sys.argv[0]))
    print("Options:")
    print("  --id\t\t\tID of the DS2401P serial ID chip on the target adapter (15 characters, starts with '01-').")
    print("  --platform\t\tPlatform.")
    print("  --adapterid\t\tOptional. ID of the target adapter board. Set automatically if not provided.")
    print("  --help\t\tPrint this help")
### END usage()


##############################################################################
#
# Main
#
##############################################################################
def main(argv):

    serialid = None
    adapterid = 1
    platform = None
    ret = flocklab.SUCCESS
    
    # Get command line parameters.
    try:
        opts, args = getopt.getopt(argv, "hi:p:a:", ["help", "id=", "platform=", "adapterid="])
    except getopt.GetoptError as err:
        print((str(err)))
        usage()
        sys.exit(errno.EINVAL)
    except:
        print("Error %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        sys.exit(errno.EINVAL)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-i", "--id"):
            serialid = arg
        elif opt in ("-p", "--platform"):
            platform = arg
        elif opt in ("-a", "--adapterid"):
            try:
                adapterid = int(arg)
            except:
                adapterid = None
        else:
            print("Wrong API usage.")
            sys.exit(errno.EINVAL)

    if not serialid or len(serialid) != 15 or not serialid.startswith("01-"):
        print("No valid ID supplied. ID must be 15 characters long and start with 01-.")
        sys.exit(errno.EINVAL)

    # Get the config file:
    flocklab.load_config()

    # Check if a test is preparing, running or cleaning up. If yes, exit program.
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        print("Could not connect to database")
        sys.exit(errno.EPERM)
    
    try:
        # get a list of available platforms
        cur.execute("SELECT serv_tg_adapt_types_key, name FROM flocklab.tbl_serv_tg_adapt_types")
        rs = cur.fetchall()
        platforms = {}
        for adapter_type in rs:
            platforms[adapter_type[1]] = int(adapter_type[0])
        if platform in platforms:
            if adapterid is None:
                # get highest currently stored ID
                cur.execute("SELECT adapterid FROM flocklab.tbl_serv_tg_adapt_list WHERE tg_adapt_types_fk=%d ORDER BY adapterid LIMIT 1" % (platforms[platform]))
                rs = cur.fetchone()
                if rs:
                    adapterid = int(rs[0]) + 1
            cur.execute("INSERT INTO flocklab.tbl_serv_tg_adapt_list (`tg_adapt_types_fk`, `serialid`, `adapterid`) VALUES (%d, '%s', %d)" % (platforms[platform], serialid, adapterid))
            print("Serial ID %s registered for %s target adapter %d." % (serialid, platform, adapterid))
        else:
            print("'%s' is not a valid platform option. Available options: %s" % (platform, ", ".join(platforms.keys())))
           
    except MySQLdb.Error as err:
        print("MySQL error: %s" % str(err))
        ret = 1
    except:
        print("Error %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc()))
        ret = 2
    
    cur.close()
    cn.commit()
    cn.close()
    sys.exit(ret)
### END main()

if __name__ == "__main__":
    main(sys.argv[1:])
