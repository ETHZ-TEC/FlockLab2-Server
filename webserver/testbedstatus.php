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
<?php
  require_once('include/layout.php');
  require_once('include/presets.php');

  /* Get all status information about the observers from the database and display them in the table. */
  $db = db_connect();
  $sql = "SELECT observer_id, status FROM `flocklab`.`tbl_serv_observer`
          WHERE status!='disabled' AND status!='develop'
          ORDER BY observer_id;";
  $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get observer information from database because: ' . mysqli_error($db));
  mysqli_close($db);
  
  // get currently used observers
  $obslist = get_used_observers();
  $js = '';
  while ($row = mysqli_fetch_array($rs)) {
      if (in_array($row['observer_id'], $obslist)) {
          $row['status'] = 'in use';
      }
      $js.='$(sensornodes).each(function(){ if (this.node_id=='.$row['observer_id'].') { this.status="'.$row['status'].'"}});'."\n";
  }
?>
<script type="text/javascript" src="scripts/jquery-ui-1.8.21.custom.min.js"></script>
<script type="text/javascript" src="scripts/protovis-d3.3.js"></script>
<script type="text/javascript" src="scripts/flocklab-observer-positions.js"></script>
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
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
        .fillStyle(function(d) { return d.status=='online'?"green":(d.status=='offline'?"red":(d.status=='in use'?"yellow":"grey")); })
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
        
        // refresh this page in 30 seconds
        setTimeout(function() {
            location.reload();
        }, 30000);
    });
</script>
<h1>Observer Status</h1>
<br />
<div style="position:relative;margin-left:60px;padding:0;width:776px;height:420px;background-color:#fff">
    <div id="graph-bg" style="width:776px;height:420px;z-index:1;position:absolute;background:url(pics/flocklab_floormap.png);opacity:0.6;filter:alpha(opacity=60);"></div>
    <div id="graph" style="width:776px;height:420px;z-index:2;position:absolute"></div>
    <div id="graph-bg" style="width:776px;height:269px;top:500px;z-index:1;position:absolute;background:url(pics/flocklab_remote_locations_scaled.png);opacity:0.6;filter:alpha(opacity=60);"></div>
    <div style="width:300px;height:30px;left:200px;top:50px;z-index:2;position:absolute">Indoor Nodes (ETZ G Floor)</div>
    <div style="width:300px;height:30px;left:200px;top:460px;z-index:2;position:absolute">Outdoor Nodes (City of Zurich)</div>
</div>

<?php
  echo "<script type=\"text/javascript\">$js</script>";
  do_layout('Observer Status','Observer Status', '<link rel="stylesheet" href="css/ui-lightness/jquery-ui-1.8.20.custom.css">');
?>
