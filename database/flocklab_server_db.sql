-- MySQL dump 10.16  Distrib 10.1.38-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: flocklab
-- ------------------------------------------------------
-- Server version	5.7.16-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


--
-- Select the database 'flocklab'
--

USE flocklab;

--
-- Table structure for table `tbl_serv_architectures`
--

DROP TABLE IF EXISTS `tbl_serv_architectures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_architectures` (
  `serv_architectures_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `core` int(10) unsigned NOT NULL DEFAULT '0',
  `architecture` varchar(45) COLLATE utf8_bin NOT NULL DEFAULT 'msp430',
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `platforms_fk` int(10) unsigned NOT NULL,
  `description` varchar(45) COLLATE utf8_bin DEFAULT NULL,
  `optional` tinyint(4) DEFAULT '0',
  PRIMARY KEY (`serv_architectures_key`),
  KEY `fk_tbl_serv_targetimages_platform` (`platforms_fk`),
  CONSTRAINT `fk_tbl_serv_architectures_platform` FOREIGN KEY (`platforms_fk`) REFERENCES `tbl_serv_platforms` (`serv_platforms_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_dispatcher_activity`
--

DROP TABLE IF EXISTS `tbl_serv_dispatcher_activity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_dispatcher_activity` (
  `tbl_serv_dispatcher_activity_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `pid` int(10) unsigned DEFAULT NULL,
  `action` enum('start','stop','abort') COLLATE utf8_bin NOT NULL,
  `observer_fk` int(10) unsigned NOT NULL,
  `test_fk` int(10) unsigned NOT NULL,
  `time_start` datetime NOT NULL,
  PRIMARY KEY (`tbl_serv_dispatcher_activity_key`),
  UNIQUE KEY `observer_fk` (`observer_fk`),
  KEY `fk_tbl_serv_dispatcher_activity_observer` (`observer_fk`),
  KEY `fk_tbl_serv_dispatcher_activity_tests` (`test_fk`),
  CONSTRAINT `fk_tbl_serv_dispatcher_activity_observer` FOREIGN KEY (`observer_fk`) REFERENCES `tbl_serv_observer` (`serv_observer_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_tbl_serv_dispatcher_activity_tests` FOREIGN KEY (`test_fk`) REFERENCES `tbl_serv_tests` (`serv_tests_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=1181 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_groups`
--

DROP TABLE IF EXISTS `tbl_serv_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_groups` (
  `serv_groups_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `groupname` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`serv_groups_key`)
) ENGINE=InnoDB AUTO_INCREMENT=100 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_locks`
--

DROP TABLE IF EXISTS `tbl_serv_locks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_locks` (
  `tbl_serv_locks_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) COLLATE utf8_bin NOT NULL,
  `expiry_time` datetime NOT NULL,
  PRIMARY KEY (`tbl_serv_locks_key`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=2935 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_map_test_observer_targetimages`
--

DROP TABLE IF EXISTS `tbl_serv_map_test_observer_targetimages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_map_test_observer_targetimages` (
  `observer_fk` int(10) unsigned NOT NULL,
  `test_fk` int(10) unsigned NOT NULL,
  `targetimage_fk` int(10) unsigned DEFAULT NULL,
  `node_id` int(10) unsigned DEFAULT NULL,
  `slot` enum('1','2','3','4') COLLATE utf8_bin DEFAULT NULL,
  KEY `fk_tbl_serv_observer` (`observer_fk`),
  KEY `fk_tbl_serv_tests` (`test_fk`),
  KEY `fk_tbl_serv_targetimages` (`targetimage_fk`),
  CONSTRAINT `fk_tbl_serv_observer` FOREIGN KEY (`observer_fk`) REFERENCES `tbl_serv_observer` (`serv_observer_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_tbl_serv_tests` FOREIGN KEY (`test_fk`) REFERENCES `tbl_serv_tests` (`serv_tests_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_observer`
--

DROP TABLE IF EXISTS `tbl_serv_observer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_observer` (
  `serv_observer_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `ethernet_address` varchar(60) COLLATE utf8_bin NOT NULL,
  `observer_id` int(11) NOT NULL,
  `status` enum('online','offline','disabled','develop','internal') CHARACTER SET utf8 NOT NULL DEFAULT 'disabled',
  `slot_1_tg_adapt_list_fk` int(10) unsigned DEFAULT NULL,
  `slot_2_tg_adapt_list_fk` int(10) unsigned DEFAULT NULL,
  `slot_3_tg_adapt_list_fk` int(10) unsigned DEFAULT NULL,
  `slot_4_tg_adapt_list_fk` int(10) unsigned DEFAULT NULL,
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `sync_method` enum('gps','ptp','ntp') COLLATE utf8_bin NOT NULL,
  PRIMARY KEY (`serv_observer_key`),
  UNIQUE KEY `observer_id_UNIQUE` (`observer_id`),
  KEY `fk_slot_2` (`slot_2_tg_adapt_list_fk`),
  KEY `fk_slot_3` (`slot_3_tg_adapt_list_fk`),
  KEY `fk_slot_4` (`slot_4_tg_adapt_list_fk`),
  KEY `fk_slot_1` (`slot_1_tg_adapt_list_fk`),
  CONSTRAINT `fk_slot_1` FOREIGN KEY (`slot_1_tg_adapt_list_fk`) REFERENCES `tbl_serv_tg_adapt_list` (`serv_tg_adapt_list_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_slot_2` FOREIGN KEY (`slot_2_tg_adapt_list_fk`) REFERENCES `tbl_serv_tg_adapt_list` (`serv_tg_adapt_list_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_slot_3` FOREIGN KEY (`slot_3_tg_adapt_list_fk`) REFERENCES `tbl_serv_tg_adapt_list` (`serv_tg_adapt_list_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_slot_4` FOREIGN KEY (`slot_4_tg_adapt_list_fk`) REFERENCES `tbl_serv_tg_adapt_list` (`serv_tg_adapt_list_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=50 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_platforms`
--

DROP TABLE IF EXISTS `tbl_serv_platforms`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_platforms` (
  `serv_platforms_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) COLLATE utf8_general_ci NOT NULL,
  `description` text COLLATE utf8_bin,
  `freq_2400` tinyint(1) NOT NULL DEFAULT '0',
  `freq_868` tinyint(1) NOT NULL DEFAULT '0',
  `freq_433` tinyint(1) NOT NULL DEFAULT '0',
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `active` TINYINT NULL DEFAULT 1,
  PRIMARY KEY (`serv_platforms_key`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_reservations`
--

DROP TABLE IF EXISTS `tbl_serv_reservations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_reservations` (
  `serv_reservation_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `group_id_fk` int(10) unsigned NOT NULL,
  `time_start` datetime NOT NULL,
  `time_end` datetime NOT NULL,
  PRIMARY KEY (`serv_reservation_key`),
  KEY `fk_tbl_serv_reservations` (`group_id_fk`),
  CONSTRAINT `fk_tbl_serv_reservations_groups` FOREIGN KEY (`group_id_fk`) REFERENCES `tbl_serv_groups` (`serv_groups_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=525 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_resource_allocation`
--

DROP TABLE IF EXISTS `tbl_serv_resource_allocation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_resource_allocation` (
  `serv_resource_allocation_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `time_start` datetime NOT NULL,
  `time_end` datetime NOT NULL,
  `test_fk` int(10) unsigned NOT NULL,
  `observer_fk` int(10) unsigned NOT NULL,
  `resource_type` enum('freq_2400','freq_868','freq_433','slot_1','slot_2','slot_3','slot_4','mux') COLLATE utf8_bin NOT NULL,
  PRIMARY KEY (`serv_resource_allocation_key`),
  KEY `fk_tbl_serv_resource_allocation_observer` (`observer_fk`),
  KEY `fk_tbl_serv_resource_allocation_tests` (`test_fk`),
  CONSTRAINT `fk_tbl_serv_resource_allocation_observer` FOREIGN KEY (`observer_fk`) REFERENCES `tbl_serv_observer` (`serv_observer_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_tbl_serv_resource_allocation_tests` FOREIGN KEY (`test_fk`) REFERENCES `tbl_serv_tests` (`serv_tests_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2289 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_targetimages`
--

DROP TABLE IF EXISTS `tbl_serv_targetimages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_targetimages` (
  `serv_targetimages_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) COLLATE utf8_bin NOT NULL,
  `description` text COLLATE utf8_bin,
  `owner_fk` int(10) unsigned NOT NULL,
  `platforms_fk` int(10) unsigned NOT NULL,
  `core` int(8) unsigned DEFAULT '0',
  `binary` longblob,
  `binary_hash_sha1` varchar(40) COLLATE utf8_bin DEFAULT NULL,
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`serv_targetimages_key`),
  KEY `fk_tbl_serv_targetimages_users` (`owner_fk`),
  KEY `fk_tbl_serv_targetimages_platform` (`platforms_fk`),
  KEY `index_tbl_serv_targetimages_binary_hash_sha1` (`binary_hash_sha1`),
  CONSTRAINT `fk_tbl_serv_targetimages_platform` FOREIGN KEY (`platforms_fk`) REFERENCES `tbl_serv_platforms` (`serv_platforms_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_tbl_serv_targetimages_users` FOREIGN KEY (`owner_fk`) REFERENCES `tbl_serv_users` (`serv_users_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=33510 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_tests`
--

DROP TABLE IF EXISTS `tbl_serv_tests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_tests` (
  `serv_tests_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `title` varchar(45) COLLATE utf8_bin NOT NULL,
  `description` text COLLATE utf8_bin,
  `owner_fk` int(10) unsigned NOT NULL,
  `testconfig_xml` longtext COLLATE utf8_bin NOT NULL,
  `time_start_wish` datetime NOT NULL,
  `time_start_act` datetime DEFAULT NULL,
  `time_end_wish` datetime NOT NULL,
  `time_end_act` datetime DEFAULT NULL,
  `setuptime` int(11) DEFAULT NULL COMMENT 'Time needed to setup the test',
  `cleanuptime` int(11) DEFAULT NULL COMMENT 'Time needed to cleanup the test',
  `test_status` enum('not schedulable','planned','preparing','running','cleaning up','syncing','synced','finished','aborting','failed','todelete','deleted','retention expiring') COLLATE utf8_bin NOT NULL DEFAULT 'not schedulable',
  `test_status_preserved` enum('not schedulable','planned','preparing','running','cleaning up','syncing','synced','finished','aborting','failed','todelete','deleted','retention expiring') COLLATE utf8_bin DEFAULT NULL COMMENT 'Status of the test before beeing deleted.',
  `retention_expiration_warned` timestamp NULL DEFAULT NULL,
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `dispatched` tinyint(4) DEFAULT '0',
  PRIMARY KEY (`serv_tests_key`),
  KEY `fk_tbl_serv_test_owner` (`owner_fk`),
  CONSTRAINT `fk_tbl_serv_test_owner` FOREIGN KEY (`owner_fk`) REFERENCES `tbl_serv_users` (`serv_users_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=64162 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_tg_adapt_list`
--

DROP TABLE IF EXISTS `tbl_serv_tg_adapt_list`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_tg_adapt_list` (
  `serv_tg_adapt_list_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `tg_adapt_types_fk` int(10) unsigned NOT NULL,
  `serialid` varchar(15) COLLATE utf8_bin UNIQUE NOT NULL,
  `adapterid` int(11) DEFAULT NULL COMMENT 'ID as labelled on adapter',
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`serv_tg_adapt_list_key`),
  KEY `fk_tbl_serv_tg_adapt_types` (`tg_adapt_types_fk`),
  CONSTRAINT `fk_tbl_serv_tg_adapt_types` FOREIGN KEY (`tg_adapt_types_fk`) REFERENCES `tbl_serv_tg_adapt_types` (`serv_tg_adapt_types_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=310 DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='Table keeps an up-to-date list of every serial ID which belo';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_tg_adapt_types`
--

DROP TABLE IF EXISTS `tbl_serv_tg_adapt_types`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_tg_adapt_types` (
  `serv_tg_adapt_types_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) COLLATE utf8_general_ci NOT NULL,
  `description` text COLLATE utf8_bin,
  `platforms_fk` int(10) unsigned NOT NULL,
  `last_changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`serv_tg_adapt_types_key`),
  KEY `fk_tbl_serv_tg_adapt_types_1` (`platforms_fk`),
  CONSTRAINT `fk_tbl_serv_tg_adapt_types_1` FOREIGN KEY (`platforms_fk`) REFERENCES `tbl_serv_platforms` (`serv_platforms_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_user_groups`
--

DROP TABLE IF EXISTS `tbl_serv_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_user_groups` (
  `serv_user_groups_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `group_fk` int(10) unsigned NOT NULL,
  `user_fk` int(10) unsigned NOT NULL,
  PRIMARY KEY (`serv_user_groups_key`),
  KEY `fk_tbl_serv_user_groups` (`user_fk`),
  KEY `fk_tbl_serv_user_groups_groups` (`group_fk`),
  CONSTRAINT `fk_tbl_serv_user_groups` FOREIGN KEY (`user_fk`) REFERENCES `tbl_serv_users` (`serv_users_key`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_tbl_serv_user_groups_groups` FOREIGN KEY (`group_fk`) REFERENCES `tbl_serv_groups` (`serv_groups_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=100 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_users`
--

DROP TABLE IF EXISTS `tbl_serv_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_users` (
  `serv_users_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `lastname` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  `firstname` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  `username` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  `country` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  `password` varchar(40) COLLATE utf8_unicode_ci NOT NULL,
  `email` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  `institution_type` enum('university','researchinstitute','company','other') CHARACTER SET utf8 NOT NULL DEFAULT 'other',
  `institution` varchar(500) COLLATE utf8_unicode_ci NOT NULL,
  `quota_runtime` int(11) NOT NULL DEFAULT '60' COMMENT 'Runtime per test in minutes',
  `quota_tests` int(11) NOT NULL DEFAULT '3' COMMENT 'Max no. of tests to be scheduled',
  `retention_time` int(11) NOT NULL DEFAULT '60' COMMENT 'Retention time for testresults in days. After this time, all testresults are deleted. A value of -1 means that tests should be kept infinitely.',
  `role` enum('user','admin','internal') COLLATE utf8_unicode_ci NOT NULL DEFAULT 'user',
  `is_active` tinyint(4) NOT NULL DEFAULT '1',
  `create_time` datetime NOT NULL,
  `last_login` datetime DEFAULT NULL,
  `login_count` int(11) NOT NULL DEFAULT '0',
  `disable_infomails` tinyint(4) NOT NULL DEFAULT '0' COMMENT 'If set to 1, the user will not get emails which just inform about the status of a test. Emails with warnings/errors will still be sent though.',
  `last_changed` datetime DEFAULT NULL,
  PRIMARY KEY (`serv_users_key`)
) ENGINE=InnoDB AUTO_INCREMENT=370 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_web_link_measurements`
--

DROP TABLE IF EXISTS `tbl_serv_link_measurements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_link_measurements` (
  `serv_link_measurements_key` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `test_fk` int(10) unsigned DEFAULT NULL,
  `platform_fk` int(10) unsigned NOT NULL,
  `begin` datetime NOT NULL,
  `radio_cfg` text COLLATE utf8_bin,
  `links` mediumblob,
  `links_html` longtext COLLATE utf8_bin,
  PRIMARY KEY (`serv_link_measurements_key`),
  KEY `date_begin` (`begin`),
  KEY `fk_tbl_serv_link_measurements_platforms` (`platform_fk`),
  CONSTRAINT `fk_tbl_serv_link_measurements_platforms` FOREIGN KEY (`platform_fk`) REFERENCES `tbl_serv_platforms` (`serv_platforms_key`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=13880 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tbl_serv_web_status`
--

DROP TABLE IF EXISTS `tbl_serv_web_status`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tbl_serv_web_status` (
  `serv_web_status_key` int(11) NOT NULL AUTO_INCREMENT,
  `title` text COLLATE utf8_bin,
  `message` text COLLATE utf8_bin NOT NULL,
  `time_start` datetime DEFAULT NULL,
  `time_end` datetime DEFAULT NULL,
  `show` tinyint(4) NOT NULL DEFAULT '1' COMMENT 'Show message only if set to 1',
  `ui_lock` enum('false','true') COLLATE utf8_bin NOT NULL DEFAULT 'false',
  PRIMARY KEY (`serv_web_status_key`),
  UNIQUE KEY `serv_web_status_key_UNIQUE` (`serv_web_status_key`)
) ENGINE=InnoDB AUTO_INCREMENT=50 DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='Table used to show status information to flocklab users on w';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2019-02-28 14:13:08
