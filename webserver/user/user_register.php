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
<?php require_once('include/libflocklab.php'); ?>
<?php require_once('include/recaptcha.php'); ?>
<?php 
	$first  = ($_POST['first'] == "no") ? false : true;
	$error = false;
	$errors = array();
	
	// If the page is called for the second time, validate form and send an email to the flocklab admin on success.
	if (!$first) {
		$institution 	 = $_POST['institution'];
		$institutiontype = $_POST['institutiontype'];
		$firstname		 = $_POST['firstname'];
		$lastname		 = $_POST['lastname'];
		$emailaddress	 = $_POST['emailaddress'];
		$username		 = $_POST['username'];
		$country		 = $_POST['country'];
		$passwd			 = sha1($_POST['passwd']);
		$retypepasswd	 = sha1($_POST['retypepasswd']);
		$description	 = $_POST['description'];
		$comments		 = $_POST['comments'];
		$termsofuse	 = $_POST['termsofuse'];
		
		/* Check necessary fields */
		// Check necessary fields:
		if (($institution=="") || ($institutiontype=="") || ($firstname=="") || ($lastname=="") || ($emailaddress=="") || ($passwd=="") || ($retypepasswd=="") || ($description=="") || ($country=="")) {
			$error = true;
			array_push($errors, "Please fill out all fields marked with an asterisk.");
		}		
		// If institution is "other", it has to be specified in the comments section:
		if (($institutiontype == "other") && ($comments == "")) {
			$error = true;
			array_push($errors, "Please specify your type of institution in the comments section.");
		}
		// Check if passwords are the same:
		if ($passwd != $retypepasswd) {
			$error = true;
			array_push($errors, "Passwords are not the same.");
		}
		// Check if username already exists:
		$db = db_connect();
		$sql = "SELECT COUNT(*) FROM `tbl_serv_users` WHERE `username` = '" . mysqli_real_escape_string($db, $username) . "'";
		$rs = mysqli_query($db, $sql) or flocklab_die('Cannot check username against database because: ' . mysqli_error($db));
		$row = mysqli_fetch_row($rs);
		mysqli_close($db);
		if ($row[0] > 0) {
			$error = true;
			array_push($errors, "Username already exists in database.");
		}
		
		// Check captcha:
		if (recaptcha_verify() == false) {
			$error = true;
			array_push($errors, "Captcha was not entered correctly.");
		}
		
		// Check if terms of use are accepted:
		if ($termsofuse <> "yes") {
			$error = true;
			array_push($errors, "Terms of use have to be accepted.");
		}
		
		// If there was no error, insert the data into the database and send an email to the flocklab admin:
		if (!$error) {
			$db = db_connect();
			$sql =	"INSERT INTO `tbl_serv_users` (`lastname`, `firstname`, `username`, `country`, `password`, `email`, `institution_type`, `institution`, `is_active`,`create_time`)
				VALUES (
				'" . mysqli_real_escape_string($db, $lastname) . "', 
				'" . mysqli_real_escape_string($db, $firstname) . "',
				'" . mysqli_real_escape_string($db, $username) . "',
				'" . mysqli_real_escape_string($db, $country) . "',
				'" . mysqli_real_escape_string($db, $passwd) . "',
				'" . mysqli_real_escape_string($db, $emailaddress) . "',
				'" . mysqli_real_escape_string($db, $institutiontype) . "',
				'" . mysqli_real_escape_string($db, $institution) . "', 0, NOW())";
			mysqli_query($db, $sql) or flocklab_die('Cannot store user information in database because: ' . mysqli_error($db));
			mysqli_close($db);
		
			$adminemails = get_admin_emails();
			$to = implode(", ", $adminemails);
			$subject = "Request for FlockLab user account";
			$message = "A request for a new FlockLab user account has been placed on www.flocklab.ethz.ch/user/user_register.php\n\n";
			$message = $message . "First Name:            $firstname\n";
			$message = $message . "Last Name:             $lastname\n";
			$message = $message . "Username:              $username\n";
			$message = $message . "Country:               $country\n";
			$message = $message . "Institution :          $institution\n";
			$message = $message . "Institution type:      $institutiontype\n";
			$message = $message . "Email:                 $emailaddress\n"; 
			$message = $message . "Password SHA1 Hash:    $passwd\n"; 
			$message = $message . "FL will be used for:   $description\n"; 
			$message = $message . "Comments:              $comments\n";
			$message = $message . "Terms of use accepted: $termsofuse\n"; 
			$message = $message . "\n";
			$message = wordwrap($message, 70);
			$header  = 'Reply-To: ' . $emailaddress . "\r\n" .
					   'X-Mailer: PHP/' . phpversion();
			mail($to, $subject, $message, $header); 
		}
	}
?>
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
	"http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
	<link rel="stylesheet" type="text/css" href="css/flocklab.css">
	<link rel="shortcut icon" href="pics/icons/favicon.ico" type="image/x-ico; charset=binary">
	<link rel="icon" href="pics/icons/favicon.ico" type="image/x-ico; charset=binary">

	<title>FlockLab - Register Account</title>

	<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
	<meta name="AUTHOR" content="ETH Zurich, Christoph Walser, CH-8092 Zurich, Switzerland">
	<meta name="COPYRIGHT" content="ETH Zurich, Switzerland">
	<meta name="LANGUAGE" content="English">
	<meta name="ROBOTS" content="noindex, nofollow">
	<meta name="DATE" content="2011-2012">	
	
	<script type="text/javascript" src="scripts/jquery-latest.js"></script>
	<script type="text/javascript" src="scripts/jquery.validate.min.js"></script>
	<script type="text/javascript">
		$(document).ready(function(){
		$("#flocklabform").validate({
				rules: {
					institution: "required",
					institutiontype: "required",
					country: "required",
					firstname: "required",
					lastname: "required",
					emailaddress: {
						required: true,
						email: true
					},
					username: {
						required: true,
						minlength: 3,
						maxlength: 10
					},
					passwd: {
						required: true,
						minlength: 8
					},
					retypepasswd: {
						required: true,
						equalTo: "#passwd"
					},
					description: "required",
					termsofuse: "required",
					comments: {
						required: function(element) {
							return $("#institutiontype").val() == "other";
						}
					}
				},
				messages: {
					retypepasswd: {
						equalTo: "The passwords do not match."
					},
					termsofuse: "Please accept the terms of use.",
					comments: "Specify type of institution here."
				}
		});
		});
	</script>
	<script src='https://www.google.com/recaptcha/api.js'></script>
</head>
<body>
	<div id="container" class="container">
		<div id="header" class="header">
			<a href="http://www.flocklab.ethz.ch"><img alt="FlockLab" src="pics/flocklab_eth_logo.png"></a>
		</div> <!-- END header -->
		<div id="content" class="content">
			<h1>Register for a FlockLab Account</h1>
			<form id="flocklabform" name="flocklabform" method="post" action="user_register.php">
			<?php
				if ($first || $error) { 
					if ($error) {
						echo "<div class='warning'><div style='float:left;'><img alt='' src='pics/icons/att.png'></div>";
							echo "<p>Please correct the following errors:</p><ul>";
							foreach ($errors as $line)
								echo "<li>" . $line . "</li>";
							echo "</ul>"; 
						echo "</div>";
					}
			?>
				<p>Please fill out the form below to request an account for FlockLab. Fields marked with * are mandatory.</p>
				<span class="formfield">Institution:*</span><input type="text" name="institution" id="institution" value="<?php echo $institution;?>"><br>
				<span class="formfield">Type of Institution:*</span><select name="institutiontype" id="institutiontype">
					<option value="university"   <?php echo ($institutiontype == "university") ? 'selected="selected"' : "";?>>University</option>
					<option value="researchinstitute" <?php echo ($institutiontype == "researchinstitute") ? 'selected="selected"' : "";?>>Research Institute</option>
					<option value="company"   <?php echo ($institutiontype == "company") ? 'selected="selected"' : "";?>>Company</option>
					<option value="other"   <?php echo ($institutiontype == "other") ? 'selected="selected"' : "";?>>Other (specify under comments)</option>
				</select><br>
				<span class="formfield">Country:*</span><select name="country" id="country">
				<option value=""></option>
				<?php
					foreach (countries() as $c) {
						echo '<option value="'.$c.'" '.(($country == $c) ? 'selected="selected"' : "").'>'.$c.'</option>';
					}
				?>
				</select><br>
				<span class="formfield">First Name:*</span><input type="text" name="firstname" id="firstname" value="<?php echo $firstname;?>"><br>
				<span class="formfield">Last Name:*</span><input type="text" name="lastname" id="lastname" value="<?php echo $lastname;?>"><br>
				<span class="formfield">E-mail Address:*</span><input type="text" name="emailaddress" id="emailaddress" value="<?php echo $emailaddress;?>"><br>
				<span class="formfield">Username*:</span><input type="text" name="username" id="username" value="<?php echo $username;?>"><br>
				<span class="formfield">Password:*</span><input type="password" name="passwd" id="passwd" value=""><label id="passwderror" class="error" for="passwd" generated="true" style="display: inline;"></label><br>
				<span class="formfield">Retype Password:*</span><input type="password" name="retypepasswd" id="retypepasswd" value=""><br>
				<span class="formfield">What do you want to do with FlockLab (Please be specific, e.g. what kind of node platform or protocols you intend to use; ...):*</span><textarea name="description" id="description" cols="50" rows="5"><?php echo $description;?></textarea><br>
				<span class="formfield">Comments:</span><textarea name="comments" id="comments" cols="50" rows="5"><?php echo $comments;?></textarea><br>
				<span class="formfield">Terms of use:*</span><input type="checkbox" name="termsofuse" id="termsofuse" value="yes" <?php echo $termsofuse=='yes' ? 'checked' : '' ;?>> I accept the <a href="http://user.flocklab.ethz.ch/terms_of_use.php" target="_blank">terms of use</a>.<br>
				<span class="formfield">Captcha:*</span><?php recaptcha_print(); ?>
				<p>
					<input type="hidden" name="first" value="no">
					<input type="submit" value="Request Account">&nbsp;&nbsp;
					<input type="button" value="Cancel" onclick="window.location='index.php'">
				</p>
			<?php 
				} else { 
					echo "<p class='info'><img alt='' src='pics/icons/info.png'>Your request has been submitted. You will be contacted as soon as it is processed.</p>";
					echo "<input type=\"button\" value=\"Finish\" onclick=\"window.location='index.php'\">";
				}
			?>
			</form>
		</div> <!-- END content -->
		<div style="clear:both"></div>
	</div> <!-- END container -->
</body>
</html>
