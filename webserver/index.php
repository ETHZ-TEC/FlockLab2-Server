<?php 
    /*
     * __author__      = "Christoph Walser <walser@tik.ee.ethz.ch>"
     * __copyright__   = "Copyright 2010, ETH Zurich, Switzerland, Christoph Walser"
     * __license__     = "GPL"
     * __version__     = "$Revision: 2888 $"
     * __date__        = "$Date: 2014-08-22 10:01:11 +0200 (Fri, 22 Aug 2014) $"
     * __id__          = "$Id: index.php.normal 2888 2014-08-22 08:01:11Z rlim $"
     * __source__      = "$URL: svn://svn.ee.ethz.ch/flocklab/trunk/server/webserver/user/index.php.normal $" 
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
                    setTimeout("trackTest("+testid+",\""+status+"\")", 5000);
                }
            },
            fail: function() {
                setTimeout("trackTest("+testid+",\""+status+"\")", 30000);
            },
            dataType: "json"
        });
    }
    
    var addedTests=Array();
    
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
                setTimeout("trackNewTests()", 5000);
            },
            fail: function() {
                setTimeout("trackNewTests()", 30000);
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
    
    $(document).ready(function() {
        var table_rows = Math.max(Math.floor(($(window).height() - 300) / 25),10);
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
</script>
<?php
//echo '<br />Notice: Due to maintenance work in our building, some of the observers will be sporadically unavailable from ... to ... .<br /><br />';
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
            <table id="test_overview" class="tablesorter" style="display:none">
                <thead>
                    <tr>
                        <th width="35px">ID</th>
                        <th width="100px">Title</th>
                        <th width="130px">Description</th>
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
                    $max_len = 50; // maximum length of text before being cut
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
                        echo "<td class='qtip_show' title='" . htmlentities($row['title']) . "'>" . htmlentities($row['title']) . "</td>";
                        // Description. If longer than $max_len characters, display as tooltip:
                        if (strlen($row['description']) <= $max_len) 
                            echo "<td>" . htmlentities($row['description']) . "</td>";
                        else
                            echo "<td class='qtip_show' title='" . htmlentities($row['description']) . "'>" . htmlentities(substr($row['description'],0,$max_len)) . "...</td>";
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
            <span id="pager" class="pager">
                <span class="texticonsm first link" alt="first" title="first"><<</span>
                <span class="texticonsm prev link" alt="prev" title="prev"><</span>
                <span class="pagedisplay"></span>
                <span class="texticonsm next link" alt="next" title="next">></span>
                <span class="texticonsm last link" alt="last" title="last">>></span>
                <input class="pagesize" style="visibility: hidden;" id="pager_num_rows" value="15">
            </span> <br >
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
            <p><a style="color:#666666;text-decoration:none;" href="newtest.php"><span class="texticon">+</span> add new test</a></p>
<?php
do_layout('Manage Tests','Manage Tests');
?>
