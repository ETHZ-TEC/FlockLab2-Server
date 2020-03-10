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
    <script type="text/javascript">
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
            
            $('#calendar').fullCalendar({
                header: {
                    left:   'prev,next today',
                    center: 'title',
                    right:  'agendaDay,agendaWeek,month'
                },
                firstDay:    1,
                weekends:    true,
                lazyFetching: true,
                eventColor:  '#28549f',
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
                //events:      'fullcalendar_feed.php',
                events: function(start, end, callback) {
                    $.ajax({
                        url: 'fullcalendar_feed.php',
                        dataType: 'json',
                        data: {
                            "start": start.getTime()/1000,
                            "end": end.getTime()/1000,
                        },
                        success: function(data) {
                            var events = [];
                            var now = new Date();
                            $(data).each(function() {
                                if (this.start != null && this.end != null) {
                                    this.start = UTCDate(this.start);
                                    this.end = UTCDate(this.end);
                                    if (this.end < this.start) {
                                        this.end = new Date(this.start.getTime() + 1000);
                                    }
<?php
if ($_SESSION['is_admin']) {
echo '
                                    if (this.color=="chocolate" || !this.hasOwnProperty("color"))
                                        this.url="webdavs://'.$_SESSION['username'].'@'.preg_replace('#/[^/]*$#','',$_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI']).'/webdav/"+this.id+"/";
';}
else {
echo '
                                    if (this.color=="chocolate")
                                        this.url="webdavs://'.$_SESSION['username'].'@'.preg_replace('#/[^/]*$#','',$_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI']).'/webdav/"+this.id+"/";
';}
?>
                                    events.push(this);
                                }
                            });
                            callback(events);
                        }
                    });
                },
                eventRender: function(event, element) {
                    element.qtip({
                        content: event.description,
                        style: 'flocklab',
                    });
                },
                loading: function(bool) {
                    if (!bool) {
                        // Scroll to today:
                        var now = new Date();
                        var elem = $('#calendar').find('*[data-date="' + now.getFullYear()+ "-" + (now.getMonth()+1<10?'0':'') + (now.getMonth()+1) + "-" + now.getDate() + '"]');
                        if (elem.html() != null) {
                            $('html, body').animate({ scrollTop: (elem.offset().top)}, 'slow');
                        }
                    }
                },
            });            
        });
    </script>
            <h1>Full Calendar</h1>
            <div id='calendar' class='calendar'></div>
<?php
do_layout('Full Calendar','Full Calendar');
?>
