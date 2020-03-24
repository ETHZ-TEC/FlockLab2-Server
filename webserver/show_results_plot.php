<?php include_once('include/presets.php');?>
<?php
  if ($_SESSION['logged_in']) {
      if (isset($_GET['t']) && is_numeric($_GET['t']) && check_testid($_GET['t'], $_SESSION['serv_users_key'])) {
          // user is logged in and test belongs to the user
          $plot = $CONFIG['viz']['dir'].'/flocklab_plot_'.$_GET['t'].'.html';
          if (file_exists($plot)) {
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
          } else {
              echo "file '$plot' not found";
          }
      }
  }
?>
