/**
 *
 * QTip configuration for FlockLab website. 
 * Include this script in every page where you want to use qTip tooltips.
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
 
 
/* qTip default style */

$.fn.qtip.styles.flocklab = {
	width: 200,
	padding: 5,
	textAlign: 'center',
	'font-size': 'x-small',
	'font-family': 'Verdana, Arial, Helvetica, sans-serif',
	border: {
		width: 7,
		radius: 5,
	},
	tip: 'topLeft',
	position: {
		corner: {
			target: 'topRight',
			tooltip: 'bottomLeft'
		}
	},
	name: 'dark'
}

