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
<?php require_once('include/layout.php');require_once('include/presets.php'); ?>
<?php
    if (!isset($_SESSION['is_admin']) || !$_SESSION['is_admin'])
        exit(1);
    if (isset($_POST['is_active']) && isset($_POST['user_id'])) {
        $db = db_connect();
        $sql =    "UPDATE tbl_serv_users SET is_active=".mysqli_real_escape_string($db, $_POST['is_active'])." WHERE serv_users_key=".mysqli_real_escape_string($db, $_POST['user_id']);
        $rs = mysqli_query($db, $sql) or flocklab_die('Cannot update user propery in database because: ' . mysqli_error($db));
        // send email to the user
        if ($_POST['is_active']) {
            // fetch the user email
            $sql =    "SELECT email, last_login from tbl_serv_users where serv_users_key=".mysqli_real_escape_string($db, $_POST['user_id']);
            $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get user email from database because: ' . mysqli_error($db));
            $row = mysqli_fetch_array($rs);
            if (file_exists("template/newuser_emailtemplate.txt") && $row['last_login'] === NULL) {    // only send mail to new users (who have not yet logged in)
                $msg = file_get_contents("template/newuser_emailtemplate.txt");
                send_mail("Re: Request for FlockLab user account", $msg, $row['email']);
            }
        }
        mysqli_close($db);
    }
?>
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
            $("form>input[type='checkbox']").each(function() {
            $(this).bind('change',function() {
                $(this).val($(this).attr('checked')?1:0);
                $(this).attr('checked', true);
                $(this).parent().submit();
                });
        });
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 25),10);
        $("#pager_num_rows").attr('value', table_rows);        
        $("#res_overview")
            .tablesorter({widgets: ["zebra"] })
            .tablesorterPager({container: $("#pager"), positionFixed: false});
        $(".qtip_show").qtip( {
            content: {text: false},
            style  : "flocklab",
        });
        $("#res_overview").show();
        $.cookie.json = true;
        var user_tbl_state;
         try { user_tbl_state = $.cookie('flocklab.usersort'); }
         catch (err) {
            user_tbl_state = null;
        }
        if ( user_tbl_state == null) {
            user_tbl_state = {s: [[0,1]], p: 0};
        }
        $("#res_overview").data('tablesorter').page = user_tbl_state.p;
        $("#res_overview").trigger("sorton",[user_tbl_state.s]);
        $("#res_overview").bind("applyWidgets",function() { 
            $.cookie('flocklab.usersort', {s:$("#res_overview").data('tablesorter').sortList, p:$("#res_overview").data('tablesorter').page});
        });
    });
</script>
<?php
echo '<h1>Admin User Management</h1>';
                /* Get all users from the database and display them in the table. */
                $db = db_connect();
                $sql =    "SELECT serv_users_key, lastname, firstname, username, email, is_active, quota_runtime, quota_tests, role, UNIX_TIMESTAMP(create_time) as create_time_ts, DATE_FORMAT(create_time,'%d.%m.%Y') as create_date, last_login from  tbl_serv_users";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get users from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                ?>
            <form name="resadd" method="post" action="#">
            <table id="res_overview" class="tablesorter" style="display:none">
                <thead>
                    <tr>
                        <th width="70px">Username</th>
                        <th width="70px">First name</th>
                        <th width="80px">Last name</th>
                        <th width="140px">E-Mail</th>
                        <th width="50px">Create date</th>
                        <th width="50px">Quota</th>
                        <th width="30px">Role</th>
                        <th width="30px">Active</th>
                    </tr>
                </thead>
                <tbody>
                <?php 
                    $i = 0;
                    while ($row = mysqli_fetch_array($rs)) {
                        $i++;
                        if ($i%2 == 1) {
                            echo "<tr class='even'>";
                        } else {
                            echo "<tr class='odd'>";
                        }
                        echo "<td>" . htmlentities($row['username']) . "</td>";
                        echo "<td>" . htmlentities($row['firstname']) . "</td>";
                        echo "<td>" . htmlentities($row['lastname']) . "</td>";
                        echo "<td>" . htmlentities($row['email']) . "</td>";
                        echo '<td><span style="display:none">'.$row['create_time_ts'].'</span>' . htmlentities($row['create_date']) . "</td>";
                        echo "<td>" . (string)$row['quota_tests'] . " / " . (string)$row['quota_runtime'] . "min</td>";
                        echo "<td>" . htmlentities($row['role']) . "</td>";
                        echo '<td><span style="display:none">'.$row['is_active'].'</span><form action="admin_user_management.php" method="post"><input name="is_active" type="checkbox" onclick="if(this.checked) { if(!confirm(\'Active this user? An email will be sent.\')) { return false; } }" ' . ($row['is_active']==1?' checked="true"':'') . '><input type="hidden" name="user_id" value ="'.$row['serv_users_key'].'"></form></td>';
                        echo "</tr>";
                    }
            ?>
                </tbody>
            </table>
            </form>
            <span id="pager" class="pager">
                <span class="texticonsm first link" alt="first" title="first"><<</span>
                <span class="texticonsm prev link" alt="prev" title="prev"><</span>
                <span class="pagedisplay"></span>
                <span class="texticonsm next link" alt="next" title="next">></span>
                <span class="texticonsm last link" alt="last" title="last">>></span>
                <input class="pagesize" style="visibility: hidden;" id="pager_num_rows" value="15">
            </span> <br >
<?php
do_layout('User Management','User Management');
?>
