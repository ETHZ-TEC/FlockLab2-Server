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
    $errors = array();
    $process = false;
    if (isset($_POST['submit'])) {
        $process = true;
        $image = Array();
        // Get the file and check if it is a valid image
        $imagefile = $_FILES['imagefile'];
        if ($imagefile["error"] != 0) {
          // There was an error during file upload:
          array_push($errors, "There was an error when uploading the file.");
        }
        else {
          $image['data']=file_get_contents($imagefile['tmp_name']);
        }
        foreach(Array('name','description','os') as $field)
          $image[$field] = isset($_POST[$field])?$_POST[$field]:null;
        if (isset($_POST['platform'])) {
            $image['core'] = preg_replace('/.*_/','',$_POST['platform']);
            $image['platform'] = preg_replace('/_.*/','',$_POST['platform']);
        }
        if (validate_image($image, $errors)) {
          $dup = check_image_duplicate($image);
          if ($dup!==false)
            array_push($errors, "Image already exists in database (Id ".$dup.")");
          else
            $image_id = store_image($image);
        }
    }

    /* If the page is called with a file associated, validate it and show the results */
    if ($process && empty($errors)) {
      echo "<div class=\"info\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/success.png\"></div>";
      echo "<p>The image (Id ".$image_id.") has been successfully added.</p><ul>";
      echo "</div><p></p>";
      include('images.php');
      echo '<meta http-equiv="Refresh" content="10; URL=images.php">';
      exit();
    }
?>
<script type="text/javascript">
    $(document).ready(function() {
        $('.qtip_show').qtip( {
            content: {text: false},
            style  : 'flocklab',
        });
        $("#uploadform").validate({
            rules: {
                imagefile: "required",
            },
            errorPlacement: function(error, element) {
                error.insertAfter(element);
            }
        });
    });
</script>

<h1>Upload Test Image</h1>
<br />
<?php
    // Show validation errors:
    if (!empty($errors)) {
      echo "<div class=\"warning\"><div style=\"float:left;\"><img alt=\"\" src=\"pics/icons/att.png\"></div>";
      echo "<p>Please correct the following errors:</p><ul>";
      foreach ($errors as $error)
        echo "<li>" . $error . "</li>";
      echo "</div><p></p>";
    }
    echo '
      <form id="uploadform" name="uploadform" method="post" action="newimage.php" enctype="multipart/form-data">
      <fieldset>
        <legend>Upload new test image</legend>
        <span class="formfield qtip_show" title="Provide file in ELF (Executable and Linkable Format) or Intel hex format. Note that binary patching (assigning node IDs) is only supported with ELF files.">Image File (ELF/hex):*</span><input type="file" name="imagefile" id="imagefile" size="27" class="required"><br />
        <span class="formfield">Name:*</span><input type="text" name="name" size="27" class="required" value="'.(isset($_POST['name'])?htmlentities($_POST['name']):'').'"><br />
        <span class="formfield">Description:</span><textarea name="description" size="27">'.(isset($_POST['description'])?htmlentities($_POST['description']):'').'</textarea><br />
        <span class="formfield">Platform:*</span><select name="platform" class="required"><option />';
    foreach (get_available_platforms() as $key => $platform) {
      foreach ($platform as $pcore) {
          $cdesc = strlen($pcore['core_desc']) > 0 ? ': '.$pcore['core_desc'] : '';
          $corekey = $key.'_'.$pcore['core'];
          echo '<option value="'.$corekey.'"'.(isset($_POST['platform']) && $_POST['platform']==$corekey ? ' selected="true"' : '').'>'.$pcore['name'].$cdesc.'</option>';
      }
    }
    echo '</select><br />
      </fieldset>
      <p></p>
      <input type="submit" name="submit" value="Upload image">
      </form>';

    do_layout('Upload New Test Image','Manage Images');
?>
