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
