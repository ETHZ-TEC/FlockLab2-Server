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
    
if (isset($_GET['p'])) {
    //debug();
    $platform = explode( '_' , $_GET['p']);
    $radio = count($platform) > 1?"LOWER(radio)='".strtolower($platform[1])."'":'(radio="" OR radio is NULL)';
    $platform = strtolower($platform[0]);
    // Connect to database and get available measurements:
    $db = db_connect();
    $sql = "SELECT serv_link_measurements_key, begin
        FROM `flocklab`.tbl_serv_web_link_measurements
        LEFT JOIN tbl_serv_platforms ON (serv_platforms_key = platform_fk)
        WHERE LOWER(name)='".mysqli_real_escape_string($db, $platform)."' AND ".$radio." AND links is not NULL
        ORDER BY begin ASC
        ";
    $rs = mysqli_query($db, $sql) or flocklab_die('Error: ' . mysqli_error($db));
    mysqli_close($db);
    
    // Build the array of tests. If possible, append start and/or end time to the message:
    $tests = array(
        'dateTimeFormat'=>'iso8601',
        'events'=> array (),
    );
    while ($row = mysqli_fetch_array($rs)) {
        
        $d = new DateTime($row['begin']);
        $tests['events'][]=array(
            'start'=>$d->format(DATE_ISO8601),
            //'end'=>$d->format(DATE_ISO8601),
            'durationEvent'=>FALSE,
            'title'=>'',
            'description'=>$row['serv_link_measurements_key'],
        );
    }

    // JSON-encode the array and return it to the calendar:
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($tests);

}
else if (isset($_GET['q']) and is_numeric($_GET['q'])) {
    // Connect to database and get link measurements:
    $db = db_connect();
    $sql = "SELECT CONVERT(links USING utf8) as links 
        FROM `flocklab`.tbl_serv_web_link_measurements 
        WHERE serv_link_measurements_key=".$_GET['q'];
    $rs = mysqli_query($db, $sql) or flocklab_die('Error: ' . mysqli_error($db));
    mysqli_close($db);
    
    if (mysqli_num_rows($rs) == 1) {
        header('Content-Type: application/xml; charset=utf-8');
        $row = mysqli_fetch_array($rs);
        echo $row['links'];
    }

}
?>
