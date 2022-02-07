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
<?php require_once('include/libflocklab.php');?>
<?php require_once('include/recaptcha.php');?>
<?php 
    $first  = ($_POST['first'] == "no") ? false : true;
    $error = false;
    $errors = array();
    
      // If the page is called for the second time, validate and process form:
    if (!$first) {
        $emailaddress = $_POST['emailaddress'];
        $username     = $_POST['username'];
        
        // Check necessary fields:
        if ($emailaddress == "" || $username == "") {
            $error = true;
            array_push($errors, "Please fill out all fields marked with an asterisk.");
        }

        // Check captcha:
        if (recaptcha_verify() == false) {
            $error = true;
            array_push($errors, "Captcha was not entered correctly.");
        }
        
        // If there was no error, set a new, random password in the DB and send it to the user by email:
        if (!$error) {
            $db   = db_connect();
            // Check if user exists in database:
            $sql  = "SELECT * FROM `tbl_serv_users` WHERE `username` = '" . mysqli_real_escape_string($db, $username) . "' AND `email` = '" . mysqli_real_escape_string($db, $emailaddress) . "'";
            $rs   = mysqli_query($db, $sql) or flocklab_die('Cannot get user information from database because: ' . mysqli_error($db));
            $rows = mysqli_fetch_array($rs);
            if ($rows) {
                // Generate a temporary password and store it:
                $newpassword = substr(hash('sha512', rand()), 0, 16);
                $newhash     = sha1($newpassword);
                $sql         = "UPDATE `tbl_serv_users` SET `password` = '" . $newhash . "' WHERE `username` = '" . mysqli_real_escape_string($db, $username) . "' AND `email` = '" . mysqli_real_escape_string($db, $emailaddress) . "'";
                mysqli_query($db, $sql) or flocklab_die('Cannot get set new password for user in database because: ' . mysqli_error($db));
            }             
            mysqli_close($db);
        
            // If user was found and password has been set, inform user:
            if (isset($newpassword)) {
                $subject = "[FlockLab] Request for password recovery";
                $message = "A request for a FlockLab password recovery has been placed on the FlockLab user interface.\n".
                           "If this request has not been placed by you, please contact us at ".$CONFIG['email']['admin_email'].".\n\n".
                           "Your password has been reset to the following new password: \n\n$newpassword\n\n".
                           "Please login at ".$CONFIG['xml']['namespace']."/user and change the password in your account settings afterwards.\n\n";
                $message = wordwrap($message, 70);
                send_mail($subject, $message, $emailaddress);
            } else {
                $error = true;
                array_push($errors, "No user found with the specified name/email combination.");    
            }
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

    <title>FlockLab - Password Recovery</title>

    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="AUTHOR" content="ETH Zurich, Christoph Walser, CH-8092 Zurich, Switzerland">
    <meta name="COPYRIGHT" content="ETH Zurich, Switzerland">
    <meta name="LANGUAGE" content="English">
    <meta name="ROBOTS" content="noindex, nofollow">
    <meta name="DATE" content="2011-2013">
    
    <script type="text/javascript" src="scripts/jquery-latest.js"></script>
    <script type="text/javascript" src="scripts/jquery.validate.min.js"></script>
    <script type="text/javascript">
        $(document).ready(function(){
        $("#flocklabform").validate({
                rules: {
                    emailaddress: {
                        required: true,
                        email: true
                    },
                    username: {
                        required: true
                    }
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
            <h1>FlockLab Password Recovery</h1>
            <form id="flocklabform" name="flocklabform" method="post" action="user_passwordrecovery.php">
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
                <p>Please fill out the form below to request a new password for your FlockLab account. Fields marked with * are mandatory.</p>
                <span class="formfield">Username:*</span><input type="text" name="username" id="username" value="<?php echo $username; ?>"><br>
                <span class="formfield">E-mail Address:*</span><input type="text" name="emailaddress" id="emailaddress" value="<?php echo $emailaddress; ?>"><br>
                <span class="formfield">Captcha:*</span><?php recaptcha_print(); ?>
                <p>
                    <input type="hidden" name="first" value="no">
                    <input type="submit" value="Request new Password">&nbsp;&nbsp;
                    <input type="button" value="Cancel" onclick="window.location='login.php'">
                </p>
            <?php 
                } else { 
                    echo "<p class='info'><img alt='' src='pics/icons/info.png'>Your request has been submitted. A new password will be sent to your E-mail address if it is registered in our database.</p>";
                    echo "<input type=\"button\" value=\"Finish\" onclick=\"window.location='login.php'\">";
                }
            ?>
            </form>
        </div> <!-- END content -->
        <div style="clear:both"></div>
    </div> <!-- END container -->
</body>
</html>
