#! /usr/bin/env python3

__author__		= "Balz Maag <bmaag@ee.ethz.ch>"
__copyright__	= "Copyright 2010, ETH Zurich, Switzerland, Balz Maag"
__license__		= "GPL"


import os, sys, subprocess, getopt, errno, tempfile, time, shutil, struct, __main__, operator
from xml.etree.ElementTree import ElementTree
from struct import pack
# Import local libraries
from lib.flocklab import SUCCESS
import lib.flocklab as flocklab


### Global variables ###
###
scriptname = os.path.basename(__main__.__file__)
scriptpath = os.path.dirname(os.path.abspath(sys.argv[0]))
###
debug  = False
logger = None

headerBin = dict(
  route='0000',
  tracing='0001',
  actuation='0010',
  nth='0011',
  start='0100',
  cb='0101',
  barrier='0110',
)

onOffBin = dict(
  on='1111',
  off='0000'
)

b_min = 30
b_max = 60

##############################################################################
#
# timeformat_xml2epoch -	Convert between different timeformats of 
#							XML config file and FlockLab services
#
##############################################################################
def timeformat_xml2epoch(config=None, timestring=""):
	if (not config) or (not timestring):
		return errno.EINVAL
	try:
		# First convert time from xml-string to time format:
		servicetime = time.strptime(timestring, config.get("observer", "timeformat"))
		# Now convert to epoch:
		servicetimeepoch = int(time.mktime(servicetime))
	except:
		return errno.EFAULT
	
	return servicetimeepoch	
### END timeformat_xml2epoch()

##############################################################################
#
# Usage
#
##############################################################################
def usage():						 
	print("Usage: %s --xml=<path> --outfile=<path> [--debug] [--help]" %sys.argv[0])
	print("Convert a test-configuration in the provided XMl to a binary command file for FPGA UART transmission")
	print("Options:")
	print("  --xml=<path>\t\t\tPath to the XML file with the testconfiguration.")
	print("  --outfile=<path>\t\t\tPath to the file where the configuration is written to.")
	print("  --debug\t\t\tOptional. Print debug messages to log.")
	print("  --help\t\t\tOptional. Print this help.")
### END usage()




##############################################################################
#
# MAIN: converts a xml-testdescription into binary commands for the FPGA
#
#
##############################################################################
def main(argv):
	global debug
	global logger
	xmlfile = None
	outfile = None
	last_barrier = 0
	
	# Get logger:
	logger = flocklab.get_logger(loggername=scriptname, loggerpath=scriptpath)
	# get config
	config = flocklab.get_config()

	# Get command line parameters.
	try:								
		opts, args = getopt.getopt(argv, "hdx:o:", ["help", "debug", "xml=", "outfile="])
	except getopt.GetoptError as err:
		print(str(err))
		logger.error(str(err))
		usage()
		sys.exit(errno.EINVAL)
	except:
		logger.error("Error: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
		sys.exit(errno.EINVAL)
	for opt, arg in opts:
		if opt in ("-x", "--xml"):
			xmlfile = arg
			if not (os.path.exists(xmlfile)):
				err = "Error: file %s does not exist" %(str(xmlfile))
				logger.error(err)
				sys.exit(errno.EINVAL)
		elif opt in ("-o", "--outfile"):
			outfile = arg
		elif opt in ("-h", "--help"):
			debug = True
			usage()
			sys.exit(SUCCESS)
		elif opt in ("-d", "--debug"):
			debug = True
		else:
			logger.error("Wrong API usage")
			usage()
			sys.exit(errno.EINVAL)
	 
	 # Check for mandatory arguments:
	if not xmlfile:
		print("Wrong API usage")
		logger.error("Wrong API usage")
		usage()
		sys.exit(errno.EINVAL)
	
	errors = []
	
	# open uart config file
	try:
		f = open(outfile,"wb")
	except:
		logger.warn("Error opening binary config file")
		sys.exit(errno.EINVAL)
	# parse xml file
	#xmlfile = "current.xml"
	try:
		tree = ElementTree()
		tree.parse(xmlfile)
		if debug:
			logger.debug("Parsed XML.")
	except:
		msg = "Could not find or open XML file at %s."%(str(xmlfile))
		errors.append(msg)
		if debug:
			logger.error(msg)	


	# sequence in binary file must be:
	# 1. route off
	# 2. tracing
	# 3. nth sample
	# 4. reset pin actuation at time 0.0
	# 5. start at time StartTime
	
	##############################################################################
	# 
	# ROUTING 
	#
	##############################################################################
	# routing off, no xml parsing needed:
	try:
		f.write((int(headerBin['route'] + onOffBin['off'],2).to_bytes(1, 'big')))
	except:
		logger.error("Error writing route off command to cmd-file")
	 
	##############################################################################
	# 
	# TRACING
	#
	##############################################################################
	tracePins = []
	if (tree.find('obsGpioMonitorConf') != None):
		if debug:
			logger.debug("Found config for GPIO monitoring.")
	
		# find all tracing pins
	 
		subtree = tree.find('obsGpioMonitorConf')
		pinconfs = list(subtree.getiterator("pinConf"))
		for pinconf in pinconfs:
			tracePins.append(pinconf.find('pin').text)
  
	# set appropriate bit in tracing-pin byte
	traceBin = 0;
	for i in tracePins:
		traceBin |= (1 << flocklab.daqpin_abbr2num(i))
	

	##############################################################################
	# 
	# ACTUATION
	#
	##############################################################################
	
	# Format: actuatePins = ['startimeEpoch','microsecs','pin','level']
	actuatePins = []
	rstTime = [];
	if (tree.find('obsGpioSettingConf') != None):
		if debug:
			logger.debug("Found config for GPIO setting.")
		subtree = tree.find('obsGpioSettingConf')
		pinconfs = list(subtree.getiterator("pinConf"))
		# first find start and stop time of test
		for i in pinconfs:
			pin = flocklab.daqpin_abbr2num(i.find('pin').text)
			starttimeEpoch = timeformat_xml2epoch(config, i.find('absoluteTime/absoluteDateTime').text)
			if pin == 0:
				rstTime.append(starttimeEpoch)
		
		rstTime.sort()
		# get the actual test start time
		testStartTime = rstTime[0]
		# get the actual test stop time
		testStopTime = rstTime[len(rstTime)-1]
		
		if testStartTime > testStopTime:
			logger.error("Invalid test start and stop time")
			sys.exit(EINVAL)
		
		invalid_actuation_cnt = 0
		for pinconf in pinconfs:
			pin = flocklab.daqpin_abbr2num(pinconf.find('pin').text)
			# we want also to monitor pins which are actuated
			traceBin |= (1 << pin)
			# tracing and actuation pins do not share the same bit-field in the corresponding uart packet (act. is shifted by 1 bit to left compared to trace.)
			pin = pin + 1;
			level = flocklab.daqlevel_str2abbr(pinconf.find('level').text)
			interval = int(pinconf.find('intervalMicrosecs').text)
			count = int(pinconf.find('count').text)
			# Get time and bring it into right format:
			starttimeEpoch = timeformat_xml2epoch(config, pinconf.find('absoluteTime/absoluteDateTime').text)
			microsecs = int(pinconf.find('absoluteTime/absoluteMicrosecs').text)
			# add actuations
			for j in range(0,count):
				intSec = (microsecs + (j)*interval)/1000000
				intMicro = (microsecs +(j)*interval)%1000000
				if starttimeEpoch + intSec - testStartTime + intSec >= 0 and intMicro >= 0 and testStopTime - starttimeEpoch - intSec >= 0:
					actuatePins.append([starttimeEpoch-testStartTime + intSec, intMicro, pin, level])
				else:
					invalid_actuation_cnt = invalid_actuation_cnt + 1
		if invalid_actuation_cnt > 0:
			logger.debug("There were %d invalid actuation times." % (invalid_actuation_cnt))
		
		# sort all the gathered configs by time
		traceBinString = str(bin(traceBin))[2:].zfill(8)
		# write the tracing config command to the config file	 
		f.write((int(headerBin['tracing'] + traceBinString[0:4],2).to_bytes(1, 'big')))
		f.write((int('1' + traceBinString[4:8] + '000',2).to_bytes(1, 'big')))
		
	##############################################################################
	# 
	# POWER PROFILING: basically is an actuation
	#
	##############################################################################
	# 
	# TODO: multiple sammpling rates??? complicates the config a bit as we need to change the sampling rate right before the next actuation command which starts the powerprofiling
	nthsample = 1
	if (tree.find('obsPowerprofConf') != None):
		if debug:
			logger.debug("Found config for powerprofiling.")
		# Cycle through all powerprof configs and insert them into file:
		subtree = tree.find('obsPowerprofConf')
		profconfs = list(subtree.getiterator("profConf"))
		for profconf in profconfs:
			duration = int(profconf.find('duration').text)
			# Get time and bring it into right format:
			starttimeEpoch = timeformat_xml2epoch(config, profconf.find('absoluteTime/absoluteDateTime').text)
			microsecs = int(profconf.find('absoluteTime/absoluteMicrosecs').text)
			nthsample = profconf.find('samplingDivider')
			if nthsample != None:
				nthsample = int(nthsample.text)
			else:
				nthsample = int(config.get('observer', 'daq_pp_nth_sample_default'))
			# set adc_off_act to low, at the starttime and to high after duration
			if starttimeEpoch - testStartTime >= 0 and microsecs >= 0:
				actuatePins.append([starttimeEpoch - testStartTime, microsecs, 0, 0])
			else:
				logger.error("Invalid actuation time")
			
			durMicro = (duration*1000)%1000000
			durSec = int(duration/1000)
			
			if starttimeEpoch - testStartTime + durSec >= 0 and microsecs + durMicro >= 0:
				actuatePins.append([starttimeEpoch - testStartTime + durSec, microsecs + durMicro, 0, 1])
			else:
				logger.error("Invalid actuation time")
	
	# write nth-sample to the file
	if nthsample != None:
		nthString = str(bin(nthsample))[2:].zfill(11)
		f.write((int(headerBin['nth'] + nthString[0:4],2).to_bytes(1, 'big')))
		f.write((int('1' + nthString[4:11] ,2).to_bytes(1, 'big')))
		
	# sort the commands by: second -> microsecond -> pin-number
	actuatePins.sort(key=operator.itemgetter(0,1,2))
	# update toggle states
	pinstates = {}
	for i in range(0,len(actuatePins)):
		if actuatePins[i][3]==flocklab.TOGGLE:
			if actuatePins[i][2] in pinstates:
				actuatePins[i][3]=(pinstates[actuatePins[i][2]] + 1) % 2 # toggle
			else:
				actuatePins[i][3]=flocklab.HIGH # initial state, set to HIGH
		pinstates[actuatePins[i][2]] = actuatePins[i][3];
	
	# now we can write the test-start packet
	f.write((int(headerBin['start'] + onOffBin['on'],2).to_bytes(1, 'big')))   # 0x4f
	f.write(pack('>I',testStartTime))

	actCmds = list(range(0,len(actuatePins)))
	for ind in actCmds:
		actPin = 0
		actPin |= 1 << actuatePins[ind][2]
		actPin = str(bin(actPin))[2:].zfill(4)
		actLevel = 0
		actLevel |= actuatePins[ind][3] << actuatePins[ind][2]
		actLevel = str(bin(actLevel))[2:].zfill(4)
		actSec = str(bin(int(actuatePins[ind][0]) * 5 + int(actuatePins[ind][1] / 200000)))[2:].zfill(17) # '1s' on the FPGA is 200ms
		actSubsec = str(bin((actuatePins[ind][1] % 200000) * 10))[2:].zfill(21) # subsec has a resolution of 100ns
		# insert a barrier every time the actuation time is > last_barrier + b_min
		if actuatePins[ind][0] > last_barrier + b_max:
			last_barrier = actuatePins[ind][0] - b_min
			f.write((int(headerBin['barrier'] + '0000',2).to_bytes(1, 'big')))
			f.write(pack('>I',int(last_barrier + testStartTime)))

		f.write((int(headerBin['actuation'] + actPin,2).to_bytes(1, 'big')))
		f.write((int('1' + actLevel + actSec[0:3],2).to_bytes(1, 'big')))
		f.write((int('1' + actSec[3:10],2).to_bytes(1, 'big')))
		f.write((int('1' + actSec[10:17],2).to_bytes(1, 'big')))
		f.write((int('1' + actSubsec[0:7],2).to_bytes(1, 'big'))) #5 data
		f.write((int('1' + actSubsec[7:14],2).to_bytes(1, 'big'))) #6 data
		f.write((int('1' + actSubsec[14:21],2).to_bytes(1, 'big'))) #7 data
	 
	f.flush()
	os.fsync(f.fileno())
	f.close()
	sys.exit(SUCCESS)


if __name__ == "__main__":
	try:
		main(sys.argv[1:])
	except Exception:
		msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
		flocklab.error_logandexit(msg, errno.EAGAIN, name, logger, config)
