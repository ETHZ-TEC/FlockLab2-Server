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
      // abort test
      update_add_test(get_testconfig($_POST['testid']), $errors, $_POST['testid'], True);
    }
    else
      array_push($errors, "Test does not belong to you.");
  }
  if (!isset($_POST['testid'])) 
    array_push($errors, "Unknown testid.");
?>
<script type="text/javascript">
    $(document).ready(function() {
        $('.qtip_show').qtip( {
            content: {text: false},
            style  : 'flocklab',
        });
    });
</script>

<h1>Manage Tests</h1>
            <?php
            if (count($errors)>0) {
              echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
              echo "<!-- cmd --><p>Error:</p><ul>";
              foreach ($errors as $error)
                echo "<li>" . $error . "</li>";
              echo "</ul></div><p><!-- cmd --></p>";
            }
            else if (isset($_POST['removeit']) && isset($_POST['testid'])) {
              echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
              echo "<!-- cmd --><p>The test has been aborted.</p><!-- cmd -->";
              echo "</div><p></p>";
              include('index.php');
              exit();
            }
            else {
              $db = db_connect();
              $sql =   "SELECT serv_tests_key, title, description, time_start_act, time_start_wish, time_end_act, time_end_wish, test_status, `targetimage_fk`
                    FROM tbl_serv_tests  LEFT JOIN tbl_serv_map_test_observer_targetimages ON (serv_tests_key = test_fk)
                    WHERE owner_fk = " . $_SESSION['serv_users_key'] . " AND serv_tests_key = ".mysqli_real_escape_string($db, $_POST['testid'])."
                    GROUP BY `targetimage_fk`";
              $res = mysqli_query($db, $sql) or flocklab_die('Cannot fetch test information: ' . mysqli_error($db));
              $row = mysqli_fetch_assoc($res);
              // Find out the state of the test:
            $schedulable    = true;
                        $planned        = false;
                        $running        = false;
                        $finished        = false;
                        $preparing        = false;
                        $cleaningup        = false;
                        $failed            = false;
                        $aborting        = false;
                        $syncing        = false;
                        $synced            = false;
                        $retentionexp    = false;
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
                <form method="post" action="test_abort.php" enctype="multipart/form-data">
                <fieldset>
                <legend>Abort test</legend>
                <div class="warning"><div style="float:left;"><img alt="" src="pics/icons/att.png"></div>
                <p>The following test will be aborted:</p>
                <p><table>
                <tr><td>Test ID</td><td>'.$row['serv_tests_key'].'</td></tr>
                <tr><td>Title</td><td>'.$row['title'].'</td></tr>
                <tr><td>Description</td><td style="white-space:normal;">'.$row['description'].'</td></tr>
                <tr><td>State</td>';
              echo "<td>";
              echo "<img src='".state_icon($row['test_status'])."' height='16px' alt='".state_short_description($row['test_status'])."' title='".state_long_description($row['test_status'])."' class='qtip_show' />";
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
                <input type="hidden" name="testid" value="'.htmlentities($_POST['testid']).'">
                <input type="submit" name="removeit" value="Remove test">
                </fieldset>
                <p></p>
                </form>';
                }
            ?>
<!-- END content -->
<?php
do_layout('Manage Tests','Manage Tests');
?>
