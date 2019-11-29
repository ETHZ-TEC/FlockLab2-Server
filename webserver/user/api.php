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

    if ($_POST['q'] == 'obs') {
      // return a list of the currently available observers
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
        if (isset($_POST['platform'])) {
          $platform = mysqli_real_escape_string($db, $_POST['platform']);
        }
        $output = "";
        while ($row = mysqli_fetch_assoc($res)) {
          if ($platform == "" || !strcasecmp($platform, $row['name1']) || !strcasecmp($platform, $row['name2']) || !strcasecmp($platform, $row['name3']) ||   !strcasecmp($platform, $row['name4'])) {
            $output .= $row['observer_id']." ";
          }
        }
        echo json_encode(array('status' => 'ok', 'output' => trim($output)));
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
    else {
      echo json_encode(array('status' => 'error', 'output' => 'unknown query'));
    }
  } else {
    echo json_encode(array('status' => 'error', 'output' => 'invalid API usage'));
  }
?>
