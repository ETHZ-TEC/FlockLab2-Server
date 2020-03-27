<?php include_once('include/presets.php');?>
<?php
  if ($_SESSION['logged_in']) {
      if (isset($_GET['t']) && is_numeric($_GET['t']) && check_testid($_GET['t'], $_SESSION['serv_users_key'])) {
          // user is logged in and test belongs to the user
          $plot = $CONFIG['viz']['dir'].'/flocklab_plot_'.$_GET['t'].'.html';
          $fs = filesize($plot);

          // download the file
          if (isset($_GET['a']) && $_GET['a'] == 'dl') {
              header('Content-disposition: attachment; filename=flocklab_plot_'.$_GET['t'].'.html');
              header('Content-type: text/html');
              header("Content-Length: ".$fs);
              $fh = fopen($plot, "r");
              if ($fh) {
                  // read and print html file line by line
                  $max_read = 2048;
                  do {
                      echo fread($fh, 1024 * 1024);
                      $max_read--;
                  } while (!feof($fh) && $max_read > 0);
                  fclose($fh);
              }
          // display the file
          } else {
              if (file_exists($plot)) {
                  if ($fs > (256 * 1024 * 1024)) {
                      echo "<br />The requested file is too large to display. Try to <a href='show_results_plot.php?t=".$_GET['t']."&a=dl'>download</a> it instead.";
                  } else {
                      echo file_get_contents($plot);
                      /*$fh = fopen($plot,"r");
                      if ($fh) {
                          // read and print html file line by line
                          $line = fgets($fh);
                          while ($line !== false) {
                              echo $line;
                              $line = fgets($fh);
                          }
                          fclose($fh);
                      }*/
                  }
              } else {
                  echo "file '$plot' not found";
              }
          }
      }
  }
?>
