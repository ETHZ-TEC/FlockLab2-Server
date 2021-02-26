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
  require_once('include/layout.php');
  require_once('include/presets.php');
  
  if (isset($_GET['action']) && !isset($_POST['action'])) {
    $_POST['action'] = $_GET['action'];
  }
  if (isset($_GET['test_id']) && !isset($_POST['test_id'])) {
    $_POST['test_id'] = $_GET['test_id'];
  }
  if (isset($_GET['platform']) && !isset($_POST['platform'])) {
    $_POST['platform'] = $_GET['platform'];
  }
  
  $db = db_connect();
  $sql = "SELECT DISTINCT a.platform_fk, b.name FROM `flocklab`.`tbl_serv_link_measurements` AS `a`
          LEFT JOIN tbl_serv_platforms AS `b` ON `a`.platform_fk = `b`.serv_platforms_key
          WHERE `a`.links IS NOT NULL";
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get link test information from database because: ' . mysqli_error($db));
  
  if (isset($_POST['action']) && $_POST['action'] == 'dl') {
    if (isset($_POST['test_id']) && is_numeric($_POST['test_id']) && intval($_POST['test_id']) >= 0) {
      $sql = "SELECT links FROM `flocklab`.`tbl_serv_link_measurements`
              WHERE test_fk = ".sprintf("%d", intval($_POST['test_id']));
      $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get link test information from database because: ' . mysqli_error($db));
      if ($rs !== false) {
        $row = mysqli_fetch_assoc($rs);
        header("Content-Type: binary/octet-stream");
        header("Content-Disposition: attachment; filename=\"linktest_".$_POST['test_id'].".pkl\"");
        echo $row['links'];
      } else {
        header("HTTP/1.0 400 Bad Request");
      }
      mysqli_close($db);
    }
    exit();
  }
  
  // get currently used observers
  $platforms = Array();
  while ($row = mysqli_fetch_array($rs)) {
    $platforms[] = array('key' => $row[0], 'name' => $row[1]);
  }
  
  $linktestdata = "";
  if (isset($_POST['test_id']) && is_numeric($_POST['test_id']) && intval($_POST['test_id']) >= 0) {
    // fetch the linktest data
    $sql = "SELECT links_html FROM `flocklab`.`tbl_serv_link_measurements`
            WHERE test_fk = ".sprintf("%d", intval($_POST['test_id']));
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get link test information from database because: ' . mysqli_error($db));
    if ($row = mysqli_fetch_array($rs)) {
      $linktestdata = $row[0];
    }
  } else {
    $_POST['test_id'] = -1;
  }
  $linktests = Array();
  if (isset($_POST['platform']) && is_numeric($_POST['platform']) && intval($_POST['platform']) >= 0) {
    // get a list of all linktest for the specified platform
    $sql = "SELECT a.test_fk, b.name, a.begin, a.radio_cfg FROM `flocklab`.`tbl_serv_link_measurements` AS `a`
            LEFT JOIN tbl_serv_platforms AS `b` ON `a`.platform_fk = `b`.serv_platforms_key
            WHERE `a`.links IS NOT NULL and `a`.platform_fk = ".sprintf("%d", intval($_POST['platform']))."
            ORDER BY serv_link_measurements_key DESC";
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get link test information from database because: ' . mysqli_error($db));
    while ($row = mysqli_fetch_array($rs)) {
      $linktests[] = array('test_id' => $row[0], 'start_time' => $row[2], 'radio_cfg' => $row[3]);
    }
  } else {
    $_POST['platform'] = -1;
  }
  
  mysqli_close($db);
?>
<h1>Link Tests</h1>
<form>
<table>
  <thead>
    <tr>
      <th width="200px">Select a platform</th>
      <th width="200px">Select a link test</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <select name="platforms[]" style="width:200px" onChange="$(document.selecttest.platform).val($(this).val());document.selecttest.submit()">
          <option value="-1">-</option>
<?php
  $selected_platform = 0;
  if (isset($_POST['platform'])) {
    $selected_platform = $_POST['platform'];
  }
  foreach ($platforms as $p) {
    echo '<option value="'.$p['key'].'"'.($selected_platform == $p['key'] ? ' selected="selected"' : '').'>'.$p['name'].'</option>';
  }
?>
        </select>
      </td>
      <td>
        <select name="tests[]" multiple style="width:200px;height:200px" onChange="$(document.selecttest.test_id).val($(this).val());document.selecttest.submit()">
<?php
  $selected_test = 0;
  if (isset($_POST['test_id'])) {
    $selected_test = $_POST['test_id'];
  }
  foreach ($linktests as $l) {
    echo '<option value="'.$l['test_id'].'"'.($selected_test == $l['test_id'] ? ' selected="selected"' : '').'>'.$l['start_time'].'</option>';
  }
?>
        </select>
      </td>
    </tr>
  </tbody>
</table>
<div id="linktest">
<br />
<?php
  if ($_POST['test_id'] >= 0) {
    echo " &nbsp; <a href=# onclick='$(document.selecttest.action).val(\"dl\");document.selecttest.submit()'>Download test results in a machine-readable format (pickle).</a>";
  }
?>
<br />
</form>
<?php
  echo '<form name="selecttest" method="post" action="'.$_SERVER['PHP_SELF'].'"><input type="hidden" name="platform" value="'.$_POST['platform'].'"><input type="hidden" name="test_id" value="'.$_POST['test_id'].'"><input type="hidden" name="action" value=""></form>';
?>
  <br />
  <br />
<?php
  echo $linktestdata;
?>
</div>

<?php
  echo "<script type=\"text/javascript\">$js</script>";
  do_layout('Link Tests','Link Tests', '<link rel="stylesheet" href="css/ui-lightness/jquery-ui-1.8.20.custom.css">');
?>
