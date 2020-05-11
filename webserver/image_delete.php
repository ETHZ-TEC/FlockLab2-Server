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
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
  $errors = array();
  
  if (isset($_POST['removeit']) && isset($_POST['imageid'])) {
    // remove image
    $db = db_connect();
    $sql =    'UPDATE `tbl_serv_targetimages`
            SET `binary` = NULL, `binary_hash_sha1` = NULL
             WHERE `owner_fk` = '.$_SESSION['serv_users_key'].' 
                 AND `serv_targetimages_key` = ' .mysqli_real_escape_string($db, $_POST['imageid']);
    mysqli_query($db, $sql) or flocklab_die('Cannot remove image: ' . mysqli_error($db));
  }
?>
            <?php
            if (isset($_POST['removeit']) && isset($_POST['imageid'])) {
              echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
              echo "<p>The image has been removed.</p><ul>";
              echo "</div><p></p>";
              include('images.php');
              echo '<meta http-equiv="Refresh" content="10; URL=images.php">';
              exit();
            }
            else {
                echo '
                <script type="text/javascript">
                    $(document).ready(function() {
                    $(".qtip_show").qtip( {
                        content: {text: false},
                        style  : "flocklab",
                    });
                    });
                </script>
    
                <h1>Manage Images</h1>';
              $db = db_connect();
              $sql =  'SELECT `serv_targetimages_key`, `tbl_serv_targetimages`.`name` as `name`, `tbl_serv_targetimages`.`description` as `description`,  `tbl_serv_platforms`.`name` as `platform_name`, `tbl_serv_targetimages`.`last_changed`
                FROM `tbl_serv_targetimages`
                LEFT JOIN `tbl_serv_platforms` ON `platforms_fk` = `tbl_serv_platforms`.`serv_platforms_key`
                WHERE `owner_fk` = '.$_SESSION['serv_users_key'].' AND `serv_targetimages_key` = ' .mysqli_real_escape_string($db, $_POST['imageid']);
              $res = mysqli_query($db, $sql) or flocklab_die('Cannot fetch image information: ' . mysqli_error($db));
              $row = mysqli_fetch_assoc($res);
              echo '
                <form method="post" action="image_delete.php" enctype="multipart/form-data">
                <fieldset>
                <legend>Remove image</legend>
                <div class="warning"><div style="float:left;"><img alt="" src="pics/icons/att.png"></div>
                <p>The following image will be removed:</p>
                <p><table>
                <tr><td>Image ID</td><td>'.$row['serv_targetimages_key'].'</td></tr>
                <tr><td>Name</td><td>'.$row['name'].'</td></tr>
                <tr><td>Description</td><td>'.$row['description'].'</td></tr>
                <tr><td>Platform</td><td>'.$row['platform_name'].'</td></tr>
                <tr><td>Date</td><td>'.$row['last_changed'].'</td></tr>
                </table></p>
                </div><p></p>
                <input type="hidden" name="imageid" value="'.htmlentities($_POST['imageid']).'">
                <input type="submit" name="removeit" value="Remove image">
                </fieldset>
                <p></p>
                </form>';
                }
            ?>
<!-- END content -->
<?php
do_layout('Manage Images','Manage Images');
?>
