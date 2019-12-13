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
<?php require_once('include/layout.php');require_once('include/presets.php');
$editable = true;
if (isset($_POST['doit']) && isset($_POST['testid']) && isset($_POST['xmlfile'])) {
    $xmlfile = $_POST['xmlfile'];
    $errors = array();
    // check test_owner = user
    if (check_testid($_POST['testid'], $_SESSION['serv_users_key'])) {
        $status = get_teststatus($_POST['testid']);
        if ($status=='planned') {
            $res = update_add_test($_POST['xmlfile'], $errors, $_POST['testid']);
        }
        else {
            array_push($errors, "Only planned tests can be edited.");
            $editable = false;
        }
    }
    else
        array_push($errors, "Test does not belong to you.");
}
else if(isset($_POST['testid']) && isset($_POST['starttime'])) { // reschedule request
    $new_start_time = strtotime($_POST['starttime']);
    $errors = array();
    // check test_owner = user
    if (check_testid($_POST['testid'], $_SESSION['serv_users_key'])) {
        $status = get_teststatus($_POST['testid']);
        if ($status=='planned') {
            // get xml_config
            $config = get_testconfig($_POST['testid']);
            $testconfig = new SimpleXMLElement($config);
            // shift start and end time
            $timeshift_sec = $new_start_time - strtotime($testconfig->generalConf->scheduleAbsolute->start);
            $time = new DateTime ($testconfig->generalConf->scheduleAbsolute->start);
            $time->modify($timeshift_sec.' seconds');
            $testconfig->generalConf->scheduleAbsolute->start = $time->format(DATE_W3C);
            $time = new DateTime ($testconfig->generalConf->scheduleAbsolute->end);
            $time->modify($timeshift_sec.' seconds');
            $testconfig->generalConf->scheduleAbsolute->end = $time->format(DATE_W3C);
            // write new xml and validate test
            $xmlfile = $testconfig->asXML();
            $res = update_add_test($xmlfile, $errors, $_POST['testid']);
        }
    }
}
  // Show validation errors:
  if (isset($errors)) {
    if (!empty($errors)) {
    echo '<h1>Edit Test</h1>';
      echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
      echo "<p>Please correct the following errors:</p><ul>";
      foreach ($errors as $error)
          echo "<li>" . $error . "</li>";
      echo "</div><p></p>";
    } else {
      echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
      echo "<p>The test was successfully updated.</p><ul>";
      echo "</div><p></p>";
      include('index.php');
      exit();
    }
  }
  if ((!isset($errors) || !empty($errors)) && $editable) {
    echo '<h1>Edit Test</h1>';
    echo '<form name="form_test" action="test_edit.php" method="post" enctype="multipart/form-data"><div id="test">';
    if (isset($errors))
      echo '<textarea name="xmlfile" style="width:100%;height:500px">'.$xmlfile.'</textarea>';
    else {
      $config = get_testconfig($_POST['testid']);
      echo '<textarea name="xmlfile" style="width:100%;height:500px">'.$config.'</textarea>';
    }
    echo '</div>
      <input type="hidden" name="testid" value="'.$_POST['testid'].'">
      <input type="reset" value="reset">
      <input type="submit" name="doit" value="save configuration">
      </form>';
  }
?>
<?php
do_layout('Edit Test','Manage Tests');
?>