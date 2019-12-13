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
<?php require_once('include/layout.php');require_once('include/presets.php');
$javascript = '<link rel="stylesheet" href="css/ui-lightness/jquery-ui-1.8.20.custom.css">';
?>
<style type="text/css">
    .bold { font-weight: bold}
</style>
<script type="text/javascript" src="scripts/jquery-ui-1.8.21.custom.min.js"></script>
<script type="text/javascript" src="scripts/protovis-d3.3.js"></script>
<script type="text/javascript" src="scripts/flocklab-observer-positions.js"></script>
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
        $( "#tabs" ).tabs();
        $( "#tabs ul" ).removeClass('ui-corner-all');
        
        $.cookie.json = true;
        var tabsel;
        try { tabsel = $.cookie('flocklab.statetab'); }
         catch (err) {
            tabsel = null;
        }
        if ( tabsel == null) {
            tabsel = 0;
        }        
        $( "#tabs" ).tabs('select',tabsel);
        $( "#tabs" ).bind( "tabsselect", function( event, ui ) {
            $.cookie('flocklab.statetab', ui.index);
        } );

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
        
        // plot map
        vis = new pv.Panel()
        .width(776)
        .height(900)
        .canvas("graph");

        force = vis.add(pv.Layout.Force)
        .nodes(sensornodes).links([])
        .iterations(0);

        force.node.add(pv.Dot)
        .shapeSize(function(d) {return 230;})
        .fillStyle(function(d) { return d.status=='online'?"green":(d.status=='offline'?"red":"grey"); })
        .strokeStyle(function() {return this.fillStyle().darker()})
        .lineWidth(1)
        .left(function(d) {return d.x})
        .bottom(function(d) {return d.y})
        .title(function(d) {return d.status})
        .event("mouseover", function(d) {d.selected = true;vis.render()})
        .event("mouseout", function(d) {d.selected = false;vis.render()});

        force.label.add(pv.Label)
        .text(function(d) {return d.node_id;})
        .font(function() {return "bold 11px sans-serif";});
        
        vis.render();
        
        // interactive platform names
         $('.targetplatform').bind('mouseover', function(event) {
            $('.targetplatform').removeClass('bold');
            $('.targetplatform:contains(' + $(this).text()+')').addClass('bold');
         });
    });
</script>
            <h1>FlockLab Status</h1>
    <div id="tabs">
    <ul>
        <li><a href="#tabs-1">Map</a></li>
        <li><a href="#tabs-2">Table</a></li>
        <li><a href="#tabs-3">3D - Plan</a></li>
    </ul>
    <div id="tabs-1" style="background-color:white">
        <div style="position:relative;margin-left:60px;padding:0;width:776px;height:800px;background-color:#fff">
            <div id="graph-bg" style="width:776px;height:800px;z-index:1;position:absolute;background:url(pics/flocklab_floormap.png);opacity:0.6;filter:alpha(opacity=60);"></div>
            <div id="graph" style="width:776px;height:419px;z-index:2;position:absolute"></div>
        </div>
    </div>
    <div id="tabs-2" style="padding-left:10px">
                <?php 
                /* Get all status information about the observers from the database and display them in the table. */
                $db = db_connect();
                $sql =    "SELECT obs.observer_id, obs.status, obs.last_changed, 
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
                        ORDER BY obs.observer_id
                        ;";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get observer information from database because: ' . mysqli_error($db));
                mysqli_close($db);
            ?>
            <div><table id="statustable" class="tablesorter" style="width:885px">
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
                        if ($row['observer_id'] < 10 )
                            echo "<td>00";
                        elseif ($row['observer_id'] < 100 )
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
                        $js.='$(sensornodes).each(function(){ if (this.node_id=='.$row['observer_id'].') { this.status="'.$row['status'].'"}});'."\n";
                    }
                ?>
                </tbody>
            </table>
            <span id="pager" class="pager">
                <img src="pics/icons/first.gif" alt="first" class="first">
                <img src="pics/icons/prev.gif" alt="prev" class="prev">
                <span class="pagedisplay"></span>
                <img src="pics/icons/next.gif" alt="next" class="next">
                <img src="pics/icons/last.gif" alt="last" class="last">
                <input class="pagesize" style="visibility: hidden;" id="pager_num_rows" value="15">
            </span> <br >
            </div>
    </div>
    <div id="tabs-3">
        <p>
            The main part of FlockLab is located inside our office building (green shaded area on the left of the picture). The outdoor nodes are located on the terrace and the wall of an adjacent building one floor below the indoor nodes (green shaded areas in the middle and right). See "Map"-tab for more information.
        </p>
        <img alt="" src="pics/flocklab_googleearth.jpg" width="900px">
    </div>
</div>

<?php
echo "<script type=\"text/javascript\">\n".$js."\n</script>";
do_layout('FlockLab Status','FlockLab Status', $javascript);
?>
