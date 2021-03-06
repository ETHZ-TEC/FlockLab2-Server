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
        if (isset($_POST['inlist']) && isset($_POST['group'])) {
            $db = db_connect();
            foreach ($_POST['inlist'] as $user) {
                $sql =    "DELETE FROM tbl_serv_user_groups where group_fk=".mysqli_real_escape_string($db, $_POST['group'])." and user_fk=".mysqli_real_escape_string($db, $user);
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot remove user from group because: ' . mysqli_error($db));
                echo "remove user ".$user." from group ".$_POST['group'];
            }
            mysqli_close($db);
        }
        if (isset($_POST['notinlist']) && isset($_POST['group'])) {
            $db = db_connect();
            foreach ($_POST['notinlist'] as $user) {
                $sql =    "insert into tbl_serv_user_groups (group_fk, user_fk) values (".mysqli_real_escape_string($db, $_POST['group']).",".mysqli_real_escape_string($db, $user).")";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot add user to group because: ' . mysqli_error($db));
                echo "add user ".$user." to group ".$_POST['group'];
            }
            mysqli_close($db);
        }
?>
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
            $([$("#add_start_time"), $("#add_end_time")]).each(function() {
            var otime = $(this).html();
            $(this).empty().append('<input style="width:200px" name="'+this[0].id+'" value="'+otime+'">');
        });
    });
</script>
<?php
echo '<h1>Admin Groups</h1>';
                /* Get groups */
                $db = db_connect();
                $sql =    "SELECT serv_groups_key, groupname FROM tbl_serv_groups";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get reservations from database because: ' . mysqli_error($db));
                $groups = array();
                while ($row = mysqli_fetch_array($rs)) {
                    $groups[$row['serv_groups_key']]=$row['groupname'];
                }
                if (empty($_POST['group'])) {
                    reset($groups);
                    $selgroup = key($groups);
                }
                else {
                    $selgroup = $_POST['group'];
                }
                $sql =    "SELECT group_fk, serv_users_key, username FROM tbl_serv_user_groups left join tbl_serv_users on (user_fk=tbl_serv_users.serv_users_key) where group_fk=".$selgroup." order by username";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get reservations from database because: ' . mysqli_error($db));
                $isuser = array();
                while ($row = mysqli_fetch_array($rs)) {
                    $isuser[$row['serv_users_key']]=$row['username'];
                }
                $sql =    "SELECT sum(group_fk=".$selgroup.") as isgroup, serv_users_key, username FROM tbl_serv_users left join tbl_serv_user_groups on (user_fk=tbl_serv_users.serv_users_key) group by serv_users_key having isgroup is null or isgroup=0 order by username";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get reservations from database because: ' . mysqli_error($db));
                $notuser = array();
                while ($row = mysqli_fetch_array($rs)) {
                    $notuser[$row['serv_users_key']]=$row['username'];
                }
                mysqli_close($db);
                $max_len = 50;
                ?>
            <form name="resadd" method="post" action="admin_groups.php">
            <table>
                <thead>
                    <tr>
                        <th width="300px">Group</th>
                        <th width="100px">Users not in group</th>
                        <th width="100px">Users in group</th>
                    </tr>
                </thead>
                <tbody>
                <tr><td></td><td>Select users to add<br><center><img src="pics/icons/sort_desc.gif"></center></td><td>Select users to be removed<br><center><img src="pics/icons/sort_desc.gif"></center></td></tr>
            <?php 
                    echo '<tr><td><select name="group" style="width:200px" onChange="$(document.chgrp.group).val($(this).val());document.chgrp.submit()">';
                    foreach ($groups as $idx=>$names) {
                        if (strlen($names) <= $max_len) 
                            echo '<option value="'.$idx.'"'.($idx==$selgroup?' selected="selected"':'').'>' . $names . '</option>';
                        else
                            echo '<option value="'.$idx.'"'.($idx==$selgroup?' selected="selected"':'').'>'. substr($names,0,$max_len) . '...</option>';
                    }
                    echo '</select></td><td><select name="notinlist[]" multiple style="width:150px;height:400px">';
                    foreach ($notuser as $idx=>$user) {
                        echo '<option value="'.$idx.'">' . $user . '</option>';
                    }
                    echo '</select></td><td><select name="inlist[]" multiple style="width:150px;height:400px">';
                    foreach ($isuser as $idx=>$user) {
                        echo '<option value="'.$idx.'">' . $user . '</option>';
                    }
                    echo "</td></tr></tbody></table><input type='button' onClick='document.resadd.submit()' value='update group'>";
            ?>
            </form>
            <!-- Forms for processing actions -->
            <!--<form name="resdel" method="post" action="admin_group_reservation.php"><input type="hidden" name="resid" value=""></form>-->
            <form name="chgrp" method="post" action="admin_groups.php"><input type="hidden" name="group" value=""></form>
<?php
do_layout('Groups','Groups');
?>
