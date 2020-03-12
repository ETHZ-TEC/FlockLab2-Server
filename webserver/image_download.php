<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision: 2435 $"
     * __date__        = "$Date: 2013-09-27 16:03:15 +0200 (Fri, 27 Sep 2013) $"
     * __id__          = "$Id: testconfig_download.php 2435 2013-09-27 14:03:15Z walserc $"
     * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/testconfig_download.php $" 
     */
?>
<?php include_once('include/presets.php');?>
<?php
if (isset($_POST['imageid']) && is_numeric($_POST['imageid']) && check_imageid($_POST['imageid'],$_SESSION['serv_users_key'])) {
  $db = db_connect();
  $sql =  "SELECT `binary`, p.`name` `platform`
    FROM tbl_serv_targetimages i
    left join tbl_serv_platforms p on (i.platforms_fk = p.serv_platforms_key)
    WHERE ".($_SESSION['is_admin']?"":("owner_fk = " . $_SESSION['serv_users_key'] . " AND "))."`serv_targetimages_key`=".mysqli_real_escape_string($db, $_POST['imageid']);
  $res = mysqli_query($db, $sql);
  if ($res !== false) {
    $row = mysqli_fetch_assoc($res);
    // Send the file to the user's browser:
    header("Content-Type: binary/octet-stream");
    header("Content-Disposition: attachment; filename=\"". $_POST['imageid'] .".".$row['platform'].".exe\"");
    echo $row['binary'];
  }
  else {
    header("HTTP/1.0 400 Bad Request");
  }
}
else
  header("HTTP/1.0 400 Bad Request");
?>
