-- mod-uac: revert capital trainer spawns (14 rows in current emission)

DELETE FROM `creature` WHERE `guid` BETWEEN 6005000 AND 6009999;
