#! /usr/bin/env python3

import os, sys, getopt, traceback, MySQLdb, signal, random, time, errno, multiprocessing, subprocess, re, logging, __main__, threading, struct, types, queue, math, shutil, lxml.etree
import lib.daemon as daemon
import lib.flocklab as flocklab
from rocketlogger.data import RocketLoggerData
import pandas as pd
import numpy as np


logger                   = None
debug                    = False
testid                   = None 
errors                   = []
FetchObsThread_list      = []
FetchObsThread_stopEvent = None
FetchObsThread_queue     = None
obsfiledir               = None
testresultsdir           = None
testresultsfile_dict     = {}
mainloop_stop            = False
owner_fk                 = None
obsdict_byid             = None
serialdict               = None

ITEM_TO_PROCESS = 0
ITEM_PROCESSED  = 1


##############################################################################
#
# Error classes
#
##############################################################################
class DbFileEof(Exception):
    pass

class DbFileReadError(Exception):
    def __init__(self, expectedSize, actualSize, fpos):
        self.expectedSize = expectedSize
        self.actualSize = actualSize
        self.fpos = fpos
### END Error classes



##############################################################################
#
# Class ServiceInfo
#
##############################################################################
class ServiceInfo():
    def __init__(self, servicename):
        self.servicename = servicename
        self.files = []
        self.pattern = "^%s_[0-9]+\.[a-z]+$" % servicename
    
    def matchFileName(self, filename):
        return re.search(self.pattern, os.path.basename(filename)) is not None
        
    def addFile(self, filename):
        self.files.append(filename)
    
    def stripFileList(self, removelast=True):
        self.files.sort()
        if ((len(self.files) > 0) and removelast):
            self.files.pop()
### END ServiceInfo


##############################################################################
#
# sigterm_handler
#
##############################################################################
def sigterm_handler(signum, frame):
    """If the program is terminated by sending it the signal SIGTERM 
    (e.g. by executing 'kill') or SIGINT (pressing ctrl-c), 
    this signal handler is invoked for cleanup."""
    
    global mainloop_stop
    global FetchObsThread_stopEvent

    logger.info("Process received SIGTERM or SIGINT signal")
        
    # Signal all observer fetcher threads to stop:
    logger.debug("Stopping observer fetcher threads...")
    shutdown_timeout = flocklab.config.getint("fetcher", "shutdown_timeout")
    try:
        FetchObsThread_stopEvent.set()
    except:
        pass
    for thread in FetchObsThread_list:
        try:
            thread.join(shutdown_timeout)
        except:
            logger.warning("Fetcher thread did not stop within %d seconds." % shutdown_timeout)
    # Set DB status:
    logger.debug("Setting test status in DB to 'syncing'...")
    try:
        (cn, cur) = flocklab.connect_to_db()
        flocklab.set_test_status(cur, cn, testid, 'syncing')
        cur.close()
        cn.close()
    except:
        logger.warning("Could not connect to database.")
    
    # Tell the main loop to stop:
    mainloop_stop = True
    logger.debug("Set stop signal for main loop.")
### END sigterm_handler


##############################################################################
#
# Functions for parsing observer DB files data
#
##############################################################################
def parse_serial(buf):
    _data = struct.unpack("iii%ds" % (len(buf) - 12), buf) #int service; struct timeval timestamp;char * data
    return (_data[0], _data[3], "%i.%06i" % (_data[1], _data[2]))


##############################################################################
#
# Functions for converting observer DB data
#
##############################################################################
def convert_serial(obsdata, observer_id, node_id):
    try:
        result = "%s,%s,%s,%s,%s\n" % (obsdata[2], observer_id, node_id, serialdict[obsdata[0]], obsdata[1].decode('utf8').rstrip())
    except UnicodeDecodeError:
        # discard result, return empty string
        result = "%s,%s,%s,%s,\n" % (obsdata[2], observer_id, node_id, serialdict[obsdata[0]])
    return result


##############################################################################
#
# read_from_db_file: Read from an open DB file from an observer
#
##############################################################################
def read_from_db_file(dbfile):
    _buf = dbfile.read(4)
    if len(_buf) < 4:
        dbfile.close()
        raise DbFileEof()
    else:
        _size = struct.unpack("<I",_buf)
        _buf = dbfile.read(_size[0])
        if len(_buf) != _size[0]:
            _fpos = dbfile.tell() - 4 - len(_buf)
            dbfile.close()
            raise DbFileReadError(_size[0], len(_buf), _fpos)
        return _buf
### END read_from_db_file


##############################################################################
#
# worker_dbfiles: Parses observer DB files.
#
##############################################################################
def worker_dbfiles(queueitem=None, nodeid=None, resultfile_path=None, resultfile_lock=None, commitsize=1, parse_f=None, convert_f=None, logqueue=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        obsdbfile_path = "%s/%s" % (fdir,f)
        loggername = "(%s.%d) " % (cur_p.name, obsid)
        # Open file:
        dbfile = open(obsdbfile_path, 'rb')
        rows = 0
        conv_values = []
        while not dbfile.closed:
            # Process DB file line by line:
            try:
                # Parse one line:
                buf = read_from_db_file(dbfile)
                obsdata = parse_f(buf)
                # Convert data if needed:
                if convert_f != None:
                    conv_data = convert_f(obsdata, obsid, nodeid)
                    conv_values.append(conv_data)
                    rows += 1
                # Visualize data:
                if (commitsize > 0) & (rows >= commitsize):
                    # Write data to file:
                    #logqueue.put_nowait((loggername, logging.DEBUG, "Opening file %s for writing..." % (resultfile_path)))
                    resultfile_lock.acquire()
                    f = open(resultfile_path, 'a')
                    f.writelines(conv_values)
                    f.close()
                    resultfile_lock.release()
                    logqueue.put_nowait((loggername, logging.DEBUG, "Committed results to %s after %d rows" % (resultfile_path, rows)))
                    rows = 0
                    conv_values = []
            except DbFileEof:
                # logqueue.put_nowait((loggername, logging.DEBUG, "DbFileEof has occurred."))
                break # dbfile has been closed in parser (most likely because EOF was reached)
            except DbFileReadError as err:
                msg = "%s: Packet size (%i) did not match payload size (%i) @ %d." %(obsdbfile_path, err.expectedSize, err.actualSize, err.fpos)
                _errors.append((msg, errno.EIO, obsid))
                logqueue.put_nowait((loggername, logging.ERROR, msg))
        if (len(conv_values) > 0):
            # There is still data left. Do a last commit
            # Write data to file:
            resultfile_lock.acquire()
            f = open(resultfile_path, 'a')
            f.writelines(conv_values)
            f.close()
            resultfile_lock.release()
            logqueue.put_nowait((loggername, logging.DEBUG, "Committed final results to %s after %d rows" % (resultfile_path, rows)))
        # Remove processed file:
        os.unlink(obsdbfile_path)
    except:
        msg = "Error in worker process: %s: %s\n%s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_dbfiles


##############################################################################
#
# worker_gpiotracing: Worker function for converting and aggregating gpio
#               tracing data. Unlike for the other services, this function works on
#               whole observer DB files.
#
##############################################################################
def worker_gpiotracing(queueitem=None, nodeid=None, resultfile_path=None, logqueue=None, arg=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        inputfilename = "%s/%s" % (fdir, f)
        loggername = "(%s.%d) " % (cur_p.name, obsid)

        with open(resultfile_path, "a") as outfile:
            infile = open(inputfilename, "r")
            for line in infile:
                try:
                    (timestamp, ticks, pin, level) = line.strip().split(',', 3)
                    outfile.write("%s,%s,%s,%s,%s,%s\n" % (timestamp, ticks, obsid, nodeid, pin, level))
                except ValueError:
                    logqueue.put_nowait((loggername, logging.ERROR, "Could not parse line '%s' in gpiotracing worker process." % line))
                    break
            infile.close()
        os.remove(inputfilename)
    except:
        msg = "Error in gpiotracing worker process: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_gpiotracing


##############################################################################
#
# worker_powerprof: Worker function for converting and aggregating power
#        profiling data. Unlike for the other services, this function works on
#        whole observer DB files.
#
##############################################################################
def worker_powerprof(queueitem=None, nodeid=None, resultfile_path=None, logqueue=None, arg=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        inputfilename = "%s/%s" % (fdir, f)
        loggername = "(%s.%d) " % (cur_p.name, obsid)

        if arg and arg == 'rld':
            # RLD file format
            # simply move the file into the results directory
            try:
                resfilename = "%s.%s.%s.rld" % (os.path.splitext(resultfile_path)[0], obsid, nodeid)
                os.rename(inputfilename, resfilename)
            except FileExistsError:
                # TODO: properly handle case where file already exists (several rld files per observer)
                msg = "File '%s' already exists, dropping test results." % (resfilename)
                _errors.append((msg, errno.EEXIST, obsid))
                logqueue.put_nowait((loggername, logging.ERROR, msg))
        else:
            # CSV file format
            rld_data = RocketLoggerData(inputfilename).merge_channels()
            # get network time and convert to UNIX timestamp (UTC)
            timeidx = rld_data.get_time(absolute_time=True, time_reference='network')     # TODO adjust parameters for RL 1.99+
            timeidxunix = timeidx.astype('uint64') / 1e9   # convert to s
            current_ch = rld_data.get_data('I1') * 1000    # convert to mA
            voltage_ch = rld_data.get_data('V2') - rld_data.get_data('V1')    # voltage difference
            rld_dataframe = pd.DataFrame(np.hstack((current_ch, voltage_ch)), index=timeidxunix, columns=['I', 'V'])
            rld_dataframe.insert(0, 'observer_id', obsid)
            rld_dataframe.insert(1, 'node_id', nodeid)
            rld_dataframe.to_csv(resultfile_path, sep=',', index_label='time', header=False, mode='a')

            os.remove(inputfilename)
    except:
        msg = "Error in powerprof worker process: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_powerprof


##############################################################################
#
# worker_logs
#
##############################################################################
def worker_logs(queueitem=None, nodeid=None, resultfile_path=None, logqueue=None, arg=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        inputfilename = "%s/%s" % (fdir, f)
        loggername = "(%s.%d) " % (cur_p.name, obsid)

        with open(resultfile_path, "a") as outfile:
            infile = open(inputfilename, "r")
            for line in infile:
                (timestamp, msg) = line.strip().split(',', 1)
                outfile.write("%s,%s,%s,%s\n" % (timestamp, obsid, nodeid, msg))
            infile.close()
        os.remove(inputfilename)
    except:
        msg = "Error in logs worker process: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_logs()


##############################################################################
#
# worker_serial
#
##############################################################################
def worker_serial(queueitem=None, nodeid=None, resultfile_path=None, logqueue=None, arg=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        inputfilename = "%s/%s" % (fdir, f)
        loggername = "(%s.%d) " % (cur_p.name, obsid)

        with open(resultfile_path, "a") as outfile:
            infile = open(inputfilename, "r")
            # read line by line and check for decode errors
            while True:
                try:
                    line = infile.readline()
                except UnicodeDecodeError:
                    continue
                if not line:
                    break
                try:
                    (timestamp, msg) = line.strip().split(',', 1)
                except:
                    continue
                result = "%s,%s,%s,r,%s\n" % (timestamp, obsid, nodeid, msg.rstrip())
                outfile.write(result)
            infile.close()
        os.remove(inputfilename)
    except:
        msg = "Error in serial worker process: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_serial()


##############################################################################
#
# worker_datatrace
#
##############################################################################
def worker_datatrace(queueitem=None, nodeid=None, resultfile_path=None, logqueue=None, arg=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        obsdbfile_path = "%s/%s" % (fdir, f)
        loggername = "(%s.%d) " % (cur_p.name, obsid)

        with open(resultfile_path, "a") as outfile:
            infile = open(obsdbfile_path, "r")
            for line in infile:
                (timestamp, msg) = line.strip().split(',', 1)
                outfile.write("%s,%s,%s,%s\n" % (timestamp, obsid, nodeid, msg))
            infile.close()
        os.remove(obsdbfile_path)
    except:
        msg = "Error in datatrace worker process: %s: %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_datatrace()


##############################################################################
#
# worker_callback: Callback function which reports errors from worker processes
#        back to the main process
#
##############################################################################
def worker_callback(result):
    global errors
    global FetchObsThread_queue
    
    if len(result[0]) > 0:
        for (err, eno, obsid) in result:
            msg = "Error %d when processing results for Observer ID %s: %s" % (eno, obsid, err)
            errors.append(msg)
    
    try:
        FetchObsThread_queue.put(item=result[1], block=True, timeout=10)
    except queue.Full:
        msg = "Queue full after processing element"
        logger.error(msg)
    return 0
### END worker_callback


##############################################################################
#
# LogQueueThread
#
##############################################################################
class LogQueueThread(threading.Thread):
    """    Thread which logs from queue to logfile.
    """ 
    def __init__(self, logqueue, logger, stopEvent):
        threading.Thread.__init__(self) 
        self._logger        = logger
        self._stopEvent        = stopEvent
        self._logqueue        = logqueue

    def run(self):
        self._logger.info("LogQueueThread started")
            
        # Let thread run until someone calls terminate() on it:
        while not self._stopEvent.is_set():
            try:
                (loggername, loglevel, msg) = self._logqueue.get(block=True, timeout=1)
                self._logger.log(loglevel, loggername + msg)
            except queue.Empty:
                pass
        
        # Stop the process:
        self._logger.info("LogQueueThread stopped")
### END LogQueueThread


##############################################################################
#
# FetchObsThread
#
##############################################################################
class FetchObsThread(threading.Thread):
    """    Thread which downloads database files from an observer to the server.
    """ 
    def __init__(self, obsid, obsethernet, dirname, debugdirname, workQueue, stopEvent):
        threading.Thread.__init__(self) 
        self._obsid            = obsid
        self._obsethernet      = obsethernet
        self._obsfiledir       = dirname
        self._obsfiledebugdir  = debugdirname
        self._workQueue        = workQueue
        self._stopEvent        = stopEvent
        self._logger           = logger
        
        self._min_sleep        = flocklab.config.getint("fetcher", "min_sleeptime")
        self._max_randsleep    = flocklab.config.getint("fetcher", "max_rand_sleeptime")
        self._obstestresfolder = "%s/%d" % (flocklab.config.get("observer", "testresultfolder"), testid)
        
    def run(self):
        try:
            self._loggerprefix = "(FetchObsThread.%d) "%self._obsid
            self._logger.info(self._loggerprefix + "FetchObsThread starting...")
            removelast = True
                
            # Let thread run until someone calls terminate() on it:
            while removelast == True:
                """ Get data from the observer over SCP. 
                Then request data from the observer and store it in the server's filesystem. 
                Then sleep some random time before fetching data again.
                """
                # Wait for some random time:
                waittime =self._min_sleep + random.randrange(0,self._max_randsleep)
                #DEBUG self._logger.debug(self._loggerprefix + "Going to wait for %d seconds" %(waittime))
                self._stopEvent.wait(waittime) # The wait will be interrupted if the stop signal has been set causing the thread to download all remaining files
                if self._stopEvent.is_set():
                    removelast = False
                #self._logger.debug(self._loggerprefix + "Woke up")
                # Get list of available files
                cmd = ['ssh' , self._obsethernet, "ls %s/" % self._obstestresfolder]
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)  # universal_newlines makes sure that a string is returned instead of a byte object
                out, err = p.communicate(None)
                rs = p.returncode
                if (rs == flocklab.SUCCESS):
                    services = {}
                    for servicename in [ "gpio_monitor", "powerprofiling", "serial", "error", "timesync" ]:
                        services[servicename] = ServiceInfo(servicename)
                    # Read filenames
                    for dbfile in out.split():
                        # Check name and append to corresponding list
                        for service in services.values():
                            if service.matchFileName(dbfile):
                                service.addFile("%s/%s" % (self._obstestresfolder, dbfile))
                                break
                    copyfilelist = []
                    # Remove latest from each list as the observer might still be writing into it (unless stop event has been set).
                    for service in services.values():
                        service.stripFileList(removelast)
                        for dbfile in service.files:
                            copyfilelist.append(dbfile)
                        #if (len(service.files) > 0):
                        #    self._logger.debug(self._loggerprefix + "Will process files %s for service %s" % (" ".join(service.files), service.servicename))
                    
                    if len(copyfilelist) > 0:
                        # Download the database files:
                        self._logger.debug(self._loggerprefix + "Downloading results files %s" % (" ".join(copyfilelist)))
                        cmd = ['scp', '-q' ]
                        cmd.extend(["%s:%s" % (self._obsethernet, x) for x in copyfilelist])
                        cmd.append("%s/" % self._obsfiledir)
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                        out, err = p.communicate(None)
                        rs = p.wait()
                        if rs != 0:
                            self._logger.debug(self._loggerprefix + "Could not download all results files from observer. Dataloss occurred for this observer.")
                            self._logger.debug(self._loggerprefix + "Tried to execute %s, result was %d, stdout: %s, error: %s" % (str(cmd), rs, out, err))
                        else:
                            self._logger.debug("Downloaded results files from observer.")
                            # put a copy to the debug directory
                            for f in copyfilelist:
                                fname = os.path.basename(f)
                                shutil.copyfile("%s/%s" % (self._obsfiledir, fname), "%s/%s" % (self._obsfiledebugdir, fname))
                            # Tell the fetcher to start working on the files:
                            for f in copyfilelist:
                                fname = os.path.basename(f)
                                try:
                                    self._workQueue.put(item=(ITEM_TO_PROCESS, self._obsid, self._obsfiledir, fname, None), block=True, timeout=10)
                                except queue.Full:
                                    # Make sure the file is downloaded again at a later point:
                                    copyfilelist.remove(f)
                                    os.unlink("%s/%s" % (self._obsfiledir, fname))
                                    self._logger.warning(self._loggerprefix + "FetchObsThread queue is full. Cannot put %s/%s on it." % (self._obsfiledir, fname))
                            # Remove remote files if any are left:
                            if (len(copyfilelist) > 0):
                                cmd = ['ssh' ,'%s'%(self._obsethernet), "cd %s;"%self._obstestresfolder, "rm"]
                                cmd.extend(copyfilelist)
                                self._logger.debug(self._loggerprefix + "Removing files on observer...")
                                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                                out, err = p.communicate(None)
                                rs = p.wait()
                                if (rs != flocklab.SUCCESS):
                                    self._logger.error(self._loggerprefix + "Could not remove files on observer, result was %d, error: %s" % (rs, err))
                            else:
                                self._logger.debug(self._loggerprefix + "No files left to delete on observer.")
                    else:
                        self._logger.debug(self._loggerprefix + "No files to download from observer.")

                    if removelast == False: # this is the last execution of the while loop
                        cmd = ['ssh' ,'%s'%(self._obsethernet), "rm -rf %s" % self._obstestresfolder]
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                        out, err = p.communicate(None)
                        rs = p.wait()
                        if (rs != flocklab.SUCCESS):
                            self._logger.error(self._loggerprefix + "Could not remove results directory from observer, result was %d. Error: %s" % (rs, err.strip()))

                else:
                    self._logger.error(self._loggerprefix + "SSH to observer did not succeed, fetcher thread terminated with code %d. Error: %s" % (rs, err.strip()))
                    break   # abort
        
        except:
            logger.error(self._loggerprefix + "FetchObsThread crashed: %s, %s\n%s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc()))
        
        # Stop the process:
        self._logger.info(self._loggerprefix + "FetchObsThread stopped")
### END FetchObsThread


##############################################################################
#
# Start Fetcher
#
##############################################################################
def start_fetcher():
    global obsfiledir
    global FetchObsThread_list
    global FetchObsThread_queue
    global FetchObsThread_stopEvent
    global obsfetcher_dict
    
    # Daemonize the process ---
    daemon.daemonize(None, closedesc=False)
    logger.info("Daemon started")
    logger.info("Going to fetch data for test ID %d" %testid)
        
    # Get needed metadata from database ---
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        flocklab.error_logandexit("Could not connect to database.", errno.EAGAIN)
    try:
        cur.execute("""SELECT `a`.observer_id, `a`.ethernet_address 
                       FROM `tbl_serv_observer` AS `a` 
                       LEFT JOIN `tbl_serv_map_test_observer_targetimages` AS `b` ON `a`.serv_observer_key = `b`.observer_fk 
                       WHERE `b`.test_fk = %d GROUP BY `a`.observer_id;
                    """ % testid)
    except MySQLdb.Error as err:
        msg = str(err)
        flocklab.error_logandexit(msg, errno.EIO)
    except:
        logger.warning("Error %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
    rs = cur.fetchall()
    cur.close()
    cn.close()
    logger.debug("Got list of FlockLab observers from database.")
    if not rs:
        logger.info("No observers found for this test. Nothing has to be done, thus exiting...")
        return errno.ENODATA
        
    # Start fetcher threads ---
    # Create a directory structure to store the downloaded files from the DB:
    obsfiledir = "%s/%d" % (flocklab.config.get('fetcher', 'obsfile_dir'), testid)
    if not os.path.exists(obsfiledir):
        os.makedirs(obsfiledir)
    obsfiledebugdir = "%s/%d" % (flocklab.config.get('fetcher', 'obsfile_debug_dir'), testid)
    if not os.path.exists(obsfiledebugdir):
        os.makedirs(obsfiledebugdir)
        #DEBUG logger.debug("Created %s"%obsfiledir)
    # Start one fetching thread per observer
    FetchObsThread_stopEvent = threading.Event()
    FetchObsThread_queue = queue.Queue(maxsize=10000)
    for observer in rs:
        obsid = int(observer[0])
        # Create needed directories:
        dirname = "%s/%d" % (obsfiledir, obsid)
        if (not os.path.exists(dirname)):
            os.makedirs(dirname)
        debugdirname = "%s/%d" % (obsfiledebugdir, obsid)
        if (not os.path.exists(debugdirname)):
            os.makedirs(debugdirname)
        # Start thread: 
        try:
            thread = FetchObsThread(obsid, observer[1], dirname, debugdirname, FetchObsThread_queue, FetchObsThread_stopEvent)
            FetchObsThread_list.append(thread)
            thread.start()
            logger.debug("Started fetcher thread for observer %d" % (obsid))
        except:
            logger.warning("Error when starting fetcher thread for observer %d: %s, %s" % (obsid, str(sys.exc_info()[0]), str(sys.exc_info()[1])))
            continue
    
    return flocklab.SUCCESS
### END start_fetcher


##############################################################################
#
# Stop Fetcher
#
##############################################################################
def stop_fetcher():
    # Get oldest running instance of the fetcher for the selected test ID which is the main process and send it the terminate signal:
    try:
        pid = flocklab.get_fetcher_pid(testid)
        # Signal the process to stop:
        if (pid > 0):
            # Do not stop this instance if it is the only one running:
            if (pid == os.getpid()):
                raise ValueError
            logger.debug("Sending SIGTERM signal to process %d" % pid)
            os.kill(pid, signal.SIGTERM)
            # wait for process to finish (timeout..)
            shutdown_timeout = flocklab.config.getint("fetcher", "shutdown_timeout")
            pidpath = "/proc/%d" % pid
            while os.path.exists(pidpath) & (shutdown_timeout > 0):
                time.sleep(1)
                shutdown_timeout = shutdown_timeout - 1
            if os.path.exists(pidpath):
                logger.error("Fetcher with PID %d is still running, killing process..." % pid)
                # send kill signal
                os.kill(pid, signal.SIGKILL)
                time.sleep(3)
                # check if there is a remaining fetcher process
                pid = flocklab.get_fetcher_pid(testid)
                if pid > 0 and pid != os.getpid():
                    logger.warning("Found a remaining fetcher thread with PID %d, killing it now..." % (pid))
                    os.kill(pid, signal.SIGKILL)
                raise ValueError
        else:
            raise ValueError
    except ValueError:
        # Set DB status in order to allow dispatcher and scheduler to go on.:
        logger.debug("Setting test status in DB to 'synced'...")
        try:
            (cn, cur) = flocklab.connect_to_db()
            flocklab.set_test_status(cur, cn, testid, 'synced')
            cur.close()
            cn.close()
        except:
            logger.warning("Could not connect to database.")
        return errno.ENOPKG
    
    return flocklab.SUCCESS
### END stop_fetcher


##############################################################################
#
# Class WorkManager
#
##############################################################################
class WorkManager():
    def __init__(self):
        self.worklist = {}
        self.pattern = re.compile("_[0-9].*")
        self.workcount = 0
        
    def _next_item_with_state(self, service, obsid):
        stateitem = list(self.worklist[service][obsid][1][0])
        stateitem[4] = self.worklist[service][obsid][0]
        return tuple(stateitem)
        
    def add(self, item):
        service = self.pattern.sub("",item[3])
        obsid = item[1]
        if service not in self.worklist:
            self.worklist[service] = {}
        if obsid not in self.worklist[service]:
            self.worklist[service][obsid] = [None, []] # workerstate / worklist
        # if list is empty, we're good to process, otherwise just append it and return None
        if len(self.worklist[service][obsid][1]) == 0:
            self.worklist[service][obsid][1].append(item)
            self.workcount = self.workcount + 1
            return self._next_item_with_state(service, obsid)
        else:
            self.worklist[service][obsid][1].append(item)
            self.workcount = self.workcount + 1
            return None
        
    def done(self, item):
        service = self.pattern.sub("",item[3])
        obsid = item[1]
        if item[1:-1] == self.worklist[service][obsid][1][0][1:-1]:
            self.worklist[service][obsid][0] = item[4] # save state
            self.worklist[service][obsid][1].pop(0)
            self.workcount = self.workcount - 1
        else:
            logger.error("work done for item that was not enqueued: %s" % str(item))
        # if there is more work to do, return next item
        if len(self.worklist[service][obsid][1]) > 0:
            return self._next_item_with_state(service, obsid)
        else:
            return None
    
    def finished(self):
        return self.workcount == 0
    
### END WorkManager


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print("Usage: %s --testid=<int> [--stop] [--debug] [--help]" % __file__)
    print("Options:")
    print("  --testid=<int>\t\tTest ID of test to which incoming data belongs.")
    print("  --stop\t\t\tOptional. Causes the program to stop a possibly running instance of the fetcher.")
    print("  --debug\t\t\tOptional. Print debug messages to log.")
    print("  --help\t\t\tOptional. Print this help.")
### END usage()


##############################################################################
#
# Main
#
##############################################################################
def main(argv):
    
    ### Get global variables ###
    global logger
    global debug
    global testid
    global testresultsdir
    global testresultsfile_dict
    global owner_fk
    global obsdict_byid
    global serialdict
    
    stop = False
    
    # Get logger:
    logger = flocklab.get_logger()
        
    # Get the config file ---
    flocklab.load_config()

    # Get command line parameters ---
    try:
        opts, args = getopt.getopt(argv, "hedt:", ["help", "stop", "debug", "testid="])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warning(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        msg = "Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        flocklab.error_logandexit(msg, errno.EAGAIN)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-d", "--debug"):
            debug = True
            logger.setLevel(logging.DEBUG)
        elif opt in ("-t", "--testid"):
            try:
                testid = int(arg)
            except ValueError:
                err = "Wrong API usage: testid has to be integer"
                print(str(err))
                logger.warning(str(err))
                usage()
                sys.exit(errno.EINVAL)
        elif opt in ("-e", "--stop"):
            stop = True
        else:
            print("Wrong API usage")
            logger.warning("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Check if the necessary parameters are set ---
    if not testid:
        print("Wrong API usage")
        logger.warning("Wrong API usage")
        sys.exit(errno.EINVAL)
        
    # Check if the Test ID exists in the database ---
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        flocklab.error_logandexit("Could not connect to database.", errno.EAGAIN)
    rs = flocklab.check_test_id(cur, testid)
    cur.close()
    cn.close()
    if rs != 0:
        if rs == 3:
            msg = "Test ID %d does not exist in database." %testid
            flocklab.error_logandexit(msg, errno.EINVAL)
        else:
            msg = "Error when trying to get test ID from database: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            flocklab.error_logandexit(msg, errno.EIO)
        
    # Add Test ID to logger name ---
    logger.name += " (Test %d)"%testid
    
    # Start / stop the fetcher ---
    ret = flocklab.SUCCESS
    if stop:
        ret = stop_fetcher()
        logger.info("FlockLab fetcher stopped.")
        sys.exit(ret)

    # Start the fetcher processes which download data from the observers: 
    ret = start_fetcher()
    if ret == flocklab.SUCCESS:
        logger.info("FlockLab fetcher started.")
    else:
        msg = "Start function returned error. Exiting..."
        os.kill(os.getpid(), signal.SIGTERM)
        rs = flocklab.error_logandexit(msg, ret)
        
    # Get needed metadata ---
    try:
        (cn, cur) = flocklab.connect_to_db()
    except:
        flocklab.error_logandexit("Could not connect to database.", errno.EAGAIN)
    rs = flocklab.get_test_owner(cur, testid)
    if isinstance(rs, tuple):
        owner_fk = rs[0]
    else:
        owner_fk = None
    rs = flocklab.get_test_obs(cur, testid)
    if isinstance(rs, tuple):
        obsdict_byid = rs[1]
    else:
        obsdict_byid = None
    # Dict for serial service: 'r' means reader (data read from the target), 'w' means writer (data written to the target):
    serialdict = {0: 'r', 1: 'w'}
    
    #find out the start and stoptime of the test
    cur.execute("SELECT `time_start_wish`, `time_end_wish` FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d" %testid)
    # Times are going to be of datetime type:
    ret = cur.fetchone() 
    teststarttime = ret[0]
    teststoptime  = ret[1]
    ppFileFormat  = None
    
    # Find out which services are used to allocate working threads later on ---
    # Get the XML config from the database and check which services are used in the test.
    servicesUsed_dict = {'gpiotracing': 'gpioTracingConf', 'powerprofiling': 'powerProfilingConf', 'serial': 'serialConf', 'datatrace': 'dataTraceConf'}
    cur.execute("SELECT `testconfig_xml` FROM `tbl_serv_tests` WHERE (`serv_tests_key` = %s)" %testid)
    ret = cur.fetchone()
    if not ret:
        msg = "No XML found in database for testid %d." %testid
        errors.append(msg)
        logger.error(msg)
        for service, xmlname in servicesUsed_dict.items():
            servicesUsed_dict[service] = True
    else:
        try:
            logger.debug("Got XML from database.")
            parser = lxml.etree.XMLParser(remove_comments=True)
            tree = lxml.etree.fromstring(bytes(bytearray(ret[0], encoding = 'utf-8')), parser)
            ns = {'d': flocklab.config.get('xml', 'namespace')}
            for service, xmlname in servicesUsed_dict.items():
                if tree.xpath('//d:%s' % xmlname, namespaces=ns):
                    servicesUsed_dict[service] = True
                    logger.debug("Usage of %s detected." % service)
                else:
                    servicesUsed_dict[service] = False
            # check which file format the user wants for the power profiling
            if servicesUsed_dict['powerprofiling']:
                if tree.xpath('//d:powerProfilingConf/d:fileFormat', namespaces=ns):
                    ppFileFormat = tree.xpath('//d:powerProfilingConf/d:fileFormat', namespaces=ns)[0].text
                    logger.debug("User wants file format %s for power profiling." % (ppFileFormat))
                else:
                    logger.debug("Element <fileFormat> not detected.")
        except:
            msg = "XML parsing failed: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            errors.append(msg)
            logger.error(msg)
    # Append log services (always used)
    servicesUsed_dict['errorlog'] = True
    servicesUsed_dict['timesynclog'] = True
    
    cur.close()
    cn.close()
    if ((owner_fk==None) or (obsdict_byid==None)):
        msg = "Error when getting metadata.\n"
        msg += "owner_fk: %s\nobsdict_byid: %s\n" % (str(owner_fk), str(obsdict_byid))
        msg += "Exiting..."
        logger.debug(msg)
        os.kill(os.getpid(), signal.SIGTERM)
        flocklab.error_logandexit(msg, errno.EAGAIN)
    else:
        logger.debug("Got all needed metadata.")
    
    # Start aggregating processes ---
    """    There is an infinite loop which gets files to process from the fetcher threads which download data from the observers.
        Downloaded data is then assigned to a worker process for the corresponding service and in the worker process parsed,
        converted (if needed) and aggregated into a single file per service.
        The loop is stopped if the program receives a stop signal. In this case, the loops runs until no more database files 
        are there to be processed.
    """
    if __name__ == '__main__':
        # Create directory and files needed for test results:
        testresultsdir = "%s/%d" %(flocklab.config.get('fetcher', 'testresults_dir'), testid)
        if not os.path.exists(testresultsdir):
            os.makedirs(testresultsdir)
            logger.debug("Created %s" % testresultsdir)
        manager = multiprocessing.Manager()
        for service in ('errorlog', 'gpiotracing', 'powerprofiling', 'serial', 'timesynclog', 'datatrace'):
            if servicesUsed_dict[service] == False:
                continue    # only create files for used services
            path = "%s/%s.csv" % (testresultsdir, service)
            lock = manager.Lock()
            testresultsfile_dict[service] = (path, lock)
            # Create file and write header:
            if service in ('errorlog', 'timesynclog'):
                header = 'timestamp,observer_id,node_id,message\n'
            elif service == 'gpiotracing':
                header = 'timestamp,monotonic_time,observer_id,node_id,pin_name,value\n'
            elif service == 'powerprofiling':
                if ppFileFormat == 'rld':
                    continue    # don't open a csv file
                header = 'timestamp,observer_id,node_id,current_mA,voltage_V\n'
            elif service == 'serial':
                header = 'timestamp,observer_id,node_id,direction,output\n'
            elif service == 'datatrace':
                header = 'timestamp,observer_id,node_id,variable,value,access,pc\n'
            lock.acquire()
            f = open(path, 'w')
            f.write(header)
            f.close()
            lock.release()
        # Start logging thread:
        logqueue = manager.Queue(maxsize=10000)
        LogQueueThread_stopEvent = threading.Event()
        try:
            thread = LogQueueThread(logqueue, logger, LogQueueThread_stopEvent)
            thread.start()
        except:
            logger.warning("Error when starting log queue thread: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        
        # Determine the number of CPU's to be used for each aggregating process. If a service is not used, its CPUs are assigned to other services
        cpus_free = 0
        cpus_logs = flocklab.config.getint('fetcher', 'cpus_errorlog')
        # CPUs for serial service:
        if servicesUsed_dict['serial'] == True:
            cpus_serial = flocklab.config.getint('fetcher', 'cpus_serial')
        else:
            cpus_serial = 0
            #cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_serial')
        # CPUs for GPIO tracing:
        if servicesUsed_dict['gpiotracing'] == True:
            cpus_gpiomonitoring    = flocklab.config.getint('fetcher', 'cpus_gpiomonitoring')
        else:
            cpus_gpiomonitoring = 0
            #cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_gpiomonitoring')
        # CPUs for powerprofiling:
        if servicesUsed_dict['powerprofiling'] == True:
            cpus_powerprofiling    = flocklab.config.getint('fetcher', 'cpus_powerprofiling')
        else:
            cpus_powerprofiling = 0
            #cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_powerprofiling')
        if servicesUsed_dict['datatrace'] == True:
            cpus_datatrace = 1
        else:
            cpus_datatrace = 0
        # If there are free CPUs left, give them to GPIO tracing and power profiling evenly as these services need the most CPU power:
        if cpus_free > 0:
            if (cpus_powerprofiling > 0) and (cpus_gpiomonitoring > 0):
                # Both services are used, distribute the free CPUS evenly:
                cpus_powerprofiling = cpus_powerprofiling + int(math.ceil(float(cpus_free)/2))
                cpus_gpiomonitoring = cpus_gpiomonitoring + int(math.floor(float(cpus_free)/2))
            elif cpus_powerprofiling > 0:
                # GPIO monitoring/tracing is not used, so give all CPUs to powerprofiling:
                cpus_powerprofiling = cpus_powerprofiling + cpus_free
            elif cpus_gpiomonitoring > 0:
                # Powerprofiling is not used, so give all CPUs to GPIO monitoring/tracing:
                cpus_gpiomonitoring = cpus_gpiomonitoring + cpus_free
            else:
                # Neither of the services is used, so give it to one of the other services:
                if cpus_serial > 0:
                    cpus_serial = cpus_serial + cpus_free
        cpus_total = cpus_logs + cpus_serial + cpus_gpiomonitoring + cpus_powerprofiling
        
        service_pools_dict = { 'logs': cpus_logs, 'serial': cpus_serial, 'gpiotracing': cpus_gpiomonitoring, 'powerprofiling': cpus_powerprofiling, 'datatrace': cpus_datatrace }
        if (cpus_total > multiprocessing.cpu_count()):
            logger.warning("Number of requested CPUs for all aggregating processes (%d) is higher than number of available CPUs (%d) on system." % (cpus_total, multiprocessing.cpu_count()))
        
        # Start a worker process pool for every service:
        for service, cpus in service_pools_dict.items():
            if cpus > 1:
                # currently only 1 CPU / process can be used per task since processing functions are NOT thread safe!
                logger.warning("%d is an invalid number of CPUs for service %s, using default value of 1." % (cpus, service))
                cpus = 1
            if cpus > 0:
                pool = multiprocessing.Pool(processes=cpus)
                logger.debug("Created pool for %s workers with %d processes" % (service, cpus))
                service_pools_dict[service] = pool
            else:
                service_pools_dict[service] = None
        logger.debug("Created all worker pools for services.")
        # Catch kill signals ---
        signal.signal(signal.SIGTERM, sigterm_handler)
        signal.signal(signal.SIGINT,  sigterm_handler)
        # Loop through the folders and assign work to the worker processes:
        commitsize = flocklab.config.getint('fetcher', 'commitsize')
        loggerprefix = "(Mainloop) "
        workmanager = WorkManager()
        
        # Main loop ---
        while True:
            if mainloop_stop:
                if workmanager.finished() and FetchObsThread_queue.empty():
                    # exit main loop
                    logger.debug("Work manager has nothing more to do, finishing up..")
                    break

            # Wait for FetchObsThreads to put items on queue:
            try:
                item = FetchObsThread_queue.get(block=True, timeout=5)
                (itemtype, obsid, fdir, f) = item[:4]
                logger.debug(loggerprefix + "Got element from queue: %d, %s, %s/%s" % (itemtype, str(obsid), fdir, f))
            except queue.Empty:
                # No one put any data onto the queue.
                # In normal operation, just ignore the error and try again:
                continue
            if itemtype == ITEM_TO_PROCESS:
                nextitem = workmanager.add(item)
            else: # type is ITEM_PROCESSED
                nextitem = workmanager.done(item)
            if nextitem is None:
                logger.debug(loggerprefix + "Next item is None.")
                continue
            (itemtype, obsid, fdir, f, workerstate) = nextitem
            #logger.debug(loggerprefix + "Next item is %s/%s (Obs%s)." % (fdir, f, str(obsid)))
            nodeid = obsdict_byid[obsid][1]
            callback_f = worker_callback
            # Match the filename against the patterns and schedule an appropriate worker function:
            if (re.search("^gpio_monitor_[0-9]{14}\.csv$", f) != None):
                pool        = service_pools_dict['gpiotracing']
                worker_args = [nextitem, nodeid, testresultsfile_dict['gpiotracing'][0], logqueue, None]
                worker_f    = worker_gpiotracing
            elif (re.search("^powerprofiling_[0-9]{14}\.rld$", f) != None):
                pool        = service_pools_dict['powerprofiling'] 
                worker_args = [nextitem, nodeid, testresultsfile_dict['powerprofiling'][0], logqueue, ppFileFormat]
                worker_f    = worker_powerprof
            elif (re.search("^serial_[0-9]{14}\.db$", f) != None):
                pool        = service_pools_dict['serial']
                worker_args = [nextitem, nodeid, testresultsfile_dict['serial'][0], testresultsfile_dict['serial'][1], commitsize, parse_serial, convert_serial, logqueue]
                worker_f    = worker_dbfiles
            elif (re.search("^serial_[0-9]{14}\.csv$", f) != None):
                pool        = service_pools_dict['serial']
                worker_args = [nextitem, nodeid, testresultsfile_dict['serial'][0], logqueue, None]
                worker_f    = worker_serial
            elif (re.search("^datatrace_[0-9]{14}\.csv$", f) != None):
                pool        = service_pools_dict['datatrace']
                worker_args = [nextitem, nodeid, testresultsfile_dict['datatrace'][0], logqueue, None]
                worker_f    = worker_datatrace
            elif (re.search("^error_[0-9]{14}\.log$", f) != None):
                pool        = service_pools_dict['logs']
                worker_args = [nextitem, nodeid, testresultsfile_dict['errorlog'][0], logqueue, None]
                worker_f    = worker_logs
            elif (re.search("^timesync_[0-9]{14}\.log$", f) != None):
                pool        = service_pools_dict['logs']
                worker_args = [nextitem, nodeid, testresultsfile_dict['timesynclog'][0], logqueue, None]
                worker_f    = worker_logs
            else:
                logger.warning(loggerprefix + "Results file %s/%s from observer %s did not match any of the known patterns" % (fdir, f, obsid))
                continue
            # Schedule worker function from the service's pool. The result will be reported to the callback function.
            pool.apply_async(func=worker_f, args=tuple(worker_args), callback=callback_f)
        # Stop signal for main loop has been set ---
        # Stop worker pool:
        for service, pool in service_pools_dict.items():
            if pool:
                logger.debug("Closing pool for %s..." % service)
                pool.close()
        for service, pool in service_pools_dict.items():
            if pool:
                logger.debug("Waiting for pool for %s to close..." % service)
                pool.join()
        logger.debug("Closed all pools.")
        
        # Stop logging:
        logger.debug("Stopping log queue thread...")
        LogQueueThread_stopEvent.set()
        
        # Set DB status:
        logger.debug("Setting test status in DB to 'synced'...")
        try:
            (cn, cur) = flocklab.connect_to_db()
            flocklab.set_test_status(cur, cn, testid, 'synced')
            cur.close()
            cn.close()
        except:
            logger.warning("Could not connect to database.")
        
        # Delete the obsfile directories as they are not needed anymore:
        if ((obsfiledir != None) and (os.path.exists(obsfiledir))):
            shutil.rmtree(obsfiledir)
        # Delete old debug files
        if os.path.exists(flocklab.config.get('fetcher', 'obsfile_debug_dir')):
            for d in [fn for fn in os.listdir(flocklab.config.get('fetcher', 'obsfile_debug_dir')) if os.stat("%s/%s" % (flocklab.config.get('fetcher', 'obsfile_debug_dir'), fn)).st_mtime < int(time.time()) - int(flocklab.config.get('fetcher', 'obsfile_debug_dir_max_age_days')) * 24 * 3600]:
                shutil.rmtree("%s/%s" % (flocklab.config.get('fetcher', 'obsfile_debug_dir'),d))
        if len(errors) > 0:
            msg = ""
            for error in errors:
                msg += error
            flocklab.error_logandexit(msg, errno.EBADMSG)
        else:
            ret = flocklab.SUCCESS
    
    sys.exit(ret)
### END main()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        msg = "Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv))
        flocklab.error_logandexit(msg, errno.EAGAIN)
