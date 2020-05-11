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
