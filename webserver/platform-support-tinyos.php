<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision: 1296 $"
     * __date__        = "$Date: 2011-08-12 17:06:17 +0200 (Fri, 12 Aug 2011) $"
     * __id__          = "$Id: newtest.php 1296 2011-08-12 15:06:17Z walserc $"
     * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/newtest.php $" 
     */
?>
<?php
$dir="/home/flocklab/flocklab_downloads/platform-support/tinyos-2.x/";

// make sure the directory exists
exec('cd '.$dir, $output, $retval);
if ($retval != 0) {
  echo "error code $retval";
  exit(1);
}

// create tar.gz
header('Content-Type: application/x-gzip');
header('Content-Disposition: attachment; filename="flocklab_tinyos.tar.gz"');
passthru('cd '.$dir.';tar -czvf - ./');

?>
