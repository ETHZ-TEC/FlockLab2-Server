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

import os, sys, getopt, traceback, MySQLdb, signal, time, errno, subprocess, logging, __main__, multiprocessing, queue, threading, select, socket, io, lxml.etree
import lib.daemon as daemon
import lib.flocklab as flocklab


logger      = None
debug       = False
stopevent   = None
reloadevent = None


##############################################################################
#
# sigterm_handler
#
##############################################################################
def sigterm_handler(signum, frame):
    """If the program is terminated by sending it the signal SIGTERM 
    (e.g. by executing 'kill') or SIGINT (pressing ctrl-c), 
    this signal handler is invoked for cleanup."""
    # NOTE: logging should not be used in signal handlers: https://docs.python.org/2/library/logging.html#thread-safety
    
    global stopevent
    global reloadevent
    
    logger.debug("sigterm_handler: signal %u received" % (signum))
    # Signal all threads to stop:
    if signum == signal.SIGTERM and stopevent:
        stopevent.set()
    elif signum == signal.SIGINT and reloadevent:
        reloadevent.set()
### END sigterm_handler


##############################################################################
#
# listen_process
#
##############################################################################
def listen_process(port, newConnectionQueue, _stopevent):
    while not _stopevent.is_set():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('',port))
            sock.settimeout(1)
            logger.info("Started socket %s:%d"%('',port))
            while not _stopevent.is_set():
                sock.listen(1)
                try:
                    connection, address = sock.accept()
                except socket.timeout:
                    continue
                connection.settimeout(None)
                logger.info("Connection from %s at port %d"%(str(address),port))
                address = (address[0], port)
                newConnectionQueue.put((connection, address))
            logger.info("Listen process on port %d ended." % port)
        except:
            logger.error("Listen process on port %d: Socket error %s"%(port,str(sys.exc_info()[1])))
        time.sleep(5)
### END listen_process


##############################################################################
#
# obs_connect_process
#
##############################################################################
def obs_connect_process(conreqQueue, condoneQueue, _stopevent):
    worklist = []
    while not _stopevent.is_set():
        try:
            req = conreqQueue.get(True, 1)
            worklist.append(req)
        except queue.Empty:
            pass
        for w in worklist:
            if w is None:
                worklist = []
                break
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(w)
                logger.info("Connected to observer %s on port %d" % (w[0],w[1]))
                condoneQueue.put((sock, w))
            except ConnectionRefusedError:
                logger.info("Could not connect to observer %s on port %d, dropping connection." % (w[0],w[1]))
            except Exception:
                logger.info("Could not connect to observer %s on port %d: %s, %s\n%s" % (w[0], w[1], str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc()))
            finally:
                worklist.remove(w)
### END obs_connect_process


##############################################################################
#
# update_configuration_from_db
#
##############################################################################
def update_configuration_from_db():
    # Get needed metadata from database ---
    # for all running / preparing tests
    # for each observer used in a serial configuration
    # (user remoteIp, server port, observer ip, port)
    
    proxystartport = flocklab.config.getint('serialproxy', 'startport')
    obsdataport = flocklab.config.getint('serialproxy', 'obsdataport')
    proxyConfig = []
    logger.debug("Updating configuration from DB...")
    try:
        (cn, cur) = flocklab.connect_to_db()
        cur.execute('SET time_zone="+0:00"')
    except:
        msg = "Could not connect to database"
        logger.error(msg)
        flocklab.error_logandexit(msg, errno.EAGAIN)
    try:
        # Get the XML config from the database:
        cur.execute("SELECT `testconfig_xml`, `serv_tests_key` FROM `tbl_serv_tests` WHERE (`test_status` IN ('preparing', 'running') AND `time_end_wish` >= NOW())")
        ret = cur.fetchall()
        for testconfig in ret:
            logger.debug("Create proxy config for test %d" % testconfig[1])
            # get slot mappings
            cur.execute("SELECT `observer_id`, `ethernet_address`, `slot` FROM `tbl_serv_map_test_observer_targetimages` `a` left join `tbl_serv_observer` `b` ON (`a`.`observer_fk` = `b`.`serv_observer_key`) WHERE `test_fk` = %d" % testconfig[1])
            mapret = cur.fetchall()
            mapping = {} # dict obsid -> (ip_address, port)
            for m in mapret:
                if not m[2] is None:
                    mapping[int(m[0])] = (m[1], obsdataport)
            parser = lxml.etree.XMLParser(remove_comments=True)
            tree = lxml.etree.fromstring(bytes(bytearray(testconfig[0], encoding = 'utf-8')), parser)
            ns = {'d': flocklab.config.get('xml', 'namespace')}
            logger.debug("Got XML from database.")
            ## Process serial configuration ---
            srconfs = tree.xpath('//d:serialConf', namespaces=ns)
            for srconf in srconfs:
                obsids = srconf.xpath('d:obsIds', namespaces=ns)[0].text.split()
                remoteIp = srconf.xpath('d:remoteIp', namespaces=ns)[0].text
                # Create a pair of FIFO pipes for every observer and start ncat:
                for obsid in obsids:
                    if int(obsid) in mapping:
                        proxyConfig.append(((remoteIp, proxystartport + int(obsid)),mapping[int(obsid)]))
        if len(proxyConfig) == 0:
            logger.info("No serial forwarders required.")
        else:
            logger.debug("Current proxy configuration:")
            for pc in proxyConfig:
                logger.debug("%s:%d <-> %s:%d" % (pc[0][0],pc[0][1],pc[1][0],pc[1][1]))
        return proxyConfig
    except MySQLdb.Error as err:
        msg = str(err)
        logger.error(msg)
        flocklab.error_logandexit(msg, errno.EIO)
    except:
        logger.warning("Error %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])))
        raise
### END update_configuration_from_db


##############################################################################
#
# class ProxyConnections
#
##############################################################################
class ProxyConnections():
    server_socket_process_list = {} # dict port > process
    obs_socket_list = {} # dict (obs,slot) -> socket
    server_socket_list = {} # dict (clientaddr, obs, slot) -> socket
    client_to_obs = {} # dict obs_socket -> server_socket
    obs_to_client = {} # dict server_socket -> obs_socket
    proxyConfig = []
    addlist = []
    removelist = []
    op = None
    
    def __init__(self):
        # multiprocessing events and queues
        #  for server socket processes
        self.stopevent = multiprocessing.Event()
        self.reloadevent = multiprocessing.Event()
        self.newConnectionQueue = multiprocessing.Queue()
        #  for observer reconnect process
        self.conreqQueue = multiprocessing.Queue()
        self.condoneQueue = multiprocessing.Queue()
        # start observer reconnect process
        self.op = threading.Thread(target = obs_connect_process, args=(self.conreqQueue,self.condoneQueue,self.stopevent,))
        self.op.daemon = True
        
    def reloadConfiguration(self, newconfig):
        oldconfig = self.proxyConfig
        self.proxyConfig = newconfig
        # empty observer request queue
        self.conreqQueue.put(None)
        # drop old connections
        for dc in [c for c in oldconfig if c not in newconfig]:
            logger.debug("Drop old connection %s" % str(dc))
            self.server_socket_process_list[dc[0][1]][1].set() # set stop event
            if dc[0] in self.server_socket_list and self.server_socket_list[dc[0]]:
                self.removeHandler(self.server_socket_list[dc[0]])
            elif dc[1] in self.obs_socket_list and self.obs_socket_list[dc[1]]:
                self.removeHandler(self.obs_socket_list[dc[1]])
        for dc in [c for c in oldconfig if c not in newconfig]:
            self.server_socket_process_list[dc[0][1]][0].join()
            del self.server_socket_process_list[dc[0][1]]      # remove the entry from the dictionary
        # add new connections
        for nc in [c for c in newconfig if c not in oldconfig]:
            logger.debug("Add new connection %s" % str(nc))
            self.requestListenSocket(nc[0])
            self.requestObserverSocket(nc[1])
            
    def requestListenSocket(self, addr):
        if not addr[1] in self.server_socket_process_list:
            _stopevent = multiprocessing.Event()
            lp = threading.Thread(target = listen_process, args=(addr[1],self.newConnectionQueue,_stopevent,))
            lp.daemon = True
            lp.start()
            self.server_socket_process_list[addr[1]] = (lp, _stopevent)
        
    def requestObserverSocket(self, addr):
        self.conreqQueue.put(addr)
        
    def getLists(self, is_observer):
        if is_observer:
            return self.obs_socket_list, self.server_socket_list, self.obs_to_client, self.client_to_obs
        else:
            return self.server_socket_list, self.obs_socket_list, self.client_to_obs, self.obs_to_client
    
    def removeHandler(self, conn):
        reconnect = None
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()
        # remove from socket list
        for l in (self.obs_socket_list, self.server_socket_list):
            for k,s in list(l.items()):
                if s == conn:
                    del(l[k])
                    reconnectaddr = k
                    break
        # if bidirectional, remove also other socket
        if conn in self.client_to_obs: # client connetion. remove
            reconnect = False
            src_list, dst_list, src_to_dst, dst_to_src = self.getLists(False)
        elif conn in self.obs_to_client: # observer connection. try to reconnect with timeout
            reconnect = True
            src_list, dst_list, src_to_dst, dst_to_src = self.getLists(True)
        else:
            return
        self.removelist.append(conn)
        self.removelist.append(src_to_dst[conn])
        del(dst_to_src[src_to_dst[conn]])
        del(src_to_dst[conn])
        if reconnect and reconnectaddr:
            connectionConfig = [p for p in self.proxyConfig if p[1] == reconnectaddr]
            if len(connectionConfig) > 0:
                self.requestObserverSocket(connectionConfig[0][1])
    
    def addHandler(self, conn, addr, is_observer):
        if is_observer:
            connectionConfig = [p[0] for p in self.proxyConfig if p[1] == addr]
        else:
            connectionConfig = [p[1] for p in self.proxyConfig if p[0] == addr]
        if len(connectionConfig) > 0:
            src_list, dst_list, src_to_dst, dst_to_src = self.getLists(is_observer)
            connectionConfig = connectionConfig[0]
            if addr in src_list:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
                logger.info("Connection rejected, already exists")
                return
            src_list[addr] = conn
            #logger.debug("src_list is %s" % str(src_list))
            if connectionConfig in dst_list:
                src_to_dst[conn] = dst_list[connectionConfig]
                dst_to_src[dst_list[connectionConfig]] = conn
                # forward on this connection
                self.addlist.append(conn)
                self.addlist.append(src_to_dst[conn])
                logger.info("Established connection %s" % (str((connectionConfig, addr))))
        else:
            conn.close()
            logger.info("Connection not for us, addr was %s" % str(addr))

    def getChanges(self):
        a = self.addlist
        r = self.removelist
        self.addlist = []
        self.removelist = []
        return a, r
    
    def forward(self, data, src_conn):
        if src_conn in self.client_to_obs and self.client_to_obs[src_conn]:
            self.client_to_obs[src_conn].send(data)
        elif src_conn in self.obs_to_client and self.obs_to_client[src_conn]:
            self.obs_to_client[src_conn].send(data)
    
    def run(self):
        global stopevent
        global reloadevent
        stopevent = self.stopevent
        reloadevent = self.reloadevent
        self.op.start()
        logger.info("FlockLab serial proxy started.")
        
        # infinite while loop
        inputs = [self.newConnectionQueue._reader, self.condoneQueue._reader]
        while not stopevent.is_set():
            try:
                (readable, writable, ex) = select.select(inputs,[],[],10)   # 10s timeout
            except select.error as e:
                if e[0] != errno.EINTR:
                    raise
            except Exception as e:
                logger.error("Error %s, %s" % (str(e), type(e)))
                raise
            
            # config reload necessary?
            if reloadevent.is_set():
                reloadevent.clear()
                logger.info("Reloading configuration...")
                newProxyConfig = update_configuration_from_db()
                self.reloadConfiguration(newProxyConfig)
                if len(newProxyConfig) == 0:
                    logger.info("No running tests, shutting down serial proxy...")
                    stopevent.set()
                readable = []
            
            # check new connections
            try:
                for i in readable:
                    # new connection from user
                    if i == self.newConnectionQueue._reader: 
                        try:
                            conn, addr = self.newConnectionQueue.get(False)
                            self.addHandler(conn, addr, is_observer = False)
                        except queue.Empty: 
                            pass
                    # new connection to observer
                    elif i == self.condoneQueue._reader:
                        try:
                            conn, addr = self.condoneQueue.get(False)
                            self.addHandler(conn, addr, is_observer = True)
                        except queue.Empty: 
                            pass
                    # assume it is a socket, do forwarding
                    else:
                        m = ''
                        try:
                            m = i.recv(1024)
                            logger.debug("received %d bytes from socket %s" % (len(m), str(i)))
                        except socket.error as serr:
                            # user probably disconnected, don't generate an error message
                            logger.debug("socket_error")
                            break
                        except Exception as e:
                            logger.error("error %s, %s" % (str(e), type(e)))
                        # a socket without data available is from a client that has disconnected
                        if len(m) == 0:
                            self.removeHandler(i)
                        else:
                            self.forward(m, i)
                # do book keeping
                iadd, iremove = self.getChanges()
                for r in iremove:
                    logger.debug("remove socket %s" %str(r))
                    inputs.remove(r)
                for a in iadd:
                    logger.debug("add socket %s" %str(a))
                    inputs.append(a)
            except:
                logger.error("Error %s, %s" % (str(e), type(e)))
            
        self.reloadConfiguration([])
        self.op.join()
        
        logger.info("Serial proxy stopped.")
### END class ProxyConnections


##############################################################################
#
# Start proxy
#
##############################################################################
def start_proxy():
    proxyConfig = update_configuration_from_db()
    if len(proxyConfig) == 0:
        logger.info("No connections, exiting...")
        return
    # Daemonize the process ---
    daemon.daemonize(None, closedesc=False)
    # Catch kill signals ---
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT,  sigterm_handler)
    logger.info("Serial proxy daemon started.")
    proxy = ProxyConnections()
    proxy.reloadConfiguration(proxyConfig)
    proxy.run()
### END start_proxy


##############################################################################
#
# Stop proxy
#
##############################################################################
def sig_proxy(signum):
    # Get oldest running instance of the proxy for the selected test ID which is the main process and send it the terminate signal:
    searchterm = "%s" % __file__
    cmd = ['pgrep', '-o', '-f', searchterm]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    out, err = p.communicate()
    if (p.returncode == 0):
        pid = int(out)
        # Do not stop this instance if it is the only one running:
        if (pid == os.getpid()):
            return errno.ENOPKG
    else:
        logger.warning("Command failed: %s" % (str(cmd)))
        return errno.ENOPKG
    # Signal the process to stop:
    if (pid > 0):
        logger.debug("Sending signal %d to process %d" %(signum, pid))
        try:
            os.kill(pid, signum)
            if signum == signal.SIGTERM:
                logger.debug("Waiting for process to finish...")
                # wait for process to finish (timeout..)
                shutdown_timeout = flocklab.config.getint("serialproxy", "shutdown_timeout")
                pidpath = "/proc/%d"%pid
                while os.path.exists(pidpath) & (shutdown_timeout>0):
                    time.sleep(1)
                    shutdown_timeout = shutdown_timeout - 1
                if os.path.exists(pidpath):
                    logger.warning("Serial proxy is still running, sending it the SIGKILL signal...")
                    os.kill(pid, signal.SIGKILL)
        except:
            logger.warning("Failed to send SIGKILL: %s: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1])))
    
    return flocklab.SUCCESS
### END sig_proxy


##############################################################################
#
# Usage
#
##############################################################################
def usage():
    print("Usage: %s --notify/start/stop [--debug] [--help]" % __file__)
    print("Options:")
    print("  --notify\t\t\tNotifies the proxy of a change in the database.")
    print("  --start\t\t\tStarts the background process of the proxy.")
    print("  --stop\t\t\tCauses the program to stop a possibly running instance of the serial proxy.")
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
    
    stop = False
    start = False
    notify = False
    
    # Get logger:
    logger = flocklab.get_logger(debug=debug)
    
    # Get the config file ---
    flocklab.load_config()
    
    # Get command line parameters ---
    try:
        opts, args = getopt.getopt(argv, "hnsed", ["help", "notify", "start", "stop", "debug"])
    except getopt.GetoptError as err:
        print(str(err))
        logger.warning(str(err))
        usage()
        sys.exit(errno.EINVAL)
    except:
        logger.error("Error when getting arguments: %s: %s" %(str(sys.exc_info()[0]), str(sys.exc_info()[1])), errno.EAGAIN)
        sys.exit(errno.EINVAL)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(flocklab.SUCCESS)
        elif opt in ("-d", "--debug"):
            debug = True
            logger.setLevel(logging.DEBUG)
        elif opt in ("-e", "--stop"):
            stop = True
        elif opt in ("-s", "--start"):
            start = True
        elif opt in ("-n", "--notify"):
            notify = True
        else:
            print("Wrong API usage")
            logger.warning("Wrong API usage")
            sys.exit(errno.EINVAL)
    
    # Start / stop the proxy ---
    ret = flocklab.SUCCESS
    if stop:
        ret = sig_proxy(signal.SIGTERM)
        logger.debug("SIGTERM sent to serial proxy daemon.")
    elif notify:
        ret = sig_proxy(signal.SIGINT)
        logger.debug("SIGINT sent to serial proxy daemon.")
    
    if start or (notify and ret == errno.ENOPKG):
        # Start the proxy processes:
        ret = flocklab.SUCCESS
        try:
            logger.debug("Starting serial proxy...")
            start_proxy()
        except Exception:
            logger.error("Failed to start serial proxy daemon.\n%s" % traceback.format_exc())
            ret = flocklab.FAILED
        
    sys.exit(ret)
### END main()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        flocklab.error_logandexit("Encountered error: %s: %s\n%s\nCommand line was: %s" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]), traceback.format_exc(), str(sys.argv)))
