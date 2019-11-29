<?php // $Id$
require_once "HTTP/WebDAV/Server/FilesystemFlocklab.php";
	$server = new HTTP_WebDAV_Server_Filesystem();
	$server->ServeRequest();
?>