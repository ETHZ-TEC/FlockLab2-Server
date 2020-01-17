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
<?php
ob_start();
$LAYOUT=TRUE;

function layout_die($status) {
    //ob_clean();
    echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
    echo "<p>Fatal Error:</p>";
    echo "<p>".$status."</p>";
    echo "</div><p></p>";
    do_layout('Error', '');
    die();
}

function do_layout($title, $current_menu_context, $javascript = "") {
    $content = file_get_contents('template/index.html');

    // do menu
    if (!isset($_SESSION['is_admin']) || !$_SESSION['is_admin'])
        $content = preg_replace('/<!-- ADMIN_START -->.*<!-- ADMIN_END -->/', '', $content);
    $content = preg_replace('#(right_arrow)(\.png\'[^>]*> '.$current_menu_context.'</a>)#', '$1_red$2', $content);
    
    // fill in content
    $content = str_replace('<!-- TEMPLATE javascript -->', $javascript, $content);
    $content = str_replace('<!-- TEMPLATE content -->',ob_get_contents (),$content);
    $content = str_replace('<!-- TEMPLATE title -->', $title, $content);
    ob_end_clean();
    ob_start("ob_gzhandler");

    // print
    echo $content;
}
?>