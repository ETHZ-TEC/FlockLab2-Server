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
require_once('include/auth.php');
$script_starttime = microtime(true);
if (isset($_GET['t']) && isset($_GET['o']) && isset($_GET['s']) && isset($_GET['m']) && is_numeric($_GET['t']) && is_numeric($_GET['o']) && is_numeric($_GET['s']) && is_numeric($_GET['m'])) {
	$testid = $_GET['t'];
	$obsid = $_GET['o'];
	$starttime = $_GET['s'];
	// check access rights for this use and this tests
	// check if directory exists
	// viz/testid_userfk
	$viz_path = $CONFIG['viz']['dir'].'/'.$testid.'_'. $_SESSION['serv_users_key'];
	if (!file_exists ($viz_path)) {
// 	if (!check_testid($testid, $_SESSION['serv_users_key'])) {
		header("HTTP/1.0 401 Unauthorized");
		exit();
	}
	
	// find viz image for request
	// images are in $CONFIG['viz']['dir']/<testid>
	$oldest = -1;
	
	if ($_GET['m']==0) { // power
		$searchname = 'power';
		$searchending = 'png';
	}
	else {
		$searchname = 'gpiom';
		$searchending = 'json';
	}

	foreach (glob($viz_path.'/'.$searchname.'_'.$obsid.'*.'.$searchending) as $filename) {
		if ((preg_match('/'.$searchname.'_'.$obsid.'_([0-9]*)\.'.$searchending.'/', $filename, $matches)>0) && ($matches[1]>$starttime)) {
			if ($oldest<0 || $oldest > $matches[1]) {
				$oldest=$matches[1];
				$imgfilename=$filename;
			}
			else {
				// remove old image
			}
		}
	}


	// output
	if ($oldest > 0) {
		header("Processing-Time: ".(1000*(microtime(true) - $script_starttime))." ms");
		header("Start-Time: ".$oldest);
		//header("Observer-Id: ".$obsid);
		if ($_GET['m']==0) {
			if (!isset($_GET['q'])) {
				//header("HTTP/1.0 304 Not Modified");
				header_remove("Cache-Control");
				header_remove("Pragma");
				header("Expires: ".date(DATE_RFC1123, time() + 300));
				header("Content-Type: image/png");
				header("Start-Time: ".$oldest);
				readfile ($imgfilename);
			}
			else {
			// remove old images
	// 			unlink($CONFIG['viz']['dir'].'/'.$testid.'/'.$imgfilename);
			}
		}
		else {
			ob_start("ob_gzhandler");
			header("Start-Time: ".$oldest);
			readfile ($imgfilename);
		}
	}
	else {
		// use some error header to signal missing or no data
		header("HTTP/1.0 410 Vizualization data not available");
	}
}
else if (isset($_GET['t']) && is_numeric($_GET['t'])) {
	// look for directory and get timerange of available viz data
	$testid = $_GET['t'];
	$viz_path = $CONFIG['viz']['dir'].'/'.$testid.'_'. $_SESSION['serv_users_key'];
	if (!file_exists ($viz_path)) {
		header("HTTP/1.0 401 Unauthorized");
		exit();
	}
	$range_min = -1;
	$range_max = -1;
	
	foreach (glob($viz_path.'/*') as $filename) {
		if (preg_match('/[a-z]*_[0-9]*_([0-9]*)\..*/', $filename, $matches) > 0) {
			if ($range_min<0 || $range_min > $matches[1]) {
				$range_min=$matches[1];
			}
			else if ($range_max<0 || $range_max < $matches[1]) {
				$range_max=$matches[1];
			}
		}
	}
	header("Range-Min: ".$range_min);
	header("Range-Max: ".$range_max);
}
else {
	// use some error header to signal wrong request
	header("HTTP/1.0 400 Bad Request");
}
?>
