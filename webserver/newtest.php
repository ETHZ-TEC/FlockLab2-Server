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
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
$first  = ((isset($_POST['first'])) && ($_POST['first'] == "no")) ? false : true;
$errors = array();

// be sure that the user supplied configuration is valid
if (isset($_POST['xmlfile'])) {
  $tmp_xmlfile = tempnam(sys_get_temp_dir(), 'flocklab');
  file_put_contents($tmp_xmlfile, $_POST['xmlfile']);
}
// If the page is called for at least the second time, validate the XML file provided by the user:
else if (!$first) {
  // Get the file and check if it has an XML MIME type:
  $xmlfile = $_FILES['xmlfile'];
  if ($xmlfile["error"] != 0) {
    // There was an error during file upload:
    array_push($errors, "There was an error when uploading the file.");
  }
  else if (!(in_array($xmlfile["type"], array("text/xml", "application/xml")))) {
    // The uploaded file is not XML:
    array_push($errors, "Uploaded file is not XML.");      
  } else {
    $tmp_xmlfile = $xmlfile['tmp_name'];
  }
}

// process config
if (isset($tmp_xmlfile) && empty($errors)) {
    $xml_config = file_get_contents($tmp_xmlfile);
    $res = update_add_test($xml_config, $errors);
}

      
?>
<?php
/* If the page is called with a file associated, validate it and show the results */
if (isset($tmp_xmlfile) && empty($errors)) {
    echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
    echo "<!-- cmd --><p>Test (Id ".$res['testId'].") successfully added.</p><!-- cmd --></div>";
    echo "<!-- flocklabscript,".$res['testId'].",".$res['start']->format(DATE_ISO8601).",".$res['start']->format("U")."-->";
    echo "<p></p>";
    include('index.php');
    exit();
}
?>
<script type="text/javascript">
$(document).ready(function() {
  $('.qtip_show').qtip( {
    content: {text: false},
    style  : 'flocklab',
  });
  $("#xmluploadform").validate({
    rules: {
      xmlfile: "required",
    },
    errorPlacement: function(error, element) {
      error.insertAfter(element);
    }
  });
});
</script>
<h1>Create New Test</h1>
<?php
// Show validation errors:  
if (!empty($errors)) {
    echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
    echo "<!-- cmd --><p>Please correct the following errors:</p><ul>";
    foreach ($errors as $error)
      echo "<li>" . $error . "</li>";
    echo "</ul><!-- cmd --></div><p></p>";
  }

?>
<form id="xmluploadform" name="xmluploadform" method="post" action="newtest.php" enctype="multipart/form-data">
  <fieldset>
    <legend>Upload XML test configuration</legend>
    <span class="formfield">XML File:*</span><input type="file" name="xmlfile" id="xmlfile" size="27" class="required"><br />
    <p>A template XML test configuration can be downloaded <a href="xml/flocklab_template.xml" target="_blank">here</a>, the XML schema file against which is validated can be found <a href="xml/flocklab.xsd" target="_blank">here</a>.<br>
                Detailed information is available on the <a href="https://gitlab.ethz.ch/tec/public/flocklab/flocklab/-/wikis/Man/XmlConfig">FlockLab XML Test Configuration File Help page</a>.</p>
  </fieldset>
  <p></p>
  <input type="hidden" name="first" value="no">
  <input type="submit" value="Create test">
</form>
<?php
do_layout('Create New Test','Manage Tests');
?>
