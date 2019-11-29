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
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
	$errors = array();
  
	if (isset($_POST['removeit']) && isset($_POST['testid'])) {
		if (check_testid($_POST['testid'], $_SESSION['serv_users_key'])) {
			// remove test
			$db = db_connect();
			// remove images too ?
			$rmimages = array();
			if (isset($_POST['remove_images'])) {
				// search for images that are only used in this test
				$sql = 'SELECT COUNT(DISTINCT test_fk) as DC, a.targetimage_fk
					FROM (
					SELECT targetimage_fk, serv_tests_key
					FROM
					tbl_serv_tests LEFT JOIN tbl_serv_map_test_observer_targetimages ON (serv_tests_key = test_fk)
					WHERE owner_fk = '.$_SESSION['serv_users_key'].' AND serv_tests_key = '.mysqli_real_escape_string($db, $_POST['testid']).'
					GROUP BY `targetimage_fk`
					) as a
					LEFT JOIN tbl_serv_map_test_observer_targetimages as b ON (a.targetimage_fk = b.targetimage_fk)
					GROUP BY targetimage_fk
					HAVING DC=1';
				$res = mysqli_query($db, $sql) or flocklab_die('Cannot remove test: ' . mysqli_error($db));
				$num = mysqli_num_rows($res);
				while ($num-- > 0) {
					$row = mysqli_fetch_assoc($res);
					array_push($rmimages, $row['targetimage_fk']);
				}
			}
			mysqli_close($db);
			// delete related image binaries (keep metadata for statistics)
			$db = db_connect();
			foreach($rmimages as $imid) {
				$sql =  'UPDATE `tbl_serv_targetimages`
						SET `binary` = NULL
						WHERE `serv_targetimages_key` = '.$imid;
				mysqli_query($db, $sql) or flocklab_die('Cannot remove test: ' . mysqli_error($db));
			}
			// mark test to be deleted
			$sql =  'UPDATE tbl_serv_tests SET test_status="todelete"
				WHERE `owner_fk` = '.$_SESSION['serv_users_key'].' AND `serv_tests_key` = ' .mysqli_real_escape_string($db, $_POST['testid']);
			mysqli_query($db, $sql) or flocklab_die('Cannot remove test: ' . mysqli_error($db));
			// remove resource allocations
			$sql =  'DELETE from tbl_serv_resource_allocation
				WHERE `test_fk` = ' .mysqli_real_escape_string($db, $_POST['testid']);
			mysqli_query($db, $sql) or flocklab_die('Cannot remove test: ' . mysqli_error($db));
			mysqli_close($db);
		}
		else
			array_push($errors, "Test does not belong to you.");
	}
	if (!isset($_POST['testid'])) 
		array_push($errors, "Unknown testid.");
		
	if (isset($_POST['removeit']) && isset($_POST['testid']) && count($errors)==0) {
		echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
		echo "<!-- cmd --><p>The test has been removed.</p><!-- cmd -->";
		echo "</div><p></p>";
		include('index.php');
		exit();
	}
	echo '
	<script type="text/javascript">
		$(document).ready(function() {
		$(".qtip_show").qtip( {
			content: {text: false},
			style  : "flocklab",
		});
		});
	</script>
	<h1>Manage Tests</h1>';

	if (count($errors)>0) {
		echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
		echo "<!-- cmd --><p>Error:</p><ul>";
		foreach ($errors as $error)
		echo "<li>" . $error . "</li>";
		echo "</ul></div><p><!-- cmd --></p>";
	}
	else {
		$db = db_connect();
		$sql =   "SELECT serv_tests_key, title, description, time_start_act, time_start_wish, time_end_act, time_end_wish, test_status, `targetimage_fk`
			FROM tbl_serv_tests  LEFT JOIN tbl_serv_map_test_observer_targetimages ON (serv_tests_key = test_fk)
			WHERE owner_fk = " . $_SESSION['serv_users_key'] . " AND serv_tests_key = ".mysqli_real_escape_string($db, $_POST['testid'])." AND test_status <> 'deleted' AND test_status <> 'todelete'
			GROUP BY `targetimage_fk`";
		$res = mysqli_query($db, $sql) or flocklab_die('Cannot fetch test information: ' . mysqli_error($db));
		$row = mysqli_fetch_assoc($res);
		// Find out the state of the test:
				$schedulable	= true;
				$planned		= false;
				$running		= false;
				$finished		= false;
				$preparing		= false;
				$cleaningup		= false;
				$failed 		= false;
				$aborting		= false;
				$syncing		= false;
				$synced			= false;
				$retentionexp	= false;
				switch($row['test_status']) {
					case "planned":
						$planned = true;
						break;
					case "preparing":
						$preparing = true;
						break;
					case "running":
						$running = true;
						break;
					case "cleaning up":
						$cleaningup = true;
						break;
					case "finished":
						$finished = true;
						break;
					case "not schedulable":
						$schedulable = false;
						break;
					case "failed":
						$failed = true;
						break;
					case "aborting":
						$aborting = true;
						break;
					case "syncing":
						$syncing = true;
						break;
					case "synced":
						$synced = true;
						break;
					case "retention expiring":
						$retentionexp = true;
						break;
				}
		echo '
		<form method="post" action="test_delete.php" enctype="multipart/form-data">
		<fieldset>
		<legend>Remove test</legend>
		<div class="warning"><div style="float:left;"><img alt="" src="pics/icons/att.png"></div>';
		// If the tests is running, it cannot be deleted but must rather be aborted. Show a corresponding warning:
		if ($preparing || $running || $cleaningup || $syncing) {
			echo  '
			<p>The test with ID '.$row['serv_tests_key'].' is currently in state "'.$row['test_status'].'" cannot be deleted but has rather to be aborted. 
			Please go back to the test overview and reload the table by clicking <a href="index.php">here</a>.</p>';
		} else {
			echo '
			<p>The following test will be removed:</p>
			<p><table>
			<tr><td>Test ID</td><td>'.$row['serv_tests_key'].'</td></tr>
			<tr><td>Title</td><td>'.$row['title'].'</td></tr>
			<tr><td>Description</td><td style="white-space:normal;">'.$row['description'].'</td></tr>
			<tr><td>State</td>';
			echo "<td>";
			echo "<img src='".state_icon($row['test_status'])."' height='16px' alt='".state_short_description($row['test_status'])."' title='".state_long_description($row['test_status'])."' class='qtip_show' />";
			echo " ".state_short_description($row['test_status']);
			echo '</td>
			</tr>
			<tr><td>Start</td>';
			// Start time: dependent of state of test
			if ($running || $cleaningup || $finished || $failed || $aborting || $syncing || $synced || $retentionexp) {
				$d = new DateTime($row['time_start_act']);
				echo "<td title='Actual start time' class='qtip_show time'>" . $d->format('U') . "</td>";
			}
			elseif ($planned || $preparing) {
				$d = new DateTime($row['time_start_wish']);
				echo "<td title='Planned start time' class='qtip_show'><i class='time'>" . $d->format('U') . "</i></td>";
			}
			elseif (!$schedulable)
				echo "<td title='Test is not schedulable' class='qtip_show'>n/a</td>";
						else
				echo "<td title='Test is in unknown state' class='qtip_show'>n/a</td>";
			echo '</tr>
			<tr><td>End</td>';
			// End time: dependent of state of test
			if ($planned || $preparing || $running || $cleaningup || $syncing || $synced || $retentionexp) {
				$d = new DateTime($row['time_end_wish']);
				echo "<td title='Planned end time' class='qtip_show'><i class='time'>" .$d->format('U'). "</i></td>";
			}
			elseif ($finished || $failed) {
				$d = new DateTime($row['time_end_act']);
				echo "<td title='Actual end time' class='qtip_show time'>" . $d->format('U') . "</td>";
			}
			elseif ($aborting)
				echo "<td title='Test is currently aborting' class='qtip_show'>n/a</td>";
			elseif (!$schedulable)
				echo "<td title='Test is not schedulable' class='qtip_show'>n/a</td>";
			else
				echo "<td title='Test is in unknown state' class='qtip_show'>n/a</td>";
			echo '</tr>
			<tr><td>Images used</td><td><ul>';
			if (isset($row['targetimage_fk']))
				echo '<li>'.$row['targetimage_fk'].'</li>';
			$num = mysqli_num_rows($res) - 1;
			while ($num-- > 0) {
			$row = mysqli_fetch_assoc($res);
			echo '<li>'.$row['targetimage_fk'].'</li>';
			}
			echo '</ul></td><tr>
			</table></p>
			<p><input type="checkbox" name="remove_images" values="1" /> Remove also test images that are used in this test.</p>
			</div><p></p>
			<input type="hidden" name="testid" value="'.htmlentities($_POST['testid']).'">
			<input type="submit" name="removeit" value="Remove test">';
		}
		echo '
		</fieldset>
		<p></p>
		</form>';
	}
	?>
<!-- END content -->
<?php
do_layout('Manage Tests','Manage Tests');
?>
