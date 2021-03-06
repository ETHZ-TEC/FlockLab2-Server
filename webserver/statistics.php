<?php
/**
 * Copyright (c) 2010 - 2020, ETH Zurich, Computer Engineering Group
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of the copyright holder nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 */
?>
<?php
  require_once('include/layout.php');
  require_once('include/presets.php');
?>
<?php
  $statsfilename = "statistics.dat";
  $stats = parse_ini_file($statsfilename);
  $granularity = $stats['granularity'];     // month or year
  
  function convert_x_label($entry, $labels) {
    $num2month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (is_array($labels) && $labels[0] == 'month') {
      $idx = intval($entry) - 1;
      if ($idx >= 0 && $idx < 12) {
        return $num2month[$idx];
      }
    }
    return $entry;
  }
  
  function create_pie_chart($elem_id, $data_array) {
    echo "var myChart = new Chart(document.getElementById(\"$elem_id\"), { 
    type: 'pie', options: { responsive: true, cutoutPercentage: 50, legend: { display: true, position: 'right', labels: { fontSize: 12 } } }, data: {";  
    $entries = unserialize(str_replace('\'', '"', $data_array));
    $labels = "";
    $data = "";
    foreach ($entries as $entry => $val) {
      $labels .= "'".$entry."', ";
      $data   .= (string)$val.", ";
    }
    echo "    labels: [$labels], datasets: [{ data: [$data], backgroundColor: defaultColors }] 
    }, });\n";
  }
  
  function create_bar_chart($elem_id, $data_array, $axeslabels) {
    $alabels = "";
    if (is_array($axeslabels)) {
      $alabels = ", scales: { xAxes: [{ scaleLabel: { display: true, labelString: '$axeslabels[0]', fontSize: 12 } }], yAxes: [{ scaleLabel: { display: true, labelString: '$axeslabels[1]', fontSize: 12 } }] }";
    }
    echo "var myChart = new Chart(document.getElementById(\"$elem_id\"), { 
    type: 'bar', options: { responsive: true, legend: { display: false } $alabels }, data: {";  
    $entries = unserialize(str_replace('\'', '"', $data_array));
    $labels = "";
    $data = "";
    foreach ($entries as $entry => $val) {
      $labels .= "'".$entry."', ";
      $data   .= (string)$val.", ";
    }
    echo "    labels: [$labels], datasets: [{ data: [$data], backgroundColor: defaultColors[0] }] 
    }, });\n";
  }
  
  function create_line_chart($elem_id, $data_array, $axeslabels) {
    $alabels = "";
    if (is_array($axeslabels)) {
      $alabels = ", scales: { xAxes: [{ scaleLabel: { display: true, labelString: '$axeslabels[0]', fontSize: 12 } }], yAxes: [{ ticks: { beginAtZero: true }, scaleLabel: { display: true, labelString: '$axeslabels[1]', fontSize: 12 } }] }";
    }
    echo "var myChart = new Chart(document.getElementById(\"$elem_id\"), { 
    type: 'line', options: { responsive: true, legend: { display: false } $alabels }, data: {";  
    $entries = unserialize(str_replace('\'', '"', $data_array));
    $labels = "";
    $data = "";
    foreach ($entries as $entry => $val) {
      $labels .= "'".convert_x_label($entry, $axeslabels)."', ";
      $data   .= (string)$val.", ";
    }
    echo "    labels: [$labels], datasets: [{ data: [$data], fill: false, showLine: true, cubicInterpolationMode: 'monotone', borderWidth: 3, borderColor: defaultColors[0], pointRadius: 3, pointStyle: 'circle' }] 
    }, });\n";
  } 
  
  function create_multi_line_chart($elem_id, $multi_data_array, $data_labels, $axeslabels) {
    $alabels = "";
    if (is_array($axeslabels)) {
      $alabels = ", scales: { xAxes: [{ scaleLabel: { display: true, labelString: '$axeslabels[0]', fontSize: 12 } }], yAxes: [{ ticks: { beginAtZero: true }, scaleLabel: { display: true, labelString: '$axeslabels[1]', fontSize: 12 } }] }";
    }
    echo "var myChart = new Chart(document.getElementById(\"$elem_id\"), { 
    type: 'line', options: { responsive: true $alabels }, data: { datasets: [\n";
    $labels = "";
    $count = 0;
    foreach ($multi_data_array as $dataset) {
      $entries = unserialize(str_replace('\'', '"', $dataset));
      $data = "";
      foreach ($entries as $entry => $val) {
        if ($count == 0) {
          $labels .= "'".convert_x_label($entry, $axeslabels)."', ";
        }
        $data .= (string)$val.", ";
      }
      echo "      { label: '$data_labels[$count]', data: [$data], fill: false, showLine: true, borderColor: defaultColors[$count], borderWidth: 3, pointRadius: 3 },\n"; 
      $count = $count + 1;
    }
    echo "    ], labels: [$labels] \n}, });\n";
  }
  
  function print_tests_percent($val) {
    global $stats;
    echo (string)round(intval($val) * 100 / intval($stats['num_tests'])) . "%";
  }
?>

<!--<script type="text/javascript" src="scripts/jquery-1.9.1.min.js"></script>-->
<script type="text/javascript" src="scripts/jquery-ui-1.8.21.custom.min.js"></script>
<script type="text/javascript" src="scripts/Chart.bundle.min.js"></script>
<script type="text/javascript">
  var defaultColors =  ['#3366CC','#DC3912','#FF9900','#109618','#990099','#3B3EAC','#0099C6','#DD4477','#66AA00','#B82E2E','#316395','#994499','#22AA99','#AAAA11','#6633CC','#E67300','#8B0707','#329262','#5574A6','#3B3EAC'];
</script>
<style>
  .chartContainer { float: left; display: block; width: 700px; text-align: left; margin-top: 10px; margin-bottom: 10px; padding: 10px; }
  .chartTitle { margin: 25px; width: 100%; text-align: center; font-weight: bold }
  .chartArea { display: block; }
  .numberField { text-align: right; }
</style>

<h1>Flocklab 2 Statistics</h1>
<br />
&nbsp;&nbsp;<i>Note: you can find the archived statistics of the old FlockLab <a href="statistics_old.php">here</a>.</i>
<br />
<div class="chartContainer">
  <table>
    <tr><td><b>Flocklab users</b></td></tr>
    <tr><td>Number of registered users: </td><td class="numberField"><?php echo $stats['registered']; ?></td></tr>
    <tr><td>Number of active users: </td><td class="numberField"><?php echo $stats['active']; ?></td></tr>
    <tr><td>Number of different countries: </td><td class="numberField"><?php echo $stats['num_countries']; ?></td></td></tr>
    <tr><td>Number of different institutions: </td><td class="numberField"><?php echo $stats['num_institutions']; ?></td></td></tr> 
    <tr><td></td></tr>
    <tr><td><b>Tests</b></td></tr>
    <tr><td>Total number of tests since March 2020: </td><td class="numberField"><?php echo $stats['num_tests']; ?></td></td></tr>
    <tr><td>Average test duration [min]: </td><td class="numberField"><?php echo (string)round(intval($stats['avg_runtime']) / 60); ?></td></td></tr>
    <tr><td>Average setup + cleanup time overhead per test [s]: </td><td class="numberField"><?php echo (string)(intval($stats['avg_setup_time']) + intval($stats['avg_cleanup_time'])); ?></td></td></tr>
    <tr><td></td></tr>
    <tr><td><b>Used platforms</b></td></tr>
    <tr><td>Number of tests on the TmoteSky (TelosB) platform: </td><td class="numberField"><?php echo $stats['tmote_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['tmote_tests']); ?></td></tr>
    <tr><td>Number of tests on the DPP platform: </td><td class="numberField"><?php echo $stats['dpp_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['dpp_tests']); ?></td></tr>
    <tr><td>Number of tests on the DPP2 (LoRa) platform: </td><td class="numberField"><?php echo $stats['dpp2_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['dpp2_tests']); ?></td></tr>
    <tr><td>Number of tests on the nRF5 platform: </td><td class="numberField"><?php echo $stats['nrf_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['nrf_tests']); ?></td></tr>
    <tr><td></td></tr>
    <tr><td><b>Used services</b></td></tr>
    <tr><td>Number of tests with serial logging: </td><td class="numberField"><?php echo $stats['serial_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['serial_tests']); ?></td></tr>
    <tr><td>Number of tests with GPIO tracing: </td><td class="numberField"><?php echo $stats['gpiotracing_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['gpiotracing_tests']); ?></td></tr>
    <tr><td>Number of tests with GPIO actuation: </td><td class="numberField"><?php echo $stats['gpioactuation_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['gpioactuation_tests']); ?></td></tr>
    <tr><td>Number of tests with power profiling: </td><td class="numberField"><?php echo $stats['powerprof_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['powerprof_tests']); ?></td></tr>
    <tr><td>Number of tests with debug service: </td><td class="numberField"><?php echo $stats['debug_tests']; ?></td></td><td class="numberField"><?php print_tests_percent($stats['debug_tests']); ?></td></tr>
  </table>
</div>
<div class="chartContainer"><div class="chartTitle">Flocklab users by country</div><canvas id="chartCountries" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Flocklab users by institution</div><canvas id="chartInstitutions" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Most popular platforms (motes)</div><canvas id="chartMotes" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Number of active users by <?php echo $granularity ?></div><canvas id="chartUsersYear" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Total number of tests by <?php echo $granularity ?></div><canvas id="chartTestsYear" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Testbed utilization by <?php echo $granularity ?></div><canvas id="chartUtilizationYear" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Weekly testbed utilization over last 12 months</div><canvas id="chartUtilizationWeek" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Test durations (cumulative distribution function)</div><canvas id="chartTestRuntime" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Number of tests per platform and <?php echo $granularity ?></div><canvas id="chartPlatformsYear" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Services used in tests</div><canvas id="chartServicesYear" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Platform utilization by users and <?php echo $granularity ?></div><canvas id="chartPlatformsUsers" class="chartArea"></canvas></div>
<div class="chartContainer"><div class="chartTitle">Service utilization by users and <?php echo $granularity ?></div><canvas id="chartServicesUsers" class="chartArea"></canvas></div>

<div class="chartContainer"><br /><br />Last update: <?php echo date('c', $stats['last_update']) ?></div>

<script type="text/javascript">
  <?php
    create_pie_chart("chartCountries", $stats['country']);
    create_pie_chart("chartInstitutions", $stats['institution']);
    create_pie_chart("chartMotes", $stats['tests_per_mote']);
    create_line_chart("chartUsersYear", $stats['users_per_year'], [$granularity, "number of active users"]);
    create_line_chart("chartTestsYear", $stats['tests_per_year'], [$granularity, "number of scheduled tests"]);
    create_line_chart("chartUtilizationYear", $stats['utilization_per_year'], [$granularity, "utilization %"]);
    create_bar_chart("chartUtilizationWeek", $stats['utilization_per_week'], ["week", "utilization %"]);
    create_line_chart("chartTestRuntime", $stats['runtime_cdf'], ["runtime [minutes]", "percentage of tests"]);
    $dataseries = [$stats['tmote_per_year'], $stats['dpp_per_year'], $stats['dpp2_per_year'], $stats['nrf_per_year']];
    $dataserieslabels = ['Tmote', 'DPP', 'DPP2LoRa', 'nRF5'];
    create_multi_line_chart("chartPlatformsYear", $dataseries, $dataserieslabels, [$granularity, "number of tests"]);
    $dataseries = [$stats['serial_per_year'], $stats['gpiotracing_per_year'], $stats['gpioactuation_per_year'], $stats['powerprof_per_year'], $stats['debug_per_year']];
    $dataserieslabels = ['serial', 'GPIO tracing', 'GPIO actuation', 'power profiling', 'debug & datatrace'];
    create_multi_line_chart("chartServicesYear", $dataseries, $dataserieslabels, [$granularity, "percentage of tests"]);
    $dataseries = [$stats['tmoteusers_per_year'], $stats['dppusers_per_year'], $stats['dpp2users_per_year'], $stats['nrfusers_per_year']];
    $dataserieslabels = ['Tmote', 'DPP', 'DPP2LoRa', 'nRF5'];
    create_multi_line_chart("chartPlatformsUsers", $dataseries, $dataserieslabels, [$granularity, "percentage of users"]);
    $dataseries = [$stats['serialusers_per_year'], $stats['gpiotracingusers_per_year'], $stats['gpioactuationusers_per_year'], $stats['powerprofusers_per_year'], $stats['debugusers_per_year']];
    $dataserieslabels = ['serial', 'GPIO tracing', 'GPIO actuation', 'power profiling', 'debug & datatrace'];
    create_multi_line_chart("chartServicesUsers", $dataseries, $dataserieslabels, [$granularity, "percentage of users"]);
  ?>
</script>

<?php 
  do_layout('Statistics','Statistics');
?>
