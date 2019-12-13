<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision$"
     * __date__        = "$Date$"
     * __id__          = "$Id$"
     * __source__      = "$URL$" 
     */

    require_once('include/auth.php'); 
    
    //debug();
    
    
    // Connect to database and get all currently active status messages:
    $db = db_connect();
    $sql =    "SELECT * 
        FROM `flocklab`.`tbl_serv_web_status` 
        WHERE 
            (`show` = 1) AND
            ((UTC_TIMESTAMP() > `time_start`) OR (`time_start` IS NULL)) AND
            ((UTC_TIMESTAMP() < `time_end`) OR (`time_end` IS NULL))
        ORDER BY `time_start` ASC, `time_end` ASC
        ";
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get status messages from database because: ' . mysqli_error($db));
    mysqli_close($db);
    
    // Build the array of events. If possible, append start and/or end time to the message:
    $events = array();
    while ($row = mysqli_fetch_array($rs)) {
        $msg = "<i>";
        if ($row['time_start'] != "") {
            $d = new DateTime($row['time_start']);
            $msg = sprintf('%sFrom <div class="time" style="display:inline">%s</div> ', $msg, $d->format('U'));
        }
        if ($row['time_end'] != "") {
            $d = new DateTime($row['time_end']);
            if (strlen($msg) == 3) {
                $msg = $msg . "Until";
            } else {
                $msg = $msg . "until";
            }
            $msg = sprintf('%s <div class="time" style="display:inline">%s</div>', $msg, $d->format('U'));
        }
        if (strlen($msg) > 3) {
            $msg = $msg . ": ";
        }
        $msg = $msg . '</i>';
        if ($row['title'] != "") {
            $msg = $msg . '<b>' . $row['title'] . '</b>: ';
        }
        $msg = $msg . $row['message'];
        $events[] =  $msg;
    }

    // JSON-encode the array and return it to the calendar:
    echo json_encode($events);

?>
