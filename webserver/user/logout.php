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
<?php
    require_once('include/libflocklab.php');
    
    session_start();
     
    // Destroy the session (tghis will also remove the temp directory).     
    destroy_session();

    $hostname = $_SERVER['HTTP_HOST'];
    $path = dirname($_SERVER['PHP_SELF']);

    header('Location: https://'.$hostname.($path == '/' ? '' : $path).'/login.php');
?>
