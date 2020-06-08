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
<?php include_once('include/presets.php');?>
<?php
  if (isset($_POST['q'])) {
    $status = array('online');
    $userrole = get_user_role($_POST['username']);
    if ($userrole == 'internal') {
      $status[] = 'internal';
    }
    if ($userrole == 'admin') {
      $status[] = 'develop';
      $status[] = 'internal';
    }
    $status = "('" .join("', '", $status) ."')";

    if ($_POST['q'] == 'obs' && isset($_POST['platform'])) {
      $db = db_connect();
      $platform = strtolower(mysqli_real_escape_string($db, $_POST['platform']));
      // return a list of the currently available observers
      $sql = "SELECT obs.observer_id AS obsid FROM flocklab.tbl_serv_observer AS obs
              LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS a ON obs.slot_1_tg_adapt_list_fk = a.serv_tg_adapt_list_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot1 ON a.tg_adapt_types_fk = slot1.serv_tg_adapt_types_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS b ON obs.slot_2_tg_adapt_list_fk = b.serv_tg_adapt_list_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot2 ON b.tg_adapt_types_fk = slot2.serv_tg_adapt_types_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS c ON obs.slot_3_tg_adapt_list_fk = c.serv_tg_adapt_list_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot3 ON c.tg_adapt_types_fk = slot3.serv_tg_adapt_types_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_list AS d ON obs.slot_4_tg_adapt_list_fk = d.serv_tg_adapt_list_key
              LEFT JOIN flocklab.tbl_serv_tg_adapt_types AS slot4 ON d.tg_adapt_types_fk = slot4.serv_tg_adapt_types_key
              WHERE obs.status IN $status AND '$platform' IN (LOWER(slot1.name), LOWER(slot2.name), LOWER(slot3.name), LOWER(slot4.name))
              ORDER BY obs.observer_id;";
      $res = mysqli_query($db, $sql);
      if (!$res) {
        echo json_encode(array('status' => 'error', 'output' => mysqli_error($db)));
      }
      else {
        $output = implode(" ", array_column(mysqli_fetch_all($res, MYSQLI_ASSOC), "obsid"));
        echo json_encode(array('status' => 'ok', 'output' => $output));
      }
    }
    else if ($_POST['q'] == 'platform') {
      $db = db_connect();
      $sql = "SELECT obs.observer_id, slot1.name AS name1, slot1.description AS desc1,
              slot2.name AS name2, slot2.description AS desc2,
              slot3.name AS name3, slot3.description AS desc3,
              slot4.name AS name4, slot4.description AS desc4
              FROM `flocklab`.`tbl_serv_observer` AS obs
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS a ON obs.slot_1_tg_adapt_list_fk = a.serv_tg_adapt_list_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot1 ON a.tg_adapt_types_fk = slot1.serv_tg_adapt_types_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS b ON obs.slot_2_tg_adapt_list_fk = b.serv_tg_adapt_list_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot2 ON b.tg_adapt_types_fk = slot2.serv_tg_adapt_types_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS c ON obs.slot_3_tg_adapt_list_fk = c.serv_tg_adapt_list_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot3 ON c.tg_adapt_types_fk = slot3.serv_tg_adapt_types_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS d ON obs.slot_4_tg_adapt_list_fk = d.serv_tg_adapt_list_key
              LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot4 ON d.tg_adapt_types_fk = slot4.serv_tg_adapt_types_key
              WHERE obs.status IN $status
              ORDER BY obs.observer_id;";
      $res = mysqli_query($db, $sql);
      if (!$res) {
        echo json_encode(array('status' => 'error', 'output' => mysqli_error($db)));
      }
      else {
        $output = [];
        while ($row = mysqli_fetch_assoc($res)) {
          $output[] = $row['name1'];
          $output[] = $row['name2'];
          $output[] = $row['name3'];
          $output[] = $row['name4'];
        }
        echo json_encode(array('status' => 'ok', 'output' => join(" ", array_unique(array_filter($output)))));
      }
    }
    else if ($_POST['q'] == 'testinfo') {
      if (!isset($_POST['id'])) {
        echo json_encode(array('status' => 'error', 'output' => 'no test ID specified'));
        exit();
      }
      $db = db_connect();
      $sql = "SELECT title, description, test_status as status, UNIX_TIMESTAMP(time_start_wish) AS start_planned, UNIX_TIMESTAMP(time_start_act) AS start_act, UNIX_TIMESTAMP(time_end_wish) AS end_planned, UNIX_TIMESTAMP(time_end_act) AS end_act
              FROM `flocklab`.`tbl_serv_tests`
              WHERE serv_tests_key=".intval($_POST['id'])." AND owner_fk=$_SESSION[serv_users_key]";
      $res = mysqli_query($db, $sql);
      if (!$res) {
        echo json_encode(array('status' => 'error', 'output' => mysqli_error($db)));
      }
      else {
        $row = mysqli_fetch_assoc($res);
        if ($row) {
          echo json_encode(array('status' => 'ok', 'output' => array('title' => $row['title'], 'description' => $row['description'], 'status' => $row['status'], 'start_planned' => $row['start_planned'], 'start' => $row['start_act'], 'end_planned' => $row['end_planned'], 'end' => $row['end_act'])));
        } else {
          echo json_encode(array('status' => 'error', 'output' => 'test ID '.intval($_POST['id']).' not found'));
        }
      }
    }
    else {
      echo json_encode(array('status' => 'error', 'output' => 'unknown query'));
    }

  } else if (isset($_POST['s'])) {

    if ($_POST['s'] == 'title' && isset($_POST['id']) && isset($_POST['val'])) {
      // set the test title
      $db = db_connect();
      $sql = "UPDATE tbl_serv_tests SET title='". mysqli_real_escape_string($db, $_POST['val']) ."' WHERE serv_tests_key=". intval($_POST['id']) ." AND owner_fk=". $_SESSION['serv_users_key'] ." LIMIT 1";
      $rs = mysqli_query($db, $sql);
      mysqli_close($db);

    } else if ($_POST['s'] == 'desc' && isset($_POST['id']) && isset($_POST['val'])) {
      // set the test description
      $db = db_connect();
      $sql = "UPDATE tbl_serv_tests SET description='". mysqli_real_escape_string($db, $_POST['val']) ."' WHERE serv_tests_key=". intval($_POST['id']) ." AND owner_fk=". $_SESSION['serv_users_key'] ." LIMIT 1";
      $rs = mysqli_query($db, $sql);
      mysqli_close($db);

    } else {
      echo json_encode(array('status' => 'error', 'output' => 'invalid API usage'));
    }

  } else {
    echo json_encode(array('status' => 'error', 'output' => 'invalid API usage'));
  }
?>
