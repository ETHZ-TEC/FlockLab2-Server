<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision: 2888 $"
     * __date__        = "$Date: 2014-08-22 10:01:11 +0200 (Fri, 22 Aug 2014) $"
     * __id__          = "$Id: index.php.normal 2888 2014-08-22 08:01:11Z rlim $"
     * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/index.php.normal $" 
     */
?>
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
    if (!isset($_SESSION['is_admin']) || !$_SESSION['is_admin'])
        exit(1);
    if (isset($_POST['resid'])) {
        $db = db_connect();
        $sql =    "DELETE FROM tbl_serv_reservations where serv_reservation_key=".mysqli_real_escape_string($db, $_POST['resid']);
        $rs = mysqli_query($db, $sql) or flocklab_die('Cannot delete reservation in database because: ' . mysqli_error($db));
        mysqli_close($db);
    }
    if (isset($_POST['add_group'])) {
        $db = db_connect();
        $sql =    'INSERT INTO tbl_serv_reservations (group_id_fk, time_start, time_end) values ('.mysqli_real_escape_string($db, $_POST['add_group']).',FROM_UNIXTIME('.strtotime(mysqli_real_escape_string($db, $_POST['add_start_time'])).'),FROM_UNIXTIME('.strtotime(mysqli_real_escape_string($db, $_POST['add_end_time'])).'))';
        $rs = mysqli_query($db, $sql) or flocklab_die('Cannot add reservation in database because: ' . mysqli_error($db));
        mysqli_close($db);
    }
?>
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
            $([$("#add_start_time"), $("#add_end_time")]).each(function() {
            var otime = $(this).html();
            $(this).empty().append('<input style="width:200px" name="'+this[0].id+'" value="'+otime+'">');
        });
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 25),10);
        $("#pager_num_rows").attr('value', table_rows);        
        $("#res_overview")
            .tablesorter({widgets: ["zebra"] })
            .tablesorterPager({container: $("#pager"), positionFixed: false});
        $(".qtip_show").qtip( {
            content: {text: false},
            style  : "flocklab",
        });
        $("#res_overview").show();
        $.cookie.json = true;
        var res_tbl_state;
         try { res_tbl_state = $.cookie('flocklab.ressort'); }
         catch (err) {
            res_tbl_state = null;
        }
        if ( res_tbl_state == null) {
            res_tbl_state = {s: [[0,1]], p: 0};
        }
        $("#res_overview").data('tablesorter').page = res_tbl_state.p;
        $("#res_overview").trigger("sorton",[res_tbl_state.s]);
        $("#res_overview").bind("applyWidgets",function() { 
            $.cookie('flocklab.ressort', {s:$("#res_overview").data('tablesorter').sortList, p:$("#res_overview").data('tablesorter').page});
        });
    });
</script>
<?php
echo '<h1>Admin Group Reservations</h1>';
                /* Get all reservations from the database and display them in the table. */
                $db = db_connect();
                $sql =    "SELECT serv_groups_key, groupname, GROUP_CONCAT(username SEPARATOR ', ') as group_list FROM (tbl_serv_groups left join tbl_serv_user_groups on (group_fk=serv_groups_key)) left join tbl_serv_users on (user_fk=tbl_serv_users.serv_users_key) GROUP BY group_fk";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get reservations from database because: ' . mysqli_error($db));
                $groups = array();
                while ($row = mysqli_fetch_array($rs)) {
                    $groups[$row['serv_groups_key']]=Array('name' => $row['groupname'], 'users' => $row['group_list']);
                }
                $sql =    "SELECT serv_reservation_key, group_id_fk, time_start, time_end, groupname, group_list
FROM tbl_serv_reservations LEFT JOIN (
SELECT serv_groups_key, groupname, GROUP_CONCAT(username SEPARATOR ', ') as group_list FROM (tbl_serv_groups left join tbl_serv_user_groups on (group_fk=serv_groups_key)) left join tbl_serv_users on (user_fk=tbl_serv_users.serv_users_key) GROUP BY serv_groups_key) as groups on (groups.serv_groups_key = group_id_fk)
ORDER BY time_start DESC";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get reservations from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                
                ?>
            <form name="resadd" method="post" action="admin_group_reservation.php">
            <table id="res_overview" class="tablesorter" style="display:none">
                <thead>
                    <tr>
                        <th width="200px">Group</th>
                        <th width="200px">Start</th>
                        <th width="200px">End</th>
                        <th width="60px" class='qtip_show' title='Actions'>Actions</th>
                    </tr>
                </thead>
                <tbody>
                <?php 
                    $i = 0;
                    $max_len = 30; // maximum length of text before being cut
                    while ($row = mysqli_fetch_array($rs)) {
                        $i++;
                        if ($i%2 == 1) {
                            echo "<tr class='even'>";
                        } else {
                            echo "<tr class='odd'>";
                        }
                        echo "<td class='qtip_show' title='" . htmlentities($row['group_list']) . "'>" . htmlentities($row['groupname']) . "</td>";
                        // Start time
                        echo "<td title='start time' class='qtip_show'><i class='starttime'>" . date_to_tzdate($row['time_start']). "</i></td>";
                        // End time
                            echo "<td title='end time' class='qtip_show'><i class='endtime'>" . date_to_tzdate($row['time_end']). "</i></td>";
                        echo "</td>";
                        echo "<td>";
                        echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete reservation' class='qtip_show' onClick='document.resdel.resid.value = " . $row['serv_reservation_key'] . ";document.resdel.submit();'>";
                        echo "</td></tr>";
                    }
                    // add new reservation
                    $now = new DateTime();
                    $now = $now->format('U');
                    echo '<tr><td><span style="display:none">0</span><select name="add_group" style="width:200px">';
                    foreach ($groups as $idx=>$group) {
                        echo '<option value="'.$idx.'">' . $group['name'] . '</option>';
                    }
                    echo '</select></td><td><span class="time" id="add_start_time">'.$now.'</span></td><td><span class="time" id="add_end_time">'.($now+3600).'</span></td>';
                    echo "<td><span class='qtip_show texticon link' alt='Add' title='Add reservation' onClick='document.resadd.submit();'>+</span></td>";
                    echo '</tr>';
            ?>
                </tbody>
            </table>
            </form>
            <span id="pager" class="pager">
                <span class="texticonsm first link" alt="first" title="first"><<</span>
                <span class="texticonsm prev link" alt="prev" title="prev"><</span>
                <span class="pagedisplay"></span>
                <span class="texticonsm next link" alt="next" title="next">></span>
                <span class="texticonsm last link" alt="last" title="last">>></span>
                <input class="pagesize" style="visibility: hidden;" id="pager_num_rows" value="15">
            </span> <br >
            <!-- Forms for processing actions -->
            <form name="resdel" method="post" action="admin_group_reservation.php"><input type="hidden" name="resid" value=""></form>
<?php
do_layout('Group Reservations','Group Reservations');
?>
