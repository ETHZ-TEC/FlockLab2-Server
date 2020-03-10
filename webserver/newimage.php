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
        <span class="formfield qtip_show" title="Provide file in ELF (Executable and Linkable Format) such as exe, srec or sba.">Image File (ELF):*</span><input type="file" name="imagefile" id="imagefile" size="27" class="required"><br />
        <span class="formfield">Name:*</span><input type="text" name="name" size="27" class="required" value="'.(isset($_POST['name'])?htmlentities($_POST['name']):'').'"><br />
        <span class="formfield">Description:</span><textarea name="description" size="27">'.(isset($_POST['description'])?htmlentities($_POST['description']):'').'</textarea><br />
        <span class="formfield">OS:*</span><select name="os" class="required"><option />';
    foreach(get_available_os() as $key => $os) {
      echo '<option value="'.$key.'"'.(isset($_POST['os']) && $_POST['os']==$key?' selected="true"':'').'>'.$os.'</option>';
    }
    echo '</select><br />
        <span class="formfield">Platform:*</span><select name="platform" class="required"><option />';
    foreach(get_available_platforms() as $key => $platform) {
      foreach($platform as $pcore) {
          $cdesc = strlen($pcore['core_desc'])>0?': '.$pcore['core_desc']:'';
          $corekey = $key.'_'.$pcore['core'];
          echo '<option value="'.$corekey.'"'.(isset($_POST['platform']) && $_POST['platform']==$key?' selected="true"':'').'>'.$pcore['name'].$cdesc.'</option>';
      }
    }
    echo '</select><br />
      </fieldset>
      <p></p>
      <input type="submit" name="submit" value="Upload image">
      </form>';

    do_layout('Upload New Test Image','Manage Images');
?>
