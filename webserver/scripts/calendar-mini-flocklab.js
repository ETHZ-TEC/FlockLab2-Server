/**
 *
 * Fullcalendar template for FlockLab website. 
 * Include this script in every page where you want to use the calendar
 * in mini calendar mode. The CSS is done in flocklab.css
 *
 *
 * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
 * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
 * __license__     = "GPL"
 * __version__     = "$Revision$"
 * __date__        = "$Date$"
 * __id__          = "$Id$"
 * __source__      = "$URL$" 
 *
 */
 
$(document).ready(function() {
	/**
	* returns a Date object constructed from the UTC date string s
	**/
	function UTCDate(s) {
	  var s_ = s;
	  var parts = s_.match(/(\d+)/g);
	  var d = new Date()
	  d.setUTCFullYear(parts[0], parts[1]-1, parts[2]);
	  d.setUTCHours(parts[3], parts[4], parts[5]);
	  return d;
	}
	
	$('#minicalendar').fullCalendar({
		header: {
			left:   '',
			center: 'title',
			right:  ''
		},
		firstDay:    1,
		weekends:    true,
		lazyFetching: true,
		eventColor: '#1F407A',
		defaultView: 'month',
		slotMinutes: 30,
		allDaySlot:  false,
		axisFormat:  'HH:mm',
		weekMode:    'liquid',
		timeFormat: {
			agenda:      'HH:mm{ - HH:mm}',
			'':          'HH:mm{ - HH:mm}'
		},
		columnFormat: {
			agendaWeek:      'ddd MM-dd'
		},
		events: function(start, end, callback) {
		  $.ajax({
		  url: 'fullcalendar_feed.php',
		  dataType: 'json',
		  data: {
		    "start": start.getTime()/1000,
		    "end": end.getTime()/1000,
			"mini": true,
		  },
		  success: function(data) {
		    var events = [];
			var day_events = [];
			var day = '';
			var thisday;
			var day_min = 0;
			var day_max = 0;
		    $(data).each(function() {
				if (this.start != null && this.end != null) {
					this.start = UTCDate(this.start);
					this.end = UTCDate(this.end);
					thisday = this.start.getFullYear()+'-'+(1+this.start.getMonth())+'-'+this.start.getDate();
					if (day!=thisday) {
						if (day_events.length > 5) {
							events = events.concat({id:day, color:"#40508d", title:"more than 5 tests",description:'', allDay:false,start:new Date(day_min),end:new Date(day_max)});
						}
						else {
							events = events.concat(day_events);
						}
						day = thisday;
						day_events=[];
						day_min = this.start;
						day_may = this.end;
					}
					day_min = Math.min(this.start, day_min);
					day_max = Math.max(this.end, day_max);
					day_events.push(this);
				}
			});
			events = events.concat(day_events);
			setTimeout("$('#minicalendar').fullCalendar( 'refetchEvents' );",30000);
			callback(events);
		  },
		  fail: function() {
			setTimeout("$('#minicalendar').fullCalendar( 'refetchEvents' );",60000);
		  }
		  });
		},
		eventRender: function(event, element) {
			var starthours   = event.start.getHours();
			var startminutes = event.start.getMinutes();
			if (event.end == null) {
				var endhours     = event.start.getHours();
				var endminutes   = event.start.getMinutes();
			}
			else {
				var endhours     = event.end.getHours();
				var endminutes   = event.end.getMinutes();
			}
			var starttime = ((starthours < 10) ? "0" + starthours : starthours) + ":" + ((startminutes < 10) ? "0" + startminutes : startminutes);
			var endtime   = ((endhours < 10) ? "0" + endhours : endhours)       + ":" + ((endminutes < 10) ? "0" + endminutes : endminutes);
			element.qtip({
				content: '<b>' + starttime + ' - ' + endtime + '</b> ' + event.title,
				style: 'flocklab',
			});
			
		},
	});
});
