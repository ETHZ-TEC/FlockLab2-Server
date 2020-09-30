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
<?php include_once('include/presets.php');?>
<?php
  if ($_SESSION['logged_in']) {
      if (isset($_GET['t']) && is_numeric($_GET['t']) && (check_testid($_GET['t'], $_SESSION['serv_users_key']) || $_SESSION['is_admin'])) {
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
