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
    if ((!isset($_GET['testid']) || !is_numeric($_GET['testid'])) && (!isset($_GET['updatesince']) || !is_numeric($_GET['updatesince']))) {
        return;
    }
    // Connect to database and get the corresponding test info:
    $db = db_connect();
    $sql = "SELECT serv_tests_key as testid, title, description, time_start, time_end, test_status 
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
