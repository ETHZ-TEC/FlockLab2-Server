<?php 
	/*
	 * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
	 * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
	 * __license__     = "GPL"
	 * __version__     = "$Revision: 2888 $"
	 * __date__        = "$Date: 2014-08-22 10:01:11 +0200 (Fri, 22 Aug 2014) $"
	 * __id__          = "$Id: index.php.normal 2888 2014-08-22 08:01:11Z rlim $"
	 * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/index.php.normal $" 
	 */
?>
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
	if (!isset($_SESSION['is_admin']) || !$_SESSION['is_admin'])
		exit(1);
?>
<script type="text/javascript" src="scripts/jquery-ui-1.8.21.custom.min.js"></script>
<script type="text/javascript" src="scripts/protovis-d3.3.js"></script>
<?php
echo '<h1>Admin Statistics</h1><table>';
				$testoverhead = 2*3*60; // time needed to setup and clean up a test in seconds
				$db = db_connect();
				$sql = "select count(*) as num from tbl_serv_users";
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				$row = mysqli_fetch_array($rs);
				echo '<tr><td><b>Number of users</b></td><td>'.$row['num'].'</td></tr>';
				
				echo '<tr><td><b>Users by institution</b></td><td></td></tr>';
				$sql = 'select institution, count(institution) as num from tbl_serv_users group by institution';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				while ($row = mysqli_fetch_array($rs)) {
					echo '<tr><td>&nbsp;&nbsp;'.$row['institution'].'</td><td>'.$row['num'].'</td></tr>';
				}
				
				echo '<tr><td><b>Users by country</b></td><td></td></tr>';
				$sql = 'select country, count(country) as num from tbl_serv_users group by country';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				while ($row = mysqli_fetch_array($rs)) {
					echo '<tr><td>&nbsp;&nbsp;'.$row['country'].'</td><td>'.$row['num'].'</td></tr>';
				}
				
				// Tests, by nodes, with setup and cleanup
				$sql = 'select year(time_start_act) as y, count(*) as num from tbl_serv_tests where test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null group by year(time_start_act) having y is not null';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				$testcount=Array();
				while ($row = mysqli_fetch_array($rs)) {
					$year = $row['y'];
					echo '<tr><td><b>Number of tests '.$year.' (avg [max] setup / cleanup time)</td><td>'.$row['num'].'</td></tr>';
					$testcount[$year] = $row['num'];
					$sql = 'select year(time_start_act), pname, count(*) as c, time_start_act, b.test_status_preserved, avg(setuptime) as tsetup, avg(cleanuptime) as tcleanup, max(setuptime) as tsetupmax, max(cleanuptime) as tcleanupmax from (select distinct test_fk, tbl_serv_platforms.name as pname from tbl_serv_map_test_observer_targetimages left join tbl_serv_targetimages on (targetimage_fk = serv_targetimages_key) left join tbl_serv_platforms on (platforms_fk = serv_platforms_key)) as a left join tbl_serv_tests as b on (a.test_fk = b.serv_tests_key) where year(time_start_act) = '.$year.' and (b.test_status_preserved in ("finished", "retention expiring", "synced") or b.test_status_preserved is null) and time_start_act is not null and pname is not null group by pname order by time_start_act, pname';
					$rs2 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
					while ($row = mysqli_fetch_array($rs2)) {
						echo '<tr><td>&nbsp;&nbsp;'.$row['pname'].'</td><td>'.$row['c'].' ('.round($row['tsetup']).' ['.round($row['tsetupmax']).'] / '.round($row['tcleanup']).'  ['.round($row['tcleanupmax']).'] s)</td></tr>';
					}
					// Tests by service
					$sql = 'select year(time_start_act) as y, sum(1) as num_all, sum(ExtractValue(testconfig_xml, "count(/testConf/serialConf|/testConf/serialReaderConf)") > 0) as num_serial, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioTracingConf|/testConf/gpioMonitorConf)") > 0) as num_tracing, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioActuationConf|/testConf/gpioSettingConf)") > 0) as num_actuation, sum(ExtractValue(testconfig_xml, "count(/testConf/powerProfilingConf|/testConf/powerprofConf)") > 0) as num_power from tbl_serv_tests where year(time_start_act) = '.$year.' and (test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null)';
					$rs3 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
					$row = mysqli_fetch_array($rs3);
					foreach (array('Serial'=>'num_serial','GPIO tracing'=>'num_tracing','GPIO actuation'=>'num_actuation','Power profiling'=>'num_power') as $service=>$field) {
						echo '<tr><td>&nbsp;&nbsp;'.$service.'</td><td>'.$row[$field].' ('.(round($row[$field] / $row['num_all'] * 100 )).'%)</td></tr>';
					}
				}
				
				// Users by service and node type
				$sql = 'select year(time_start_act) as y, count(distinct owner_fk) as num from tbl_serv_tests where test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null group by year(time_start_act) having y is not null';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				while ($row = mysqli_fetch_array($rs)) {
					$year = $row['y'];
					$num_users = $row['num'];
					echo '<tr><td><b>Number of active users in '.$year.'</td><td>'.$row['num'].'</td></tr>';
					$sql = 'select year(time_start_act), pname, count(distinct owner_fk) as c, time_start_act, b.test_status_preserved from (select distinct test_fk, tbl_serv_platforms.name as pname from tbl_serv_map_test_observer_targetimages left join tbl_serv_targetimages on (targetimage_fk = serv_targetimages_key) left join tbl_serv_platforms on (platforms_fk = serv_platforms_key)) as a left join tbl_serv_tests as b on (a.test_fk = b.serv_tests_key) where year(time_start_act) = '.$year.' and (b.test_status_preserved in ("finished", "retention expiring", "synced") or b.test_status_preserved is null) and time_start_act is not null and pname is not null group by pname order by time_start_act, pname';
					$rs2 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
					while ($row = mysqli_fetch_array($rs2)) {
						echo '<tr><td>&nbsp;&nbsp;'.$row['pname'].'</td><td>'.$row['c'].' ('.(round($row['c']/$num_users * 100)).'%)</td></tr>';
					}
					
					$sql = 'select sum(num_all > 0) as user_all, sum(num_serial > 0) as user_serial, sum(num_tracing > 0) as user_tracing, sum(num_actuation > 0) as user_actuation, sum(num_power > 0) as user_power from (select year(time_start_act) as y, sum(1) as num_all, sum(ExtractValue(testconfig_xml, "count(/testConf/serialConf|/testConf/serialReaderConf)") > 0) as num_serial, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioTracingConf|/testConf/gpioMonitorConf)") > 0) as num_tracing, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioActuationConf|/testConf/gpioSettingConf)") > 0) as num_actuation, sum(ExtractValue(testconfig_xml, "count(/testConf/powerProfilingConf|/testConf/powerprofConf)") > 0) as num_power from tbl_serv_tests where year(time_start_act) = '.$year.' and (test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null) group by owner_fk) as stats;';
					$rs3 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
					$row = mysqli_fetch_array($rs3);
					foreach (array('Serial'=>'user_serial','GPIO tracing'=>'user_tracing','GPIO actuation'=>'user_actuation','Power profiling'=>'user_power') as $service=>$field) {
						echo '<tr><td>&nbsp;&nbsp;'.$service.'</td><td>'.$row[$field].' ('.(round($row[$field] / $row['user_all'] * 100 )).'%)</td></tr>';
					}
				}
				
				// Occupied per year
				$sql = 'select year(time_start_act) as y, min(time_start_act) as minp, max(time_end_act) as maxp, max(time_end_act - time_start_act), sum(timestampdiff(SECOND,time_start_act,time_end_act)) as duration from tbl_serv_tests where (test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null) and (time_end_act is not null and time_start_act is not null and time_start_act < time_end_act and timestampdiff(SECOND,time_start_act,time_end_act) < 72 * 3600) group by  year(time_start_act)';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				while ($row = mysqli_fetch_array($rs)) {
					echo '<tr><td><b>Time occupied '.$row['y'].'</b></td><td>'.round((($row['duration'] + $testcount[$row['y']] * $testoverhead) / 3600)).' hours ('.round((($row['duration'] + $testcount[$row['y']] * $testoverhead) / (strtotime($row['maxp'])-strtotime($row['minp'])) * 100)).'%)</td></tr>';
				}
				
				// last year, weekly resolution
				$sql = 'select year(time_start_act) as y, week(time_start_act) as w, count(*) as num from tbl_serv_tests where 
								datediff(DATE_SUB(DATE_SUB(CURDATE(),INTERVAL (DAY(CURDATE())-1) DAY),INTERVAL 12 MONTH),time_start_act) <=0 AND
								(test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null)
								group by year(time_start_act), week(time_start_act) having y is not null';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				$testcount = Array();
				while ($row = mysqli_fetch_array($rs)) {
					$testcount[$row['y'].'-'.$row['w']] = $row['num'];
				}
				$sql = 'select year(time_start_act) as y, week(time_start_act) as w, min(time_start_act) as minp, max(time_end_act) as maxp, max(timestampdiff(SECOND,time_start_act,time_end_act)), sum(timestampdiff(SECOND,time_start_act,time_end_act)) as duration from tbl_serv_tests
					where
					datediff(DATE_SUB(DATE_SUB(CURDATE(),INTERVAL (DAY(CURDATE())-1) DAY),INTERVAL 12 MONTH),time_start_act) <=0 AND
					(test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null) and
					(time_end_act is not null and time_start_act is not null and time_start_act < time_end_act and timestampdiff(SECOND,time_start_act,time_end_act) < 72 * 3600)
					group by year(time_start_act), week(time_start_act) having y is not null';
				$rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
				$uval=Array();$uweek=Array();
				while ($row = mysqli_fetch_array($rs)) {
					// echo '<tr><td>&nbsp;&nbsp;Time occupied '.$row['y'].' week '.$row['w'].'</td><td>'.round((($row['duration'] + $testcount[$row['y'].'-'.$row['w']] * $testoverhead) / 3600)).' hours ('.round((($row['duration'] + $testcount[$row['y'].'-'.$row['w']] * $testoverhead) / (7*24*3600) * 100)).'%)</td></tr>';
					array_push($uval, round((($row['duration'] + $testcount[$row['y'].'-'.$row['w']] * $testoverhead) / (7*24*3600) * 100)));
					array_push($uweek, $row['w']);
				}
				echo '
				<script type="text/javascript">
var uval=['.implode(',',$uval).'];
var uweek=['.implode(',',$uweek).'];
$(document).ready(function() {
var vis = new pv.Panel()
	.canvas("usagebars")
	.width(860)
	.height(125);
	
vis.add(pv.Rule)
	.data(pv.range(0, 101, 50))
	.bottom(function(d) { return d + 10.5;})
	.left(26)
	.width(794)
	.add(pv.Label).textAlign("right");

vis.add(pv.Bar)
	.data(pv.range(0, uval.length, 1))
	.width(10)
	.height(function(d){ return uval[d];})
	.bottom(10)
	.left(function() {return this.index * 14 + 26;})
	.anchor("bottom").add(pv.Label)
	.text(function(d) {return uweek[d];})
	.textBaseline("top");
vis.add(pv.Label)
	.left(10)
	.top(50)
	.textAlign("center")
	.textAngle(-0.5 * Math.PI)
	.text("Utilization (%)");
	
vis.render();
});
</script>
				';
				mysqli_close($db);
				?>
				<tr><td colspan="2"><b>Weekly utilization during the most recent 12 months</b><div id="usagebars"></div></td></tr>
				</table>
<?php
do_layout('Statistics','Statistics');
?>
