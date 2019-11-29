#!/usr/bin/env python3

__author__		= "Reto Da Forno <reto.daforno@tik.ee.ethz.ch>"
__copyright__	= "Copyright 2018, ETH Zurich, Switzerland"
__license__		= "GPL"


import sys, os, __main__, time, re
import lib.flocklab as flocklab


scriptname = os.path.basename(__main__.__file__)
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))


if __name__ == "__main__":
  r = []
  if len(sys.argv) == 2:
    # no email provided -> extract all addresses from the database
    try:
      config = flocklab.get_config(configpath=scriptpath)
      logger = flocklab.get_logger(loggername=scriptname, loggerpath=scriptpath)
      (cn, cur) = flocklab.connect_to_db(config, logger)
      cur.execute("""SELECT email FROM `tbl_serv_users` WHERE is_active=1;""")
      ret = cur.fetchall()
      if not ret:
        print("failed to get user emails from database")
        cur.close()
        cn.close()
        sys.exit()
      for elem in ret:
        r.append(elem[0])
      cur.close()
      cn.close()
    except Exception as e:
      print("could not connect to database: " + sys.exc_info()[1][0])
      sys.exit()
      
  elif len(sys.argv) == 3:
    r = re.split('[ ,;]+', sys.argv[2])
    if not '@' in r[0]:
      print("invalid email address")
      sys.exit()
    
  else:
    print("Usage:  ./%s [subject] [recipients] < [filename]" % scriptname)
    sys.exit()

  msg = sys.stdin.read()
  print("mail content:\n" + msg)
  s = sys.argv[1]
  sys.stdout.write("sending mail with subject '" + s + "' to " + str(len(r)) + " recipient(s) in  ")
  sys.stdout.flush()
  try:
    for x in range(5, 0, -1):
      sys.stdout.write('\b' + str(x))
      sys.stdout.flush()
      time.sleep(1)
      
    print(" ")
    for usermail in r:
      flocklab.send_mail(subject=s, message=msg, recipients=usermail)
      print("email sent to " + usermail)
    
  except KeyboardInterrupt:
    print("\naborted")
