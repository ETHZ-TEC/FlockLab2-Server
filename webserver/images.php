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
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">

    var editingTitle = 0;
    var editingDesc  = 0;
    
    function editTitle(testid) {
        if (editingTitle == 0) {
            editingTitle = testid;
            val = $("#title" + testid).text();
            $("#title" + testid).html("<input type='text' style='overflow:visible' id='newtitle" + testid + "' value='" + val + "' />");
        }
    }
    
    function editDesc(testid) {
        if (editingDesc == 0) {
            editingDesc = testid;
            val = $("#desc" + testid).text();
            $("#desc" + testid).html("<input type='text' id='newdesc" + testid + "' value='" + val + "' />");
        }
    }
    
    $(document).ready(function() {
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 40),10);
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
    
    $(document).mousedown(function(evt) {
        if(editingTitle > 0 && evt.target.id != "newtitle" + editingTitle) {
            newtitle = $("#newtitle" + editingTitle).val();
            if (confirm("save changes?")) {
                $.post("api.php", "s=imgname&id=" + editingTitle + "&val=" + newtitle, function() { location.reload(); });
            } else {
                $("#title" + editingTitle).text(newtitle);
            }
            editingTitle = 0;
        }
        if(editingDesc > 0 && evt.target.id != "newdesc" + editingDesc) {
            newdesc = $("#newdesc" + editingDesc).val();
            if (confirm("save changes?")) {
                $.post("api.php", "s=imgdesc&id=" + editingDesc + "&val=" + newdesc, function() { location.reload(); });
            } else {
                $("#desc" + editingDesc).text(newdesc);
            }
            editingDesc = 0;
        }
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
    $sql =   "SELECT `serv_targetimages_key`, `tbl_serv_targetimages`.`name` as `name`, `tbl_serv_targetimages`.`description` as `description`, `tbl_serv_architectures`.`description` as `core_desc`, `tbl_serv_platforms`.`name` as `platform_name`, `tbl_serv_targetimages`.`last_changed`, GROUP_CONCAT(DISTINCT `test_fk` SEPARATOR ', ') test_ids, `tbl_serv_tests`.`test_status` 
              FROM `tbl_serv_targetimages`
              LEFT JOIN `tbl_serv_platforms` ON `platforms_fk` = `tbl_serv_platforms`.`serv_platforms_key`
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
<table>
  <tr>
    <td width="200px" class="transparentbg"><a style="color:#666666;text-decoration:none;" href="newimage.php"><span class="texticon">+</span> add new test image</a></td>
    <td width="500px" style="text-align:center" class="transparentbg"><span id="pager" class="pager" style="text-align:right">
          <span class="texticonsm first link bold" alt="first" title="first"><<</span>
          <span class="texticonsm prev link bold" alt="prev" title="prev"><</span>
          <span class="pagedisplay"></span>
          <span class="texticonsm next link bold" alt="next" title="next">></span>
          <span class="texticonsm last link bold" alt="last" title="last">>></span>
          <input class="pagesize" style="visibility: hidden; width: 0px" id="pager_num_rows" value="15">
        </span>
    </td>
    <td width="200px" class="transparentbg"></td>
  </tr>
</table>
<table id="test_overview" class="tablesorter" style="display:none">
    <thead>
        <tr>
            <th width="40px">ID</th>
            <th width="100px">Name</th>
            <th width="200px">Description</th>
            <th width="100px">Platform</th>
            <th width="180px">Upload Date</th>
            <th>Used in Test</th>
            <th width="60px" class='qtip_show' title='Actions'>Actions</th>
        </tr>
    </thead>
    <tbody>
<?php 
    $i = 0;
    $max_len = 30; // maximum length of text before beeing cut
    while ($row = mysqli_fetch_assoc($rs)) {
        $i++;
        if ($i%2 == 1) {
            echo "<tr class='even'>";
        } else {
            echo "<tr class='odd'>";
        }
        echo "<td>" . $row['serv_targetimages_key'] . "</td>";
        // Name. If longer than $max_len characters, display as tooltip:
        echo "<td class='qtip_show' title='" . $row['name'] . "' id='title".$row['serv_targetimages_key']."' ondblclick='editTitle(".$row['serv_targetimages_key'].")'>" . $row['name'] . "</td>";
        // Description. If longer than $max_len characters, display as tooltip:
        if (strlen($row['description']) <= $max_len) 
            echo "<td id='desc".$row['serv_targetimages_key']."' ondblclick='editDesc(".$row['serv_targetimages_key'].")'>" . $row['description'] . "</td>";
        else
            echo "<td class='qtip_show' title='" . $row['description'] . "' id='desc".$row['serv_targetimages_key']."' ondblclick='editDesc(".$row['serv_targetimages_key'].")'>" . substr($row['description'], 0, $max_len) . "...</td>";
        // Platform. If longer than $max_len characters, display as tooltip:
        $corenum = in_array($row['platform_name'], $multicore)?': '.$row['core_desc']:'';
        echo "<td class='qtip_show' title='" . $row['platform_name'] .$corenum. "'>" . $row['platform_name'] .$corenum. "</td>";
        // Date
        echo "<td title='upload date' class='qtip_show'>" . date_to_tzdate($row['last_changed']) . "</td>";
        // Test IDs
        if (strlen($row['test_ids']) <= $max_len)
            echo "<td class='qtip_show' title='IDs of tests in which this image has been used'>" . $row['test_ids'] . "</td>";
        else
            echo "<td class='qtip_show' title='".$row['test_ids']."'>" . substr($row['test_ids'], 0, $max_len) . "...</td>";
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
<br />
<i>Note: you can edit the test title and description with a double click.</i>
<?php
  }
?>
<!-- Forms for processing actions -->
<form name="tstimgdel" method="post" action="image_delete.php"><input type="hidden" name="imageid" value=""></form>
<form name="tstimgdownload" method="post" action="image_download.php"><input type="hidden" name="imageid" value=""></form>
<!-- END content -->
<?php
  do_layout('Manage Images','Manage Images');
?>
