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
    require_once('include/libflocklab.php');
    session_start();

    $first = ((isset($_REQUEST['first'])) && ($_REQUEST['first'] == "no")) ? false : true;    
    $login_msg = "Login failed.";
    
    # if already logged in, then redirect to index.php
    if (isset($_SESSION['logged_in']) && $_SESSION['logged_in']) {
        header('Location: https://'.$_SERVER[HTTP_HOST].substr($_SERVER[REQUEST_URI], 0, strrpos($_SERVER[REQUEST_URI], "/") + 1)."index.php");
    }
    
    if ($_SERVER['REQUEST_METHOD'] == 'POST') {
        $hostname = $_SERVER['HTTP_HOST'];
        $path = dirname($_SERVER['PHP_SELF']);
        
        // Forward to next page:
        if ($_SERVER['SERVER_PROTOCOL'] == 'HTTP/1.1') {
          if (substr(php_sapi_name(), 0, 3) == 'cgi') {
            header('Status: 303 See Other');
          }
          else {
            header('HTTP/1.1 303 See Other');
          }
        }
        
        $dologin = do_login($_POST['username'], $_POST['password']);
        if ($dologin === true) {
            if (isset($_SESSION['request_path'])) {
                header('Location: https://'.$hostname.$_SESSION['request_path']);
                unset($_SESSION['request_path']);
            }
            else {
                header('Location: https://'.$hostname.($path == '/' ? '' : $path).'/index.php');
            }
            exit;
        }
        else if ($dologin === false){
            header('Location: https://'.$hostname.($path == '/' ? '' : $path).'/login.php?first=no'); 
            exit;
        }
        else {
            $login_msg = $dologin;
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
    <title>FlockLab - Login</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="AUTHOR" content="ETH Zurich, Christoph Walser, CH-8092 Zurich, Switzerland">
    <meta name="COPYRIGHT" content="ETH Zurich, Switzerland">
    <meta name="LANGUAGE" content="English">
    <meta name="ROBOTS" content="noindex, nofollow">
    <meta name="DATE" content="2011">
    <script type="text/javascript" src="scripts/jquery-latest.js"></script>
    <script type="text/javascript" src="scripts/timezone-flocklab.js"></script>
</head>
<body>
    <div id="container" class="container">
        <div id="header" class="header">
            <a href="http://www.flocklab.ethz.ch"><img alt="FlockLab" src="pics/flocklab_eth_logo.png"></a>
        </div> <!-- END header -->
        <div id="content" class="content">
            <div id="login" class="login">
            <?php 
                if (!$first) {
                    echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
                    echo "<p>".$login_msg."</p>";
                    echo "</div><p></p>";
                }
            ?>
                    <div id="loginspan">
                    <p class="warning">
                    <img alt="" src="pics/icons/att.png">
                    Javascript seems to be turned off in your browser. Turn it on to be able to use FlockLab.
                    </p>
                </div>    
            </div> <!-- END login -->
        </div> <!-- END content -->
        <div style="clear:both"></div>
    </div> <!-- END container -->
    
    <script type="text/javascript">
        document.getElementById('loginspan').innerHTML = '<form action="login.php" method="post"><table><tr><td colspan="2"><b>User Login for FlockLab<\/b><\/td><\/tr><tr><td>Username:<\/td><td><input name="username" id="username" type="text"><\/td><\/tr><tr><td>Password:<\/td><td><input name="password" type="password"><input name="first" type="hidden" value="no"><\/td><\/tr><tr><\/tr><tr><td><\/td><td>No login yet? Register here <a href="user_register.php"><img src="pics/icons/right_arrow.png"><\/a><br>Forgot password? Recover it <a href="user_passwordrecovery.php"><img src="pics/icons/right_arrow.png"><\/a><\/td><\/tr><tr><td><\/td><td><input type="submit" value="Login"><\/td><\/tr><\/table><\/form>';
        document.getElementById('username').focus();
    </script>
</body>
</html>
