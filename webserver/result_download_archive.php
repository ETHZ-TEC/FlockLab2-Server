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
<?php include_once('include/presets.php');?>
<?php
    // provide archive
    if (isset($_POST['testid']) && is_numeric($_POST['testid']) && (check_testid($_POST['testid'],$_SESSION['serv_users_key']) || $_SESSION['is_admin'])) {
        $testid = $_POST['testid'];
        // check file
        $archivepath =  $CONFIG['testmanagementserver']['archivedir'];
        $archive = 
        $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"ls -l ".$archivepath.'/'.$testid.".tar.gz\"";
        exec($cmd , $output, $ret);
        if ($ret > 0) {
            echo json_encode(array('status'=>'error', 'output'=>'data not available'));
            exit();
        }
        else {
            $size = explode(' ', $output[0]);
            $size = preg_replace('/([0-9]*) .*/','$1',$size[4]);
             if (strlen($size)>0)
                 $size=intval($size);
             else {
                echo json_encode(array('status'=>'error', 'output'=>'could not determine archive size'));
                exit();
             }
             if (!isset($_POST['query']) || $_POST['query']!='get') {
                echo json_encode(array('status'=>'success', 'testid'=>$testid));
                exit();
             }
            $cmd = "ssh ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"cat ".$archivepath.'/'.$testid.".tar.gz\"";
            $stream = popen($cmd, "r");
            // Send the file to the user's browser:
            header("Content-Type: application/x-gzip");
            header("Content-Disposition: attachment; filename=\"flocklab_testresults_" . $_POST['testid'] . ".tar.gz\"");
            header("Content-Length: ".$size);
            $chunksize = 512*1024;
            do {
                echo fread($stream, $chunksize);
                set_time_limit (30);
            } 
            while (!feof($stream));
            pclose($stream);
        }
    }
    else {
        echo json_encode(array('status'=>'error', 'output'=>'unknown testid'));
    }
?>
