#! /usr/bin/env python3

__author__    = "Christoph Walser <walserc@tik.ee.ethz.ch>"
__copyright__ = "Copyright 2010, ETH Zurich, Switzerland"
__license__   = "GPL"

import sys, os, getopt, errno, threading, time, subprocess, queue, re, logging, traceback, __main__, urllib.request, urllib.error, urllib.parse, json, tempfile, MySQLdb, datetime
# Import local libraries
from lib.flocklab import SUCCESS
import lib.flocklab as flocklab


### Global variables ###
###
scriptname = os.path.basename(__main__.__file__)
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
name = "MMC check"
###
logger			= None
debug		   	= False
config			= None
zabbixServer	= "http://carrel.ethz.ch/zabbix/api_jsonrpc.php"



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
# MmcCheckThread
#
##############################################################################
class MmcCheckThread(threading.Thread):
	"""	Thread which calls MMC check script on an observer. 
	""" 
	def __init__(self, observer_ethernet, errors_queue, setupscriptpath):
		threading.Thread.__init__(self) 
		self._observer_ethernet	= observer_ethernet
		self._setupscriptpath	= setupscriptpath
		self._errors_queue		= errors_queue
		self._abortEvent		= threading.Event()
		self._errors			= []
		self._p					= None
		self._restore_logs = False
		
	def run(self):
		try:
			logger.debug("MmcCheckThread for %s starting..."%(self._observer_ethernet))
			# Download log data from observer because we want to restore it after the check:
			logger.debug("Downloading log files from %s..." %(self._observer_ethernet))
			(self._logtar_fd, self._logtar_name) = tempfile.mkstemp(".tar.gz", "flocklab_")
			cmd = ['ssh' ,'%s'%(self._observer_ethernet), "tar czf - /media/card/log/"]
			self._p = subprocess.Popen(cmd, stdout=self._logtar_fd, stderr=subprocess.PIPE)
			while self._p.returncode == None:
				self._abortEvent.wait(1.0)
				self._p.poll()
			if self._abortEvent.is_set():
				self._p.kill()
			else:
				out, err = self._p.communicate()
			os.close(self._logtar_fd)
			rs = self._p.returncode
			if (rs == SUCCESS):
				logger.debug("Downloaded log files from %s to file %s" %(self._observer_ethernet, self._logtar_name))
				self._restore_logs = True
			elif (rs == 255):
				msg = "%s is not reachable, thus MMC check script failed."%(self._observer_ethernet)
				self._errors.append((msg, errno.EHOSTUNREACH, self._observer_ethernet))
				logger.error(msg)
				raise Error
			else:
				msg = "Could not download log files from %s: failed with error code %s and error message %s" %(str(self._observer_ethernet), str(errno.errorcode[rs]), str(out))
				self._errors.append((msg, rs, self._observer_ethernet))
				logger.error(msg)
				logger.error("Tried to execute %s"%str(cmd))
				# continue without keeping old log files
			
			# Call the MMC check script on the observer:
			logger.debug("Executing MMC check script on %s..." %(self._observer_ethernet))
			cmd = ['ssh' ,'%s'%(self._observer_ethernet), "mmc_check.sh"]
			self._p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			while self._p.returncode == None:
				self._abortEvent.wait(1.0)
				self._p.poll()
			if self._abortEvent.is_set():
				self._p.kill()
			else:
				out, err = self._p.communicate()
			rs = self._p.returncode
			if (rs == SUCCESS):
				logger.debug("MMC check script on %s succeeded." %(self._observer_ethernet))
			elif (rs == 255):
				msg = "%s is not reachable, thus MMC check script failed."%(self._observer_ethernet)
				self._errors.append((msg, errno.EHOSTUNREACH, self._observer_ethernet))
				logger.error(msg)
				raise Error
			else:
				msg = "MMC check script on %s failed with error code %s and error message %s" %(str(self._observer_ethernet), str(errno.errorcode[rs]), str(out))
				self._errors.append((msg, rs, self._observer_ethernet))
				logger.error(msg)
				logger.error("Tried to execute %s"%str(cmd))
				raise Error
			
			# Restore the media card on the observer:
			logger.debug("Re-creating contents of MMC card on %s..." %(self._observer_ethernet))
			cmd = ["%s/setup_new_observer.sh"%self._setupscriptpath, self._observer_ethernet, "-sdsetuponly"]
			self._p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self._setupscriptpath)
			while self._p.returncode == None:
				self._abortEvent.wait(1.0)
				self._p.poll()
			if self._abortEvent.is_set():
				self._p.kill()
			else:
				out, err = self._p.communicate()
			rs = self._p.returncode
			if (rs == SUCCESS):
				logger.debug("MMC card re-created on %s." %(self._observer_ethernet))
			elif (rs == 255):
				msg = "%s is not reachable, thus MMC check script failed."%(self._observer_ethernet)
				self._errors.append((msg, errno.EHOSTUNREACH, self._observer_ethernet))
				logger.error(msg)
				raise Error
			else:
				msg = "Could not re-create MMC card on %s: failed with error code %s and error message %s" %(str(self._observer_ethernet), str(errno.errorcode[rs]), str(out))
				self._errors.append((msg, rs, self._observer_ethernet))
				logger.error(msg)
				logger.error("Tried to execute %s"%str(cmd))
				raise Error
		
			# Upload log data to observer:
			if self._restore_logs:
				logger.debug("Restoring log files to MMC card on %s..." %(self._observer_ethernet))
				self._logtar_fd = open(self._logtar_name)
				cmd = ['ssh', '%s'%(self._observer_ethernet), 'tar xzf - -C /']
				self._p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=self._logtar_fd)
				while self._p.returncode == None:
					self._abortEvent.wait(1.0)
					self._p.poll()
				if self._abortEvent.is_set():
					self._p.kill()
				else:
					out, err = self._p.communicate()
				rs = self._p.returncode
				self._logtar_fd.close()
				if (rs == SUCCESS):
					logger.debug("Log files restored to MMC card on %s." %(self._observer_ethernet))
				elif (rs == 255):
					msg = "%s is not reachable, thus MMC check script failed."%(self._observer_ethernet)
					self._errors.append((msg, errno.EHOSTUNREACH, self._observer_ethernet))
					logger.error(msg)
					raise Error
				else:
					msg = "Could not restore log files to MMC card on %s: failed with error code %s and error message %s" %(str(self._observer_ethernet), str(errno.errorcode[rs]), str(out))
					self._errors.append((msg, rs, self._observer_ethernet))
					logger.error(msg)
					logger.error("Tried to execute %s"%str(cmd))
					raise Error
			else:
				logger.debug("Skipping restoration of log files to MMC card on %s..." %(self._observer_ethernet))
			
			# Determine number of badblocks on MMC card:
			logger.debug("Checking number of badblocks on MMC card on %s..." %(self._observer_ethernet))
			cmd = ['ssh' ,'%s'%(self._observer_ethernet), 'dumpe2fs -b /dev/mmcblk0p1 | wc -l']
			self._p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
			while self._p.returncode == None:
				self._abortEvent.wait(1.0)
				self._p.poll()
			if self._abortEvent.is_set():
				self._p.kill()
			else:
				out, err = self._p.communicate()
			rs = self._p.returncode
			if (rs == SUCCESS):
				n = int(out)
				logger.debug("Number of badblocks on MMC card on %s: %d" %(self._observer_ethernet, n))
				if n > 0:
					if n > 200:
						msg = "Number of badblocks on MMC on %s: %d. Consider replacing the card as there are quite many blocks bad"%(self._observer_ethernet, n)
					else:
						msg = "Number of badblocks on MMC on %s: %d. Everything is fine, no action required."%(self._observer_ethernet, n)
					self._errors.append((msg, errno.EIO, self._observer_ethernet))
					logger.error(msg)
			elif (rs == 255):
				msg = "%s is not reachable, thus MMC check script failed."%(self._observer_ethernet)
				self._errors.append((msg, errno.EHOSTUNREACH, self._observer_ethernet))
				logger.error(msg)
				raise Error
			else:
				msg = "Could not check number of badblocks on MMC card on %s: failed with error code %s and error message %s" %(str(self._observer_ethernet), str(errno.errorcode[rs]), str(out))
				self._errors.append((msg, rs, self._observer_ethernet))
				logger.error(msg)
				logger.error("Tried to execute %s"%str(cmd))
				raise Error
			
			# Restart observer:
			logger.debug("Reboot %s..." %(self._observer_ethernet))
			cmd = ['ssh' ,'%s'%(self._observer_ethernet), 'reboot']
			self._p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			
		except:
			# Main thread requested abort.
			# Close a possibly still running subprocess:
			if (self._p is not None) and (self._p.poll() is not None):
				self._p.kill()
			msg = "MmcCheckThread for %s aborted because of error: %s: %s"%(self._observer_ethernet, str(sys.exc_info()[0]), str(sys.exc_info()[1]))
			self._errors.append((msg, errno.ECOMM, self._observer_ethernet))
			logger.error(msg)
		finally:
			if (len(self._errors) > 0):
				self._errors_queue.put((self._observer_ethernet, self._errors))
			try:
				os.unlink(self._logtar_name)
			except OSError:
				pass # ignore if file is not there
			
	def abort(self):
		self._abortEvent.set()
	
### END MmcCheckThread



##############################################################################
#
# Authenticate on Zabbix server
#
##############################################################################
def zabbixAuthenticate(server):
	data = json.dumps({"jsonrpc":"2.0","method":"user.login","params":{"user":"flocklab_api","password":"flockrock"},"id":"1"})
	req = urllib.request.Request(server, data, headers = {'Content-Type': 'application/json'})
	ret = urllib.request.urlopen(req)
	out = ret.read()
	try:
		pairs = out.split(',')[1]
		authkey = pairs.split(':')[1]
		authkey = authkey[1:-1]
	except:
		authkey = None
	finally:
		return authkey
### END zabbixAuthenticate()



##############################################################################
#
# Usage
#
##############################################################################
def usage():
	print("Usage: %s [--obslist <list>] [--debug] [--help]" %scriptname)
	print("  --obslist\t\t\tOptional. Only check observers in list. List is a colon separated string.")
	print("  --debug\t\t\tOptional. Print debug messages to log.")
	print("  --help\t\t\tOptional. Print this help.")
### END usage()



##############################################################################
#
# Main
#
##############################################################################
def main(argv):
	global logger
	global debug
	global config
	errors = []
	warnings = []
	obslist = []
		
	# Set timezone to UTC:
	os.environ['TZ'] = 'UTC'
	time.tzset()
		
	# Get logger:
	logger = flocklab.get_logger(loggername=scriptname, loggerpath=scriptpath)
	
	# Get the config file:
	config = flocklab.get_config(configpath=scriptpath)
	if not config:
		msg = "Could not read configuration file. Exiting..."
		flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
	#logger.debug("Read configuration file.")
		
	# Get the arguments:
	try:
		opts, args = getopt.getopt(argv, "o:dh", ["obslist=", "debug", "help"])
	except getopt.GetoptError as err:
		print(str(err))
		logger.warn(str(err))
		usage()
		sys.exit(errno.EINVAL)
	except:
		msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
		flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
	
	for opt, arg in opts:
		if opt in ("-o", "--obslist"):
			obslist = arg.split(':')
			try:
				obslist = list(map(int, obslist))
			except:
				msg = "Could not parse observer list. Exiting..."
				flocklab.error_logandexit(msg, errno.EINVAL, name, logger, config)
		elif opt in ("-d", "--debug"):
			debug = True
			logger.setLevel(logging.DEBUG)
			logger.debug("Detected debug flag.")
		elif opt in ("-h", "--help"):
			usage()
			sys.exit(SUCCESS)
		else:
			logger.warn("Wrong API usage")
			sys.exit(errno.EINVAL)
	
	try:
		# Reserve testbed ---
		# Connect to the database:
		try:
			(cn, cur) = flocklab.connect_to_db(config, logger)
		except:
			msg = "Could not connect to database"
			flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
		# find next available slot
		starttime = datetime.datetime.now()
		sql = "SELECT DATE_SUB(time_start_wish, INTERVAL %d MINUTE), DATE_ADD(time_end_wish, INTERVAL %d MINUTE) FROM tbl_serv_tests WHERE time_end_wish > '%s' AND test_status IN ('planned','preparing','running','cleaning up','syncing','synced','aborting') ORDER BY time_start_wish ASC"
		cur.execute(sql % (int(config.get('tests', 'setuptime')), int(config.get('tests', 'cleanuptime')), starttime.strftime(config.get("database", "timeformat"))))
		ret = cur.fetchall()
		for r in ret:
			if r[0] - starttime > datetime.timedelta(hours=int(config.get("mmccheck", "reservation_duration_h"))):
				break
			starttime = r[1]
		# add reservation slot
		sql = "INSERT INTO tbl_serv_reservations (group_id_fk, time_start, time_end) VALUES (%d, '%s', '%s');"
		cur.execute(sql % (int(config.get('mmccheck', 'reservation_group_id')), starttime.strftime(config.get("database", "timeformat")),  (starttime + datetime.timedelta(hours=int(config.get("mmccheck", "reservation_duration_h")))).strftime(config.get("database", "timeformat"))))
		cn.commit()
		cur.close()
		cn.close()
		# ----
		logger.debug("Starttime of testbed reservation is: %s" % str(starttime))
		starttime = time.mktime(starttime.timetuple())
		# Wait for testbed reservation to start ---
		if len(errors) == 0:
			waittime = starttime - time.time() + 10
			while waittime >= 0.0:
				# Interrupt waiting every 5 minutes if needed: 
				waittime = 300 if waittime > 300 else waittime					
				logger.info("Going to sleep for %f seconds."%waittime)
				time.sleep(waittime)
				logger.info("Woke up")
				waittime = starttime - time.time() + 10
		# Put Flocklab-Group in Zabbix into maintenance mode ---
		logger.debug("Putting FlockLab group in Zabbix into maintenance mode...")
		maintenance_id = None
		logger.debug("Authenticating on Zabbix server...")
		authkey = zabbixAuthenticate(zabbixServer)
		if authkey == None:
			errors.append("Could not authenticate on Zabbix server.")
		else:
			logger.debug("Authenticated on Zabbix server")
			now = time.time() - 60
			nowint = int(float(now))
			duration = 3600*int(config.get('mmccheck', 'reservation_duration_h'))
			data = json.dumps({"jsonrpc":"2.0","method":"maintenance.create","params":[{"groupids":[11],"name":"Maintenance for FLockLab","maintenance_type":"0","description":"Maintenance for FlockLab", "active_since":nowint,"active_till":nowint + duration + 100,"timeperiods":[{"timeperiod_type":"0","start_date":nowint,"period":duration}],}],"id":"3","auth":authkey})
			req = urllib.request.Request(zabbixServer, data, headers = {'Content-Type': 'application/json'})
			ret = urllib.request.urlopen(req)
			out = ret.read()
			try: 
				pairs = out.split(',')[1]
				maintenance_id = pairs.split(':')[2]
				maintenance_id = maintenance_id[2:-3]
				logger.debug("Put FlockLab group on Zabbix into maintenance mode (maintenance ID %s)"%maintenance_id)
			except:
				errors.append("Could not put FlockLab group on Zabbix into maintenance mode.")
				maintenance_id = None
			
		# Get all available observers ---
		if len(errors) == 0:
			try:
				(cn, cur) = flocklab.connect_to_db(config, logger)
				logger.debug("Connected to database.")
				sql =	"""	SELECT `ethernet_address` 
							FROM `tbl_serv_observer` 
							WHERE `status` = 'online'
						"""
				if len(obslist) > 0:
					sql = sql + ' AND `observer_id` IN (%s)' % (','.join(map(str,obslist)))
				sql = sql + ';'
				rows = cur.execute(sql)
				rs = cur.fetchall()
				if not rs:
					errors.append("Found no observers which are online.")
				else:
					logger.debug("Found %d online observers."%rows)
					observers = []
					for obs in rs:
						observers.append(obs[0])
				try:
					cur.close()
					cn.close()
				except:
					pass
			except:
				errors.append("Could not connect to database.")
		
		# Run MMC check on observers ---
		if len(errors) == 0:
			# Start a thread for each observer:
			thread_list = []
			errors_queue = queue.Queue()
			for observer in observers:
				thread = MmcCheckThread(observer, errors_queue, setupscriptpath)
				thread_list.append(thread)
				thread.start()
				logger.debug("Started thread for %s" %(observer))
			# Wait for all threads to finish:
			for thread in thread_list:
				# Wait at most as long as the testbed is reserved for the threads to finish.
				thread.join(timeout=3600*int(config.get('mmccheck', 'reservation_duration_h')))
				if thread.isAlive():
					# Timeout occurred. Signal the thread to abort:
					logger.error("Telling thread for observer to abort...")
					thread.abort()
			# Wait again for the aborted threads:
			for thread in thread_list:	
				thread.join(timeout=20)
				if thread.isAlive():
					msg = "Thread for observer is still alive but should be aborted now."
					errors.append(msg)
					logger.error(msg)
				
			# Get all errors (if any):
			if not errors_queue.empty():
				logger.error("Queue with errors from observer threads is not empty. Getting errors...")
			while not errors_queue.empty():
				errs = errors_queue.get()
				for err in errs[1]:
					logger.error("Error from observer thread for %s: %s" %(str(err[2]), str(err[0])))
					errors.append(err[0])
		
		# Take Flocklab group on Zabbix out of maintenance mode:
		if maintenance_id:
			logger.debug("Taking FlockLab group in Zabbix out of maintenance mode...")
			logger.debug("Authenticating on Zabbix server...")
			authkey = zabbixAuthenticate(zabbixServer)
			if authkey == None:
				errors.append("Could not authenticate on Zabbix server.")
				errors.append("Flocklab group not taken out of maintenance mode on Zabbix server due to errors. Please do so manually.")
			else:
				logger.debug("Authenticated on Zabbix server.")
				data = json.dumps({"jsonrpc":"2.0","method":"maintenance.delete","params":[maintenance_id],"auth":authkey,"id":"4"})
				req = urllib.request.Request(zabbixServer, data, headers = {'Content-Type': 'application/json'})
				ret = urllib.request.urlopen(req)
				out = ret.read()
				if '"maintenanceids":["%s'%maintenance_id in out:
					logger.debug("FlockLab group taken out of maintenance mode on Zabbix server.")
				else:
					errors.append("Flocklab group not taken out of maintenance mode on Zabbix server due to errors. Please do so manually.")
				
		
		# Free testbed from reservation ---
		try:
			(cn, cur) = flocklab.connect_to_db(config, logger)
			logger.info("Removing reservation to free testbed...")
			sql = "DELETE FROM tbl_serv_reservations WHERE group_id_fk = %d;"
			cur.execute(sql % int(config.get('mmccheck', 'reservation_group_id')))
			cn.commit()
			cur.close()
			cn.close()
		except:
			msg = "Could not connect to database"
			flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
		
		# Inform admins ---
		if ((len(errors) > 0) or (len(warnings) > 0)):
			msg = "The following errors/warnings occurred:\n\n"
			for error in errors:
				msg = msg + "\t * ERROR: %s\n" %(str(error))
			for warn in warnings:
				msg = msg +  "\t * WARNING: %s\n" %(str(warn))
			logger.debug("Finished with %d errors and %d warnings"%(len(errors), len(warnings)))
			flocklab.error_logandexit(msg, errno.EFAULT, name, logger, config)
		else:
			# Send email to admin:
			try:
				cn, cur = flocklab.connect_to_db(config, logger)
				admin_emails = flocklab.get_admin_emails(cur, config)
				cur.close()
				cn.close()
				if ((admin_emails == 1) or (admin_emails == 2)):
					logger.error("Error when getting admin emails from database")
					raise
			except:
				# Use backup email address:
				admin_emails = "flocklab@tik.ee.ethz.ch"
			finally:
				msg = "Successfully finished MMC checks on observers."
				logger.debug(msg)
				flocklab.send_mail(subject="[FlockLab %s]"%(scriptname.capitalize()), message=msg, recipients=admin_emails)
	except Exception:
		msg = "Unexpected error: %s: %s"%(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
		print(msg)
		flocklab.error_logandexit(msg, errno.EFAULT, name, logger, config)
	sys.exit(SUCCESS)
		
### END main()

if __name__ == "__main__":
	try:
		main(sys.argv[1:])
	except Exception:
		msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
		flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)


