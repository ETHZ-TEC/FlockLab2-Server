/**
 *
 * Script for statusbar on FlockLab website. 
 * Include this script in every page where you want to use the statusbar.
 * The CSS is done in flocklab.css
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

function getFeed() {
	jQuery.getJSON('statusbar_feed.php',function(items){
		jQuery('#vertical-ticker').empty();
		var statusbarElem = 0;
		jQuery.each(items,function(index,value){
			jQuery('#vertical-ticker').append('<li>'+value+'</li>');
			statusbarElem++;
		});
		$('#status').text("FlockLab has currently " + statusbarElem + ((statusbarElem == 1) ? " issue" : " issues"));
                $('#vertical-ticker').find('.time').each(function(){
                    unixtimestamp2tzstring(this);});
		if (statusbarElem > 0) {
			$('#statusbar').show();
		}
		setTimeout('getFeed();', 30000);
	}).error(function() { setTimeout('getFeed();', 60000); });
}

$(document).ready(function() {
	$('#statusbar').hover(function() {
		$(this).find('ul').fadeIn();
	},
	function() {
		$(this).find('ul').fadeOut();
	});
	getFeed();
});
