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
  
  if (isset($_POST['removeit']) && isset($_POST['imageid'])) {
    // remove image
    $db = db_connect();
    $sql =	'UPDATE `tbl_serv_targetimages`
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
			  $sql =  'SELECT `serv_targetimages_key`, `tbl_serv_targetimages`.`name` as `name`, `tbl_serv_targetimages`.`description` as `description`, `tbl_serv_operatingsystems`.`name` as `os_name`, `tbl_serv_platforms`.`name` as `platform_name`, `tbl_serv_targetimages`.`last_changed`
				FROM `tbl_serv_targetimages`
				LEFT JOIN (`tbl_serv_platforms`, `tbl_serv_operatingsystems`) ON (`operatingsystems_fk`=`tbl_serv_operatingsystems`.`serv_operatingsystems_key` AND `platforms_fk` = `tbl_serv_platforms`.`serv_platforms_key`)
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
			    <tr><td>Os</td><td>'.$row['os_name'].'</td></tr>
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