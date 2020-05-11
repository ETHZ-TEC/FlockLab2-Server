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
if (isset($_POST['imageid']) && is_numeric($_POST['imageid']) && check_imageid($_POST['imageid'],$_SESSION['serv_users_key'])) {
  $db = db_connect();
  $sql =  "SELECT `binary`, p.`name` `platform`, `core`
           FROM tbl_serv_targetimages i
           LEFT JOIN tbl_serv_platforms p on (i.platforms_fk = p.serv_platforms_key)
           WHERE ".($_SESSION['is_admin']?"":("owner_fk = " . $_SESSION['serv_users_key'] . " AND "))."`serv_targetimages_key`=".mysqli_real_escape_string($db, $_POST['imageid']);
  $res = mysqli_query($db, $sql);
  if ($res !== false) {
    $row = mysqli_fetch_assoc($res);
    $fileext = ".exe";
    if (!preg_match('/[^a-zA-Z0-9:\s]+/', $row['binary']) && $row['binary'][0] == ':') {
      $fileext = ".hex";
    }
    // for platform DPP append the core
    $coredict = ['cc430', 'bolt', 'msp432', 'sensor'];
    $core = (strtolower($row['platform']) == "dpp") ? "_".$coredict[$row['core']] : "";
    // Send the file to the user's browser:
    header("Content-Type: binary/octet-stream");
    header("Content-Disposition: attachment; filename=\"image". $_POST['imageid'] ."_".strtolower($row['platform']).$core.$fileext."\"");
    echo $row['binary'];
  }
  else {
    header("HTTP/1.0 400 Bad Request");
  }
}
else
  header("HTTP/1.0 400 Bad Request");
?>
