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
    $configfile = "/home/flocklab/flocklab_config.ini";
    if (!file_exists($configfile)) {
        die("File '$configfile' not found!");
    }
    $CONFIG = parse_ini_file($configfile, true);
    if ($CONFIG === FALSE) {
        die("Failed to parse config file!");
    }
    if (!file_exists($CONFIG['webserver']['sessiondir'])) {
        mkdir ($CONFIG['webserver']['sessiondir']);
    }
    session_save_path($CONFIG['webserver']['sessiondir']);
?>