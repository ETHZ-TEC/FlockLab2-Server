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
$path="/home/flocklab/flocklab_downloads/shell-tool/";
$filename="flocklab";

// make sure the file exists
if (!file_exists($path.$filename)) {
  echo "file not found";
  exit(1);
}
header('Content-Disposition: attachment; filename="flocklab_tool.tar.gz"');
passthru('cd '.$path.'; tar -czvf - '.$filename);

?>
