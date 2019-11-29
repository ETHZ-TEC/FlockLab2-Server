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
	
if (isset($_GET['p'])) {
	//debug();
	$platform = explode( '_' , $_GET['p']);
	$radio = count($platform) > 1?"LOWER(radio)='".strtolower($platform[1])."'":'(radio="" OR radio is NULL)';
	$platform = strtolower($platform[0]);
	// Connect to database and get available measurements:
	$db = db_connect();
	$sql = "SELECT serv_link_measurements_key, begin
		FROM `flocklab`.tbl_serv_web_link_measurements
		LEFT JOIN tbl_serv_platforms ON (serv_platforms_key = platform_fk)
		WHERE LOWER(name)='".mysqli_real_escape_string($db, $platform)."' AND ".$radio." AND links is not NULL
		ORDER BY begin ASC
		";
	$rs = mysqli_query($db, $sql) or flocklab_die('Error: ' . mysqli_error($db));
	mysqli_close($db);
	
	// Build the array of tests. If possible, append start and/or end time to the message:
	$tests = array(
		'dateTimeFormat'=>'iso8601',
		'events'=> array (),
	);
	while ($row = mysqli_fetch_array($rs)) {
		
		$d = new DateTime($row['begin']);
		$tests['events'][]=array(
			'start'=>$d->format(DATE_ISO8601),
			//'end'=>$d->format(DATE_ISO8601),
			'durationEvent'=>FALSE,
			'title'=>'',
			'description'=>$row['serv_link_measurements_key'],
		);
	}

	// JSON-encode the array and return it to the calendar:
	header('Content-Type: application/json; charset=utf-8');
	echo json_encode($tests);

}
else if (isset($_GET['q']) and is_numeric($_GET['q'])) {
	// Connect to database and get link measurements:
	$db = db_connect();
	$sql = "SELECT CONVERT(links USING utf8) as links 
		FROM `flocklab`.tbl_serv_web_link_measurements 
		WHERE serv_link_measurements_key=".$_GET['q'];
	$rs = mysqli_query($db, $sql) or flocklab_die('Error: ' . mysqli_error($db));
	mysqli_close($db);
	
	if (mysqli_num_rows($rs) == 1) {
		header('Content-Type: application/xml; charset=utf-8');
		$row = mysqli_fetch_array($rs);
		echo $row['links'];
	}

}
?>
