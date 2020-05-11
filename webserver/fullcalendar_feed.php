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
    ob_start("ob_gzhandler");
    //debug();
    // Transform request parameters to MySQL datetime format.
    $mysqlstart = date( 'Y-m-d H:i:s T', $_GET['start']);
    $mysqlend = date('Y-m-d H:i:s T', $_GET['end']);
    $mini = isset($_GET['mini']) && $_GET['mini']==TRUE;
    
    // Connect to database and get the corresponding events:
    $guard_setup_sec = $CONFIG['tests']['setuptime'];
    $guard_cleanup_sec = $CONFIG['tests']['cleanuptime'];
    $db = db_connect();
    // planned tests
    $sql = "SELECT `a`.serv_tests_key, `a`.title, `a`.description, `a`.time_start_wish, `a`.time_end_wish, `a`.owner_fk,
                   `b`.username, `b`.firstname, `b`.lastname, `a`.time_start_act, `a`.time_end_act, `a`.test_status,
                   DATE_ADD(`a`.time_start_wish, INTERVAL -".$guard_setup_sec." SECOND) as time_start_offset,
                   DATE_ADD(`a`.time_end_wish, INTERVAL ".$guard_cleanup_sec." SECOND) as time_end_offset
            FROM `tbl_serv_tests` AS `a`
            LEFT JOIN `tbl_serv_users` AS `b` ON `a`.owner_fk = `b`.serv_users_key
            WHERE (`a`.test_status NOT IN ('not schedulable', 'todelete', 'deleted') OR (`a`.test_status_preserved IS NOT NULL AND `a`.test_status_preserved IN ('finished','failed'))) 
              AND ( (`a`.time_start_wish BETWEEN '" . $mysqlstart . "' AND '" . $mysqlend . "') OR (`a`.time_end_wish BETWEEN '" . $mysqlstart . "' AND '" . $mysqlend . "') )
            ORDER BY `a`.time_start_wish";
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get calendar data from database because: ' . mysqli_error($db));
    
    // Build the array of events:
    $events = array();
    while ($row = mysqli_fetch_array($rs)) {
        // Create the event depending on the owner: if it is an event which belongs to the logged-in user, show more info and color it differently.
        if ($row['owner_fk'] == $_SESSION['serv_users_key']) {
            if ($row['test_status'] == 'failed' || $row['test_status'] == 'finished' || $row['test_status'] == 'retention expiring' || $row['test_status'] == 'deleted' || $row['test_status'] == 'todelete' ) {
                $events[] = array(
                    'id'          => $row['serv_tests_key'],
                    'title'       => 'Test ' . $row['serv_tests_key'] . ': ' . $row['title'],
                    'description' => $mini?'':'Test-ID: ' . $row['serv_tests_key'] . '<br/>Duration: '.date("H:i", strtotime($row['time_start_act'])).' - '.date("H:i", strtotime($row['time_end_act'])).'<br/>Title: ' . $row['title'] . '<br/> Description: ' . $row['description'].'<br />Status: '.$row['test_status'],
                    'start'       => $row['time_start_act'],
                    'end'         => $row['time_end_act'],
                    'allDay'      => false,
                    'color'       => '#eca427',
                );
            }
            else {
                // Insert offset for test setup as separate event in order not to confuse the user:
                $events[] = array(
                    'id'          => 'service',
                    'title'       => 'Test setup',
                    'description' => $mini?'':'Time needed by FlockLab to setup your test.',
                    'start'       => $row['time_start_offset'],
                    'end'         => $row['time_start_wish'],
                    'allDay'      => false,
                    'color'       => 'orange',
                );
                // Insert actual test:
                $events[] = array(
                    'id'          => $row['serv_tests_key'],
                    'title'       => 'Test ' . $row['serv_tests_key'] . ': ' . $row['title'],
                    'description' => $mini?'':'Test-ID: ' . $row['serv_tests_key'] . '<br/>Duration: '.date("H:i", strtotime($row['time_start_wish'])).' - '.date("H:i", strtotime($row['time_end_wish'])).'<br/>Title: ' . $row['title'] . '<br/> Description: ' . $row['description'].'<br />Status: '.$row['test_status'],
                    'start'       => $row['time_start_wish'],
                    'end'         => $row['time_end_wish'],
                    'allDay'      => false,
                    'color'       => '#eca427',
                );
                // Insert offset for test finish as separate event in order not to confuse the user:
                $events[] = array(
                    'id'          => 'service',
                    'title'       => 'Test cleanup',
                    'description' => $mini?'':'Time needed by FlockLab to cleanup your test.',
                    'start'       => $row['time_end_wish'],
                    'end'         => $row['time_end_offset'],
                    'allDay'      => false,
                    'color'       => 'orange',
                );
            }
        } elseif ($_SESSION['is_admin'] == true) {
            // The user is admin and can thus see all tests:
            $event = array(
                    'id'          => $row['serv_tests_key'],
                    'title'       => $row['username'] . ' (' . $row['firstname'] . ' ' . $row['lastname'] . ')',
                    'description' => $mini?'':'ID: ' . $row['serv_tests_key'] . '<br/>Duration: '.date("H:i", strtotime($row['time_start_wish'])).' - '.date("H:i", strtotime($row['time_end_wish'])).'<br/>Title: ' . $row['title'] . '<br/> Description: ' . $row['description'] . '<br/> User: ' . $row['username'] . ' (' . $row['firstname'] . ' ' . $row['lastname'] . ')' . '<br/>Status: ' . $row['test_status'],
                    'allDay'      => false,
            );
            if (isset($row['time_start_act']))
                $event['start'] = $row['time_start_act'];
            else
                $event['start'] = $row['time_start_offset'];
            if (isset($row['time_end_act']))
                $event['end'] = $row['time_end_act'];
            else
                $event['end'] = $row['time_end_offset'];
            array_push($events, $event);
        
        } else {
            // The event is not owned by the logged-in user, thus just show one event without details and add the offsets directly to the event:            
        $event = array(
                'id'          => $row['serv_tests_key'],
                'title'       => 'Occupied',
                'description' => $mini?'':'Another user is running a test.',
                'allDay'      => false,
            );
            if (isset($row['time_start_act']))
                $event['start'] = $row['time_start_act'];
            else
                $event['start'] = $row['time_start_offset'];
            if (isset($row['time_end_act']))
                $event['end'] = $row['time_end_act'];
            else
                $event['end'] = $row['time_end_offset'];
            array_push($events, $event);
        }
    }
    
    // add reservation slots that affect this user (i.e., blocks time) 
    $sql = 'SELECT max(`user_fk` = '.$_SESSION['serv_users_key'].') as `reservation_match`, `time_start`, `time_end`, `serv_reservation_key`, `group_id_fk`
        FROM `tbl_serv_reservations` LEFT JOIN `tbl_serv_user_groups` ON `group_fk`=`group_id_fk`
        WHERE `time_end` > NOW() AND
        (`time_start` BETWEEN "' . $mysqlstart . '" AND "' . $mysqlend . '" OR
        `time_end` BETWEEN "' . $mysqlstart . '" AND "' . $mysqlend . '")
        GROUP BY serv_reservation_key
        '. ($_SESSION['is_admin'] == true?'':'HAVING `reservation_match` is NULL OR `reservation_match` <> 1');
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get calendar data from database because: ' . mysqli_error($db));
    while ($row = mysqli_fetch_array($rs)) {    
        $event = array(
            'id'          => $row['serv_reservation_key'],
            'title'       => ($_SESSION['is_admin'] == true?'Reservation for group '.$row['group_id_fk']:'Occupied'),
            'description' => $mini?'':'Another user is running a test.',
            'allDay'      => false,
        );
        $event['start'] = $row['time_start'];
        $event['end'] = $row['time_end'];
        array_push($events, $event);
    }
    mysqli_close($db);

    // JSON-encode the array and return it to the calendar:
    echo json_encode($events);

?>
