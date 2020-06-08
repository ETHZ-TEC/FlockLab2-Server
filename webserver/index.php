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
<script type="text/javascript" src="scripts/jquery.cookie.js"></script>
<script type="text/javascript">
    function getResult(testid, timeout) {
        // hide ui
        if ($(".dlpane").length == 0) {
            $("body").first().prepend('<div class="dlpane" style="position:absolute;margin:0;z-index:10000;width:100%;height:100%;background-color:#000;opacity:0.4;filter:alpha(opacity=40);"><\/div>'+
            '<div class="dlpane" style="position:absolute;font-family: Verdana, Arial, Helvetica, sans-serif;width:100%;z-index:10001;background-color:gray"><div class="info" style="width:100%"><div style="float:left;"><img height="50" width="50" alt="" src="pics/icons/wait.gif"><\/div>'+
            '<p>Please wait while test results are being fetched (Id '+testid+'). Depending on the amount of data this could take several minutes.. <\/p><\/div><\/div>'
            );
        }
        // make ajax query
        $.ajax({
            type: "POST",
            url: "result_download_archive.php",
            data: { testid : testid },
            success: function(data) {
                switch (data.status) {
                case "fetching":
                // poll again
                setTimeout("getResult("+data.testid+", "+Math.min(1000,timeout + 100)+")",timeout);
                break;
                case "success":
                // redirect
                // new iframe
                var frame_id = 'download_'+(new Date()).getTime();
                $('body').append('<iframe style="display:none" name="'+frame_id+'">');
                // set target
                $("#downloadform").attr('target', frame_id);
                $("[name=testid]","#downloadform").first().val(data.testid);
                $("[name=query]","#downloadform").first().val("get");
                $("#downloadform").submit();
                // unhide ui
                $(".dlpane").remove();
                break;
                case "error":
                // unhide ui
                $(".dlpane").remove();
                alert("An error occurred: "+data.output);
                break;
                }
            },
            dataType: "json"
        });
    }
    
    var trackTestTimer;
    
    function trackTest(testid, status) {
        // make ajax query
        $.ajax({
            type: "GET",
            url: "test_feed.php",
            data: { testid : testid },
            success: function(data) {
                if (data.length==0 || data[0].test_status != status) {
                    document.location.href="index.php";
                }
                else {
                    trackTestTimer = setTimeout("trackTest("+testid+",\""+status+"\")", 5000);
                }
            },
            fail: function() {
                trackTestTimer = setTimeout("trackTest("+testid+",\""+status+"\")", 30000);
            },
            dataType: "json"
        });
    }
    
    var addedTests=Array();
    
    var refreshPageTimer;
    
    function trackNewTests() {
        // make ajax query
        var now = new Date();
        now=Math.round(now.getTime() / 1000 - 3600 + now.getTimezoneOffset()*60);
        var x = now;
        $.ajax({
            type: "GET",
            url: "test_feed.php",
            data: { updatesince : now },
            success: function(data) {
                $(data).each(function() {
                    var testid = parseInt(this.testid);
                    if ($.inArray(testid,addedTests)<0) {
                        // reload
                        document.location.href="index.php";
                    }
                });
                refreshPageTimer = setTimeout("trackNewTests()", 5000);
            },
            fail: function() {
                refreshPageTimer = setTimeout("trackNewTests()", 30000);
            },
            dataType: "json"
        });
    }
    
    function reschedule(el) {
        $("i.starttime>form").each(function() {
            var otime = $('input[name=starttime]', this).val();
            $(this).parent().bind("click",  function() {reschedule(this)});
            $(this).parent().empty().append(otime);
        });
        var otime = $(el).text();
        var testid = $("td:first-child", $(el).parents("tr")).text();
        $(el).empty().append('<form name="reschedule" method="post" action="test_edit.php"><input type="hidden" name="testid" value="'+testid+'"><input style="width:100%" name="starttime" type="text" value="'+otime+'"></form>')
        $(el).unbind("click");
    }
    
    var editingTitle = 0;
    var editingDesc  = 0;
    
    function editTitle(testid) {
        if (editingTitle == 0) {
            editingTitle = testid;
            clearTimeout(trackTestTimer);
            clearTimeout(refreshPageTimer);
            val = $("#title" + testid).text();
            $("#title" + testid).html("<input type='text' style='overflow:visible' id='newtitle" + testid + "' value='" + val + "' />");
        }
    }
    
    function editDesc(testid) {
        if (editingDesc == 0) {
            editingDesc = testid;
            clearTimeout(trackTestTimer);
            clearTimeout(refreshPageTimer);
            val = $("#desc" + testid).text();
            $("#desc" + testid).html("<input type='text' id='newdesc" + testid + "' value='" + val + "' />");
        }
    }
    
    $(document).ready(function() {
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 40),10);
        $("#pager_num_rows").attr('value', table_rows);
        $("#test_overview")
            .tablesorter({widgets: ["zebra"] })
            .tablesorterPager({container: $("#pager"), positionFixed: false});
        $(".qtip_show").qtip( {
            content: {text: false},
            style  : "flocklab",
        });
        $("#test_overview").show();
        $.cookie.json = true;
        var test_tbl_state;
         try { test_tbl_state = $.cookie('flocklab.testsort'); }
         catch (err) {
            test_tbl_state = null;
        }
        if ( test_tbl_state == null) {
            test_tbl_state = {s: [[0,1]], p: 0};
        }
        $("#test_overview").data('tablesorter').page = test_tbl_state.p;
        $("#test_overview").trigger("sorton",[test_tbl_state.s]);
        $("#test_overview").bind("applyWidgets",function() {
            $.cookie('flocklab.testsort', {s:$("#test_overview").data('tablesorter').sortList, p:$("#test_overview").data('tablesorter').page});
        });
        // time change for not yet running tests
        $("i.starttime").bind('click', function() {reschedule(this)});
        trackNewTests();
    });
    
    $(document).mousedown(function(evt) {
        if(editingTitle > 0 && evt.target.id != "newtitle" + editingTitle) {
            newtitle = $("#newtitle" + editingTitle).val();
            if (confirm("save changes?")) {
                $.post("api.php", "s=title&id=" + editingTitle + "&val=" + newtitle, function() { location.reload(); });
            } else {
                $("#title" + editingTitle).text(newtitle);
            }
            editingTitle = 0;
        }
        if(editingDesc > 0 && evt.target.id != "newdesc" + editingDesc) {
            newdesc = $("#newdesc" + editingDesc).val();
            if (confirm("save changes?")) {
                $.post("api.php", "s=desc&id=" + editingDesc + "&val=" + newdesc, function() { location.reload(); });
            } else {
                $("#desc" + editingDesc).text(newdesc);
            }
            editingDesc = 0;
        }
    });
</script>
<?php
echo '<h1>Manage Tests for '.$_SESSION['firstname'] . ' ' . $_SESSION['lastname']. '</h1>';
                /* Get all test of the current user from the database and display them in the table. */
                $db = db_connect();
                $sql = "SELECT serv_tests_key, title, description, time_start_act, time_start_wish, time_end_act, time_end_wish, test_status, ExtractValue(testconfig_xml, 'testConf/targetConf/dbImageId') image_ids
                        FROM tbl_serv_tests 
                        WHERE owner_fk = " . $_SESSION['serv_users_key'] . " AND test_status <> 'deleted' AND test_status <> 'todelete'
                        ORDER BY serv_tests_key DESC";
                $rs = mysqli_query($db, $sql) or flocklab_die('Cannot get tests from database because: ' . mysqli_error($db));
                $nrows = mysqli_num_rows($rs);
                mysqli_close($db);
                
                // If there are no tests for this user, display a message instead of the table:
                if ($nrows == 0) {
                    echo "<p class='warning'><img alt='' src='pics/icons/att.png'>No test defined yet. Register your first test <a href='newtest.php'>here</a>.</p>";
                }
                // If there are tests for this user, display them (with alternating row coloring):
                else {
                    ?>
            <table>
              <tr>
                <td width="200px" class="transparentbg"><a style="color:#666666;text-decoration:none;" href="newtest.php"><span class="texticon">+</span> add new test</a></td>
                <td width="500px" style="text-align:center" class="transparentbg"><span id="pager" class="pager" style="text-align:right">
                      <span class="texticonsm first link bold" alt="first" title="first"><<</span>
                      <span class="texticonsm prev link bold" alt="prev" title="prev"><</span>
                      <span class="pagedisplay"></span>
                      <span class="texticonsm next link bold" alt="next" title="next">></span>
                      <span class="texticonsm last link bold" alt="last" title="last">>></span>
                      <input class="pagesize" style="visibility: hidden; width: 0px" id="pager_num_rows" value="15">
                    </span>
                </td>
                <td width="200px" class="transparentbg"></td>
              </tr>
            </table>
            <table id="test_overview" class="tablesorter" style="display:none">
                <thead>
                    <tr>
                        <th width="35px">ID</th>
                        <th width="100px">Title</th>
                        <th width="150px">Description</th>
                        <th width="30px">IMG</th>
                        <th width="35px" class='qtip_show' title='State'>State</th>
                        <th>Start</th>
                        <th>End</th>
                        <th width="80px" class='qtip_show' title='Actions'>Actions</th>
                    </tr>
                </thead>
                <tbody>
                <?php 
                    $i = 0;
                    $max_len = 60; // maximum length of text before being cut
                    $js = '';$all = array();
                    $now = new DateTime();
                    $now = $now->format('U');
                    while ($row = mysqli_fetch_array($rs)) {
                        // Find out the state of the test:
                        $schedulable  = true;
                        $planned      = false;
                        $running      = false;
                        $finished     = false;
                        $preparing    = false;
                        $cleaningup   = false;
                        $failed       = false;
                        $aborting     = false;
                        $syncing      = false;
                        $synced       = false;
                        $retentionexp = false;
                        switch($row['test_status']) {
                            case "planned":
                                $planned = true;
                                break;
                            case "preparing":
                                $preparing = true;
                                break;
                            case "running":
                                $running = true;
                                break;
                            case "cleaning up":
                                $cleaningup = true;
                                break;
                            case "finished":
                                $finished = true;
                                break;
                            case "not schedulable":
                                $schedulable = false;
                                break;
                            case "failed":
                                $failed = true;
                                break;
                            case "aborting":
                                $aborting = true;
                                break;
                            case "syncing":
                                $syncing = true;
                                break;
                            case "synced":
                                $synced = true;
                                break;
                            case "retention expiring":
                                $retentionexp = true;
                                break;
                        }
                        if ($row['test_status'] != "failed" && $row['test_status'] !="finished" && $row['test_status'] !="not schedulable" && $row['test_status'] !="retention expiring") {
                            $js .='setTimeout("trackTest('.$row['serv_tests_key'].',\"'.$row['test_status'].'\")", 3000);'."\n";
                        }
                        $all[]=$row['serv_tests_key'];
                        $i++;
                        if ($i%2 == 1) {
                            echo "<tr class='even'>";
                        } else {
                            echo "<tr class='odd'>";
                        }
                        echo "<td>" . $row['serv_tests_key'] . "</td>";
                        // Title. If longer than $max_len characters, display as tooltip:
                        echo "<td class='qtip_show' title='" . htmlentities($row['title']) . "' id='title".$row['serv_tests_key']."' ondblclick='editTitle(".$row['serv_tests_key'].")'>" . htmlentities($row['title']) . "</td>";
                        // Description. If longer than $max_len characters, display as tooltip:
                        if (strlen($row['description']) <= $max_len) 
                            echo "<td id='desc".$row['serv_tests_key']."' ondblclick='editDesc(".$row['serv_tests_key'].")'>" . htmlentities($row['description']) . "</td>";
                        else
                            echo "<td class='qtip_show' title='" . htmlentities($row['description']) . "' id='desc".$row['serv_tests_key']."' ondblclick='editDesc(".$row['serv_tests_key'].")'>" . htmlentities(substr($row['description'],0,$max_len)) . "...</td>";
                        // Image ID
                        echo "<td class='qtip_show' title='image IDs used in this test'>" . $row['image_ids'] . "</td>";
                        // Status
                        echo "<td>";
                        echo "<span style='display:none'>".$row['test_status']."</span>"; // needed to make cell sortable by JQuery
                        echo "<img src='".state_icon($row['test_status'])."' height='16px' alt='".state_short_description($row['test_status'])."' title='".state_long_description($row['test_status'])."' class='qtip_show' >";
                        echo "</td>";
                        // Start time: dependent of state of test
                        if ( $running || $cleaningup || $finished || $failed || $aborting || $syncing || $synced || $retentionexp) {
                            echo "<td title='Actual start time' class='qtip_show'>" . date_to_tzdate($row['time_start_act']). "</td>";
                        }
                        elseif ($preparing || $planned) {
                            echo "<td title='Planned start time' class='qtip_show'><i class='starttime'>" . date_to_tzdate($row['time_start_wish']). "</i></td>";
                        }
                        else
                            echo "<td title='Test is not schedulable' class='qtip_show'>n/a</td>";
                        // End time: dependent of state of test
                        if ($planned || $preparing || $running) {
                            echo "<td title='Planned end time' class='qtip_show'><i class='endtime'>" . date_to_tzdate($row['time_end_wish']). "</i></td>";
                        }
                        elseif ($cleaningup || $finished || $failed || $syncing  || $synced || $retentionexp) {
                            echo "<td title='Actual end time' class='qtip_show'>" . date_to_tzdate($row['time_end_act']). "</td>";
                        }
                        elseif ($aborting)
                            echo "<td title='Test is currently aborting' class='qtip_show'>n/a</td>";
                        elseif (!$schedulable)
                            echo "<td title='Test is not schedulable' class='qtip_show'>n/a</td>";
                        else
                            echo "<td title='Test is in unknown state' class='qtip_show'>n/a</td>";
                        // Actions: dependent of state of test
                        echo "<td>";
                        if ($planned) {
                            echo "<span style='display:none'>planned</span>"; // needed to make cell sortable by JQuery
                            echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete test' class='qtip_show link' onClick='document.tstdel.testid.value = " . $row['serv_tests_key'] . ";document.tstdel.submit();'>";
                            echo "<img src='pics/icons/edit.png' style='margin-left:3px' height='16px' alt='Edit' title='Edit test' class='qtip_show link' onClick='document.tstedt.testid.value = " . $row['serv_tests_key'] . ";document.tstedt.submit();'>";
                        } elseif ($running) {
                            echo "<span style='display:none'>running</span>"; // needed to make cell sortable by JQuery
                            echo "<img src='pics/icons/cancel.png' height='16px' alt='Abort' title='Abort test' class='qtip_show link' onClick='document.tstabrt.testid.value = " . $row['serv_tests_key'] . ";document.tstabrt.submit();'>";
                        } elseif ($preparing || $cleaningup || $syncing || $synced) {
                            echo "<span style='display:none'>preparing</span>"; // needed to make cell sortable by JQuery
                        } elseif ($finished) {
                            echo "<span style='display:none'>finished</span>"; // needed to make cell sortable by JQuery
                            echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete test' class='qtip_show link' onClick='document.tstdel.testid.value = " . $row['serv_tests_key'] . ";document.tstdel.submit();'>";
                            echo "<img src='pics/icons/download.png' style='margin-left:5px' height='16px' alt='Download' title='Download results' class='qtip_show link' onClick='getResult(".$row['serv_tests_key'].", 100);'>";
                            if ($CONFIG['viz']['generate_plots']) {
                                $plot = $CONFIG['viz']['dir'].'/flocklab_plot_'.$row['serv_tests_key'].'.html';
                                if (file_exists($plot)) {
                                    echo "<a href='show_results_plot.php?t=".$row['serv_tests_key']."' target='_blank'><img src='pics/icons/chart.png' style='margin-left:5px' height='16px' alt='Results' title='Plot results' class='qtip_show' ></a>";
                                }
                            }
                        } elseif ($retentionexp) {
                            echo "<span style='display:none'>retentionexpiring</span>"; // needed to make cell sortable by JQuery
                            echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete test' class='qtip_show link' onClick='document.tstdel.testid.value = " . $row['serv_tests_key'] . ";document.tstdel.submit();'>";
                            echo "<img src='pics/icons/download.png' style='margin-left:5px' height='16px' alt='Download' title='Download results' class='qtip_show link' onClick='getResult(".$row['serv_tests_key'].", 100);'>";
                        } elseif ($failed) {
                            echo "<span style='display:none'>notschedulable</span>"; // needed to make cell sortable by JQuery
                            echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete test.' class='qtip_show link' onClick='document.tstdel.testid.value = " . $row['serv_tests_key'] . ";document.tstdel.submit();'>";
                        } elseif (!$schedulable) {
                            echo "<span style='display:none'>notschedulable</span>"; // needed to make cell sortable by JQuery
                            echo "<img src='pics/icons/trash.png' height='16px' alt='Delete' title='Delete test.' class='qtip_show link' onClick='document.tstdel.testid.value = " . $row['serv_tests_key'] . ";document.tstdel.submit();'>";
                        } elseif ($aborting) {
                        } else {
                            echo "<span style='display:none'>unknown</span>"; // needed to make cell sortable by JQuery
                        }
                        echo "<img src='pics/icons/preview.png' style='margin-left:5px' height='16px' alt='Download config' title='Download test configuration.' class='qtip_show link' onClick='document.tstcdnl.testid.value = " . $row['serv_tests_key'] . ";document.tstcdnl.submit();'>";
                        echo "</td>";
                        echo "</tr>";
                    }
            ?>
                </tbody>
            </table>
            <br />
            <br />
            <i>Note: you can edit the test title and description with a double click.</i>
            <?php 
            echo "<script type=\"text/javascript\">
            $(document).ready(function() {
            ".$js;
            if (count($all)>0)
                echo 'addedTests.push('.implode(',',$all).');'."\n";
            echo "});\n</script>";
            }?>
            <!-- Forms for processing actions -->
            <form name="tstdel" method="post" action="test_delete.php"><input type="hidden" name="testid" value=""></form>
            <form name="tstedt" method="post" action="test_edit.php"><input type="hidden" name="testid" value=""></form>
            <form name="tstabrt" method="post" action="test_abort.php"><input type="hidden" name="testid" value=""></form>
            <form name="resdwn" method="post" id="downloadform" action="result_download_archive.php"><input type="hidden" name="testid" value=""><input type="hidden" name="query" value=""></form>
            <form name="tstcdnl" method="post" action="testconfig_download.php"><input type="hidden" name="testid" value=""></form>
<?php
do_layout('Manage Tests','Manage Tests');
?>
