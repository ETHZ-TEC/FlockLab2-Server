#! /usr/bin/env python3

import os, sys, getopt, traceback, MySQLdb, signal, random, time, errno, multiprocessing, subprocess, re, logging, __main__, threading, struct, types, queue, math, shutil, lxml.etree
import lib.daemon as daemon
import lib.flocklab as flocklab
from rocketlogger.data import RocketLoggerData
import pandas as pd


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
pindict                  = None
obsdict_byid             = None
servicedict              = None
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
            logger.warn("Fetcher thread did not stop within %d seconds." % shutdown_timeout)
    # Set DB status:
    logger.debug("Setting test status in DB to 'syncing'...")
    try:
        (cn, cur) = flocklab.connect_to_db()
        flocklab.set_test_status(cur, cn, testid, 'syncing')
        cur.close()
        cn.close()
    except:
        logger.warn("Could not connect to database.")
    
    # Tell the main loop to stop:
    mainloop_stop = True
    logger.debug("Set stop signal for main loop.")
### END sigterm_handler


##############################################################################
#
# Functions for parsing observer DB files data
#
##############################################################################
def parse_gpio_setting(buf):
    _data = struct.unpack("<Iiiiii",buf) #unsigned int gpio;int value;struct timeval time_planned;struct timeval time_executed;
    return (_data[0], str(_data[1]), "%i.%06i" % (_data[2],_data[3]), "%i.%06i" % (_data[4],_data[5]))

def parse_serial(buf):
    _data = struct.unpack("iii%ds" % (len(buf) - 12),buf) #int service; struct timeval timestamp;char * data
    return (_data[0], _data[3], "%i.%06i" % (_data[1],_data[2]))

def parse_error_log(buf):
    _data = struct.unpack("<iii%ds" % (len(buf) - 12),buf) #struct timeval timestamp; int service_fk; char errormessage[1024];
    return (str(_data[2]), _data[3], "%i.%06i" % (_data[0],_data[1]))


##############################################################################
#
# Functions for converting observer DB data
#
##############################################################################
def convert_gpio_setting(obsdata, observer_id, node_id):
    return "%s,%s,%s,%s,%s,%s\n" %(obsdata[2], obsdata[3], observer_id, node_id, pindict[obsdata[0]][0], obsdata[1])

def convert_gpio_monitor(obsdata, observer_id, node_id):
    return "%s,%s,%s,%s,%s\n" %(obsdata[1], observer_id, node_id, obsdata[0], obsdata[2])

def convert_serial(obsdata, observer_id, node_id):
    return "%s,%s,%s,%s,%s\n" %(obsdata[2], observer_id, node_id, serialdict[obsdata[0]], obsdata[1])

def convert_error_log(obsdata, observer_id, node_id):
    return "%s,%s,%s,%s\n" %(obsdata[2], observer_id, node_id, obsdata[1])



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
# worker_convert_and_aggregate: Worker function for multiprocessing pools.
#        Parses observer DB files for all services, converts values (if needed)
#        and aggregates them into single test result files.
#
##############################################################################
def worker_convert_and_aggregate(queueitem=None, nodeid=None, resultfile_path=None, resultfile_lock=None, commitsize=1, vizimgdir=None, parse_f=None, convert_f=None, viz_f=None, logqueue=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        obsdbfile_path = "%s/%s" % (fdir,f)
        loggername = "(%s.Obs%d)" % (cur_p.name, obsid)
        #logqueue.put_nowait((loggername, logging.DEBUG, "Import file %s"%obsdbfile_path))
        # Open file:
        dbfile = open(obsdbfile_path, 'rb')
        rows = 0
        viz_values = []
        conv_values = []
        while not dbfile.closed:
            # Process DB file line by line:
            try:
                # Parse one line:
                buf = read_from_db_file(dbfile)
                obsdata = parse_f(buf)
                viz_values.append(obsdata)
                # Convert data if needed:
                if convert_f != None:
                    conv_data = convert_f(obsdata, obsid, nodeid)
                    conv_values.append(conv_data)
                    rows += 1
                # Visualize data:
                if (commitsize > 0) & (rows >= commitsize):
                    if viz_f != None:
                        #logqueue.put_nowait((loggername, logging.DEBUG, "Viz started..."))
                        viz_f(testid, owner_fk, viz_values, obsid, vizimgdir, logger)
                        #logqueue.put_nowait((loggername, logging.DEBUG, "Viz done."))
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
                    viz_values = []
            except DbFileEof:
                # logqueue.put_nowait((loggername, logging.DEBUG, "DbFileEof has occurred."))
                break # dbfile has been closed in parser (most likely because EOF was reached)
            except DbFileReadError as err:
                msg = "%s: Packet size (%i) did not match payload size (%i) @ %d." %(obsdbfile_path, err.expectedSize, err.actualSize, err.fpos)
                _errors.append((msg, errno.EIO, obsid))
                logqueue.put_nowait((loggername, logging.ERROR, msg))
        if (len(conv_values) > 0):
            # There is still data left. Do a last commit:
            if (viz_f != None) and (len(viz_values) > 0):
                #logqueue.put_nowait((loggername, logging.DEBUG, "Viz started..."))
                viz_f(testid, owner_fk, viz_values, obsid, vizimgdir, logger)
                #logqueue.put_nowait((loggername, logging.DEBUG, "Viz done."))
            # Write data to file:
            #logqueue.put_nowait((loggername, logging.DEBUG, "Opening file %s for final writing..." % (resultfile_path)))
            resultfile_lock.acquire()
            f = open(resultfile_path, 'a')
            f.writelines(conv_values)
            f.close()
            resultfile_lock.release()
            logqueue.put_nowait((loggername, logging.DEBUG, "Committed final results to %s after %d rows" % (resultfile_path, rows)))
        # Remove processed file:
        #logqueue.put_nowait((loggername, logging.DEBUG, "Remove %s" % (obsdbfile_path)))
        os.unlink(obsdbfile_path)
    except:
        msg = "Error in worker process: %s: %s\n%s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc())
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_convert_and_aggregate


##############################################################################
#
# worker_gpiotracing: Worker function for converting and aggregating gpio
#               tracing data. Unlike for the other services, this function works on
#               whole observer DB files.
#
##############################################################################
def worker_gpiotracing(queueitem=None, nodeid=None, resultfile_path=None, slotcalib_factor=1, slotcalib_offset=0, vizimgdir=None, viz_f=None, logqueue=None):
    try:
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        obsdbfile_path = "%s/%s" % (fdir, f)
        loggername = "(%s.Obs%d)" % (cur_p.name, obsid)

        with open(resultfile_path, "a") as outfile:
            infile = open(obsdbfile_path, "r")
            for line in infile:
                try:
                    (timestamp, pin, level) = line.split(',')
                    outfile.write("%s,%s,%s,%s,%s" % (timestamp, obsid, nodeid, pin, level))
                except ValueError:
                    logqueue.put_nowait((loggername, logging.ERROR, "Could not parse line '%s' in gpiotracing worker process." % line))
                    break
            infile.close()
        os.remove(obsdbfile_path)

        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED

        return (_errors, processeditem)
    except:
        msg = "Error in gpiotracing worker process: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
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
def worker_powerprof(queueitem=None, nodeid=None, resultfile_path=None, slotcalib_factor=1, slotcalib_offset=0, vizimgdir=None, viz_f=None, logqueue=None, PpStatsQueue=None):
    try:
        channel_names = ['I1','V1','V2']
        _errors = []
        cur_p = multiprocessing.current_process()
        (itemtype, obsid, fdir, f, workerstate) = queueitem
        obsdbfile_path = "%s/%s" % (fdir, f)
        loggername = "(%s.Obs%d) " % (cur_p.name, obsid)

        rld_data = RocketLoggerData(obsdbfile_path).merge_channels()
        rld_dataframe = pd.DataFrame(rld_data.get_data(channel_names), index=rld_data.get_time(), columns=channel_names)
        rld_dataframe.insert(0, 'observer_id', obsid)
        rld_dataframe.insert(1, 'node_id', nodeid)
        rld_dataframe.to_csv(resultfile_path, sep=',', index_label='time', header=False, mode='a')

        os.remove(obsdbfile_path)
        
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        
        return (_errors, processeditem)
    except:
        msg = "Error in powerprof worker process: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        _errors.append((msg, errno.ECOMM, obsid))
        logqueue.put_nowait((loggername, logging.ERROR, msg))
    finally:
        processeditem = list(queueitem)
        processeditem[0] = ITEM_PROCESSED
        return (_errors, tuple(processeditem))
### END worker_powerprof


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
            self._loggerprefix = "(FetchObsThread.Obs%d) "%self._obsid
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
                cmd = ['ssh' ,'%s'%(self._obsethernet), "ls %s/" % self._obstestresfolder]
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)  # universal_newlines makes sure that a string is returned instead of a byte object
                out, err = p.communicate(None)
                rs = p.returncode
                if (rs == flocklab.SUCCESS):
                    services = {}
                    for servicename in [ "gpio_setting", "gpio_monitor", "powerprofiling", "serial" ]:
                        services[servicename] = ServiceInfo(servicename)
                        services["error_%s"%servicename] = ServiceInfo("error_%s"%servicename)
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
                                    self._logger.warn(self._loggerprefix + "FetchObsThread queue is full. Cannot put %s/%s on it." % (self._obsfiledir, fname))
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
                            self._logger.error(self._loggerprefix + "Could not remove results directory from observer, result was %d, stdout: %s, error: %s" % (rs, out, err))

                else:
                    self._logger.error(self._loggerprefix + "SSH to observer did not succeed, result was %d, error: %s" % (rs, err))
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
        logger.warn("Error %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
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
            logger.warn("Error when starting fetcher thread for observer %d: %s, %s" % (obsid, str(sys.exc_info()[0]), str(sys.exc_info()[1])))
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
            try:
                os.kill(pid, signal.SIGTERM)
                # wait for process to finish (timeout..)
                shutdown_timeout = flocklab.config.getint("fetcher", "shutdown_timeout")
                pidpath = "/proc/%d"%pid
                while os.path.exists(pidpath) & (shutdown_timeout>0):
                    time.sleep(1)
                    shutdown_timeout = shutdown_timeout - 1
                if os.path.exists(pidpath):
                    logger.error("Fetcher is still running, killing process...")
                    # send kill signal
                    os.kill(pid, signal.SIGKILL)
                    raise ValueError
            except:
                pass
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
            logger.warn("Could not connect to database.")
        
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
    global pindict
    global obsdict_byid
    global servicedict
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
        logger.warn(str(err))
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
                logger.warn(str(err))
                usage()
                sys.exit(errno.EINVAL)
        elif opt in ("-e", "--stop"):
            stop = True
        else:
            print("Wrong API usage")
            logger.warn("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Check if the necessary parameters are set ---
    if not testid:
        print("Wrong API usage")
        logger.warn("Wrong API usage")
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
    rs = flocklab.get_pinmappings(cur)
    if isinstance(rs, dict):
        pindict = rs
    else:
        pindict = None
    rs = flocklab.get_test_obs(cur, testid)
    if isinstance(rs, tuple):
        obsdict_byid = rs[1]
    else:
        obsdict_byid = None
    # Dict for serial service: 'r' means reader (data read from the target), 'w' means writer (data written to the target):
    serialdict = {0: 'r', 1: 'w'}
    # Get calibration data for used slots and add it to obsdict ---
    ppstats={}
    for (obsid, (obskey, nodeid)) in obsdict_byid.items():
        ppstats[obsid]=(0.0,0)
        rs = flocklab.get_slot_calib(cur, int(obskey), testid)
        if isinstance(rs, tuple):
            obsdict_byid[obsid] = (nodeid, rs)
        else:
            obsdict_byid = None
            break
    rs = flocklab.get_servicemappings(cur)
    if isinstance(rs, dict):
        servicedict = rs
    else:
        servicedict = None
    
    #find out the start and stoptime of the test
    cur.execute("SELECT `time_start_wish`, `time_end_wish` FROM `tbl_serv_tests` WHERE `serv_tests_key` = %d" %testid)
    # Times are going to be of datetime type:
    ret = cur.fetchone() 
    teststarttime = ret[0]
    teststoptime  = ret[1]
    FlockDAQ = False
    
    # Find out which services are used to allocate working threads later on ---
    # Get the XML config from the database and check which services are used in the test.
    servicesUsed_dict = {'gpiotracing': 'gpioTracingConf', 'gpioactuation': 'gpioActuationConf', 'powerprofiling': 'powerProfilingConf', 'serial': 'serialConf'}
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
        except:
            msg = "XML parsing failed: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
            errors.append(msg)
            logger.error(msg)
    
    cur.close()
    cn.close()
    if ((owner_fk==None) or (pindict==None) or (obsdict_byid==None) or (servicedict==None)):
        msg = "Error when getting metadata.\n"
        msg += "owner_fk: %s\npindict: %s\nobsdict_byid: %s\nservicedict: %s\n" % (str(owner_fk), str(pindict), str(obsdict_byid), str(servicedict))
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
        for service in ('errorlog', 'gpiotracing', 'gpioactuation', 'powerprofiling', 'serial', 'powerprofilingstats'):
            path = "%s/%s.csv" % (testresultsdir, service)
            lock = manager.Lock()
            testresultsfile_dict[service] = (path, lock)
            # Create file and write header:
            if service == 'errorlog':
                header = '# timestamp,observer_id,node_id,errormessage\n'
            elif service == 'gpiotracing':
                header = 'observer_id,node_id,pin_name,# timestamp,value\n'
            elif service == 'gpioactuation':
                header = '# timestamp_planned,timestamp_executed,observer_id,node_id,pin_name,value\n'
            elif service == 'powerprofiling':
                header = 'timestamp,observer_id,node_id,I1,V1,V2\n'
            elif service == 'serial':
                header = '# timestamp,observer_id,node_id,direction,output\n'
            elif service == 'powerprofilingstats':
                header = '# observer_id,node_id,mean_mA\n'
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
            logger.warn("Error when starting log queue thread: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        
        PpStatsQueue = manager.Queue(maxsize=1)
        PpStatsQueue.put(ppstats)
        # Determine the number of CPU's to be used for each aggregating process. If a service is not used, its CPUs are assigned to other services
        cpus_free = 0
        cpus_errorlog = flocklab.config.getint('fetcher', 'cpus_errorlog')
        # CPUs for serial service:
        if servicesUsed_dict['serial'] == True:
            cpus_serial    = flocklab.config.getint('fetcher', 'cpus_serial')
        else:
            cpus_serial    = 0
            cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_serial')
        # CPUs for GPIO actuation. If the service is not used, assign a CPU anyhow since FlockLab always uses this service to determine start and stop times of a test.
        #cpus_errorlog = flocklab.config.getint('fetcher', 'cpus_errorlog')
        if servicesUsed_dict['gpioactuation'] == True:
            cpus_gpiosetting = flocklab.config.getint('fetcher', 'cpus_gpiosetting')
        else:
            cpus_gpiosetting = 1
            cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_gpiosetting') - cpus_gpiosetting
        # CPUs for GPIO tracing:
        if servicesUsed_dict['gpiotracing'] == True:
            cpus_gpiomonitoring    = flocklab.config.getint('fetcher', 'cpus_gpiomonitoring')
        else:
            cpus_gpiomonitoring = 0
            cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_gpiomonitoring')
        # CPUs for powerprofiling:
        if servicesUsed_dict['powerprofiling'] == True:
            cpus_powerprofiling    = flocklab.config.getint('fetcher', 'cpus_powerprofiling')
        else:
            cpus_powerprofiling = 0
            cpus_free = cpus_free + flocklab.config.getint('fetcher', 'cpus_powerprofiling')
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
                elif cpus_gpiosetting > 0:
                    cpus_gpiosetting = cpus_gpiosetting + cpus_free
        cpus_total = cpus_errorlog + cpus_serial + cpus_gpiosetting + cpus_gpiomonitoring + cpus_powerprofiling
        
        service_pools_dict = { 'errorlog': cpus_errorlog, 'serial': cpus_serial, 'gpioactuation': cpus_gpiosetting, 'gpiotracing': cpus_gpiomonitoring, 'powerprofiling': cpus_powerprofiling }
        if (cpus_total > multiprocessing.cpu_count()):
            logger.warn("Number of requested CPUs for all aggregating processes (%d) is higher than number of available CPUs (%d) on system." % (cpus_total, multiprocessing.cpu_count()))
        
        # Start a worker process pool for every service:
        for service, cpus in service_pools_dict.items():
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
        vizimgdir = flocklab.config.get('viz','imgdir')
        commitsize = flocklab.config.getint('fetcher', 'commitsize')
        enableviz = flocklab.config.getint('viz','enablepreview')
        loggerprefix = "(Mainloop) "
        workmanager = WorkManager()
        # Main loop ---
        while 1:
            if mainloop_stop:
                if workmanager.finished() and FetchObsThread_queue.empty():
                    # exit main loop
                    logger.debug("Work manager has nothing more to do, finishing up..")
                    break
                else:
                    if FetchObsThread_queue.empty():
                        logger.debug("Received stop signal, but the fetcher queue is not yet empty...")
                    else:
                        logger.debug("Received stop signal, but workmanager is still busy...")
                    time.sleep(5)
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
            logger.debug(loggerprefix + "Next item is %s/%s (Obs%s)." % (fdir, f, str(obsid)))
            nodeid = obsdict_byid[obsid][0]
            callback_f = worker_callback
            worker_f = worker_convert_and_aggregate
            # Match the filename against the patterns and schedule an appropriate worker function:
            if (re.search("^gpio_setting_[0-9]{14}\.db$", f) != None):
                pool        = service_pools_dict['gpioactuation']
                worker_args = [nextitem, nodeid, testresultsfile_dict['gpioactuation'][0], testresultsfile_dict['gpioactuation'][1], commitsize, vizimgdir, parse_gpio_setting, convert_gpio_setting, None, logqueue]
            elif (re.search("^gpio_monitor_[0-9]{14}\.csv$", f) != None):
                pool        = service_pools_dict['gpiotracing']
                worker_args = [nextitem, nodeid, testresultsfile_dict['gpiotracing'][0], obsdict_byid[obsid][1][1], obsdict_byid[obsid][1][0], vizimgdir, None, logqueue]
                worker_f    = worker_gpiotracing
                logger.debug(loggerprefix + "resultfile_path: %s" % str(testresultsfile_dict['gpiotracing'][0]))
                logger.debug(loggerprefix + "queue item: %s" % str(nextitem))
                logger.debug(loggerprefix + "node id: %s" % str(nodeid))
                #if (enableviz == 1):
                #    worker_args[6] = flocklab.viz_gpio_monitor
            elif (re.search("^powerprofiling_[0-9]{14}\.rld$", f) != None):
                # Power profiling has a special worker function which parses the whole file in a C module:
                pool        = service_pools_dict['powerprofiling'] 
                worker_args = [nextitem, nodeid, testresultsfile_dict['powerprofiling'][0], obsdict_byid[obsid][1][1], obsdict_byid[obsid][1][0], vizimgdir, None, logqueue, PpStatsQueue]
                worker_f    = worker_powerprof
                #if (enableviz == 1):
                #    worker_args[6] = flocklab.viz_powerprofiling
            elif (re.search("^serial_[0-9]{14}\.db$", f) != None):
                #logger.debug(loggerprefix + "File %s contains serial service results"%f)
                pool        = service_pools_dict['serial']
                worker_args = [nextitem, nodeid, testresultsfile_dict['serial'][0], testresultsfile_dict['serial'][1], commitsize, vizimgdir, parse_serial, convert_serial, None, logqueue]
            elif (re.search("^error_.*_[0-9]{14}\.db$", f) != None):
                logger.debug(loggerprefix + "File %s contains error logs"%f)
                pool        = service_pools_dict['errorlog']
                worker_args =  [nextitem, nodeid, testresultsfile_dict['errorlog'][0], testresultsfile_dict['errorlog'][1], commitsize, vizimgdir, parse_error_log, convert_error_log, None, logqueue]
            else:
                logger.warn(loggerprefix + "Results file %s/%s from observer %s did not match any of the known patterns" %(fdir, f, obsid))
                continue
            # Schedule worker function from the service's pool. The result will be reported to the callback function.
            pool.apply_async(func=worker_f, args=tuple(worker_args), callback=callback_f)
        # Stop signal for main loop has been set ---
        # Stop worker pool:
        for service, pool in service_pools_dict.items():
            if pool:
                logger.debug("Closing pool for %s..."%service)
                pool.close()
        for service, pool in service_pools_dict.items():
            if pool:
                logger.debug("Waiting for pool for %s to close..."%service)
                pool.join()
        logger.debug("Closed all pools.")
        # Write pp stats
        ppstats = PpStatsQueue.get()
        f = open(testresultsfile_dict['powerprofilingstats'][0], 'a')
        for (obsid, (avg, count)) in ppstats.items():
            nodeid = obsdict_byid[obsid][0]
            f.write("%d,%d,%0.6f\n" % (obsid, nodeid, avg))
        f.close()
            
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
            logger.warn("Could not connect to database.")
        
        
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
