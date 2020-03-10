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
  $js = '';
  while ($row = mysqli_fetch_array($rs)) {
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
<h1>Observer Status</h1>
<br />
<div style="position:relative;margin-left:60px;padding:0;width:776px;height:800px;background-color:#fff">
    <div id="graph-bg" style="width:776px;height:800px;z-index:1;position:absolute;background:url(pics/flocklab_floormap.png);opacity:0.6;filter:alpha(opacity=60);"></div>
    <div id="graph" style="width:776px;height:419px;z-index:2;position:absolute"></div>
</div>

<?php
  echo "<script type=\"text/javascript\">$js</script>";
  do_layout('Observer Status','Observer Status', '<link rel="stylesheet" href="css/ui-lightness/jquery-ui-1.8.20.custom.css">');
?>
