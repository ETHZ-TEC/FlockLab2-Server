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
<?php require_once('config.php'); ?>
<?php

/* 
  * Helper functions for Google reCAPTCHA v2
  *
  * Notes
  * - insert the following line within the <head> section:
  *   <script src='https://www.google.com/recaptcha/api.js'></script>
  * - insert the following line where you want the captcha to appear (must be within a <form>):
  *   <?php recaptcha_print(); ?>
  */


/* CONFIG */
define("RECAPTCHA_SITEKEY", $CONFIG['recaptcha']['sitekey']);
define("RECAPTCHA_SECRETKEY", $CONFIG['recaptcha']['secretkey']);
define("RECAPTCHA_VERIFY_SERVER", "https://www.google.com/recaptcha/api/siteverify");


if (RECAPTCHA_SECRETKEY == null || RECAPTCHA_SECRETKEY == '') {
    flocklab_die("To use reCAPTCHA you must get an API key from <a href='https://www.google.com/recaptcha/admin/create'>https://www.google.com/recaptcha/admin/create</a>");
}
  

function recaptcha_qsencode($data) 
{
    $req = "";
    foreach ( $data as $key => $value )
        $req .= $key . '=' . urlencode( stripslashes($value) ) . '&';
    return substr($req, 0, strlen($req) - 1);  // remove '&' at end
}

/*
##############################################################################
#
# recaptcha_print
# 
# prints (inserts) the CAPTCHA challenge
#
##############################################################################
*/
function recaptcha_print() 
{
    echo '<div class="g-recaptcha" data-sitekey="'.RECAPTCHA_SITEKEY.'"></div>';
}
 
/*
##############################################################################
#
# recaptcha_verify
# 
# verifies a previously submitted captcha response
#
# @return: true if response is valid, false otherwise
#
##############################################################################
*/
function recaptcha_verify()
{    
    $response = $_POST["g-recaptcha-response"];
    if ($response == null || strlen($response) == 0) {
        return false;
    }
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, RECAPTCHA_VERIFY_SERVER);
    // Set so curl_exec returns the result instead of outputting it.
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, recaptcha_qsencode(array ('secret' => RECAPTCHA_SECRETKEY,
                                                                   'response' => $response,
                                                                   'remoteip' => $_SERVER["REMOTE_ADDR"])));
    // Get the response and close the channel.
    $response = curl_exec($ch);
    if ($response === false) {
        echo "cURL failed: ".curl_error($ch)."<br />";
        return false;
    }
    curl_close($ch);

    $answers = explode("\n", $response[0]);
    return $answers[0];
}
?>
