<?php 
	/*
	 * __author__      = "Roman Lim <lim@tik.ee.ethz.ch>"
	 * __copyright__   = "Copyright 2016, ETH Zurich, Switzerland"
	 * __license__     = "GPL"
	 * __version__     = "$Revision: 2435 $"
	 * __date__        = "$Date: 2013-09-27 16:03:15 +0200 (Fri, 27 Sep 2013) $"
	 * __id__          = "$Id: config.php 2435 2013-09-27 14:03:15Z walserc $"
	 * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/include/config.php $" 
	 */
?>
<?php
require_once('include/config.php');
    
/*
##############################################################################
#
# flocklab_log
#
##############################################################################
*/
function flocklab_log($msg)
{
	global $CONFIG;
	$logfile = $CONFIG['testmanagementserver']['logdir']. '/webserver_user.log';
	$date = date('d/m/Y H:i:s T');
	$msg = trim($msg) ."\n";
	file_put_contents ( $logfile , $date.' - '.$_SERVER['SCRIPT_NAME'].' - '. (isset($_SESSION['username'])?$_SESSION['username']:'no user').' - '.$msg , $flags = FILE_APPEND );
}

?>
