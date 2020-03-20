<?php 
    /*
     * __author__      = "Reto Da Forno <reto.daforno@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2017, ETH Zurich, Switzerland"
     * __license__     = "GPL"
     */
?>
<?php
set_include_path(get_include_path() . PATH_SEPARATOR . "/home/flocklab/webserver");

require_once('include/libflocklab.php');

if (!set_time_limit(120)) {
  die("unable to set max. execution time");
}

$statsFileName = "/home/flocklab/webserver/statistics.dat";


function collect_stats($filename)
{
  if (!is_string($filename)) return;

  $testoverhead = 2 * 1 * 60;           // config value
  
  // --- start data collection ---
  
  //$citations = shell_exec("./scripts/scholar.py -C 10650874796619438829 -c 1 | grep Citations -m 1 | awk '{ print $2 }'");  // citation count
  
  $db = db_connect();
  $sql = "select count(*) as num from tbl_serv_users";
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  $row = mysqli_fetch_array($rs);
  $usercnt = $row['num'];
  
  $sql = "select COUNT(*) as num from tbl_serv_users where datediff(DATE_SUB(DATE_SUB(CURDATE(),INTERVAL (DAY(CURDATE())-1) DAY),INTERVAL 12 MONTH),last_login) <=0 and is_active=1";
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  $row = mysqli_fetch_array($rs);
  $usercntactive = $row['num'];
  
  $sql = 'select country, count(country) as num from tbl_serv_users group by country';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  $countries['others'] = 0;
  $countrycnt = 0;
  while ($row = mysqli_fetch_array($rs)) {
    $countrycnt = $countrycnt + 1;
    if (intval($row['num']) < 5) {
      $countries['others'] += intval($row['num']);
    } else {
      $countries[$row['country']] = intval($row['num']);
    }
  }
  arsort($countries);
  $sql = 'select institution, count(institution) as num from tbl_serv_users group by institution';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  $institutions['others'] = 0;
  $institutioncnt = 0;
  while ($row = mysqli_fetch_array($rs)) {
    $institutioncnt = $institutioncnt + 1;
    if (intval($row['num']) < 5) {
      $institutions['others'] += intval($row['num']);
    } else {
      $institutions[$row['institution']] = intval($row['num']);
    }
  }
  arsort($institutions);
  // number of tests per year and mote, including service type
  $tests_per_year = Array();
  $testcnt = 0;
  $tests_per_mote = Array();
  $tmotetests_per_year = Array();
  $tmotetestcnt = 0;
  $dpptests_per_year = Array();
  $dpptestcnt = 0;
  $dpp2tests_per_year = Array();
  $dpp2testcnt = 0;
  $nrftests_per_year = Array();
  $nrftestcnt = 0;
  $serial_per_year = Array();
  $serialcnt = 0;
  $gpiotracing_per_year = Array();
  $gpiotracingcnt = 0;
  $gpioactuation_per_year = Array();
  $gpioactuationcnt = 0;
  $powerprof_per_year = Array();
  $powerprofcnt = 0;
  $sql = 'select year(time_start_act) as y, count(*) as num from tbl_serv_tests where time_start_act is not null group by year(time_start_act)';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  while ($row = mysqli_fetch_array($rs)) {
    $year = $row['y'];
    $tests_per_year[$year] = $row['num'];
    $testcnt = $testcnt + $row['num'];    
    // initialize with 0
    $tmotetests_per_year[$year] = 0;
    $dpptests_per_year[$year] = 0;
    $dpp2tests_per_year[$year] = 0;
    $nrftests_per_year[$year] = 0;
    $sql = 'select pname, count(*) as c from (select distinct test_fk, tbl_serv_platforms.name as pname from tbl_serv_map_test_observer_targetimages left join tbl_serv_targetimages on (targetimage_fk = serv_targetimages_key) left join tbl_serv_platforms on (platforms_fk = serv_platforms_key)) as a left join tbl_serv_tests as b on (a.test_fk = b.serv_tests_key) where year(time_start_act) = '.$year.' and pname is not null group by pname';
    $rs2 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
    while ($row = mysqli_fetch_array($rs2)) {
      if (array_key_exists($row['pname'], $tests_per_mote)) {
        $tests_per_mote[$row['pname']] = $tests_per_mote[$row['pname']] + $row['c'];
      } else {
        $tests_per_mote[$row['pname']] = $row['c'];
      }
      if ($row['pname'] == 'Tmote') {
        $tmotetests_per_year[$year] = round($row['c'] * 100 / $tests_per_year[$year]);
        $tmotetestcnt = $tmotetestcnt + $row['c'];
      } else if ($row['pname'] == 'DPP') {
        $dpptests_per_year[$year] = round($row['c'] * 100 / $tests_per_year[$year]);
        $dpptestcnt = $dpptestcnt + $row['c'];
      } else if ($row['pname'] == 'DPP2LoRa') {
        $dpp2tests_per_year[$year] = round($row['c'] * 100 / $tests_per_year[$year]);
        $dpp2testcnt = $dpp2testcnt + $row['c'];
      } else if ($row['pname'] == 'nRF5') {
        $nrftests_per_year[$year] = round($row['c'] * 100 / $tests_per_year[$year]);
        $nrftestcnt = $dpptestcnt + $row['c'];
      } 
    }
    // Tests by service
    $sql = 'select year(time_start_act) as y, sum(1) as num_all, sum(ExtractValue(testconfig_xml, "count(/testConf/serialConf|/testConf/serialReaderConf)") > 0) as num_serial, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioTracingConf|/testConf/gpioMonitorConf)") > 0) as num_tracing, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioActuationConf|/testConf/gpioSettingConf)") > 0) as num_actuation, sum(ExtractValue(testconfig_xml, "count(/testConf/powerProfilingConf|/testConf/powerprofConf)") > 0) as num_power from tbl_serv_tests where year(time_start_act) = '.$year;
    $rs3 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
    $row = mysqli_fetch_array($rs3);
    
    $serial_per_year[$year] = round($row['num_serial'] * 100 / $tests_per_year[$year]);
    $serialcnt = $serialcnt + $row['num_serial'];
    $gpiotracing_per_year[$year] = round($row['num_tracing'] * 100 / $tests_per_year[$year]);
    $gpiotracingcnt = $gpiotracingcnt + $row['num_tracing'];
    $gpioactuation_per_year[$year] = round($row['num_actuation'] * 100 / $tests_per_year[$year]);
    $gpioactuationcnt = $gpioactuationcnt + $row['num_actuation'];
    $powerprof_per_year[$year] = round($row['num_power'] * 100 / $tests_per_year[$year]);
    $powerprofcnt = $powerprofcnt + $row['num_power'];
  }
  arsort($tests_per_mote);
  // Users by service and node type
  $activeusers_per_year = Array();
  $tmoteusers_per_year = Array();
  $dppusers_per_year = Array();
  $dpp2users_per_year = Array();
  $nrfusers_per_year = Array();
  $serialusers_per_year = Array();
  $gpiotracingusers_per_year = Array();
  $gpioactuationusers_per_year = Array();
  $powerprofusers_per_year = Array();
  $sql = 'select year(time_start_act) as y, count(distinct owner_fk) as num from tbl_serv_tests group by year(time_start_act) having y is not null';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  while ($row = mysqli_fetch_array($rs)) {
    $year = $row['y'];
    $num_users = $row['num'];
    $activeusers_per_year[$year] = $row['num'];
    // initialize with 0
    $tmoteusers_per_year[$year] = 0;
    $dppusers_per_year[$year] = 0;
    $dpp2users_per_year[$year] = 0;
    $nrfusers_per_year[$year] = 0;
    $sql = 'select pname, count(distinct owner_fk) as c from (select distinct test_fk, tbl_serv_platforms.name as pname from tbl_serv_map_test_observer_targetimages left join tbl_serv_targetimages on (targetimage_fk = serv_targetimages_key) left join tbl_serv_platforms on (platforms_fk = serv_platforms_key)) as a left join tbl_serv_tests as b on (a.test_fk = b.serv_tests_key) where year(time_start_act) = '.$year.' and time_start_act is not null and pname is not null group by pname';
    $rs2 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
    while ($row = mysqli_fetch_array($rs2)) {
      if ($row['pname'] == 'Tmote') {
        $tmoteusers_per_year[$year] = round($row['c'] / $num_users * 100);    // in percent
      } else if ($row['pname'] == 'DPP') {
        $dppusers_per_year[$year] = round($row['c'] / $num_users * 100);
      } else if ($row['pname'] == 'DPP2LoRa') {
        $dpp2users_per_year[$year] = round($row['c'] / $num_users * 100);
      } else if ($row['pname'] == 'nRF5') {
        $dpp2users_per_year[$year] = round($row['c'] / $num_users * 100);
      }
    }
    
    $sql = 'select sum(num_all > 0) as user_all, sum(num_serial > 0) as user_serial, sum(num_tracing > 0) as user_tracing, sum(num_actuation > 0) as user_actuation, sum(num_power > 0) as user_power from (select year(time_start_act) as y, sum(1) as num_all, sum(ExtractValue(testconfig_xml, "count(/testConf/serialConf|/testConf/serialReaderConf)") > 0) as num_serial, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioTracingConf|/testConf/gpioMonitorConf)") > 0) as num_tracing, sum(ExtractValue(testconfig_xml, "count(/testConf/gpioActuationConf|/testConf/gpioSettingConf)") > 0) as num_actuation, sum(ExtractValue(testconfig_xml, "count(/testConf/powerProfilingConf|/testConf/powerprofConf)") > 0) as num_power from tbl_serv_tests where year(time_start_act) = '.$year.' and (test_status_preserved in ("finished", "retention expiring", "synced") or test_status_preserved is null) group by owner_fk) as stats;';
    $rs3 = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
    $row = mysqli_fetch_array($rs3);
    $serialusers_per_year[$year] = round($row['user_serial'] / $num_users * 100);        // in percent
    $gpiotracingusers_per_year[$year] = round($row['user_tracing'] / $num_users * 100);
    $gpioactuationusers_per_year[$year] = round($row['user_actuation'] / $num_users * 100);
    $powerprofusers_per_year[$year] = round($row['user_power'] / $num_users * 100);
  } 
  $sql = 'select avg(setuptime) as tsetup, avg(cleanuptime) as tcleanup, avg(timestampdiff(SECOND, time_start_act, time_end_act)) as avgruntime from tbl_serv_tests where time_start_act is not null and time_end_act is not null';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  $row = mysqli_fetch_array($rs);
  $avgruntime = intval($row['avgruntime']);
  $avgsetuptime = intval($row['tsetup']);
  $avgcleanuptime = intval($row['tcleanup']);
  // runtime median  
  $runtime = Array();
  $sql = 'select timestampdiff(SECOND, time_start_act, time_end_act) as runtime from tbl_serv_tests where time_start_act is not null and time_end_act is not null';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  while ($row = mysqli_fetch_array($rs)) {
    $runtime[] = $row['runtime'];
  }
  sort($runtime, SORT_NUMERIC) or flocklab_die('Array sort failed');
  $cnt = count($runtime);
  $runtimecdf = Array();
  $cdfelem = 20;
  $step = intval($runtime[round($cnt * ($cdfelem - 1) / $cdfelem)] / $cdfelem);  // equally spaced in time
  $tcurr = $step;
  for ($i = 0; $i < $cnt && $cdfelem; $i++) {
    if ($runtime[$i] >= $tcurr) {
      $runtimecdf[(string)round($tcurr / 60)] = round($i * 100 / $cnt);   // calc the percentage at this point
      $tcurr += $step;
      $cdfelem = $cdfelem - 1;
    }
  }  
  // occupancy per year in percent
  $utilization_per_year = Array();
  $sql = 'select year(time_start_act) as y, min(time_start_act) as minp, max(time_end_act) as maxp, max(time_end_act - time_start_act), sum(timestampdiff(SECOND,time_start_act,time_end_act)) as duration from tbl_serv_tests where (time_end_act is not null and time_start_act is not null and time_start_act < time_end_act and timestampdiff(SECOND,time_start_act,time_end_act) < 72 * 3600) group by  year(time_start_act)';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  while ($row = mysqli_fetch_array($rs)) {
    $utilization_per_year[$row['y']] = round((($row['duration'] + $tests_per_year[$row['y']] * $testoverhead) / (strtotime($row['maxp']) - strtotime($row['minp'])) * 100));
  }
  // occupancy of last 12 month, weekly resolution
  $sql = 'select year(time_start_act) as y, week(time_start_act,3) as w, count(*) as num, sum(timestampdiff(SECOND, time_start_act, time_end_act)) as runtime from tbl_serv_tests where 
          datediff(DATE_SUB(DATE_SUB(CURDATE(),INTERVAL (DAY(CURDATE())-1) DAY),INTERVAL 12 MONTH),time_start_act) <=0 group by year(time_start_act), week(time_start_act,3) having y is not null';
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get statistics from database because: ' . mysqli_error($db));
  $utilization_per_week = Array();
  while ($row = mysqli_fetch_array($rs)) {
    $utilization_per_week[$row['y'].' week '.$row['w']] = round(($row['runtime'] + $row['num'] * $testoverhead) * 100 / 604800);
  }
  
  // --- data collection finished ---

  // put together the new .dat file
  $new_stats = "
[general]
last_update = ".(string)time()."

[users]
registered = ".(string)$usercnt."
active = ".(string)$usercntactive."
num_countries = ".(string)$countrycnt."
country = \"".str_replace('"', '\'', serialize($countries))."\"
num_institutions = ".(string)$institutioncnt."
institution = \"".str_replace('"', '\'', serialize($institutions))."\"
users_per_year = \"".str_replace('"', '\'', serialize($activeusers_per_year))."\"

[tests]
num_tests = ".(string)$testcnt."
tests_per_year = \"".str_replace('"', '\'', serialize($tests_per_year))."\"
tests_per_mote = \"".str_replace('"', '\'', serialize($tests_per_mote))."\"
avg_setup_time = ".(string)$avgsetuptime."
avg_cleanup_time = ".(string)$avgcleanuptime."
avg_runtime = ".(string)$avgruntime."
runtime_cdf = \"".str_replace('"', '\'', serialize($runtimecdf))."\"
utilization_per_year = \"".str_replace('"', '\'', serialize($utilization_per_year))."\"
utilization_per_week = \"".str_replace('"', '\'', serialize($utilization_per_week))."\"

[motes]
tmote_tests = ".(string)$tmotetestcnt."
tmote_per_year = \"".str_replace('"', '\'', serialize($tmotetests_per_year))."\"
tmoteusers_per_year = \"".str_replace('"', '\'', serialize($tmoteusers_per_year))."\"
dpp_tests = ".(string)$dpptestcnt."
dpp_per_year = \"".str_replace('"', '\'', serialize($dpptests_per_year))."\"
dppusers_per_year = \"".str_replace('"', '\'', serialize($dppusers_per_year))."\"
dpp2_tests = ".(string)$dpp2testcnt."
dpp2_per_year = \"".str_replace('"', '\'', serialize($dpp2tests_per_year))."\"
dpp2users_per_year = \"".str_replace('"', '\'', serialize($dpp2users_per_year))."\"
nrf_tests = ".(string)$dpp2testcnt."
nrf_per_year = \"".str_replace('"', '\'', serialize($dpp2tests_per_year))."\"
nrfusers_per_year = \"".str_replace('"', '\'', serialize($dpp2users_per_year))."\"

[services]
serial_tests = ".(string)$serialcnt."
serial_per_year = \"".str_replace('"', '\'', serialize($serial_per_year))."\"
serialusers_per_year = \"".str_replace('"', '\'', serialize($serialusers_per_year))."\"
gpiotracing_tests = ".(string)$gpiotracingcnt."
gpiotracing_per_year = \"".str_replace('"', '\'', serialize($gpiotracing_per_year))."\"
gpiotracingusers_per_year = \"".str_replace('"', '\'', serialize($gpiotracingusers_per_year))."\"
gpioactuation_tests = ".(string)$gpioactuationcnt."
gpioactuation_per_year = \"".str_replace('"', '\'', serialize($gpioactuation_per_year))."\"
gpioactuationusers_per_year = \"".str_replace('"', '\'', serialize($gpioactuationusers_per_year))."\"
powerprof_tests = ".(string)$powerprofcnt."
powerprof_per_year = \"".str_replace('"', '\'', serialize($powerprof_per_year))."\"
powerprofusers_per_year = \"".str_replace('"', '\'', serialize($powerprofusers_per_year))."\"

";

  // write the stats into the file
  file_put_contents($filename, $new_stats);
}

collect_stats($statsFileName);
?>
