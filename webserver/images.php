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
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 25),10);
        $("#pager_num_rows").attr('value', table_rows);
        $("#test_overview")
            .tablesorter({widgets: ['zebra']})
            .tablesorterPager({container: $("#pager"), positionFixed: false});
        $('.qtip_show').qtip( {
            content: {text: false},
            style  : 'flocklab',
        });
        $("#test_overview").show();
        $.cookie.json = true;
        var img_tbl_state;
        try { img_tbl_state = $.cookie('flocklab.imgsort'); }
         catch (err) {
            img_tbl_state = null;
        }
        if ( img_tbl_state == null) {
            img_tbl_state = {s: [[0,1]], p: 0};
        }
        $("#test_overview").data('tablesorter').page = img_tbl_state.p;
        $("#test_overview").trigger("sorton",[img_tbl_state.s]);
        $("#test_overview").bind("applyWidgets",function() { 
            $.cookie('flocklab.imgsort', {s:$("#test_overview").data('tablesorter').sortList, p:$("#test_overview").data('tablesorter').page});
        });
    });
</script>
<h1>Manage Images for <?php echo $_SESSION['firstname'] . " " . $_SESSION['lastname'];?></h1>
<?php 
    /* Platforms with more than one core. */
    $db = db_connect();
    $sql = "select count(core) as corenum, name from tbl_serv_architectures left join tbl_serv_platforms on serv_platforms_key = platforms_fk group by platforms_fk having corenum > 1";
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get test images from database because: ' . mysqli_error($db));
    $nrows = mysqli_num_rows($rs);
    $multicore = Array();
    while ($row = mysqli_fetch_assoc($rs))
        array_push($multicore, $row['name']);
    /* Get all test images of the current user from the database and display them in the table. */
    $sql =   "SELECT `serv_targetimages_key`, `tbl_serv_targetimages`.`name` as `name`, `tbl_serv_targetimages`.`description` as `description`, `tbl_serv_architectures`.`description` as `core_desc`, `tbl_serv_operatingsystems`.`name` as `os_name`, `tbl_serv_platforms`.`name` as `platform_name`, `tbl_serv_targetimages`.`last_changed`, `test_fk`, `tbl_serv_tests`.`test_status` 
              FROM `tbl_serv_targetimages`
              LEFT JOIN (`tbl_serv_platforms`, `tbl_serv_operatingsystems`) 
                  ON (`operatingsystems_fk`=`tbl_serv_operatingsystems`.`serv_operatingsystems_key` AND `platforms_fk` = `tbl_serv_platforms`.`serv_platforms_key`)
              LEFT JOIN `tbl_serv_architectures` 
                  ON (`tbl_serv_architectures`.`platforms_fk` = `tbl_serv_platforms`.`serv_platforms_key` AND `tbl_serv_architectures`.`core` = `tbl_serv_targetimages`.`core`)
              LEFT JOIN `tbl_serv_map_test_observer_targetimages` 
                  ON (`serv_targetimages_key` = `tbl_serv_map_test_observer_targetimages`.`targetimage_fk`)
              LEFT JOIN `tbl_serv_tests` 
                  ON (`test_fk` = `tbl_serv_tests`.`serv_tests_key`)
              WHERE (`tbl_serv_targetimages`.`owner_fk` = " . $_SESSION['serv_users_key'] . ") 
                  AND (`tbl_serv_targetimages`.`binary_hash_sha1` is not NULL)
              GROUP BY `serv_targetimages_key`
              ORDER BY `serv_targetimages_key` DESC";
    $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get test images from database because: ' . mysqli_error($db));
    $nrows = mysqli_num_rows($rs);
    mysqli_close($db);
    
    // If there are no tests for this user, display a message instead of the table:
    if ($nrows == 0) {
        echo "<p class='warning'><img alt='' src='pics/icons/att.png'>No images uploaded yet</p>";
    }
    // If there are tests for this user, display them (with alternating row coloring):
    else {
?>
<table id="test_overview" class="tablesorter" style="display:none">
    <thead>
        <tr>
            <th width="50px">ID</th>
            <th>Name</th>
            <th>Description</th>
            <th>Platform</th>
            <th>Date</th>
            <th width="60px" class='qtip_show' title='Actions'>Actions</th>
        </tr>
    </thead>
    <tbody>
<?php 
    $i = 0;
    $max_len = 16; // maximum length of text before beeing cut
    while ($row = mysqli_fetch_assoc($rs)) {
        $i++;
        if ($i%2 == 1) {
            echo "<tr class='even'>";
        } else {
            echo "<tr class='odd'>";
        }
        echo "<td>" . $row['serv_targetimages_key'] . "</td>";
        // Name. If longer than $max_len characters, display as tooltip:
        echo "<td class='qtip_show' title='" . $row['name'] . "'>" . $row['name'] . "</td>";
        // Description. If longer than $max_len characters, display as tooltip:
        if (strlen($row['description']) <= $max_len) 
            echo "<td>" . $row['description'] . "</td>";
        else
            echo "<td class='qtip_show' title='" . $row['description'] . "'>" . substr($row['description'],0,$max_len) . "...</td>";
        // Platform. If longer than $max_len characters, display as tooltip:
        $corenum = in_array($row['platform_name'], $multicore)?': '.$row['core_desc']:'';
        echo "<td class='qtip_show' title='" . $row['platform_name'] .$corenum. "'>" . $row['platform_name'] .$corenum. "</td>";
        // Date
        echo "<td title='Date' class='qtip_show'>".date_to_tzdate($row['last_changed'])."</td>";
        // Actions
        echo "<td>";
        if (is_null($row['test_fk']) || ($row['test_status'] == "deleted")) {
          echo "<span style='display:none'>delete</span>"; // needed to make cell sortable by JQuery
          echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete test image' class='qtip_show link' onClick='document.tstimgdel.imageid.value = " . $row['serv_targetimages_key'] . ";document.tstimgdel.submit();'> ";
        }
        else {
          echo "<span style='display:none'>delete not possible</span>"; // needed to make cell sortable by JQuery
          echo "<img src='pics/icons/cancel.png' height='16px' alt='Not Delete' title='This image is used in a test' class='qtip_show link'> ";
        }
        echo "<img src='pics/icons/download.png' height='16px' alt='Download' title='Download test image' class='qtip_show link' onClick='document.tstimgdownload.imageid.value = " . $row['serv_targetimages_key'] . ";document.tstimgdownload.submit();'> ";
        echo "</td>";
        echo "</tr>";
    }
?>
    </tbody>
</table>
<br />
<span id="pager" class="pager">
    <span class="texticonsm first link" alt="first" title="first"><<</span>
    <span class="texticonsm prev link" alt="prev" title="prev"><</span>
    <span class="pagedisplay"></span>
    <span class="texticonsm next link" alt="next" title="next">></span>
    <span class="texticonsm last link" alt="last" title="last">>></span>
    <input class="pagesize" style="visibility: hidden;" id="pager_num_rows" value="15">
</span> <br>
<?php
  }
?>
<!-- Forms for processing actions -->
<form name="tstimgdel" method="post" action="image_delete.php"><input type="hidden" name="imageid" value=""></form>
<form name="tstimgdownload" method="post" action="image_download.php"><input type="hidden" name="imageid" value=""></form>
<p><a style="color:#666666;text-decoration:none;" href="newimage.php"><span class="texticon">+</span> add new test image</a></p>
<!-- END content -->
<?php
  do_layout('Manage Images','Manage Images');
?>
