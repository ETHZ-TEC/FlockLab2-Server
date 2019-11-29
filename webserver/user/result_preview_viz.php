<?php 
	/*
	 * __author__      = "Roman Lim <lim@tik.ee.ethz.ch>"
	 * __copyright__   = "Copyright 2012, ETH Zurich, Switzerland"
	 * __license__     = "GPL"
	 * __version__     = "$Revision$"
	 * __date__        = "$Date$"
	 * __id__          = "$Id$"
	 * __source__      = "$URL$" 
	 */
?>
<?php
require_once('include/layout.php');require_once('include/presets.php');
$errors = array();
$style='';
if (isset($_GET['testid']))
  $testid = $_GET['testid'];
else if (isset($_POST['testid']))
  $testid = $_POST['testid'];
if (isset($testid)) {
	// check test_owner = user
	if (check_testid($testid, $_SESSION['serv_users_key'])) {
		$status = get_teststatus($testid);
// 		if ($status!='running' && $status!='cleaning up') {
// 			array_push($errors, "Only running tests have a test preview.");
// 		}
	}
	else
		array_push($errors, "Test does not belong to you.");
	// Show validation errors:
	if (isset($errors)) {
		if (!empty($errors)) {
			echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
  			echo "<p>Error occured:</p><ul>";
			foreach ($errors as $error)
				echo "<li>" . $error . "</li>";
			echo "</div><p></p>";
		} else {
$style='
<style type="text/css">
	.gpio0 {background-color: red }
	.gpio1 {background-color: blue }
	.gpio2 {background-color: #0ff }
	.gpio3 {background-color: purple }
	.gpio4 {background-color: yellow }
</style>
';
?>
<script type="text/javascript" src="scripts/jquery-ui-1.8.21.custom.min.js"></script>
<script type="text/javascript">
function log(msg) {
	$('#log').append(msg+'<br>');
}

function slide_update(progress) {
	if (progress===undefined)
		var progress = 3;
	var r = $('#slide').data('round');
	$('#slide').data('round', r+1);
	var p = parseInt($('#slide').css('left')) - progress;
	$('#slide').css('left', (p)+'px');
	view_start = slide_start - p / pps * 1e3;
	view_end = view_start + parseInt($('#view').css('width')) / pps * 1e3;
	
	// update timeline
	if (r % 3 == 0)
	$('.timeline').each(function(index) {
		var div = $(this);
		var vizmeta = div.data('vizmeta');
		if (!vizmeta.loading && (vizmeta.end < view_end + vizmeta.preloadtime)) {
			vizmeta.loading = true;
			vizmeta.updater(div);
		}
	});

	// update power
	if (r % 3 == 1)
	$('.obs > .power').each(function(index) {
		var obsdiv = $(this);
		var vizmeta = obsdiv.data('vizmeta');
		if (!vizmeta.loading && (vizmeta.end < view_end + vizmeta.preloadtime)) {
			vizmeta.loading = true;
			vizmeta.updater(obsdiv);
		}
	});
	// update gpio
	if (r % 3 == 2)
	$('.obs > .gpio').each(function(index) {
		var obsdiv = $(this);
		var vizmeta = obsdiv.data('vizmeta');
		if (!vizmeta.loading && (vizmeta.end < view_end + vizmeta.preloadtime)) {
			vizmeta.loading = true;
			vizmeta.updater(obsdiv);
		}
	});
	// update player
	if (r % 10 == 0) {
		// test.start, test.end
		// view_end 
		var player = $('#player_slider');
		var maxlen = player.width();
		var newpos = Math.round((view_end - test.start) / (test.end - test.start+1e3) * (player.width()-$('#player_slider').find('img').first().width()));
//    prog.width(prog.width()+1);
		if (progress > 0)
			$('#player_slider').find('img').first().css('left',(newpos)+'px');
		$('#player_slider').find('div').first().width((newpos+9)+'px');
	}
	

	if (reachedEnd())
		clearInterval(updateInterval);
		
};

function updateTimeline(div) {
	var vizmeta = div.data('vizmeta');
	div.append('<div style="position:absolute;left:'+Math.round(((vizmeta.end - slide_start) / 1e3 * pps))+'px;top:14px;margin:0;padding:0;height:6px;border-left:1px solid black;"><div style="text-align:center;width:60px;position:absolute;top:-15px;left:-30px">'+((vizmeta.end - test.start) / 1e3)+'<\/div><\/div>');
	vizmeta.end = vizmeta.end + 1e3;
	$(div).children().each(function() {
		if (parseInt($(this).css('left')) + 30 < -1 * parseInt($('#slide').css('left'))) {
			// remove this tick
			$(this).remove();
		}
	});

	if (vizmeta.end < test.end)
		vizmeta.loading = false;
}

function removeOld(obsdiv) {
	var oldestdiv = $('img',obsdiv).first();
	if (parseInt($(oldestdiv).css('left')) + parseInt($(oldestdiv).css('width')) < -1 * parseInt($('#slide').css('left'))) {
		// remove this image
		$(oldestdiv).remove();
		return 1;
	}
	return 0;
}
		
function powerLoadNext(obsdiv) {
	var vizmeta = obsdiv.data('vizmeta');
	var starttime = vizmeta.end - 10;
	var obsid = vizmeta.obsid;
	$.ajax({
		url: 'viz_feed.php?t='+test.id+'&o='+obsid+'&s='+starttime+'&m=0',
		type: 'GET',
		// data: { t:""+test.id, o:""+obsid, s:""+starttime, m:"0", q:"1"},
		success: function(data, textStatus, jqXHR) {
			var imgstarttime = parseInt(jqXHR.getResponseHeader('Start-Time'));
			// add image to slide
			var img = $('<img src="" alt="" style="position:absolute;left:'+Math.round(((imgstarttime- slide_start) / 1e3 * pps))+'px">');
			$(img).load(function(evtObj) {
				$(obsdiv).append($(this));
				var w = $(this).width();
				vizmeta.end = imgstarttime + w / pps * 1e3;
				if (vizmeta.end < view_end + vizmeta.preloadtime) {
					powerLoadNext(obsdiv);
				}
				else {
					if (vizmeta.end < test.end)
						vizmeta.loading = false;
					removeOld(obsdiv);
				}
			});
			$(img).attr('src', 'viz_feed.php?t='+test.id+'&o='+obsid+'&s='+starttime+'&m=0');
		},
		error: function(data, textStatus, jqXHR) {
			// start timer to retry
			if (starttime < test.end) {
				setTimeout(function() {
					if (vizmeta.end < test.end)
						vizmeta.loading = false;
				}, retryTimeout);
			}
		}
	});
}

function gpioLoadNext(obsdiv) {
	var vizmeta = obsdiv.data('vizmeta');
	var starttime = vizmeta.end-10;
	if (vizmeta.lastQueryTime > 0 && starttime <= vizmeta.lastQueryTime)
		starttime = vizmeta.lastQueryTime + 1;
	vizmeta.lastQueryTime = starttime;
	var obsid = vizmeta.obsid;
	$.ajax({
		url: 'viz_feed.php',
		dataType: 'json',
		type: 'GET',
		data: { t:""+test.id, o:""+obsid, s:""+starttime, m:"1"},
		success: function(data, textStatus, jqXHR) {
			var gpiostarttime = parseInt(jqXHR.getResponseHeader('Start-Time'));
			var state = vizmeta.state;
			// add events to slide
			var newdiv = $('<div style="position:absolute;left:'+Math.round((gpiostarttime - slide_start) / 1e3 * pps)+'px"><\/div>');
			$(data.e).each(function(){
				// l p t
				var p;
				// gpio to array: 71 > LED1, 70 > LED2, 69 > LED3, 113 > INT1, 87 > INT2
				switch (this.p) {
					case 71: p=0; break;
					case 70: p=1; break;
					case 69: p=2; break;
					case 113:p=3; break;
					case 87: p=4; break;
				}
				// <div style="position:absolute;left:500px;width:100px;height:5px;background-color:red"><\/div>
				if (this.l==0) {
					if (state[p].l == 1) {
						newdiv.append('<div class="gpio'+p+'" style="position:absolute;top:'+(p*5)+'px;left:'+Math.round((state[p].t - gpiostarttime)/ 1e3 * pps)+'px;width:'+Math.max(1, Math.round((gpiostarttime + this.t - state[p].t) / 1e3 * pps))+'px;height:5px"><\/div>');
						state[p].l = 0;state[p].t=gpiostarttime+this.t;
					}
				}
				else { // rising
					if (state[p].l == 0)
						state[p].l=1;state[p].t=gpiostarttime+this.t;
				}
				
				state[p].l=this.l;
				state[p].t=gpiostarttime+this.t;
			});
			
			obsdiv.append(newdiv);
			// check existing divs to remove
			var oldestdiv = $('div', obsdiv).first();
			var bordereventdiv = $('div',oldestdiv).last();
			if ((parseInt(bordereventdiv.css('left')) + parseInt(bordereventdiv.css('width')) + parseInt(oldestdiv.css('left'))) < -1 * parseInt($('#slide').css('left')))
				$(oldestdiv).remove();
			vizmeta.end = gpiostarttime+data.e[data.e.length-1].t;
			if (vizmeta.end < view_end + vizmeta.preloadtime)
				gpioLoadNext(obsdiv);
			else
				vizmeta.loading = false;
		},
		error: function(data, textStatus, jqXHR) {
			// start timer to retry
			if (starttime < test.end) {
				setTimeout(function() {
					if (vizmeta.end < test.end)
						vizmeta.loading = false;
				}, retryTimeout);
			}
		}
	});
}

function reachedEnd() {
	return view_end > test.end + 1e3;
}

function startSlide() {
	// check viz data
	$.ajax({
		url: 'viz_feed.php?t='+test.id,
		type: 'GET',
		success: function(data, textStatus, jqXHR) {
			var range = parseInt(jqXHR.getResponseHeader('Range-Max')) - parseInt(jqXHR.getResponseHeader('Range-Min'));
			// if ok, start it
			if (range > 60e3 || ((test.end - test.start) < 50e3)) {
				$('#wait').remove();
				$('#control').show();
				updateInterval = setInterval("slide_update()", 30);
			}
			else {
				setTimeout("startSlide()", 5e3);
				$('#wait').append('.');
			}
		},
		error: function(data, textStatus, jqXHR) {
			// start timer to retry
			setTimeout("startSlide()", 5e3);
			$('#wait').append('.');
		}
	});
}	
	
$(function() {

<?php
	// get test configuration:
	// starttime
	// endtime
	// observer ids
	$testid = $testid;
	$testconfig = new SimpleXMLElement(get_testconfig($testid));
	$obsids = array();
	
	if(isset($testconfig->powerProfilingConf->obsIds)) {
		$obsidsPp = explode(' ',$testconfig->powerProfilingConf->obsIds);
		$obsids = array_merge($obsids, array_map('intval', $obsidsPp));
	}
	if(isset($testconfig->gpioTracingConf->obsIds)) {
		$obsidsGm = explode(' ',$testconfig->gpioTracingConf->obsIds);
		$obsids = array_merge($obsids, array_map('intval', $obsidsGm));
	}
	$obsids = array_unique($obsids);

	$start = new DateTime($testconfig->generalConf->scheduleAbsolute->start);
	$start->setTimeZone(new DateTimeZone("UTC"));
	$end = new DateTime($testconfig->generalConf->scheduleAbsolute->end);
	$end->setTimeZone(new DateTimeZone("UTC"));

	echo '
	test = {
		id : '.$testid.',
		obs_list : ['.join($obsids,',').'],
		start : '.$start->format('U') * 1e3.',
		end : '.$end->format('U') * 1e3.'
	};
	';
?>
	// update for every test
	// time values in ms since 1.1.1970
	$('#h1title').empty().html('GPIO and power traces (Test-ID: '+test.id+', duration: '+Math.round((test.end - test.start)/1e3,0)+' s)');

	// constants
	pps = 100; // pixel / s
	view_end = test.start;
	view_start = view_end - parseInt($('#view').css('width')) / pps * 1e3;
	slide_start = view_start;
	preloadtime = 10e3;
	retryTimeout = 5000; // ms
	
	// TODO: query viz availability
	// if available, initialize view
	$('#view').css('height', (test.obs_list.length * 60 + 20) + "px");
	$('#labels').css('height', (test.obs_list.length * 60 + 20) + "px");
	
	// add t0
	$('#slide').append('<div style="position:absolute;left:'+parseInt($('#view').css('width'))+'px;margin:0;padding:0;height:'+(test.obs_list.length * 60 + 20)+'px;border-right:1px solid blue;"><\/div>');
	$('#slide').append('<div style="position:absolute;left:'+((test.end - slide_start) / 1e3 * pps)+'px;margin:0;padding:0;height:'+(test.obs_list.length * 60 + 20)+'px;border-right:1px solid red;"><\/div>');
	// add timeline
	var timeline = $('<div class="timeline" style="margin:0;padding:0;height:20px"><\/div>');
	timeline.data('vizmeta', { start: view_end, end: view_end, loading:false, preloadtime:preloadtime, updater:updateTimeline });
	$('#slide').append(timeline);
	$('#slide').data('round', 0);
	
	// fill slide with initial view
	$(test.obs_list).each(function(index) {
		var obsdiv = $('<div class="obs" style="margin:0;padding:0;height:60px"><\/div>');
		
		var powerdiv = $('<div class="power" style="position:absolute;margin:0;padding:0;height:60px"><\/div>');
		powerdiv.data('vizmeta', { start: view_end, end: view_end - 2e3, obsid:this, loading:false, preloadtime:preloadtime +index*60, updater:powerLoadNext, lastQueryTime:0 });
		$(obsdiv).append(powerdiv);
		
		var gpiodiv = $('<div class="gpio" style="position:absolute;margin:0;padding:0;height:60px"><\/div>');
		gpiodiv.data('vizmeta', { start: view_end, end: view_end, obsid:this, loading:false, preloadtime:preloadtime +index*60, updater:gpioLoadNext, lastQueryTime:0, state:[{l:0, t:test.start},{l:0, t:test.start},{l:0, t:test.start},{l:0, t:test.start},{l:0, t:test.start}]});
		$(obsdiv).append(gpiodiv);
		
		$('#slide').append(obsdiv);
		$('#labels').append('<div style="height:35px;text-align:right;padding-top:25px;padding-right:2px;font-weight:bold;border-right:1px solid black">'+this+'<\/div>')
	});
	
	// bind control
	$('#control').click(function() {
		if (!reachedEnd()) {
			clearInterval(updateInterval);
			if ($(this).attr('src').match(/pause.png$/)) {
				updateInterval = setInterval("slide_update(0)", 30);
				$(this).attr('src', 'pics/icons/play.png');
			}
			else {
				updateInterval = setInterval("slide_update()", 30);
				$(this).attr('src', 'pics/icons/pause.png');
			}
		}
	});
	$('#player_pos').draggable({
		axis: "x" ,
		containment: "#player_slider",
		start: function( event, ui ) {
				clearInterval(updateInterval);
				
			},
		stop: function( event, ui ) {
				// set new position
				var playerslide = parseInt($('#player_pos').css('left'));        
				var p = playerslide / ($('#player_slider').width()-$('#player_pos').width()) * (test.end - test.start + 1e3);
				p = p * pps / 1e3;
				$('#slide').css('left', (-p)+'px');
				view_start = slide_start + p / pps * 1e3;
				view_end = view_start + parseInt($('#view').css('width')) / pps * 1e3;
				// update timeline
				$('.timeline').each(function(index) {
					var vizmeta = $(this).data('vizmeta');
					vizmeta.end = parseInt(Math.max(view_start,test.start)/1e3) * 1e3;
					vizmeta.loading=false;
					$(this).empty();
				});
				// update power
				$('.obs > .power').each(function(index) {
					var vizmeta = $(this).data('vizmeta');
					vizmeta.end = parseInt(Math.max(view_start-5e3,test.start)/1e3) * 1e3;
					while (removeOld(this)){};
					vizmeta.loading=false;
					$(this).empty();
				});
				// update gpio
				$('.obs > .gpio').each(function(index) {
					var vizmeta = $(this).data('vizmeta');
					// here we would need the most recent GPIO state before our view window. As this is not deterministic, we make a conservative guess
					vizmeta.lastQueryTime = parseInt(Math.max(view_start-30e3,test.start)/1e3) * 1e3;
					vizmeta.end = vizmeta.lastQueryTime;
					$(vizmeta.state).each(function(){
						this.l=0;
					});
					vizmeta.loading=false;
					$(this).empty();
				});
				
				clearInterval(updateInterval);
				if ($('#control').attr('src').match(/pause.png$/)) {
					updateInterval = setInterval("slide_update()", 30);
				}
				else {
					updateInterval = setInterval("slide_update(0)", 30);
				}
			}      
		});

	// run slider update every .. 
	// 2s ~ 200px > speed 100px / s
	var now = new Date();
	var waittime = 120;
	if (now.getTime() - waittime * 1e3 > test.start) {
		updateInterval = setInterval("slide_update()", 30);
		$('#control').show();
	}
	else {
		//wait for data
		$('#view').append('<div id="wait" style="position:absolute;left:240px;top:50px;background-color:black;color:white;font-weight:bold;font-size:20pt;padding:8px">Processing data, please wait...'+(( test.start - (now - waittime * 1e3))/1000)+'<\/div>');
		setTimeout("startSlide()", test.start - (now - waittime * 1e3));
 	}

})

</script>
<div style="position:relative;height:30px">
	<div style="position:absolute"><h1 id="h1title">Viz</h1></div>
	<div style="float:right;width:400px">
	<div style="width:400px;position:absolute;top:-30px">
	<img id="control" style="display:none;float:right" src="pics/icons/pause.png" alt="pause/play">
	<div id="player_slider" style="float:left;margin-top:8px;border-style:solid;border-width:1px;border-color:black;width:360px;height:7px;background:url(pics/player_slider_bg.png)">
	<div style="position:absolute;width:0px;height:7px;background:url(pics/player_slider_col.png)">
	<img id="player_pos" src="pics/player_pos.png" style="position:absolute;left:-10px;top:-7px">
	<!-- div style="position:absolute;top:-45px">
	<div style="background-color:black;color:white;padding:4px"><nobr>0s .. 10s</nobr></div>
	<center><img src="pics/player_indicator.png"></center>
	</div-->
	</div>  
	</div>
	</div>
  
	</div>
</div>
<div style="position:relative;margin:0;padding:0">
	<div id="view" style="width:880px;height:100px;overflow:hidden;position:relative;left:20px">
		<div id="slide" style="position:absolute;left:0px">
		</div>
	</div>
	<div id="labels" style="width:25px;height:100px;position:absolute;top:0;left:-5px">
		<div style="height:20px;"></div>
	</div>
</div>
<div id="log"></div>

<?php
}}}
do_layout('Preview Results','Manage Tests', $style);
?>
