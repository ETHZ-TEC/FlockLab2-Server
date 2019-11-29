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
<?php require_once('include/layout.php');require_once('include/presets.php');
$style='
<style type="text/css">
ul#platform
{
list-style-type:none;
margin:0;
padding:0;
padding-top:6px;
padding-bottom:6px;
}

ul#platform li
{
display:inline;
}

ul#platform li a:link
{
font-weight:bold;
color:#FFFFFF;
background-color:#eee;
text-align:center;
padding:6px;
text-decoration:none;
}
ul#platform li a:hover,a:active,a.selected
{
background-color:#7A991A;
}

.timeline-default {
    font-family: Helvetica, Arial, sans serif;
    font-size: 8pt;
    border: 1px solid #aaa;
}
.tape-special_event, .small-special_event { background-color: orange; }
</style>
'; ?>

<script type="text/javascript" src="scripts/jquery-ui-1.8.21.custom.min.js"></script>
<script type="text/javascript" src="scripts/jquery.ui.slider.min.js"></script>
<script type="text/javascript" src="scripts/protovis-d3.3.js"></script>
<script type="text/javascript" src="scripts/flocklab-observer-positions.js"></script>
<script type="text/javascript">
$.urlParam = function(name){
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results != null) {
        return results[1];
    }
    return 0;
}

var force;
var vis;
var prr_range = {min:0, max:100};
var tl;
var current_test = {id:-1, start: new Date() };
var eventSource;
var events = {};
var rssi_scans;
var heatmap_done = true;
var links;

var platforms = {
	tmote :{ name:"Tmote", rssi_thresh:6, linkchannel:26, frq:function(k){return (2405 + 5 * (k-11)) + 'MHz'}},
	tinynode: { name:"TinyNode", rssi_thresh:7, linkchannel:5, frq:function(k){return (867.075 + 0.150 * k).toFixed(3)  + 'MHz'}},
	// opal_rf212: { name:"Opal(RF212)", rssi_thresh:1, linkchannel:0, frq:function(k){return (2405 + 5 * (k-11)) + 'MHz'}},
	// opal_rf230: { name:"Opal(RF230)", rssi_thresh:0, linkchannel:11, frq:function(k){return (2405 + 5 * (k-11)) + 'MHz'}},
  // iris: { name:"IRIS", rssi_thresh:6, linkchannel:11, frq:function(k){return (2405 + 5 * (k-11)) + 'MHz'}},
  // mica2: { name:"Mica2", rssi_thresh:0, linkchannel:0, frq:function(k){return (915.998 - 1.921 * k).toFixed(3) + 'MHz'}},
	// cc430: { name:"CC430", rssi_thresh:0, linkchannel:0, frq:function(k){return (915.998 - 1.921 * k).toFixed(3) + 'MHz'}},
	dpp: { name:"DPP", rssi_thresh:0, linkchannel:0, frq:function(k){return (915.998 - 1.921 * k).toFixed(3) + 'MHz'}}
};

var platform = platforms.tmote;
var rssi_channel = platforms.tmote.linkchannel;

function loadTestData(newplatform, selected) {
	eventSource.clear();
	$("#platform").find("a").removeClass("selected");
	tl.loadJSON("link_feed.php?p="+newplatform, function(json, url) {
		$(json.events).each(function() {
			this.icon=Timeline_urlPrefix + "images/green-circle.png";
		});
		events = json.events;
		eventSource.loadJSON(json, url);
		$(selected).find("a").addClass("selected");
		var closest = -1;
		var closest_int = -1;
		var closest_start = -1;
		$(eventSource.getAllEventIterator()._events._a).each(function() {
			if (closest < 0 || closest_int > Math.abs(this._start - current_test.start)) {
				closest=parseInt(this._obj.description);
				closest_int = Math.abs(this._start - current_test.start)
				closest_start = this._start;
			}
		});
		if (closest>0) {
			loadTestDataId(closest);
			current_test.id = closest;
			current_test.start = closest_start;
			tl.getBand(0).getEventPainter().paint();
		}
		else {
			// empty display
			var links = new Array();
			$(sensornodes).each(function(){ this.seen = false; });
			force.links(links).iterations(0);
			force.reset();
			vis.render();
			$("#heatmap").hide();
		}
	});
}

function setLinkMap(channel) {
	if (platform.linkchannel==channel) {
		force.links(links).iterations(0);
		$( "#amount" ).empty().text( "PRR: " + $( "#slider-range" ).slider( "values", 0 ) +
			"% - " + $( "#slider-range" ).slider( "values", 1 ) +"%");
	}
	else {
		var nolinks = new Array();
		force.links(nolinks).iterations(0);
		$( "#amount" ).empty().text( "no PRR available");
	}
	force.reset();
	vis.render();
}

function setHeatMap(channel) {
	var scan;
	heatmap_done = false;
	// check channel for link graph
	setLinkMap(channel);
	$(rssi_scans).each(function(){
		if (this.channel == channel)
			scan = this;
	});
	$(sensornodes).each(function(){
		this.rssi=0;
		var node = this;
		$(scan.nodes).each(function() {
			if (node.node_id == this.id)
				node.rssi = this.rssi;
		});
	});
	heatmap($('#heatmap'), 100, 110);
	heatmap_done = true;
	if (channel != rssi_channel) {
		setHeatMap(rssi_channel);
	}
}


function loadTestDataId(id) {
	links = new Array();
	$.ajax({
		url: "link_feed.php?q="+id,
		success: function(data) {
		var waslinkchannel = (platform.linkchannel==rssi_channel);
		var network = $("network", data).first();
		var platform_key = $(network).attr('platform').toLowerCase();
		if ($(network).attr('radio') !== undefined)
			platform_key = platform_key + '_' + $(network).attr('radio').toLowerCase();
		$.each(platforms, function(key){
			if (key==platform_key) {
				platform=this;
			}
		});

		// rssi
		rssi_scans = [];
		var ch = {min:Number.POSITIVE_INFINITY , max:Number.NEGATIVE_INFINITY};
		$("rssiscan", data).each(function(){
			var scan ={channel: parseInt($(this).attr("channel")), nodes:[]};
			ch.min = Math.min(ch.min, parseInt($(this).attr("channel")));
			ch.max = Math.max(ch.max, parseInt($(this).attr("channel")));
			$(this).children().each(function(){

			var frq = $(this).attr('frq').split(',');
			var id = parseInt($(this).attr('nodeid'));
			var rssi = 0; var sum = 0;
			var max_frq = 0;
			var frq_mode = 0;
			$(frq).each(function(index) {
        if (parseInt(this) > max_frq) {
          max_frq = parseInt(this);
          frq_mode = index;
        }
      });
			$(frq).each(function(index) {
        var w = index - (frq_mode + platform.rssi_thresh);
				if (w > 0)
					rssi+=parseInt(this) * w;
        w = Math.max(1, w);
				sum += parseInt(this) * w;
			});
			scan.nodes.push({id:id, rssi: rssi / sum * 100});
			});
			rssi_scans.push(scan);
		});
		if (ch.min == Number.POSITIVE_INFINITY) {
			$( "#slider-range-rssi" ).slider( "option" , { min: NaN, max: NaN} );
			$( "#amount-rssi" ).empty().text( "no RSSI data");
			$("#heatmap").hide();
			rssi_channel = platform.linkchannel;
		}
		else {
			if (waslinkchannel) {
				rssi_channel = platform.linkchannel;
			}
			else {
				if (rssi_channel < ch.min)
					rssi_channel = ch.min;
				else if (rssi_channel > ch.max)
					rssi_channel = ch.max;
			}
			$( "#slider-range-rssi" ).slider( "option" , { min: ch.min,max: ch.max, value: rssi_channel} );
			$( "#amount-rssi" ).empty().text( "Ch: "+rssi_channel + " (" + platform.frq(rssi_channel)+")");
			setHeatMap(rssi_channel);
			$("#heatmap").show();
		}

		// topology
		$(sensornodes).each(function(){ this.seen = false; });
		$("link", data).each(function(){
			var src_id = parseInt($(this).attr("src"));
			var dest_id = parseInt($(this).attr("dest"));
			var src, dest;
			$(sensornodes).each(function(index){
				if (this.node_id==src_id) {
					src=index;
					this.seen = true;
				}
				if (this.node_id==dest_id) {
					dest=index;
					this.seen = true;
				}
			});
			if (src===undefined || dest===undefined) {
				//alert("warning, src or destination of link not found.");
			}
			else {
				links.push({source:src, target:dest, value:Math.pow(parseFloat($(this).attr("prr"))*10,2)});
			}
		});
		setLinkMap(rssi_channel);

		},
	dataType: "xml"
	});
}

function heatmap(div, xnum, ynum) {
	$(div).empty();
	var vis = new pv.Panel()
	.width(div.width())
	.height(div.height())
	.canvas("heatmap")
	.antialias(false);
	var maxdist = 100;
	var xf =  xnum / div.width();
	var yf =  ynum / div.height();
	vis.add(pv.Image)
		.imageWidth(xnum)
		.imageHeight(ynum)
		.image(pv.Scale.linear()
		.domain(0, 25, 50, 95)
		.range("#fff", "#ee0", "#ff0","#f00")
		.by(function(i, j) {
			var sumdist = 1/10000;
			var sumval = 0;
			$(sensornodes).each(function() {
				var dist_sqr = Math.pow(Math.pow(i - this.x * xf, 2) + Math.pow(j - this.y * yf, 2),2);
				sumdist += 1 / dist_sqr;
				sumval += this.rssi / dist_sqr;
			});
			return sumval / sumdist;
		}));
	vis.render();
	// scale hack
	var canvas = $("canvas", div).first();
	canvas.width(div.width());
	if(!document.implementation.hasFeature('http://www.w3.org/TR/SVG11/feature#Extensibility','1.1')){ // no support for foreignObject in SVG
		canvas.prependTo(div); // move it directly to div
	}
}

$(document).ready(function() {
vis = new pv.Panel()
    .width(776)
    .height(900)
    .canvas("graph");

force = vis.add(pv.Layout.Force)
    .nodes(sensornodes).links([])
    .iterations(0);

force.link.add(pv.Line).strokeStyle(function(d, l) {
	if (l.value < prr_range.min || l.value > prr_range.max)
		return;
	return d.selected ? "rgba(10, 200, 10, 0.5)" : "rgba(80, 80, 80, 0.2)";
});

force.node.add(pv.Dot)
    .shapeSize(function(d) {return 230;})
    .fillStyle(function(d) { return d.seen?(d.selected?"#00ff00":"green"):"grey"; })
    .strokeStyle(function() {return this.fillStyle().darker()})
    .lineWidth(1)
    .left(function(d) {return d.x})
    .bottom(function(d) {return d.y})
    .title(function(d) {return d.node_id})
    .event("mouseover", function(d) {d.selected = true;vis.render()})
    .event("mouseout", function(d) {d.selected = false;vis.render()});

force.label.add(pv.Label)
	  .text(function(d) {return d.node_id;})
	  .font(function() {return "bold 11px sans-serif";});
vis.render();

$("#platform").empty();
$.each(platforms, function(n) {
	$("#platform").append("<li><a href=\"\">"+this.name+"<\/a><\/li>");
	var p = n;
	$("li", "#platform").last().bind("click", function() { $("#useinfo").hide();loadTestData(p, this);return false;});
});

$("#log").append("");
$( "#slider-range" ).slider({
			range: true,
			values: [ 0, 100 ],
			slide: function( event, ui ) {
				$( "#amount" ).empty().text( "PRR: " + ui.values[ 0 ] + "% - " + ui.values[ 1 ] +"%");
				prr_range.min = ui.values[ 0 ];
				prr_range.max = ui.values[ 1 ];
				vis.render();
			}
});
$( "#amount" ).empty().text( "PRR: " + $( "#slider-range" ).slider( "values", 0 ) +
			"% - " + $( "#slider-range" ).slider( "values", 1 ) +"%");

$( "#slider-range-rssi" ).slider({
			range: "min",
			min: 11,
			max: 26,
			value: 11,
			slide: function( event, ui ) {
				$( "#amount-rssi" ).empty().text( "Ch: " + ui.value + " (" + platform.frq(ui.value)+")");
				rssi_channel = ui.value;
				if (heatmap_done = true)
					setHeatMap(rssi_channel);
			}
});
$( "#amount-rssi" ).empty().text( "Channel");

// Timeline
Timeline.OriginalEventPainter.prototype._showBubble = function(x, y, evt) {
	loadTestDataId(evt.getDescription ());
	current_test.id = evt._obj.description;
	current_test.start = evt._start;
	tl.getBand(0).getEventPainter().paint();
}
var theme = Timeline.ClassicTheme.create();
eventSource = new Timeline.DefaultEventSource();
var bandInfos = [
     Timeline.createBandInfo({
	eventSource:    eventSource,
	 width:          "70%",
	 intervalUnit:   Timeline.DateTime.DAY,
	 intervalPixels: 100,
	 theme:          theme
     }),
     Timeline.createBandInfo({
	eventSource:    eventSource,
	 width:          "30%",
	 intervalUnit:   Timeline.DateTime.MONTH,
	 intervalPixels: 200,
	 showEventText:  false,
	 theme:          theme
     })
   ];

   bandInfos[1].syncWith = 0;
   bandInfos[1].highlight = true;
   tl = Timeline.create(document.getElementById("timeline"), bandInfos, Timeline.HORIZONTAL);
   tl.getBand(0).getEventPainter().setHighlightMatcher(function(evt) {
	return (current_test.id == evt._obj.description)?1:-1;
   });
   tl.loadJSON("link_feed.php?p=2", function(json, url) {
       $(json.events).each(function() {
	  this.icon=Timeline_urlPrefix + "images/green-circle.png";
       });
       eventSource.loadJSON(json, url);
   });

//heatmap($('#heatmap'), 100, 110);
  // check for GET request
  if ($.urlParam('p')) {
    var getpar = $.urlParam('p');
    var elem = $('#platform').find("a");
    $.each(elem, function(n) {
      if ($(this).text()==getpar) {
      var e = this;
        $.each(platforms, function(n) {
          if (this.name==getpar) {
            loadTestData(n, $(e).parent());
          }
        });
      }
    });
  }
});
</script>

<h1>Connectivity Map</h1>
<div style="height:40px">
<div style="float:left"><ul id="platform"><li></li></ul></div>
<div style="float:left;position:relative;width:0px;height:0px;">
<div id="useinfo" style="position:relative;z-index:10;left:3px;height:30px;padding:5px;width:450px;background-color:#DDD"><img src="pics/icons/left_arrow.png" alt=""> <b>Please choose a platform</b></div>
</div>
<div class="ui-widget" style="margin-left:10px;float:left;height:30px;width:200px">
	<div id="slider-range" style="margin:5px;height:5px"></div>
	<div id="amount" style="margin-left:30px">test</div>
</div>
<div class="ui-widget" style="margin-left:20px;float:left;height:30px;width:200px">
	<div id="slider-range-rssi" style="margin:5px;height:5px"></div>
	<div id="amount-rssi" style="margin-left:30px">test</div>
</div>
</div>
<div style="position:relative;padding:0;width:776px;height:900px;background-color:#fff">
 <div id="graph-bg" style="width:776px;height:900px;z-index:1;position:absolute;background:url(pics/floormap_etz_etf.png);background-repeat:no-repeat;opacity:0.6;filter:alpha(opacity=60);"></div>
 <div id="graph" style="width:776px;height:900px;z-index:2;position:absolute"></div>
 <div id="heatmap" style="width:776px;height:900px;position:absolute;left:0px;top:0px;z-index:0"></div>
 <div id="info" style="width:400px;height:300px;position:absolute;left:350px;top:550px;z-index:1;border:solid 2px black;background-color:#fff;padding:3px">
 This map visualizes two types of measurements for every platform. Measurements are performed on a regular basis. Platform, PRR range and channel is selectable with the buttons/sliders on the top.<br>
 <h3>Link quality</h3>
 In a round robin fashion, every node broadcasts 100 packets and all other nodes count the number of packets they overheard in each round. The packet reception ratio (PRR) is then calculated from this data. Thicker links between nodes indicate better PRR.
 <h3>Noise floor</h3>
 Nodes sample the signal strength in every channel. Red indicates a high noise floor, while yellow or white represents lower noise.
 </div>
</div>
<div id="timeline" class="timeline-default" style="height: 130px;width:776px; border: 1px solid #aaa; margin-top:5px"></div>

<div id="log"></div>
<?php
$timelinescript = '
<link rel="stylesheet" href="css/ui-lightness/jquery-ui-1.8.20.custom.css">
<script type="text/javascript">
      Timeline_ajax_url="scripts/timeline_2.3.0/timeline_ajax/simile-ajax-api.js";
      Timeline_urlPrefix="scripts/timeline_2.3.0/timeline_js/";
      Timeline_parameters="bundle=true";
</script>
<script type="text/javascript" src="scripts/timeline_2.3.0/timeline_js/timeline-api.js" ></script>
';

do_layout('Connectivity Map','Connectivity Map', $style."\n".$timelinescript);
?>
