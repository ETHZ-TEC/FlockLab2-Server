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
    adapterid = None
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
                cur.execute("SELECT adapterid FROM flocklab.tbl_serv_tg_adapt_list WHERE tg_adapt_types_fk=%d ORDER BY adapterid DESC LIMIT 1" % (platforms[platform]))
                rs = cur.fetchone()
                if rs:
                    adapterid = int(rs[0]) + 1
                else:
                    adapterid = 1
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
