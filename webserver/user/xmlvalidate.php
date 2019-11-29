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
	 
	//DEBUG ini_set('display_errors', 1);
	//DEBUG error_reporting(E_ALL); 
?>
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
	$first  = ((isset($_POST['first'])) && ($_POST['first'] == "no")) ? false : true;
	$errors = array();
	
	// If the page is called for at least the second time, validate the XML file provided by the user:
	if (!$first) {
		// Get the file and check if it has an XML MIME type:
		$xmlfile = $_FILES['xmlfile'];
		if ($xmlfile["error"] != 0) {
			// There was an error during file upload:
			array_push($errors, "There was an error when uploading the file.");
		}
		elseif (!(in_array($xmlfile["type"], array("text/xml", "application/xml")))) {
			// The uploaded file is not XML:
			array_push($errors, "Uploaded file is not XML.");
		} else {
			$cmd = "python ".$CONFIG['tests']['testvalidator']." -x " . $xmlfile['tmp_name'] . " -s ".$CONFIG['xml']['schemapath']." -u " . $_SESSION['serv_users_key'];
			exec($cmd , $output, $ret);
			foreach ($output as $error) {
				array_push($errors, $error);
			}
			if (empty($errors) && $ret) {
				array_push($errors, "unknown error");
			}
		}
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
			<h1>Validate XML Test Configuration</h1>
			<?php
				/* If the page is called with a file associated, validate it and show the results */
				if (!$first) {
					// Show validation errors: 					
					if (!empty($errors)) {
						echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
						echo "<!-- cmd --><p>Please correct the following errors:</p><ul>";
						foreach ($errors as $error)
							echo "<li>" . $error . "</li>";
						echo "</ul><!-- cmd --></div><p></p>";
					} else {
						echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
						echo "<!-- cmd --><p>The file validated correctly.</p><!-- cmd --></div>";
						echo "<p></p>";
						echo '<form action="newtest.php" method="post">
						      <input type="hidden" name="xmlfile" id="xmlfile" value="'.htmlentities(file_get_contents($xmlfile['tmp_name'])).'">
						      <input type="submit" value="Create test"></form>';
						echo '<p style="margin-top:30px">.. or validate another XML test configuration:</p>';
					}
				}
			?>
			<form id="xmluploadform" name="xmluploadform" method="post" action="xmlvalidate.php" enctype="multipart/form-data">
				<fieldset>
					<legend>Upload XML to validate</legend>
					<span class="formfield">XML File:*</span><input type="file" name="xmlfile" id="xmlfile" size="27" class="required"><br />
				<p>A template XML test configuration can be downloaded <a href="xml/flocklab_template.xml" target="_blank">here</a>, the XML schema file against which is validated can be found <a href="xml/flocklab.xsd" target="_blank">here</a>.<br>
				Detailed information is available on the <a href="https://gitlab.ethz.ch/tec/public/flocklab/wikis/Man/XmlConfig">FlockLab XML Test Configuration File Help page</a>.</p>
				</fieldset>
				<p></p>
				<input type="hidden" name="first" value="no">
				<input type="submit" value="Validate">
			</form>
<?php
do_layout('Validate XML','Validate XML Test Config');
?>
