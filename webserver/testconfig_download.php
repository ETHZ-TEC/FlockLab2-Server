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
?>
<?php include_once('include/presets.php');?>
<?php
if (isset($_POST['testid']) && is_numeric($_POST['testid']) && check_testid($_POST['testid'],$_SESSION['serv_users_key'])) {
  $config = get_testconfig($_POST['testid']);
  if ($config!==false) {
    // Send the file to the user's browser:
    header("Content-Type: application/xml");
    header("Content-Disposition: attachment; filename=\"flocklab_testconfiguration_" . $_POST['testid'] . ".xml\"");
    echo $config;
  }
  else {
    header("HTTP/1.0 400 Bad Request");
  }
}
else
  header("HTTP/1.0 400 Bad Request");
?>