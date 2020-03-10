<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision: 2826 $"
     * __date__        = "$Date: 2014-05-16 10:46:15 +0200 (Fri, 16 May 2014) $"
     * __id__          = "$Id: testbedstatus.php 2826 2014-05-16 08:46:15Z rlim $"
     * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/testbedstatus.php $" 
     */
?>
<?php require_once('include/layout.php'); require_once('include/presets.php'); ?>
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 25),10);
        $("#pager_num_rows").attr('value', table_rows);
        $("#statustable")
            .tablesorter({widgets: ['zebra']})
            .tablesorterPager({container: $("#pager"), positionFixed: false});
        $('.qtip_show').qtip( {
            content: {text: false},
            style  : 'flocklab',
        });
        $.cookie.json = true;
        var obs_tbl_state;
        try { obs_tbl_state = $.cookie('flocklab.obssort'); }
        catch (err) {
            obs_tbl_state = null;
        }
        if ( obs_tbl_state == null) {
           obs_tbl_state = {s: [[0,1],[2,0]], p: 0};
        }
        $("#statustable").data('tablesorter').page = obs_tbl_state.p;
        $("#statustable").trigger("sorton",[obs_tbl_state.s]);
        $("#statustable").bind("applyWidgets",function() { 
            $.cookie('flocklab.obssort', {s:$("#statustable").data('tablesorter').sortList, p:$("#statustable").data('tablesorter').page});
        });
    });
</script>
<h1>Node List (Targets)</h1>
<?php 
  /* Get all status information about the observers from the database and display them in the table. */
  $db = db_connect();
  $sql = "SELECT obs.observer_id, obs.status, obs.last_changed, 
          slot1.name AS name1, slot1.description AS desc1, 
          slot2.name AS name2, slot2.description AS desc2, 
          slot3.name AS name3, slot3.description AS desc3, 
          slot4.name AS name4, slot4.description AS desc4
          FROM `flocklab`.`tbl_serv_observer` AS obs 
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS a ON obs.slot_1_tg_adapt_list_fk = a.serv_tg_adapt_list_key 
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot1 ON a.tg_adapt_types_fk = slot1.serv_tg_adapt_types_key
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS b ON obs.slot_2_tg_adapt_list_fk = b.serv_tg_adapt_list_key 
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot2 ON b.tg_adapt_types_fk = slot2.serv_tg_adapt_types_key
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS c ON obs.slot_3_tg_adapt_list_fk = c.serv_tg_adapt_list_key 
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot3 ON c.tg_adapt_types_fk = slot3.serv_tg_adapt_types_key
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_list` AS d ON obs.slot_4_tg_adapt_list_fk = d.serv_tg_adapt_list_key 
          LEFT JOIN `flocklab`.`tbl_serv_tg_adapt_types` AS slot4 ON d.tg_adapt_types_fk = slot4.serv_tg_adapt_types_key 
          WHERE obs.status!='disabled' AND obs.status!='develop'
          ORDER BY obs.observer_id;";
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get observer information from database because: ' . mysqli_error($db));
  mysqli_close($db);
?>
<div>
  <table id="statustable" class="tablesorter" style="width:885px">
    <thead>
        <tr>
            <th style="width:40px">Observer ID</th>
            <th>Status</th>
            <th>Adapter<BR>Slot 1</th>
            <th>Adapter<BR>Slot 2</th>
            <th>Adapter<BR>Slot 3</th>
            <th>Adapter<BR>Slot 4</th>
            <th style="width:190px">Last Change</th>
        </tr>
    </thead>
    <tbody>
    <?php 
        $i = 0;
        $js = '';
        while ($row = mysqli_fetch_array($rs)) {
            $i++;
            echo ($i%2 == 1) ? "<tr class='even'>" : "<tr class='odd'>";
            if ($row['observer_id'] < 10)
                echo "<td>0";
            else
                echo "<td>";
            echo $row['observer_id'] . "</td>";
            echo "<td>" . $row['status'] . "</td>";
            echo "<td class='qtip_show targetplatform' title='";
            echo ($row['name1'] == "") ? "No or unknown adapter installed'></td>" : $row['desc1'] . "'>" . $row['name1'] . "</td>";
            echo "<td class='qtip_show targetplatform' title='";
            echo ($row['name2'] == "") ? "No or unknown adapter installed'></td>" : $row['desc2'] . "'>" . $row['name2'] . "</td>";
            echo "<td class='qtip_show targetplatform' title='";
            echo ($row['name3'] == "") ? "No or unknown adapter installed'></td>" : $row['desc3'] . "'>" . $row['name3'] . "</td>";
            echo "<td class='qtip_show targetplatform' title='";
            echo ($row['name4'] == "") ? "No or unknown adapter installed'></td>" : $row['desc4'] . "'>" . $row['name4'] . "</td>";
            echo "<td>".date_to_tzdate($row['last_changed'])."</td>";
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
  </span>
  <br />
</div>

<?php
  do_layout('Node List (Targets)','Node List (Targets)', '<link rel="stylesheet" href="css/ui-lightness/jquery-ui-1.8.20.custom.css">');
?>
