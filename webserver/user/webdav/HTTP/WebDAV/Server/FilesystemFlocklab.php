<?php
/*
 * __author__      = "Roman Lim <lim@tik.ee.ethz.ch>"
 * __copyright__   = "Copyright 2012, ETH Zurich, Switzerland"
 * __license__     = "GPL"
 * __version__     = "$Revision: 1279 $"
 * __date__        = "$Date: 2011-08-05 10:30:22 +0200 (Fri, 05 Aug 2011) $"
 * __id__          = "$Id: presets.php 1279 2011-08-05 08:30:22Z walserc $"
 * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/presets.php $" 
 */
/*
   +----------------------------------------------------------------------+
   | Copyright (c) 2002-2007 Christian Stocker, Hartmut Holzgraefe        |
   | All rights reserved                                                  |
   |                                                                      |
   | Redistribution and use in source and binary forms, with or without   |
   | modification, are permitted provided that the following conditions   |
   | are met:                                                             |
   |                                                                      |
   | 1. Redistributions of source code must retain the above copyright    |
   |    notice, this list of conditions and the following disclaimer.     |
   | 2. Redistributions in binary form must reproduce the above copyright |
   |    notice, this list of conditions and the following disclaimer in   |
   |    the documentation and/or other materials provided with the        |
   |    distribution.                                                     |
   | 3. The names of the authors may not be used to endorse or promote    |
   |    products derived from this software without specific prior        |
   |    written permission.                                               |
   |                                                                      |
   | THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS  |
   | "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT    |
   | LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS    |
   | FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE       |
   | COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,  |
   | INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, |
   | BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;     |
   | LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER     |
   | CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT   |
   | LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN    |
   | ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE      |
   | POSSIBILITY OF SUCH DAMAGE.                                          |
   +----------------------------------------------------------------------+
*/

require_once "HTTP/WebDAV/Server.php";
require_once "System.php";
ini_set("include_path", ".:../");
require_once "include/libflocklab.php";

session_start();
       
// Check if session expired and restart a new one if it did:
if(isset($_SESSION['expires']) && $_SESSION['expires'] < $_SERVER['REQUEST_TIME'] ) {
     destroy_session();
     session_start();
     session_regenerate_id();
}
       
// Set session timeout:
$_SESSION['expires'] = $_SERVER['REQUEST_TIME'] + $CONFIG['session']['expiretime'];

set_exception_handler('flog');
function flog($text) {
/*
        $f = fopen ( 'debug' , 'a' );
        fwrite($f, "\n".date(DATE_W3C).": ------------------------------------------------\n");
        fwrite($f, $text);
        fclose($f);
*/
}

    
/**
 * Filesystem access using WebDAV
 *
 * @access  public
 * @author  Hartmut Holzgraefe <hartmut@php.net>
 * @version @package-version@
 */
class HTTP_WebDAV_Server_Filesystem extends HTTP_WebDAV_Server 
{

    /**
     * Serve a webdav request
     *
     * @access public
     * @param  string  
     */
    function ServeRequest($base = false) 
    {
        // special treatment for litmus compliance test
        // reply on its identifier header
        // not needed for the test itself but eases debugging
        if (isset($this->_SERVER['HTTP_X_LITMUS'])) {
            error_log("Litmus test ".$this->_SERVER['HTTP_X_LITMUS']);
            header("X-Litmus-reply: ".$this->_SERVER['HTTP_X_LITMUS']);
        }
        array_walk ( $this->_SERVER, array($this, 'stripscript'));
        
        //flog(print_r($this->_SERVER,true));
        flog($this->_SERVER['REQUEST_METHOD'].' '.$this->_SERVER['REQUEST_URI']);
        // let the base class do all the work
        parent::ServeRequest();
    }
    
    function stripscript(&$item, $key) {
        $orig = $item;
        $item=preg_replace('#(user/webdav)/file\.php#', '$1', $item);
        //flog("strip ".$key.':['.$orig.']->['.$item.']');
    }

    /**
     * No authentication is needed here
     *
     * @access private
     * @param  string  HTTP Authentication type (Basic, Digest, ...)
     * @param  string  Username
     * @param  string  Password
     * @return bool    true on successful authentication
     */
    function check_auth($type, $user, $pass) 
    {
        if (do_login($user, $pass))
                return true;
        else
                return false;
    }


    /**
     * PROPFIND method handler
     *
     * @param  array  general parameter passing array
     * @param  array  return array for file properties
     * @return bool   true on success
     */
    function PROPFIND(&$options, &$files) 
    {
        // path should be empty or have this format
        // <testid>
        // <testid>/results.tar.gz
        // <testid>/images/

        // prepare property array
        $files["files"] = array();
        
        flog($options['path']);
        $owner_query = $_SESSION['is_admin']?"":("owner_fk = " . $_SESSION['serv_users_key'] . " AND ");
        if (preg_match('#^/?$#', $options['path'])) {
                $db = db_connect();
                $sql =  "SELECT UNIX_TIMESTAMP(last_changed) as last_changed 
                         FROM tbl_serv_tests 
                         WHERE ".$owner_query."test_status <> 'deleted' AND test_status <> 'todelete'
                         ORDER BY last_changed DESC limit 1";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                // store information for the requested path itself
                if (mysqli_num_rows($rs)==0)
                        $files["files"][] = $this->fileinfodir($this->_slashify($options["path"]), time());
                else {
                        $row = mysqli_fetch_array($rs);
                        $files["files"][] = $this->fileinfodir($this->_slashify($options["path"]), $row['last_changed']);
                }
                if (!empty($options["depth"])) {
                        $sql =  "SELECT serv_tests_key, title, description, time_start_act, time_start_wish, time_end_act, time_end_wish, test_status, UNIX_TIMESTAMP(last_changed) as last_changed
                                FROM tbl_serv_tests 
                                WHERE ".$owner_query."test_status <> 'deleted' AND test_status <> 'todelete'
                                ORDER BY serv_tests_key DESC";
                        $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                        $nrows = mysqli_num_rows($rs);
                        while ($row = mysqli_fetch_array($rs)) {
                                $files["files"][] = $this->fileinfodir($this->_slashify($options['path']).$row['serv_tests_key'], $row['last_changed']);
                        }
                }
                mysqli_close($db);
                flog(print_r($files,true));
                return true;
        }
        else if (preg_match('#^/([0-9]+)/?$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =  "SELECT serv_tests_key, test_status, UNIX_TIMESTAMP(last_changed) as last_changed, LENGTH(testconfig_xml) as configlength, UNIX_TIMESTAMP(time_end_act) as results_last_changed
                         FROM tbl_serv_tests 
                         WHERE ".$owner_query."serv_tests_key=".mysqli_real_escape_string($db, $matches[1])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                         ";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $files["files"][] = $this->fileinfodir($this->_slashify($options["path"]), $row['last_changed']);
                if (!empty($options["depth"])) {
                        // configfile
                        $files["files"][] = $this->fileinfofile($this->_slashify($options['path']).'testconfiguration.xml', $row['last_changed'], 'application/xml', $row['configlength']);
                        // images
                        $files["files"][] = $this->fileinfodir('/'.$matches[1].'/images', $row['last_changed']);
                        // results
                        if (($row['test_status']=='finished') || ($row['test_status']=='retention expiring')) {
                                $files["files"][] = $this->fileinfofile('/'.$matches[1].'/results.tar.gz', $row['results_last_changed'], 'application/x-gzip', $this->getTestSize($matches[1], True));
                                $files["files"][] = $this->fileinfofile('/'.$matches[1].'/results_nopower.tar.gz', $row['results_last_changed'], 'application/x-gzip', $this->getTestSize($matches[1], False));
                        }
                }
                flog(print_r($files,true));
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(testconfiguration\.xml)$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =  "SELECT serv_tests_key, test_status, UNIX_TIMESTAMP(last_changed) as last_changed, LENGTH(testconfig_xml) as configlength
                         FROM tbl_serv_tests 
                         WHERE ".$owner_query."serv_tests_key=".mysqli_real_escape_string($db, $matches[1])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                         ";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $files["files"][] = $this->fileinfofile($options['path'], $row['last_changed'], 'application/xml', $row['configlength']);
                flog(print_r($files,true));
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(results.tar.gz|results_nopower.tar.gz)$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =  "SELECT serv_tests_key, test_status, UNIX_TIMESTAMP(time_end_act) as results_last_changed, LENGTH(testconfig_xml) as configlength
                         FROM tbl_serv_tests 
                         WHERE ".$owner_query."serv_tests_key=".mysqli_real_escape_string($db, $matches[1])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                         ";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $files["files"][] = $this->fileinfofile('/'.$matches[1].'/results.tar.gz', $row['results_last_changed'], 'application/x-gzip', $this->getTestSize($matches[1], strpos($options['path'], '_nopower')===False));
                flog(print_r($files,true));
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(images)/?$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =   "SELECT serv_tests_key, `targetimage_fk`, UNIX_TIMESTAMP(tbl_serv_targetimages.last_changed) as image_last_changed,
                                UNIX_TIMESTAMP(tbl_serv_tests.last_changed) as last_changed,
                                length(`binary`) as imagesize, tbl_serv_operatingsystems.name as os, tbl_serv_platforms.name as platform
                                FROM tbl_serv_tests
                                LEFT JOIN tbl_serv_map_test_observer_targetimages ON (serv_tests_key = test_fk)
                                LEFT JOIN tbl_serv_targetimages ON (serv_targetimages_key = `targetimage_fk`)
                                LEFT JOIN tbl_serv_platforms ON (serv_platforms_key = `platforms_fk`)
                                LEFT JOIN tbl_serv_operatingsystems ON (serv_operatingsystems_key= `operatingsystems_fk`)
                                WHERE tbl_serv_tests.".$owner_query."serv_tests_key = ".mysqli_real_escape_string($db, $matches[1])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                                GROUP BY `targetimage_fk`";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows == 0)
                        return false;
                $row = mysqli_fetch_array($rs);
                $files["files"][] = $this->fileinfodir($this->_slashify($options["path"]), $row['last_changed']); 
                if (!empty($options["depth"])) {
                        mysqli_data_seek($rs,0);
                        while($row = mysqli_fetch_array($rs)) {
                                if (!empty($row['targetimage_fk']))
                                        $files["files"][] = $this->fileinfofile('/'.$matches[1].'/images/'.$row['targetimage_fk'].'.'.$row['platform'].'.'.$row['os'].'.exe', $row['image_last_changed'], 'application/octet-stream', $row['imagesize']);
                        }
                }
                flog(print_r($files,true));
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(images)/([0-9]+)\..*$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =   "SELECT serv_tests_key, `targetimage_fk`, UNIX_TIMESTAMP(tbl_serv_targetimages.last_changed) as image_last_changed,
                          length(`binary`) as imagesize, tbl_serv_operatingsystems.name as os, tbl_serv_platforms.name as platform
                          FROM tbl_serv_tests
                          LEFT JOIN tbl_serv_map_test_observer_targetimages ON (serv_tests_key = test_fk)
                          LEFT JOIN tbl_serv_targetimages ON (serv_targetimages_key = `targetimage_fk`)
                          LEFT JOIN tbl_serv_platforms ON (serv_platforms_key = `platforms_fk`)
                          LEFT JOIN tbl_serv_operatingsystems ON (serv_operatingsystems_key= `operatingsystems_fk`)
                          WHERE tbl_serv_tests.".$owner_query."serv_tests_key = ".mysqli_real_escape_string($db, $matches[1])."
                                AND serv_targetimages_key = ".mysqli_real_escape_string($db, $matches[3])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                          GROUP BY `targetimage_fk`";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $files["files"][] = $this->fileinfofile($options["path"], $row['image_last_changed'], 'application/octet-stream', $row['imagesize']);
                flog(print_r($files,true));
                return true;
        }
        else {
                return false;
        }
    } 
    
    function fileinfodir($path, $lastchange) {
        $info = array();
        
        $info["path"]  = $path;
        $info["props"] = array();
        // no special beautified displayname here ...
        $info["props"][] = $this->mkprop("displayname", strtoupper($info["path"]));
          
        // creation and modification time
        $info["props"][] = $this->mkprop("creationdate",    $lastchange);
        $info["props"][] = $this->mkprop("getlastmodified", $lastchange);
        // Microsoft extensions: last access time and 'hidden' status
        $info["props"][] = $this->mkprop("ishidden", 0);
        // directory (WebDAV collection)
        $info["props"][] = $this->mkprop("resourcetype", "collection");
        $info["props"][] = $this->mkprop("getcontenttype", "httpd/unix-directory");     
        return $info;
    }
    
    function fileinfofile($path, $lastchange, $mime, $size) {
        // create result array
        $info = array();
        $info["path"]  = $path;
        $info["props"] = array();
            
        // no special beautified displayname here ...
        $info["props"][] = $this->mkprop("displayname", strtoupper($info["path"]));
            
        // creation and modification time
        $info["props"][] = $this->mkprop("creationdate",    $lastchange);
        $info["props"][] = $this->mkprop("getlastmodified", $lastchange);

        // Microsoft extensions: last access time and 'hidden' status
        $info["props"][] = $this->mkprop("ishidden", 0);
        // plain file (WebDAV resource)
        $info["props"][] = $this->mkprop("resourcetype", "");
        $info["props"][] = $this->mkprop("getcontenttype", $mime);
        if ($size!=null)
            $info["props"][] = $this->mkprop("getcontentlength", $size);
        return $info;
    }
        
        

    /**
     * HEAD method handler
     * 
     * @param  array  parameter passing array
     * @return bool   true on success
     */
    function HEAD(&$options) 
    {
        flog($options['path']);
        $owner_query = $_SESSION['is_admin']?"":("owner_fk = " . $_SESSION['serv_users_key'] . " AND ");
        if (preg_match('#^/([0-9]+)/(testconfiguration\.xml)$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =  "SELECT serv_tests_key, test_status, UNIX_TIMESTAMP(last_changed) as last_changed, LENGTH(testconfig_xml) as configlength
                         FROM tbl_serv_tests 
                         WHERE ".$owner_query." serv_tests_key=".mysqli_real_escape_string($db, $matches[1])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                         ";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $options['mimetype'] = 'application/xml';
                $options['mtime'] = $row['last_changed'];        
                $options['size'] = $row['configlength'];
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(results.tar.gz|results_nopower.tar.gz)$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =  "SELECT serv_tests_key, test_status, UNIX_TIMESTAMP(time_end_act) as results_last_changed, LENGTH(testconfig_xml) as configlength
                         FROM tbl_serv_tests 
                         WHERE ".$owner_query." serv_tests_key=".mysqli_real_escape_string($db, $matches[1])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                         ";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $options['mimetype'] = 'application/x-gzip';
                $options['mtime'] = $row['results_last_changed'];
                $options['size'] = $this->getTestSize($matches[1], strpos($options['path'], '_nopower')===False);
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(images)/([0-9]+)\..*$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =   "SELECT serv_tests_key, `targetimage_fk`, UNIX_TIMESTAMP(tbl_serv_targetimages.last_changed) as image_last_changed,
                          length(`binary`) as imagesize, tbl_serv_operatingsystems.name as os, tbl_serv_platforms.name as platform
                          FROM tbl_serv_tests
                          LEFT JOIN tbl_serv_map_test_observer_targetimages ON (serv_tests_key = test_fk)
                          LEFT JOIN tbl_serv_targetimages ON (serv_targetimages_key = `targetimage_fk`)
                          LEFT JOIN tbl_serv_platforms ON (serv_platforms_key = `platforms_fk`)
                          LEFT JOIN tbl_serv_operatingsystems ON (serv_operatingsystems_key= `operatingsystems_fk`)
                          WHERE tbl_serv_tests.".$owner_query."serv_tests_key = ".mysqli_real_escape_string($db, $matches[1])."
                                AND serv_targetimages_key = ".mysqli_real_escape_string($db, $matches[3])." AND test_status <> 'deleted' AND test_status <> 'todelete'
                          GROUP BY `targetimage_fk`";
                flog($sql);
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $options['mimetype'] = 'application/octet-stream';
                $options['mtime'] = $row['image_last_changed'];        
                $options['size'] = $row['imagesize'];
                return true;
        }
        else
           return false;
    }
        
    /**
     * GET method handler
     * 
     * @param  array  parameter passing array
     * @return bool   true on success
     */
    function GET(&$options) 
    {
        // the header output is the same as for HEAD
        if (!$this->HEAD($options)) {
            return false;
        }
        $owner_query = $_SESSION['is_admin']?"":("owner_fk = " . $_SESSION['serv_users_key'] . " AND ");
        if (preg_match('#^/([0-9]+)/(testconfiguration\.xml)$#', $options['path'], $matches)==1) {
                // test info
                $config = get_testconfig(intval($matches[1]));
                if ($config==false)
                        return false;
                // no need to check result here, it is handled by the base class
                $options['data'] = $config;
            
                return true;
        }
        else if (preg_match('#^/([0-9]+)/(results.tar.gz)$#', $options['path'], $matches)==1) {
                $results = $this->getTest($matches[1], True);
                if ($results===true) {
                    return "503 Service Unavailable";
                }
                else if ($results!=false) {
                        $options['stream'] = $results;
                        flog(print_r($options,true));
                        return true;
                }
                return false; 
        }
        else if (preg_match('#^/([0-9]+)/(results_nopower.tar.gz)$#', $options['path'], $matches)==1) {
               $results = $this->getTest($matches[1], False);
                if ($results===true) {
                    return "503 Service Unavailable";
                }
                else if ($results!=false) {
                        $options['stream'] = $results;
                        return true;
                }
                return false; 
        }
        else if (preg_match('#^/([0-9]+)/(images)/([0-9]+)\..*$#', $options['path'], $matches)==1) {
                // test info
                $db = db_connect();
                $sql =   "SELECT `binary`
                          FROM tbl_serv_targetimages
                          WHERE (".$owner_query." serv_targetimages_key = ".mysqli_real_escape_string($db, $matches[3]).") 
                          AND (`binary` is not NULL)";
                $rs = mysqli_query($db, $sql) or flog('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                if ($nrows != 1)
                        return false;
                $row = mysqli_fetch_array($rs);
                $options['data'] = $row['binary'];
                return true;
        }
        return false;
    }
    
    function getTest($testid, $power){
        global $CONFIG;
        if ($power) {
            // pipe file from archive
            $archivepath =  $CONFIG['testmanagementserver']['archivedir'];
            $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"ls ".$archivepath.'/'.$testid.".tar.gz\"";
            exec($cmd , $output, $ret);
            if ($ret > 0)
                return false;
            // dump whole archive
            $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"cat ".$archivepath.'/'.$testid.".tar.gz\"";
            $stream = popen($cmd, "r");
            return $stream;
        }
        else {
            flog("nopower");
            $archivepath =  $CONFIG['testmanagementserver']['archivedir'];
            $split_path = $CONFIG['testmanagementserver']['basedir'];
            $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"ls ".$archivepath.'/'.$testid.".tar.gz\"";
            exec($cmd , $output, $ret);
            if ($ret > 0)
                return false;
            // dump stripped archive
            flog("nopower dump");
            $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"/bin/zcat ".$archivepath.'/'.$testid.".tar.gz | ".$split_path."/flocklab_archive_split | /usr/bin/pigz\"";
            flog("nopower dump ". $cmd);
            $stream = popen($cmd, "r");
            return $stream;
        }
    }
    
    function getTestSize($testid, $power){
        global $CONFIG;
        if ($power===false)
            return null;
        // file exists?
        $archivepath =  $CONFIG['testmanagementserver']['archivedir'];
        $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"ls -l ".$archivepath.'/'.$testid.".tar.gz\"";
        exec($cmd , $output, $ret);
        if ($ret > 0)
            return 0;
        else {
            $size = explode(' ', $output[0]);
            $size = preg_replace('/([0-9]*) .*/','$1',$size[4]);
             if (strlen($size)>0)
                 return intval($size);
        }
        return 0;
    }

    /**
     * PUT method handler
     * 
     * @param  array  parameter passing array
     * @return bool   true on success
     */
    function PUT(&$options) 
    {
        return "403 Forbidden";
    }


    /**
     * MKCOL method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */
        
    /**
     * DELETE method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */

    /**
     * MOVE method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */

    /**
     * COPY method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */

    /**
     * PROPPATCH method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */

    /**
     * LOCK method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */

    /**
     * UNLOCK method handler
     *
     * @param  array  general parameter passing array
     * @return bool   true on success
     */

    /**
     * checkLock() helper
     *
     * @param  string resource path to check for locks
     * @return bool   true on success
     */

}


/*
 * Local variables:
 * tab-width: 4
 * c-basic-offset: 4
 * indent-tabs-mode:nil
 * End:
 */
