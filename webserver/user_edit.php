<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2011, ETH Zurich, Switzerland, Christoph Walser"
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
    
    // If the page is called for at least the second time, see if the user wants to change anything and store it in the database if needed:
    if (!$first) {
        // Get the form data:
        $firstname          = $_POST['firstname'];
        $lastname        = $_POST['lastname'];
        $email              = $_POST['email'];
        $institutiontype = $_POST['institutiontype'];
        $institution     = $_POST['institution'];
        $country       = $_POST['country'];
        $passwd          = sha1($_POST['passwd']);
        $retypepasswd      = sha1($_POST['retypepasswd']);
        $quota_runtime      = $_POST['quotaruntime'];
        $quota_tests      = $_POST['quotatests'];
        $retention_time  = $_POST['retentiontime'];
        $username          = $_POST['username'];
        $disable_infomails = (isset($_POST['disableinfomails']) ? $_POST['disableinfomails'] : '0');
        
        // Check necessary fields:
        if (($institution=="") || ($institutiontype=="") || ($firstname=="") || ($lastname=="") || ($email=="") || ($country=="")) 
            array_push($errors, "Please fill out all fields marked with an asterisk.");
        // Check if passwords are the same:
        if ($passwd != $retypepasswd) 
            array_push($errors, "Passwords are not the same.");
        
        // If there was no error, change the data in the database:
        if (empty($errors)) {
            $db = db_connect();
            $sql =    "UPDATE `tbl_serv_users` 
                SET 
                    `lastname` = '" . mysqli_real_escape_string($db, $lastname) . "', 
                    `firstname` = '" . mysqli_real_escape_string($db, $firstname) . "',
                    `country` = '" . mysqli_real_escape_string($db, $country) . "',
                    `email` = '" . mysqli_real_escape_string($db, $email) . "',
                    `institution_type` = '" . mysqli_real_escape_string($db, $institutiontype) . "',
                    `institution` = '" . mysqli_real_escape_string($db, $institution) . "',
                    `disable_infomails` = '" . mysqli_real_escape_string($db, $disable_infomails) . "'
                WHERE serv_users_key = " . $_SESSION['serv_users_key'];
            mysqli_query($db, $sql) or flocklab_die('Cannot update user information in database because: ' . mysqli_error($db));
            // If the password was changed, reflect that also in the database:
            if ($passwd != sha1("")) {
                $sql =    "UPDATE `tbl_serv_users` SET `password` = '" . mysqli_real_escape_string($db, $passwd) . "' WHERE serv_users_key = " . $_SESSION['serv_users_key'];
                mysqli_query($db, $sql) or flocklab_die('Cannot update user password in database because: ' . mysqli_error($db));
            }
            mysqli_close($db);
        }        
    } else {
        // Get the values from the database:
        $db = db_connect();
        $sql =    "SELECT *  
            FROM tbl_serv_users
            WHERE serv_users_key = " . $_SESSION['serv_users_key'];
        $userinfo = mysqli_query($db, $sql) or flocklab_die('Cannot get user information from database because: ' . mysqli_error($db));
        mysqli_close($db);
        $row = mysqli_fetch_array($userinfo);
        $firstname        = $row['firstname'];
        $lastname         = $row['lastname'];
        $username         = $row['username'];
        $country          = $row['country'];
        $email            = $row['email'];
        $password_hash    = $row['password'];
        $institutiontype  = $row['institution_type'];
        $institution      = $row['institution'];
        $quota_runtime    = $row['quota_runtime'];
        $quota_tests      = $row['quota_tests'];
        $retention_time   = $row['retention_time'];
        $disable_infomails= $row['disable_infomails'];
    }

?>
    <script type="text/javascript">
        $(document).ready(function() {
            $('.qtip_show').qtip( {
                content: {text: false},
                style  : 'flocklab',
            });
            $("#usereditform").validate({
                rules: {
                    institution: "required",
                    institutiontype: "required",
                    firstname: "required",
                    lastname: "required",
                    country: "required",
                    email: {
                        required: true,
                        email: true
                    },
                    passwd: {
                        required: function(element) {
                            return $("#retypepasswd").val().length > 0;
                        },
                        minlength: 8
                    },
                    retypepasswd: {
                        required: function(element) {
                            return $("#passwd").val().length > 0;
                        },
                        equalTo: "#passwd"
                    },
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
                    comments: "Specify type of institution here."
                }
            });
        });
    </script>

            <h1>User Acccount for <?php echo $_SESSION['firstname'] . " " . $_SESSION['lastname'];?></h1>
            <?php
                /* If the page is called with a file associated, validate it and show the results */
                if (!$first) {
                    // Show validation errors:                     
                    if (!empty($errors)) {
                        echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
                        echo "<p>Please correct the following errors:</p><ul>";
                        foreach ($errors as $error)
                            echo "<li>" . $error . "</li>";
                        echo "</div><p></p>";
                    } else {
                        echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
                        echo "<p>Account information has been updated..</p><ul>";
                        echo "</div><p></p>";
                    }
                }
            ?>
            <form id="usereditform" name="usereditform" method="post" action="user_edit.php" enctype="multipart/form-data">
                <fieldset>
                    <legend>User information</legend>
                    <span class="formfield">First name:*</span><input type="text" name="firstname" id="firstname" value="<?php echo $firstname;?>" class="required"><br>
                    <span class="formfield">Last name:*</span><input type="text" name="lastname" id="lastname" value="<?php echo $lastname;?>" class="required"><br>
                    <span class="formfield">Username:</span><input type="text" name="username" id="username" value="<?php echo $username;?>" disabled="disabled"><br>
                    <span class="formfield">Email:*</span><input type="text" name="email" id="email" value="<?php echo $email;?>" class="required"><br>
                    <span class="formfield">Type of Institution:*</span><select name="institutiontype" id="institutiontype">
                        <option value="university"   <?php echo ($institutiontype == "university") ? 'selected="selected"' : "";?>>University</option>
                        <option value="researchinstitute" <?php echo ($institutiontype == "researchinstitute") ? 'selected="selected"' : "";?>>Research Institute</option>
                        <option value="company"   <?php echo ($institutiontype == "company") ? 'selected="selected"' : "";?>>Company</option>
                        <option value="other"   <?php echo ($institutiontype == "other") ? 'selected="selected"' : "";?>>Other (specify under comments)</option>
                    </select><br>
                    <span class="formfield">Institution:*</span><input type="text" name="institution" id="institution" value="<?php echo $institution;?>" class="required"><br>
                    <span class="formfield">Country:*</span><select name="country" id="country">
                        <option value="" <?php echo (($country == '') ? 'selected="selected"' : "");?></option>
                        <?php
                            foreach (countries() as $c) {
                                echo '<option value="'.$c.'" '.(($country == $c) ? 'selected="selected"' : "").'>'.$c.'</option>';
                            }
                        ?>
                        </select><br>
                    <span class="formfield">Password:</span><input type="password" name="passwd" id="passwd" value=""><label id="passwderror" class="error" for="passwd" generated="true" style="display: inline;"></label><br>
                    <span class="formfield">Retype Password:</span><input type="password" name="retypepasswd" id="retypepasswd" value=""><br>
                </fieldset>
                <fieldset>
                    <legend>User quotas</legend>
                    <span class="qtip_show" title="Maximum number of concurrently scheduled/running tests at any time. Tests that have just finished but whose results are not yet fully processed, are also taken into account."><span class="formfield-extrawide">Maximum number of concurrently scheduled/running tests:</span><?php echo $quota_tests;?> tests</span></span><br>
                    <span class="qtip_show" title="Maximum total runtime of all scheduled/running tests. Tests that have just finished but whose results are not yet fully processed, are also taken into account."><span class="formfield-extrawide">Maximum total runtime of all scheduled/running tests:</span><?php echo $quota_runtime;?> min</span><br>
                    <span class="qtip_show" title="After the retention time expired, a test is deleted from the database. You will get an email before the deletion but it is your responsability to save your test data externally before it is deleted."><span class="formfield-extrawide">Retention time for test results:</span><?php echo $retention_time;?> days</span><br>
                </fieldset>
                <fieldset>
                    <legend>Various</legend>
                    <span class="qtip_show" title="If checked, you will not receive test status emails from FlockLab. Error messages are still sent though."><span class="formfield-extrawide">Disable info mails about test status:</span></span><input type="checkbox" name="disableinfomails" id="disableinfomails" value="1" <?php echo ($disable_infomails == "1") ? 'checked="checked"' : '';?>><br>
                </fieldset>
                <p></p>
                <input type="hidden" name="first" value="no">
                <input type="hidden" name="quotaruntime" value="<?php echo $quota_runtime;?>">
                <input type="hidden" name="quotatests" value="<?php echo $quota_tests;?>">
                <input type="hidden" name="retentiontime" value="<?php echo $retention_time;?>">
                <input type="hidden" name="username" value="<?php echo $username;?>">
                <input type="submit" value="Save">
                <input type="button" value="Cancel" onClick="window.location='index.php'">
            </form>

<?php
do_layout('User Account','User Account');
?>
