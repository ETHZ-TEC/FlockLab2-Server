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
<?php include_once('include/presets.php');?>
<?php
    // provide archive
    if (isset($_POST['testid']) && is_numeric($_POST['testid']) && check_testid($_POST['testid'],$_SESSION['serv_users_key'])) {
        $testid = $_POST['testid'];
        // check file
        $archivepath =  $CONFIG['testmanagementserver']['archivedir'];
        $archive = 
        $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"ls -l ".$archivepath.'/'.$testid.".tar.gz\"";
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
            $cmd = "ssh ".$CONFIG['testmanagementserver']['sshflags']." ".$CONFIG['testmanagementserver']['user']."@".$CONFIG['testmanagementserver']['host']." \"cat ".$archivepath.'/'.$testid.".tar.gz\"";
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
