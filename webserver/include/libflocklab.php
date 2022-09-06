<?php
/**
 * Copyright (c) 2010 - 2020, ETH Zurich, Computer Engineering Group
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of the copyright holder nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 */
?>
<?php
require_once('include/config.php');
require_once('include/logging.php');

/*
##############################################################################
#
# db_connect
#
##############################################################################
*/
function db_connect()
{
    global $CONFIG;

    $dbh = mysqli_connect($CONFIG['database']['host'], $CONFIG['database']['user'], $CONFIG['database']['password'], $CONFIG['database']['database']) or flocklab_die ('Cannot connect to the database because: ' . mysqli_error($dbh));
    $sql='SET time_zone="+0:00"';
    mysqli_query($dbh, $sql) or flocklab_die('Cannot init timezone for database connection because: ' . mysqli_error($dbh));
    $sql='SET sql_mode=""';
    mysqli_query($dbh, $sql) or flocklab_die('Cannot set sql mode for database connection because: ' . mysqli_error($dbh));
    mysqli_query($dbh, "set names 'utf8'") or flocklab_die('Cannot set names for database connection because: ' . mysqli_error($dbh));
    return($dbh);
}



/*
##############################################################################
#
# debug
# 
# If called, the PHP option display_errors is turned on and all PHP errors 
# are output on the webpage. Use only for debugging.
#
##############################################################################
*/
function debug()
{
    if (!ini_get('display_errors')) {
        ini_set('display_errors', 1);
    }
    error_reporting(E_ALL);
}

/*
##############################################################################
#
# rrm
# 
# Recursively remove a file or directory and everything that's in it.
#
##############################################################################
*/
function rrm($dir) {
    if (!file_exists($dir)) return true;
    if (!is_dir($dir) || is_link($dir)) return unlink($dir);
    foreach (scandir($dir) as $item) {
        if ($item == '.' || $item == '..') continue;
        if (!rrm($dir . "/" . $item)) {
            chmod($dir . "/" . $item, 0777);
            if (!rrm($dir . "/" . $item)) return false;
        };
    }
    return rmdir($dir);
}
/*
##############################################################################
#
# do_login
#
# check name and password and create session.
#
# @param username
# @param password
# @return: true is successfully logged in
#
##############################################################################
*/
function do_login($username, $password) {
    global $CONFIG;

    // Check username and password:
    if (strlen($username)>0 && strlen($password) > 0) {
        $db = db_connect();
        $sql = "SELECT serv_users_key, username, firstname, lastname, email, role
            FROM tbl_serv_users 
            WHERE username = '" . mysqli_real_escape_string($db, $username) . "' AND password = '" . mysqli_real_escape_string($db, sha1($password)) . "' AND is_active=1";
        $rs = mysqli_query($db, $sql) or flocklab_die('Cannot authenticate because: ' . mysqli_error($db));
        $rows = mysqli_fetch_array($rs);
        if ($rows) {
            if ($rows['role'] != 'admin') {
                // check for global UI lock
                $sql = "SELECT message, time_start, time_end
                        FROM tbl_serv_web_status
                        WHERE time_start < UTC_TIMESTAMP() and time_end > UTC_TIMESTAMP() AND ui_lock='true'";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot authenticate because: ' . mysqli_error($db));
                if (mysqli_num_rows($rs) > 0) {
                    $rows = mysqli_fetch_array($rs);
                    $d = new DateTime($row['time_end']);
                    return $rows['message'].'<br>Access should again be possible after <span class="time">'.$d->format("U").'</span>';
                }
            }
            // update user stats
            $sql = "UPDATE tbl_serv_users set last_login=NOW(), login_count=login_count+1
                WHERE serv_users_key = " . $rows['serv_users_key'];
            mysqli_query($db, $sql);
            mysqli_close($db);
            // Set session variables for this user:
            $_SESSION['logged_in']          = true;
            $_SESSION['serv_users_key']     = $rows['serv_users_key'];
            $_SESSION['username']           = $rows['username']; 
            $_SESSION['firstname']          = $rows['firstname'];
            $_SESSION['lastname']           = $rows['lastname'];
            $_SESSION['email']              = $rows['email'];
            $_SESSION['is_admin']           = ($rows['role'] == 'admin') ? true : false;
            $_SESSION['is_internal']        = ($rows['role'] == 'internal') ? true : false;
            $_SESSION['expires'] = $_SERVER['REQUEST_TIME'] + $CONFIG['webserver']['sessionexpiretime'];
            return true;
        }
        else {
            mysqli_close($db);
        }
    }
    return false;
}
/*
##############################################################################
#
# destroy_session
# 
# Remove everything belonging to a session before destroying it.
#
##############################################################################
*/
function destroy_session() {
    // Remove the sessions temp directory:
    // rrm($_SESSION['tempdir']);

    // Destroy the session itself:
    session_destroy();

    // Destroy the sesssion cookie if it exists:
    if (isset($_COOKIE[session_name()]))
        setcookie(session_name(), null, 0);
}

/*
##############################################################################
#
# check_testid
# 
# Check if a test id belongs to the given user id
#
##############################################################################
*/
function check_testid($testid, $userid) {
    $db  = db_connect();
    $sql = "SELECT owner_fk
            FROM tbl_serv_tests
            WHERE serv_tests_key = " . $testid;
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get test owner from database because: ' . mysqli_error($db));
    $owner = mysqli_fetch_array($rs);
    mysqli_close($db);
    if ($owner['owner_fk'] == $userid) 
        return true;
    else 
        return false;
}

/*
##############################################################################
#
# check_imageid
# 
# Check if an image id belongs to the given user id
#
##############################################################################
*/
function check_imageid($imageid, $userid) {
    $db  = db_connect();
    $sql = "SELECT owner_fk
            FROM tbl_serv_targetimages
            WHERE serv_targetimages_key = " . $imageid;
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get test owner from database because: ' . mysqli_error($db));
    $owner = mysqli_fetch_array($rs);
    mysqli_close($db);
    if ($owner['owner_fk'] == $userid) 
        return true;
    else 
        return false;
}

/*
##############################################################################
#
# get_admin_emails
# 
# Get Email adresses of all Flocklab admins from the database 
#
##############################################################################
*/
function get_admin_emails() {
    global $CONFIG;
    $admins = Array();
    if (isset($CONFIG['email']['admin_email'])) {
        array_push($admins, trim($CONFIG['email']['admin_email']));
    } else {
      $db  = db_connect();
      $sql = "SELECT `email`
              FROM tbl_serv_users
              WHERE `role` = 'admin'";
      $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get admin emails from database because: ' . mysqli_error($db));
      while ($row=mysqli_fetch_array($rs)) {
          array_push($admins, $row['email']);
      }
      mysqli_close($db);
    }
    return $admins;
}

/*
##############################################################################
#
# get_flocklab_email
#
# Get the main mail address of Flocklab
#
##############################################################################
*/
function get_flocklab_email() {
    global $CONFIG;
    return $CONFIG['email']['flocklab_email'];
}

/*
##############################################################################
#
# send_mail
#
# Send an email
#
##############################################################################
*/
function send_mail($subject, $message, $recipient) {
    global $CONFIG;
    $header  = 'From: ' . $CONFIG['email']['flocklab_email'] . "\r\n" .
               'Reply-To: ' . $CONFIG['email']['admin_email'] . "\r\n" .
               'Content-Type: text/plain; charset=utf-8' . "\r\n" .
               'X-Mailer: PHP/' . phpversion();
    return mail($recipient, $subject, $message, $header);
}

/*
##############################################################################
#
# get_user_role
# 
# Get the role (access rights) of a user
#
##############################################################################
*/
function get_user_role($username=null) {
    $db = db_connect();
    if ($username == null || $username == "") {
        $sql = "SELECT role FROM tbl_serv_users WHERE serv_users_key=" . $_SESSION['serv_users_key'];
    } else {
        $sql = "SELECT role FROM tbl_serv_users WHERE username = '" . mysqli_real_escape_string($db, $username) . "'";
    }
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot authenticate because: ' . mysqli_error($db));
    $rows = mysqli_fetch_array($rs);
    if ($rows) {
        return $rows['role'];
    }
    return 'user'; /* default */
}

/*
##############################################################################
#
# get_available_platforms
# 
# from the database 
#
##############################################################################
*/
function get_available_platforms() {
    $db  = db_connect();
    $sql = 'SELECT `serv_platforms_key`, `name`, `core`, `tbl_serv_architectures`.`description` `core_desc`
            FROM `tbl_serv_platforms`
            LEFT JOIN `tbl_serv_architectures`
            ON `tbl_serv_architectures`.`platforms_fk` = `tbl_serv_platforms`.`serv_platforms_key`
            WHERE `active` = 1
            ORDER BY `name`, `core` ASC';
    $res = mysqli_query($db, $sql) or flocklab_die('Cannot fetch available platforms because: ' . mysqli_error($db));
    $num = mysqli_num_rows($res);
    $available_platforms = Array();
    $pkey = -1;
    while ($num-- > 0) {
        $row = mysqli_fetch_assoc($res);
        if ($pkey != $row['serv_platforms_key']) {
            $pkey = $row['serv_platforms_key'];
            $available_platforms[$row['serv_platforms_key']] = Array();
        }
        $available_platforms[$row['serv_platforms_key']][]=Array('name'=>$row['name'], 'core'=>$row['core'], 'core_desc'=>$row['core_desc']);
    }
    mysqli_close($db);
    return $available_platforms;
}

function get_testconfig($testid) {
    $db  = db_connect();
    $sql = "SELECT `testconfig_xml`
            FROM tbl_serv_tests
            WHERE ".($_SESSION['is_admin']?"":("owner_fk = " . $_SESSION['serv_users_key'] . " AND "))."`serv_tests_key`=".mysqli_real_escape_string($db, $testid);
    $res = mysqli_query($db, $sql);
    if ($res !== false) {
        $row = mysqli_fetch_assoc($res);
        return $row['testconfig_xml'];
    }
    return false;
}

function get_teststatus($testid) {
    $db  = db_connect();
    $sql = "SELECT `test_status`
            FROM tbl_serv_tests
            WHERE owner_fk = " . $_SESSION['serv_users_key'] . " AND `serv_tests_key`=".mysqli_real_escape_string($db, $testid);
    $res = mysqli_query($db, $sql);
    if ($res !== false) {
        $row = mysqli_fetch_assoc($res);
        return $row['test_status'];
    }
    return false;
}

/*
##############################################################################
#
# image validation
# 
# validate_image
# @param $image: assoc array('name','description','platform','data')
# @param &$errors: array where errors are added
#
##############################################################################
*/
function validate_image($image, &$errors) {
    global $CONFIG;
    $validate_image_errors = array();
    foreach(Array('name','platform') as $field)
    if (!isset($image[$field]) || strlen($image[$field])==0) {
        array_push($validate_image_errors, "Missing mandatory field <i>".$field."</i>");
    }
    // Get the file and check if it is a valid image
    $imagefile = tempnam(sys_get_temp_dir(), 'flocklab');
    file_put_contents($imagefile, $image['data']);
    $platform_list = get_available_platforms();
    // copy image file to testmanagement server
    $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." 'mkdir ".$CONFIG['testmanagementserver']['tempdir']."'";
    exec($cmd);
    $cmd = "scp ".$imagefile." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host'].":".$CONFIG['testmanagementserver']['tempdir'];
    exec($cmd, $output, $ret);
    if ($ret) {
        array_push($errors, "Failed to copy file '$test_config_file' to testmanagement server.");
        return False;
    }
    // remove unused file and adjust imagefile path
    unlink($imagefile);
    $imagefile = $CONFIG['testmanagementserver']['tempdir']."/".basename($imagefile);
    $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." '".$CONFIG['testmanagementserver']['venvwrapper']." ".$CONFIG['targetimage']['imagevalidator']." --image=".$imagefile." --platform=". $platform_list[$image['platform']][0]['name']." --core=".$image['core']."' 2>&1";
    exec($cmd , $output, $ret);
    if ($ret != 0) {
        array_push($validate_image_errors, "The supplied file is not a valid image for this platform.");
    }
    // remove file
    $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." 'rm ".$imagefile."'";
    exec($cmd, $output, $ret);
    if ($ret) {
        foreach ($output as $error) {
            array_push($errors, $error);
        }
    }
    $errors = array_merge($errors, $validate_image_errors);
    return count($errors) == 0;
}

/*
##############################################################################
#
# image validation
# 
# check_image_duplicate
# @param $image: assoc array('name','description','platform','core','data')
# @return: false if no duplicate were found, else the id of the duplicate
#
##############################################################################
*/
function check_image_duplicate($image) {
    // check hash
    $duplicate = false;
    $db = db_connect();
    $hash = hash('sha1', $image['data']);
    $sql = 'SELECT `serv_targetimages_key`, `binary`
            FROM `tbl_serv_targetimages`
            WHERE `owner_fk`='.$_SESSION['serv_users_key'].'
            AND `binary` IS NOT NULL 
            AND `binary_hash_sha1`="'.$hash.'"
            AND `platforms_fk`='.mysqli_real_escape_string($db, $image['platform']).'
            AND `core`='.mysqli_real_escape_string($db, $image['core']);
    $res = mysqli_query($db, $sql) or flocklab_die('Cannot compare to other images because: ' . mysqli_error($db));
    $num = mysqli_num_rows($res);
    while ($num-- > 0) {
        $row = mysqli_fetch_assoc($res);
        if (strcmp($row['binary'], $image['data'])==0) {
            $duplicate = $row['serv_targetimages_key'];
            break;
        }
    }
    mysqli_close($db);
    return $duplicate;
}

/*
##############################################################################
#
# image validation
# 
# store_image
# @param $image: assoc array('name','description','os','platform','core','data')
# @return: id of the stored image
# 
##############################################################################
*/
function store_image($image) {
    $id = null;
    $hash = hash('sha1', $image['data']);
    $db = db_connect();
    $sql = 'INSERT INTO `tbl_serv_targetimages` (`name`,`description`,`owner_fk`,`platforms_fk`,`core`,`binary`,`binary_hash_sha1`)
            VALUES (
            "'.mysqli_real_escape_string($db, trim($image['name'])).'",
            "'.mysqli_real_escape_string($db, trim($image['description'])).'",
            '.$_SESSION['serv_users_key'].',
            '.mysqli_real_escape_string($db, $image['platform']).',
            '.mysqli_real_escape_string($db, $image['core']).',
            "'.mysqli_real_escape_string($db, $image['data']).'",
            "'.$hash.'")';
    mysqli_query($db, $sql) or flocklab_die('Cannot save uploaded images because: ' . mysqli_error($db));
    $id = mysqli_insert_id($db);
    mysqli_close($db);
    return $id;
}

// validate test
function validate_test($test_config_file, &$errors) {
    global $CONFIG;
    // copy xml file to testmanagement server
    $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." 'mkdir ".$CONFIG['testmanagementserver']['tempdir']."'";
    exec($cmd);
    $cmd = "scp ".$test_config_file." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host'].":".$CONFIG['testmanagementserver']['tempdir'];
    exec($cmd , $output, $ret);
    if ($ret) {
        array_push($errors, "Failed to copy file '$test_config_file' to testmanagement server.");
        return False;
    }
    // adjust file name to new path
    $test_config_file = $CONFIG['testmanagementserver']['tempdir']."/".basename($test_config_file);
    // execute XML validation script in the python virtual environment on the testmanagement server as user flocklab
    $cmd = $CONFIG['testmanagementserver']['venvwrapper']." ".$CONFIG['dispatcher']['validationscript']." -x ".$test_config_file." -s ".$CONFIG['xml']['schemapath']." -u " . $_SESSION['serv_users_key'];
    exec("ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." '".$cmd."' 2>&1", $output, $ret);
    if ($ret) {
        foreach ($output as $error) {
            array_push($errors, $error);
        }
    }
    // remove copied file
    $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." 'rm ".$test_config_file."'";
    exec($cmd, $output, $ret);
    if ($ret) {
        foreach ($output as $error) {
            array_push($errors, $error);
        }
    }
    return count($errors) == 0;
}


/*
##############################################################################
#
# trigger scheduler on flocklab server to check for work.
# 
# trigger_scheduler
# 
##############################################################################
*/
function trigger_scheduler($debug = false) {
    global $CONFIG;
    // use SSH as a way to run the script under the user 'flocklab' on the testmanagement server
    $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." '".$CONFIG['testmanagementserver']['venvwrapper']." ".$CONFIG['testmanagementserver']['scheduler'].($debug ? " --debug" : "")."' > /dev/null 2>&1 &";
    exec($cmd);
}


// check quota
function check_quota($testconfig, $exclude_test = NULL, &$quota = NULL) {
    global $CONFIG;
    $this_runtime = $testconfig->generalConf->schedule->duration / 60;

    // get scheduled tests / time for this user
    $db = db_connect();
    $sql = 'SELECT SUM(TIME_TO_SEC(TIMEDIFF(`time_end`,`time_start`)))/60 as runtime, COUNT(*) as test_num
            FROM `tbl_serv_tests`
            WHERE `owner_fk` = ' . $_SESSION['serv_users_key']. ' AND (`test_status` IN("planned", "preparing", "running", "cleaning up", "aborting"))' .(is_null($exclude_test) ? '' : ' AND `serv_tests_key`!='.$exclude_test);
    $res = mysqli_query($db, $sql) or flocklab_die('Cannot check user quota because: ' . mysqli_error($db));
    $row = mysqli_fetch_assoc($res);
    $test_num = $row['test_num'];
    if ($test_num==0)
        $runtime = 0;
    else
        $runtime = $row['runtime'];

    // get scheduled tests / time for this user during office hours
    $runtime_daytime = 0;
    if ($CONFIG['tests']['quota_daytime'] && ($this_runtime <= $CONFIG['tests']['quota_daytime'])) {    // only check if runtime below allowed max., longer runtimes will be shifted/blocked by schedule_test()
        if (isset($testconfig->generalConf->schedule->start)) {
            $startdt = new DateTime($testconfig->generalConf->schedule->start);
        } else {
            $startdt = new DateTime();
        }
        $startdt->setTimeZone(new DateTimeZone("UTC"));
        $this_start     = intval($startdt->format('G'));
        $this_dayofweek = intval($startdt->format('N'));
        if ($this_start >= $CONFIG['tests']['daytime_start'] && $this_start < $CONFIG['tests']['daytime_end'] && $this_dayofweek < 6) {
            // test starts during daytime (Mo-Fr)
            $runtime_daytime = $this_runtime;
            $sql = 'SELECT SUM(TIME_TO_SEC(TIMEDIFF(`time_end`,`time_start`)))/60 as runtime, COUNT(*) as test_num
            FROM `tbl_serv_tests`
            WHERE `owner_fk` = ' . $_SESSION['serv_users_key']. ' AND (`test_status` IN("planned", "preparing", "running", "cleaning up", "aborting"))' .(is_null($exclude_test)?'':' AND `serv_tests_key`!='.$exclude_test.' AND HOUR(`time_start`) > '.$CONFIG['tests']['daytime_start'].' AND HOUR(`time_start`) < '.$CONFIG['tests']['daytime_end']);
            $res = mysqli_query($db, $sql) or flocklab_die('Cannot check user quota because: ' . mysqli_error($db));
            $row = mysqli_fetch_assoc($res);
            if ($row['test_num'] != 0)
                $runtime_daytime = $runtime_daytime + $row['runtime'];
        }
    }

    // get the allowed quota
    $sql = 'SELECT `quota_runtime`, `quota_tests`
            FROM `tbl_serv_users`
            WHERE `serv_users_key` = ' . $_SESSION['serv_users_key'];
    $res = mysqli_query($db, $sql) or flocklab_die('Cannot check user quota because: ' . mysqli_error($db));
    if (mysqli_num_rows($res) == 1) {
        $row = mysqli_fetch_assoc($res);
        if ($quota != NULL) {
            $quota['available']=array('runtime'=>$row['quota_runtime'], 'num'=>$row['quota_tests']);
            $quota['needed']=array('runtime'=>round($this_runtime + $runtime,2), 'num'=>$test_num+1);
        }
        mysqli_close($db);
        return (($test_num < $row['quota_tests']) &&
                (($this_runtime + $runtime) <= $row['quota_runtime']) &&
                ($runtime_daytime <= $CONFIG['tests']['quota_daytime']));
    }
    mysqli_close($db);
    return false;
}

// remove mappings
function remove_test_mappings($testid) {
    $db  = db_connect();
    $sql = 'DELETE FROM `tbl_serv_map_test_observer_targetimages`
            USING `tbl_serv_map_test_observer_targetimages` INNER JOIN `tbl_serv_tests` ON (`tbl_serv_map_test_observer_targetimages`.`test_fk` = `tbl_serv_tests`.`serv_tests_key` )
            WHERE `serv_tests_key` = ' .mysqli_real_escape_string($db, $testid);
    mysqli_query($db, $sql) or flocklab_die('Cannot remove test mappings: ' . mysqli_error($db));
    mysqli_close($db);
}

// add mappings
function add_test_mappings($testId, $testconfig) {
    $db = db_connect();
    // create mapping entries for every target that participates in the test
    foreach($testconfig->targetConf as $tc) {
        $observerIds = preg_split("/[\s]+/", trim($tc->obsIds));
        if (isset($tc->targetIds))
            $targedIds = preg_split("/[\s]+/", trim($tc->targetIds));
        else
            $targedIds = $observerIds;
        if (isset($tc->dbImageId)) {
            $dbImageId = iterator_to_array($tc->dbImageId, false);
        }
        else
            $dbImageId = Array('null');
        for($i = 0; $i<count($observerIds);$i++) {
            $sql =  "SELECT `serv_observer_key`
                     FROM `tbl_serv_observer`
                     WHERE `observer_id` = ".$observerIds[$i];
            $res = mysqli_query($db, $sql) or flocklab_die('Cannot retrieve observer key from database because: ' . mysqli_error($db));
            $row = mysqli_fetch_assoc($res);
            $obsKey = $row['serv_observer_key'];
            foreach ($dbImageId as $img) {
                $sql =  "INSERT INTO `tbl_serv_map_test_observer_targetimages` (`observer_fk`, `test_fk`, `targetimage_fk`, `node_id`)
                         VALUES (
                        " . $obsKey. ", 
                        " . $testId . ", 
                        " . $img . ",
                        " . mysqli_real_escape_string($db, trim($targedIds[$i])).")";
                mysqli_query($db, $sql) or flocklab_die('Cannot store test configuration in database table tbl_serv_map_test_observer_targetimages because: ' . mysqli_error($db));
            }
        }
    }
    mysqli_close($db);
}

set_exception_handler('flocklab_die');
//flocklab_die
function flocklab_die($status) {
    global $LAYOUT;
    if (isset($LAYOUT))
        layout_die($status);
    else
        die($status);
}

$states = array(
    // image, short desc., long desc.
    'planned'=>array('clock.gif','Planned','Test is planned'),
    'preparing'=>array('wait_small.gif','Preparing','Test is being prepared to run'),
    'running'=>array('wait_small.gif','Running','Test is running'),
    'cleaning up'=>array('wait_small.gif','Cleaning up','Test is being cleaned up'),
    'finished'=>array('finish.png','Finished','Test has finished'),
    'not schedulable'=>array('cancel.png','Not schedulable','Test is not schedulable for some reason, it can only be deleted'),
    'failed'=>array('cancel.png','Failed','Test failed to run'),
    'aborting'=>array('cancel.png','Aborting','Test is being aborted'),
    'syncing'=>array('wait_small.gif','Syncing data','Measurement data for this test is being synchronized'),
    'synced'=>array('wait_small.gif','Synced data','Measurement data for this test has been synchronized'),
    'retention expiring'=>array('att.png','Retention expiring','Retention time almost expired. Test configuration and measurement data will be deleted automatically soon.'),
);

function state_icon($state) {
    global $states;
    $path = 'pics/icons/';
    if (array_key_exists ( $state, $states ))
        return $path.$states[$state][0];
    else
        return $path.'cancel.png';
}

function state_short_description($state) {
    global $states;
    if (array_key_exists ( $state, $states ))
        return $states[$state][1];
    else
        return 'Unknown status.';
}

function state_long_description($state) {
    global $states;
    if (array_key_exists ( $state, $states ))
        return $states[$state][2];
    else
        return 'Test is in unknown status.';
}

function date_to_tzdate($date) {
    if (is_null($date))
        return "";
    $d = new DateTime($date);
    return "<span class='time' style='display:none'>".$d->format("U")."</span>";
}

function countries() {
    $c = file('include/countries.txt');
    return array_map( 
        function($line) { return trim(preg_replace('/[A-Z]*\|/','',$line)); }, 
        $c
    ); 
}

##############################################################################
#
# get_obsids()
#    generates a string of all available observers of a platform
#
##############################################################################
function get_obsids($platform_fk) {
    $obsids = "";
    $userrole = get_user_role();
    $status = "'online'";
    if (stripos($userrole, "admin") !== false) {
        $status .= ", 'develop', 'internal'";
    } else if (stripos($userrole, "admin") !== false) {
        $status .= ", 'internal'";
    }
    $db = db_connect();
    $sql = "SELECT obs.observer_id AS obsid FROM flocklab.tbl_serv_observer AS obs
            LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS a ON obs.slot_1_tg_adapt_list_fk = a.serv_tg_adapt_list_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot1 ON a.tg_adapt_types_fk = slot1.serv_tg_adapt_types_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS b ON obs.slot_2_tg_adapt_list_fk = b.serv_tg_adapt_list_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot2 ON b.tg_adapt_types_fk = slot2.serv_tg_adapt_types_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS c ON obs.slot_3_tg_adapt_list_fk = c.serv_tg_adapt_list_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot3 ON c.tg_adapt_types_fk = slot3.serv_tg_adapt_types_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS d ON obs.slot_4_tg_adapt_list_fk = d.serv_tg_adapt_list_key
            LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot4 ON d.tg_adapt_types_fk = slot4.serv_tg_adapt_types_key
            WHERE obs.status IN ($status) AND '$platform_fk' IN (slot1.platforms_fk, slot2.platforms_fk, slot3.platforms_fk, slot4.platforms_fk)
            ORDER BY obsid;";
    $res = mysqli_query($db, $sql);
    if ($res) {
        $obsids = implode(" ", array_column(mysqli_fetch_all($res, MYSQLI_ASSOC), "obsid"));
    }
    mysqli_close($db);
    return $obsids;
}

function explodeobsids($obsids, $platform_fk=null) {
    if ($platform_fk != null) {
        // replace "ALL" with a list of available observers
        if (stripos($obsids, "ALL") !== false) {
            $obsids = str_replace("ALL", get_obsids($platform_fk), $obsids);
        }
    }
    return explode(' ', trim(preg_replace('/\s\s+/', ' ', $obsids)));
}

##############################################################################
#
# get_used_observers()
#    get a list of all currently used observers
#
##############################################################################
function get_used_observers() {
    $obsids = [];
    $now = time();
    $db  = db_connect();
    $sql = "SELECT b.`observer_id` as obsid FROM flocklab.tbl_serv_observer AS b
            LEFT JOIN flocklab.tbl_serv_resource_allocation AS a ON b.serv_observer_key = a.observer_fk
            WHERE UNIX_TIMESTAMP(a.`time_start`) < ".$now." AND UNIX_TIMESTAMP(a.`time_end`) > ".$now."
            ORDER BY obsid;";
    $res = mysqli_query($db, $sql);
    if ($res) {
        $obsids = array_unique(array_column(mysqli_fetch_all($res, MYSQLI_ASSOC), "obsid"));
    }
    mysqli_close($db);
    return $obsids;
}

##############################################################################
#
# resource_slots
#    generates a list of the slot resources
# setup of test starts at time 0
#
##############################################################################
function resource_slots($duration, $targetnodes) {
    global $CONFIG;
    $resources = Array();
    $db = db_connect();
    foreach($targetnodes as $tn) {
        $sql = "SELECT ifnull(1*(`b`.`tg_adapt_types_fk`=".$tn['platform']."),0)
                    + ifnull(2*(`c`.`tg_adapt_types_fk`=".$tn['platform']."),0)
                    + ifnull(3*(`d`.`tg_adapt_types_fk`=".$tn['platform']."),0) 
                    + ifnull(4*(`e`.`tg_adapt_types_fk`=".$tn['platform']."),0) as slot
                FROM `tbl_serv_observer` AS `a` 
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `b` ON `a`.`slot_1_tg_adapt_list_fk` = `b`.`serv_tg_adapt_list_key`
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `c` ON `a`.`slot_2_tg_adapt_list_fk` = `c`.`serv_tg_adapt_list_key`
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `d` ON `a`.`slot_3_tg_adapt_list_fk` = `d`.`serv_tg_adapt_list_key`
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `e` ON `a`.`slot_4_tg_adapt_list_fk` = `e`.`serv_tg_adapt_list_key`
                WHERE `a`.`observer_id` = " .$tn['obsid'];
        $res = mysqli_query($db, $sql);
        if (mysqli_num_rows($res) == 1) {
            $row = mysqli_fetch_assoc($res);
            array_push($resources, Array('time_start'=>0, 'time_end'=>$duration + $CONFIG['tests']['setuptime'] + $CONFIG['tests']['cleanuptime'], 'obsid'=>$tn['obsid'], 'restype'=>'slot_'.$row['slot']));
        }
    }
    mysqli_close($db);
    return $resources;
}

##############################################################################
#
# resource_freq
#    generates a list of the freq resources
# setup of test starts at time 0
#
##############################################################################
function resource_freq($duration, $targetnodes) {
    global $CONFIG;
    $db    = db_connect();
    $sql   = "SELECT serv_platforms_key, freq_2400, freq_868, freq_433 FROM `tbl_serv_platforms`";
    $res   = mysqli_query($db, $sql);
    $freqs = Array();
    while ($row = mysqli_fetch_assoc($res)) {
        $freqs[$row['serv_platforms_key']] = $row;
    }
    $resources = Array();
    foreach($targetnodes as $tn) {
        foreach(Array('freq_2400', 'freq_868', 'freq_433') as $restype) {
            if ($freqs[$tn['platform']][$restype] == 1)
                array_push($resources, Array('time_start'=>$CONFIG['tests']['setuptime'], 'time_end'=>$duration + $CONFIG['tests']['setuptime'], 'obsid'=>$tn['obsid'], 'restype'=>$restype));
        }
    }
    return $resources;
}

##############################################################################
#
# resource_multiplexer
#    generates a list of the multiplexer resources
# setup of test starts at time 0
#
##############################################################################
function resource_multiplexer($duration, $targetnodes, $xmlconfig) {
    global $CONFIG;
    $resources = Array();
    //$ignoreObs = Array();
    # get the services which use the mux for the whole test
    /*$serviceConfNames = Array('serialConf','gpioTracingConf','gpioActuationConf','powerProfilingConf');
    foreach($xmlconfig->children() as $c) {
        if (in_array($c->getName(), $serviceConfNames)) {
            if ($c->getName() == 'serialConf' && (!$c->port || $c->port == 'usb'))
                continue;
            foreach(explodeobsids($c->obsIds) as $obsid) {
                if (! in_array($obsid, $ignoreObs)) {
                    array_push($resources, Array('time_start'=>0, 'time_end'=>$duration + $CONFIG['tests']['setuptime'] + $CONFIG['tests']['cleanuptime'], 'obsid'=>(int)$obsid, 'restype'=>'mux'));
                    array_push($ignoreObs, $obsid);
                }
            }
        }
    }*/

    foreach($targetnodes as $tn) {
        //if (! in_array($tn['obsid'], $ignoreObs)) {
            if ($duration > ($CONFIG['tests']['setuptime'] + $CONFIG['tests']['cleanuptime'])) {
                array_push($resources, Array('time_start'=>0, 'time_end'=>($CONFIG['tests']['setuptime'] + $CONFIG['tests']['setuptime']), 'obsid'=>$tn['obsid'], 'restype'=>'mux'));
                array_push($resources, Array('time_start'=>($CONFIG['tests']['setuptime'] -  $CONFIG['tests']['cleanuptime']) + $duration, 'time_end'=>$duration + ($CONFIG['tests']['setuptime'] + $CONFIG['tests']['cleanuptime']), 'obsid'=>$tn['obsid'], 'restype'=>'mux'));
            }
            else {
                array_push($resources, Array('time_start'=>0, 'time_end'=>$duration + ($CONFIG['tests']['setuptime'] + $CONFIG['tests']['cleanuptime']), 'obsid'=>$tn['obsid'], 'restype'=>'mux'));
            }
        //}
    }
    return $resources;
}

##############################################################################
#
# resource_cleanup
#    generates a list of cleanup resources (slot + multiplexer) for scheduled abort of test
#
##############################################################################
function resource_cleanup($targetnodes) {
    global $CONFIG;
    $resources = Array();
    $db = db_connect();
    foreach($targetnodes as $tn) {
        $sql = "SELECT ifnull(1*(`b`.`tg_adapt_types_fk`=".$tn['platform']."),0)
                    + ifnull(2*(`c`.`tg_adapt_types_fk`=".$tn['platform']."),0)
                    + ifnull(3*(`d`.`tg_adapt_types_fk`=".$tn['platform']."),0) 
                    + ifnull(4*(`e`.`tg_adapt_types_fk`=".$tn['platform']."),0) as slot
                FROM `tbl_serv_observer` AS `a` 
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `b` ON `a`.`slot_1_tg_adapt_list_fk` = `b`.`serv_tg_adapt_list_key`
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `c` ON `a`.`slot_2_tg_adapt_list_fk` = `c`.`serv_tg_adapt_list_key`
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `d` ON `a`.`slot_3_tg_adapt_list_fk` = `d`.`serv_tg_adapt_list_key`
                LEFT JOIN `tbl_serv_tg_adapt_list` AS `e` ON `a`.`slot_4_tg_adapt_list_fk` = `e`.`serv_tg_adapt_list_key`
                WHERE `a`.`observer_id` = " .$tn['obsid'];
        $res = mysqli_query($db, $sql);
        if (mysqli_num_rows($res) == 1) {
            $row = mysqli_fetch_assoc($res);
            array_push($resources, Array('time_start'=>0, 'time_end'=>$CONFIG['tests']['cleanuptime'], 'obsid'=>$tn['obsid'], 'restype'=>'slot_'.$row['slot']));
            array_push($resources, Array('time_start'=>0, 'time_end'=>$CONFIG['tests']['cleanuptime'], 'obsid'=>$tn['obsid'], 'restype'=>'mux'));
        }
    }
    mysqli_close($db);
    return $resources;
}

##############################################################################
#
# schedule_test
#
# returns associative array:
#    'feasible' => True / False
#    'start_time' => DateTime    time start wish
#    'end_time' => DateTime        time end wish
#
# if test is ASAP, the next possible start time is reported
##############################################################################
function schedule_test($testconfig, $resources, $exclude_test = NULL) {
    global $CONFIG;
    $db                   = db_connect();
    $guard_setup_sec      = $CONFIG['tests']['setuptime'];
    $guard_cleanup_sec    = $CONFIG['tests']['cleanuptime'];
    $allow_parallel_tests = $CONFIG['tests']['allowparalleltests'];
    $is_asap              = !isset($testconfig->generalConf->schedule->start);
    $duration             = $testconfig->generalConf->schedule->duration;
    // start is time start wish - setup time
    // end is time end wish + cleanup time
    if (!$is_asap) {
        $start = new DateTime($testconfig->generalConf->schedule->start);
        $start->setTimeZone(new DateTimeZone("UTC"));
        $end   = clone $start;
        $start->modify('-'.$guard_setup_sec.' seconds');
        $end->modify('+'.($duration + $guard_cleanup_sec).' seconds');
    }
    else {
        $start = new DateTime(); // now
        $start->setTimeZone(new DateTimeZone("UTC"));
        $end   = clone $start;
        $end->modify('+'.$testconfig->generalConf->schedule->duration.' seconds');
        $end->modify('+'.($guard_setup_sec + $guard_cleanup_sec).' seconds');
    }
    $resourcesdict = Array();
    foreach($resources as $r) {
        if (!isset($resourcesdict[$r['obskey']][$r['restype']]))
            $resourcesdict[$r['obskey']][$r['restype']] = Array();
        array_push($resourcesdict[$r['obskey']][$r['restype']], $r);
    }

    $sql = "SELECT UNIX_TIMESTAMP(a.`time_start`) as `utime_start`, UNIX_TIMESTAMP(a.`time_end`) as `utime_end`, a.`observer_fk`, a.`resource_type`
            FROM `tbl_serv_resource_allocation` a LEFT JOIN tbl_serv_tests b on (b.serv_tests_key = a.test_fk)
            WHERE (a.time_end >= '".$start->format(DATE_ISO8601)."' AND b.test_status in ('planned','preparing','running','cleaning up','syncing','synced','aborting')".(isset($exclude_test) ? " AND `test_fk`!=".$exclude_test : "").")";
    $res_usedresources = mysqli_query($db, $sql);
    $sql = "SELECT UNIX_TIMESTAMP(`time_start`) as `utime_start`, UNIX_TIMESTAMP(`time_end`) as `utime_end`, max(ifnull(user_fk,-1) = ".$_SESSION['serv_users_key'].") as `reservation_match`
            FROM `tbl_serv_reservations` LEFT JOIN `tbl_serv_user_groups` ON `group_fk`=`group_id_fk`
            WHERE `time_end` >= '".$start->format(DATE_ISO8601)."'
            GROUP BY `serv_reservation_key` HAVING `reservation_match` = 0";
    $res_reservations = mysqli_query($db, $sql);

    # Now check for all resource usage intervals if they overlap in time with an already scheduled test or reservations
    $shiftOffset = $start->format("U");
    $testShift   = $start->format("U");
    while (True) {
        $maxShift = 0; # keep track of largest shift needed (in seconds) to resolve dependencies

        # check for max allowed runtime during daytime
        if ($CONFIG['tests']['quota_daytime'] && ($duration > ($CONFIG['tests']['quota_daytime'] * 60))) {
            #$newStart     = clone $start;
            $newStart     = new DateTime();
            $newStart->setTimestamp($testShift);
            #$newStart->modify('+'.($testShift - $shiftOffset).' seconds');
            $newStartHour = intval($newStart->format('G'));
            $newStartMin  = intval($newStart->format('i'));
            $newStartDoW  = intval($newStart->format('N'));
            if (($newStartHour >= $CONFIG['tests']['daytime_start']) && ($newStartHour < $CONFIG['tests']['daytime_end']) && ($newStartDoW < 6)) {
                if (!$is_asap) {
                    return Array('feasible'=>False, 'start_time'=>$start, 'end_time'=>$end);
                }
                else {
                    # move to evening hours
                    $maxShift = ($CONFIG['tests']['daytime_end'] - $newStartHour - 1) * 3600 + (60 - $newStartMin) * 60;
                }
            }
        }
        if (mysqli_num_rows($res_reservations) > 0) {
            mysqli_data_seek($res_reservations, 0);
            $ustart = $testShift;
            $uend   = $end->format("U") + $testShift - $shiftOffset;
            while ($row = mysqli_fetch_assoc($res_reservations)) {
                # for every ret, check for collisions
                if ($row['utime_start'] <= $uend and $row['utime_end'] >= $ustart) {
                    if (!$is_asap)
                        return Array('feasible'=>False, 'start_time'=>$start, 'end_time'=>$end);
                    else {
                        $shift = $row['utime_end'] - $ustart;
                        if ($shift > $maxShift)
                            $maxShift = $shift;
                    }
                }
            }
        }
        if (mysqli_num_rows($res_usedresources) > 0) {
            mysqli_data_seek($res_usedresources, 0);
            while ($row = mysqli_fetch_assoc($res_usedresources)) {
                if (!$allow_parallel_tests) {
                    # if observer is used, then treat it as a collision (parallel tests on same observer cause problems)
                    if (isset($resourcesdict[$row['observer_fk']])) {
                        # observer is used by the new test, check the start and end times
                        $ustart = $testShift;
                        $uend   = $end->format("U") + $testShift - $shiftOffset;
                        if ($row['utime_start'] <= $uend and $row['utime_end'] >= $ustart) {
                            if (!$is_asap)
                                return Array('feasible'=>False, 'start_time'=>$start, 'end_time'=>$end);
                            else {
                                $shift = $row['utime_end'] - $ustart;
                                if ($shift > $maxShift)
                                    $maxShift = $shift;
                            }
                        }
                    }
                } else {
                    # for every ret, check for collisions
                    if (isset($resourcesdict[$row['observer_fk']]) && isset($resourcesdict[$row['observer_fk']][$row['resource_type']])) {
                        foreach ($resourcesdict[$row['observer_fk']][$row['resource_type']] as $r) {
                            //echo "<!--";print_r($row);echo "-->";
                            if ($row['utime_start'] <= $r['time_end'] + $testShift and $row['utime_end'] >= $r['time_start'] + $testShift) {
                                if (!$is_asap)
                                    return Array('feasible'=>False, 'start_time'=>$start, 'end_time'=>$end);
                                else {
                                    $shift = $row['utime_end'] - ($r['time_start'] + $testShift);
                                    if ($shift > $maxShift)
                                        $maxShift = $shift;
                                }
                            }
                        }
                    }
                }
            }
        }
        if ($maxShift > 0)
            $testShift = $testShift + $maxShift + 1; # shift by maxShift and repeat
        else
            break; # we found a valid schedule
    }
    mysqli_close($db);
    $start->modify('+'.($testShift - $shiftOffset).' seconds');
    $end->modify('+'.($testShift - $shiftOffset).' seconds');
    $start->modify('+'.$guard_setup_sec.' seconds');
    $end->modify('-'.$guard_cleanup_sec.' seconds');
    return Array('feasible'=>True, 'start_time'=>$start, 'end_time'=>$end);
}

function adjust_schedule_tag(&$testconfig) {
    // modify test description
    $start    = 0;
    $duration = 0;
    if (isset($testconfig->generalConf->schedule)) {
        if (isset($testconfig->generalConf->schedule->start)) {
            $start = $testconfig->generalConf->schedule->start;
            if (intval($start) > time()) {
                // treat as UNIX timestamp
                $start_conv = new DateTime("@$start");
                unset($testconfig->generalConf->schedule->start);
                $testconfig->generalConf->schedule->addChild('start', $start_conv->format(DATE_W3C));
            }
        }
        return;
    }
    if (isset($testconfig->generalConf->scheduleAbsolute)) {
        $start = new DateTime($testconfig->generalConf->scheduleAbsolute->start);
        $end = new DateTime($testconfig->generalConf->scheduleAbsolute->end);
        $start->setTimeZone(new DateTimeZone("UTC"));
        $end->setTimeZone(new DateTimeZone("UTC"));
        $duration = $end->getTimestamp() - $start->getTimestamp();
        unset($testconfig->generalConf->scheduleAbsolute);
    } else if (isset($testconfig->generalConf->scheduleAsap)) {
        $duration = clone $testconfig->generalConf->scheduleAsap->durationSecs;
        unset($testconfig->generalConf->scheduleAsap);
    }
    $email = clone $testconfig->generalConf->emailResults;
    unset($testconfig->generalConf->emailResults);
    $testconfig->generalConf->addChild('schedule');
    if ($start > 0) {
        $testconfig->generalConf->schedule->addChild('start', $start->format(DATE_W3C));
    }
    $testconfig->generalConf->schedule->addChild('duration', $duration);
    if ($email != '') {
        $testconfig->generalConf->addChild('emailResults', $email);
    }
}

// add resource allocations to db
function add_resource_allocation($testId, $resources, $starttime) {
    global $CONFIG;
    $db = db_connect();
    $starttime->modify('-'.$CONFIG['tests']['setuptime'].' seconds');
    foreach($resources as $r) {
        $start = clone $starttime;
        $end = clone $starttime;
        $start->modify('+'.$r['time_start'].' seconds');
        $end->modify('+'.$r['time_end'].' seconds');
        $sql = "INSERT INTO `tbl_serv_resource_allocation` (`time_start`, `time_end`, `test_fk`, `observer_fk`, `resource_type`)
                VALUES (
                '" . $start->format(DATE_ISO8601). "', 
                '" . $end->format(DATE_ISO8601) . "', 
                " . $testId . ",
                " . $r['obskey'] . ",
                '" .$r['restype']."')";
        mysqli_query($db, $sql) or flocklab_die('Cannot store test configuration in database table tbl_serv_resource_allocation because: ' . mysqli_error($db) . '\r\nSQL: ' . $sql);
    }
    mysqli_close($db);
}

##############################################################################
#
# update_add_test
# if $existing_test_id is specified, the test is updated, otherwise newly created
#    
# to abort a test ($abort = True), we schedule a cleanup slot asap
# 
# returns array of error messages, empty array if successful
#
##############################################################################
function update_add_test($xml_config, &$errors, $existing_test_id = NULL, $abort=False) {
    global $CONFIG;
    if (!$abort) {
        $tmp_xmlfile = tempnam(sys_get_temp_dir(), 'flocklab');
        file_put_contents($tmp_xmlfile, $xml_config);
        $valid = validate_test($tmp_xmlfile, $errors);
        unlink($tmp_xmlfile);
    }
    else {
        $valid = True;
    }
    if ($valid) {
        $testconfig = new SimpleXMLElement($xml_config);
        // check if client IP is IPv4
        if (preg_match('/((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])/', $_SERVER['REMOTE_ADDR'])) {
            // If no IP address is given for serial service, use the one from which the test was uploaded:
            foreach ($testconfig->serialConf as $sc) {
                if (isset($sc->remoteIp) && trim($sc->remoteIp) == "") {
                    $sc->remoteIp = $_SERVER['REMOTE_ADDR'];
                }
            }
            // If no IP address is given for debug service, use the one from which the test was uploaded:
            /*foreach ($testconfig->debugConf as $sc) {
                if (isset($sc->remoteIp) && trim($sc->remoteIp) == "") {
                    $sc->addChild('remoteIp', $_SERVER['REMOTE_ADDR']);
                }
            }*/
        }
        adjust_schedule_tag($testconfig);

        // extract embedded images
        $used_embeddedImages = Array();
        $used_dbImages = Array();
        $embeddedImages = Array();
        $dbImages = Array();
        $available_platforms = get_available_platforms();
        $targetnodes = Array();
        foreach($testconfig->targetConf as $tc) {
            foreach($tc->embeddedImageId as $eId) {
                $eId = trim($eId);
                if (!in_array($eId, $used_embeddedImages))
                    array_push($used_embeddedImages, $eId);
            }
            foreach($tc->dbImageId as $dbId) {
                $dbId = (int)trim($dbId);
                if (!in_array($dbId, $used_dbImages))
                    array_push($used_dbImages, $dbId);
            }
        }
        if (count($used_dbImages) > 0) {
            $db = db_connect();
            $sql = "select `serv_targetimages_key`, `platforms_fk` from tbl_serv_targetimages where `serv_targetimages_key` in (".join(',',$used_dbImages).")";
            $res = mysqli_query($db, $sql) or flocklab_die('Cannot fetch platform information from database because: ' . mysqli_error($db));
            while ($row = mysqli_fetch_assoc($res))
                $dbImages[$row['serv_targetimages_key']] = Array('platform' => $row['platforms_fk']);
            mysqli_close($db);
        }
        foreach($testconfig->embeddedImageConf as $im) {
            $eId = trim($im->embeddedImageId);
            if (array_key_exists($eId, $embeddedImages)) {
                array_push($errors, "Provided embedded images do not have unique IDs.");
            }
            else {
                $im_cpy = Array();
                $im_cpy['data'] = base64_decode($im->data);
                $im_cpy['embeddedImageId'] = $eId;
                $im_cpy['name'] = $im->name;
                $im_cpy['description'] = $im->description;
                $im_cpy['used'] = in_array($eId, $used_embeddedImages);
                foreach($available_platforms as $key => $platform)
                    if (strcasecmp($platform[0]['name'], trim($im->platform)) == 0)
                        $im_cpy['platform'] = $key;
                $im_cpy['core'] = isset($im->core) ? $im->core : 0;
                $embeddedImages[$eId] = $im_cpy;
            }
        }
        // check if there are images without a data block:
        foreach(array_keys($embeddedImages) as $imID) {
            if (strlen($embeddedImages[$imID]['data']) == 0) {
                // find the first entry which matches the platform (compare only first 3 characters)
                foreach($embeddedImages as $eIm) {
                    if (strncmp($eIm['platform'], $embeddedImages[$imID]['platform'], 3) && strlen($eIm['data']) > 0) {
                        $embeddedImages[$imID]['data'] = $eIm['data'];  // use the image data of this entry
                        break;
                    }
                }
                if (strlen($embeddedImages[$imID]['data']) == 0) {
                    // no image data found -> abort
                    array_push($errors, "No data provided for embedded image ID ".$imID.".");
                    break;
                }
            }
        }
        foreach($used_embeddedImages as $imId)
            if (!array_key_exists($imId, $embeddedImages))
                array_push($errors, "Missing embedded image (ID ".$imId.")");
        if (empty($errors)) {
            // check quota
            if (!check_quota($testconfig, $existing_test_id))
                array_push($errors, "Not enough quota left to run this test.");
            else {
                # parallel stuff
                # 1. calculate required resources:
                foreach($testconfig->targetConf as $tc) {
                    if (count($tc->embeddedImageId)>0) {
                        $eId  = trim($tc->embeddedImageId[0]);
                        $pkey = $embeddedImages[$eId]['platform'];
                    } else if (count($tc->dbImageId)>0) {
                        $dbId = (int)trim($tc->dbImageId[0]);
                        $pkey = $dbImages[$dbId]['platform'];
                    }
                    foreach (explodeobsids($tc->obsIds, $pkey) as $obsid) {
                        array_push($targetnodes, Array('obsid' => (int)$obsid, 'platform' => $pkey));
                    }
                }
                $duration = $testconfig->generalConf->schedule->duration;
                # 1a. slots
                $resources = Array();
                if ($abort === True) {
                    $resources = array_merge($resources, resource_cleanup($targetnodes));
                    if (isset($testconfig->generalConf->schedule->start)) {
                        unset($testconfig->generalConf->schedule);
                        $testconfig->generalConf->addChild('schedule');
                        $testconfig->generalConf->schedule->addChild('duration', -1 * $CONFIG['tests']['setuptime']); // no setup time, only cleanup
                    }
                }
                else {
                    $resources = array_merge($resources, resource_slots($duration, $targetnodes));
                    # 1b. freq
                    $resources = array_merge($resources, resource_freq($duration, $targetnodes));
                    # 1c. multiplexer
                    $resources = array_merge($resources, resource_multiplexer($duration, $targetnodes, $testconfig));
                }
                #flocklab_log('Try to schedule test. Needed resources are: '. print_r($resources, $return = True));
                # fetch observer keys
                $db      = db_connect();
                $obskeys = Array();
                $sql     = "SELECT `serv_observer_key`, `observer_id` FROM tbl_serv_observer";
                $res     = mysqli_query($db, $sql) or flocklab_die('Cannot fetch observer information from database because: ' . mysqli_error($db));
                while ($row = mysqli_fetch_assoc($res)) {
                    $obskeys[$row['observer_id']] = $row['serv_observer_key'];
                }
                foreach ($resources as $i => $r) {
                    $resources[$i]['obskey'] = $obskeys[$r['obsid']];
                }
                $locktime = microtime(true);
                acquire_db_lock('resource_allocation');
                $r = schedule_test($testconfig, $resources, $existing_test_id);
                if ($abort) { // update test to abort
                    $db  = db_connect();
                    // only schedule abort procedure if test has been started and not yet finished
                    $sql = "SELECT `test_status` FROM tbl_serv_tests WHERE `serv_tests_key`=".$existing_test_id." AND `test_status` IN ('running', 'preparing')";
                    $res = mysqli_query($db, $sql);
                    if (mysqli_num_rows($res)) {
                        // remove resource allocations
                        $sql = 'DELETE from tbl_serv_resource_allocation WHERE `test_fk` = ' .$existing_test_id;
                        mysqli_query($db, $sql) or flocklab_die('Cannot abort test: ' . mysqli_error($db));
                        // update test entry
                        $end = $r['end_time'];
                        $sql = 'UPDATE `tbl_serv_tests` SET `time_end`="' . mysqli_real_escape_string($db, $end->format(DATE_ISO8601)) . '", `test_status`="aborting"
                                WHERE `serv_tests_key`='.$existing_test_id;
                        mysqli_query($db, $sql) or flocklab_die('Cannot remove resource allocation from database: ' . mysqli_error($db));
                        $testId = $existing_test_id;
                        mysqli_close($db);
                        add_resource_allocation($testId, $resources, $r['start_time']);
                    }
                }
                else {
                    if (!$r['feasible'])
                        array_push($errors, "The selected time slot is not available.");
                    else {
                        if (!isset($testconfig->generalConf->schedule->start)) {
                            // convert from ASAP to absoulte
                            $testconfig->generalConf->schedule->addChild('start', $r['start_time']->format(DATE_W3C));
                        }
                        // strip all embedded images from xml config
                        // add embedded images to db
                        $comment = '';
                        while (count($testconfig->embeddedImageConf) > 0) {
                            $imgEId = trim($testconfig->embeddedImageConf[0]->embeddedImageId);
                            if ($embeddedImages[$imgEId]['used']) {
                                $imgId = check_image_duplicate($embeddedImages[$imgEId]);
                                if ($imgId === false) {
                                    $imgId = store_image($embeddedImages[$imgEId]);
                                    $comment.="<!-- saved embedded image '".$imgEId."' to database (ID: ".$imgId.")-->\n";
                                }
                                else {
                                    $comment.="<!-- reusing existing image from database (ID: ".$imgId.") for '".$imgEId."' -->\n";
                                }
                                $embeddedImages[$imgEId]['dbimgid'] = $imgId;
                            }
                            else {
                                // just strip it
                                unset($embeddedImages[$imgEId]);
                                $comment.="<!-- stripped embedded image '".$imgEId."', image is not used in this test -->\n";
                            }
                            unset($testconfig->embeddedImageConf[0]);
                        }
                        $xml_config = $testconfig->asXML();
                        // add newline
                        $xml_config = str_replace("><", ">\n    <", $xml_config);
                        $xml_config = preg_replace('#</testConf>#s', $comment.'</testConf>', $xml_config);
                        foreach ($embeddedImages as $im) {
                            // replace embedded image id with db id
                            $xml_config = preg_replace('#(<)embedded(ImageId\s*[^>]*>)\s*'.$im['embeddedImageId'].'\s*(</)embedded(ImageId\s*>)#s', '${1}db${2}'.$im['dbimgid'].'${3}db${4}', $xml_config);
                        }
                        // replace list of observer IDs
                        $xml_config = preg_replace('#<obsIds>[^<]*ALL[^<]*</obsIds>#si', '<obsIds>'.implode(" ", array_column($targetnodes, "obsid")).'</obsIds>', $xml_config);
                        // add test to db
                        $start = new DateTime($testconfig->generalConf->schedule->start);
                        $start->setTimeZone(new DateTimeZone("UTC"));
                        $end = clone $start;
                        $end->modify('+'.$testconfig->generalConf->schedule->duration.' seconds');
                        if (isset($existing_test_id)) { // update test
                            // remove mappings and resource allocations
                            remove_test_mappings($existing_test_id);
                            $db  = db_connect();
                            $sql =  'DELETE from tbl_serv_resource_allocation WHERE `test_fk` = ' .$existing_test_id;
                            mysqli_query($db, $sql) or flocklab_die('Cannot modify test: ' . mysqli_error($db));
                            // update test entry
                            $sql =  'UPDATE `tbl_serv_tests` SET
                                     `title`="'.mysqli_real_escape_string($db, trim($testconfig->generalConf->name)).'",
                                     `description`="'.mysqli_real_escape_string($db, trim($testconfig->generalConf->description)).'",
                                     `testconfig_xml`="'.mysqli_real_escape_string($db, trim($xml_config)).'",
                                     `time_start`="'.mysqli_real_escape_string($db, $start->format(DATE_ISO8601)) .'",
                                     `time_end`="'.mysqli_real_escape_string($db, $end->format(DATE_ISO8601)).'",
                                     `test_status`="planned"
                                     WHERE `serv_tests_key`='.$existing_test_id;
                            mysqli_query($db, $sql) or flocklab_die('Cannot store test configuration in database table tbl_serv_tests because: ' . mysqli_error($db));
                            $testId = $existing_test_id;
                            mysqli_close($db);
                        }
                        else {
                            // add test entry
                            $db  = db_connect();
                            $sql =  "INSERT INTO `tbl_serv_tests` (`title`, `description`, `owner_fk`, `testconfig_xml`, `time_start`, `time_end`, `test_status`)
                                     VALUES (
                                     '" . mysqli_real_escape_string($db, trim($testconfig->generalConf->name)) . "', 
                                     '" . mysqli_real_escape_string($db, trim($testconfig->generalConf->description)) . "', 
                                     '" . mysqli_real_escape_string($db, $_SESSION['serv_users_key']) . "',
                                     '" . mysqli_real_escape_string($db, trim($xml_config)) . "',
                                     '" . mysqli_real_escape_string($db, $start->format(DATE_ISO8601)) . "',
                                     '" . mysqli_real_escape_string($db, $end->format(DATE_ISO8601)) . "',
                                     'planned')";
                            mysqli_query($db, $sql) or flocklab_die('Cannot store test configuration in database table tbl_serv_tests (2) because: ' . mysqli_error($db));
                            $testId = mysqli_insert_id($db);
                            mysqli_close($db);
                        }
                        // create mapping entries for every target that participates in the test
                        add_resource_allocation($testId, $resources, $r['start_time']);
                        $testconfig = new SimpleXMLElement($xml_config);
                        add_test_mappings($testId, $testconfig);
                    }
                }
                release_db_lock('resource_allocation');
                flocklab_log('Schedule for test id '.$testId.' is: '. print_r($r, $return = True));
                $time_elapsed_secs = microtime(true) - $locktime;
                echo "<!-- db lock time was ".$time_elapsed_secs." s -->";
                // Ask the FlockLab scheduler to check for work:
                trigger_scheduler(true);
            }
        }
    }
    else
        unlink($tmp_xmlfile);
    if (!empty($errors))
        return Array('testId'=>Null, 'start'=>Null);
    else
        return Array('testId'=>$testId, 'start'=>$start);
}

/*
##############################################################################
#
# acquire_db_lock
# 
# try to get db lock on the specified key
# this is a blocking operation.
#
##############################################################################
*/
function acquire_db_lock($key) {
    $db = db_connect();
    $done = False;
    while (!$done) {
        $sql = "lock tables tbl_serv_locks write";
        mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
        $sql = "delete from tbl_serv_locks where expiry_time < now()";
        mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
        $sql = "select * from tbl_serv_locks where name='".$key."' limit 1";
        $res = mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
        if (mysqli_num_rows($res) == 0) {
            $sql = "insert into tbl_serv_locks (name, expiry_time) values ('".$key."', ADDTIME(now(),1))";
            mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
            $done = True;
        }
        $sql = "unlock tables";
        mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
        if (!$done)
            usleep(250000);
    }
    mysqli_close($db);
}

/*
##############################################################################
#
# release_db_lock
# 
# release the lock in the specified key
#
##############################################################################
*/
function release_db_lock($key) {
    $db = db_connect();
    $sql = "lock tables tbl_serv_locks write";
    mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
    $sql = "delete from tbl_serv_locks where name = '".$key."'";
    mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
    $sql = "unlock tables";
    mysqli_query($db, $sql) or flocklab_die('Cannot acquire database lock because: ' . mysqli_error($db));
    mysqli_close($db);
}


?>
