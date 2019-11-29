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
	
	// Check if session expired and restart a new one if it did:
	if(isset($_SESSION['expires']) && $_SESSION['expires'] < $_SERVER['REQUEST_TIME'] ) {
	    destroy_session();
	    session_start();
	    session_regenerate_id();
	}
	
	// Set session timeout:
	$_SESSION['expires'] = $_SERVER['REQUEST_TIME'] + $CONFIG['session']['expiretime'];

	$hostname = $_SERVER['HTTP_HOST'];
	$path = dirname($_SERVER['PHP_SELF']);

	// Redirect to login page if user not logged in yet:
	if (!isset($_SESSION['logged_in']) || !$_SESSION['logged_in']) {
		// check for login parameters
		if (!(isset($_POST['username']) && isset($_POST['password']) && do_login($_POST['username'], $_POST['password']))) {
			if (count($_POST)==0)
				$_SESSION['request_path']=$_SERVER['SCRIPT_NAME'];
			else 
				unset($_SESSION['request_path']);
			header('Location: https://'.$hostname.($path == '/' ? '' : $path).'/login.php'); 
			exit;
		}
	}
?>
