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
    
    // Check if session expired and restart a new one if it did:
    if(isset($_SESSION['expires']) && $_SESSION['expires'] < $_SERVER['REQUEST_TIME'] ) {
        destroy_session();
        session_start();
        session_regenerate_id();
    }
    
    // Set session timeout:
    $_SESSION['expires'] = $_SERVER['REQUEST_TIME'] + $CONFIG['webserver']['sessionexpiretime'];

    $hostname = $_SERVER['HTTP_HOST'];
    $path = dirname($_SERVER['PHP_SELF']);

    // Redirect to login page if user not logged in yet:
    if (!isset($_SESSION['logged_in']) || !$_SESSION['logged_in']) {
        // check for login parameters
        if (!(isset($_POST['username']) && isset($_POST['password']) && do_login($_POST['username'], $_POST['password']))) {
            if (count($_POST)==0)
                $_SESSION['request_path']=$_SERVER['REQUEST_URI'];    //$_SERVER['SCRIPT_NAME']
            else
                unset($_SESSION['request_path']);
            header('Location: https://'.$hostname.($path == '/' ? '' : $path).'/login.php'); 
            exit;
        }
    }
?>
