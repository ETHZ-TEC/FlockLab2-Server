<?php
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2012, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision$"
     * __date__        = "$Date$"
     * __id__          = "$Id$"
     * __source__      = "$URL$" 
     */

    require_once('include/libflocklab.php'); 
    if (!isset($_SERVER['PHP_AUTH_USER'])) {
        header('WWW-Authenticate: Basic realm="Flocklab"');
        header('HTTP/1.0 401 Unauthorized');
        echo "wrong username  / password.\n";
        exit();
    } else {
        if (!do_login($_SERVER['PHP_AUTH_USER'], $_SERVER['PHP_AUTH_PW']))
            exit();
    }
    require_once('include/iCalcreator.class.php');

    //debug();

    // Set timezone to UTC:
    date_default_timezone_set('UTC');

    // Connect to database and get the corresponding events:
    $db = db_connect();
    // Only get data for the last 30 days:
    $sql =    "SELECT serv_tests_key, title, left(description, 100) as description, ADDTIME(`a`.time_start_wish, '-00:05:00') AS time_start_w_offset, ADDTIME(`a`.time_end_wish, '00:05:00') AS time_end_w_offset,
        `b`.username
        FROM `tbl_serv_tests` AS `a`
        LEFT JOIN `tbl_serv_users` AS `b` ON `a`.owner_fk = `b`.serv_users_key
        WHERE `a`.test_status <> 'not schedulable' AND `a`.test_status <> 'deleted' AND `a`.test_status <> 'todelete' AND (`a`.time_end_wish >= ADDTIME(NOW(), '-30 0:0:0.0'))
        ORDER by `a`.time_start_wish ASC LIMIT 1000";

    $rs = mysqli_query($db, $sql) or die("Unknown error occurred.");
    mysqli_close($db);
    
    $config = array( "unique_id" => "flocklab.ethz.ch" );
    $vcalendar = new vcalendar( $config );
    
    // Build the events:
    while ($row = mysqli_fetch_array($rs)) {
        $start = date_parse($row['time_start_w_offset']);
        $end = date_parse($row['time_end_w_offset']);
        $vevent = & $vcalendar->newComponent( "vevent" );
        $vevent->setProperty( "dtstart", $start['year'], $start['month'], $start['day'], $start['hour'], $start['minute'], $start['second']);
        $vevent->setProperty( "dtend", $end['year'], $end['month'], $end['day'], $end['hour'], $end['minute'], $end['second']);
        if ($_SESSION['is_admin']) {
            $vevent->setProperty( "description", $row['description']);
            $vevent->setProperty( "summary", "FlockLab (".$row['serv_tests_key'].") [".$row['username']."]: ".$row['title']);
        }
        else if (strcmp($row['username'],$_SESSION['username'])==0) {
            $vevent->setProperty( "description", $row['description']);
            $vevent->setProperty( "summary", "FlockLab (".$row['serv_tests_key']."): ".$row['title']);
        }
        else {
            $vevent->setProperty( "description", "Flocklab is occupied.");
            $vevent->setProperty( "summary", "FlockLab is occupied.");
        }
    }

    $vcalendar->returnCalendar();
?>
