-- mod-uac: revert capital guard POI / gossip patches.

DELETE FROM `points_of_interest` WHERE `ID` BETWEEN 6010000 AND 6010099;
DELETE FROM `npc_text` WHERE `ID` BETWEEN 6010100 AND 6010199;
DELETE FROM `gossip_menu` WHERE `MenuID` BETWEEN 6010200 AND 6010299;
DELETE FROM `gossip_menu_option` WHERE `ActionPoiID` BETWEEN 6010000 AND 6010099;
