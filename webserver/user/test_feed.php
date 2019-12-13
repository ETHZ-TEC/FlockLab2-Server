<?php 
    /*
     * __author__      = "Roman Lim <lim@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Roman Lim"
     * __license__     = "GPL"
     * __version__     = "$Revision$"
     * __date__        = "$Date$"
     * __id__          = "$Id$"
     * __source__      = "$URL$" 
     */

    require_once('include/auth.php'); 
    
    //debug();
    if ((!isset($_GET['testid']) || !is_numeric($_GET['testid'])) && (!isset($_GET['updatesince']) || !is_numeric($_GET['updatesince']))) {
        return;
    }
    // Connect to database and get the corresponding test info:
    $db = db_connect();
    $sql =    "SELECT serv_tests_key as testid, title, description, time_start_act, time_start_wish, time_end_act, time_end_wish, test_status 
        FROM tbl_serv_tests 
        WHERE owner_fk = " . $_SESSION['serv_users_key'] . " AND test_status <> 'deleted' AND test_status <> 'todelete' AND ".(isset($_GET['testid'])?"serv_tests_key = ".$_GET['testid']:"last_changed >= '".date( 'Y-m-d H:i:s T', $_GET['updatesince'])."'");
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get test data from database because: ' . mysqli_error($db));
    mysqli_close($db);

    $all = array();
    while ($row = mysqli_fetch_array($rs, MYSQLI_ASSOC)) {
        $all[]=$row;
    }
    // JSON-encode test info
    echo json_encode($all);
?>
