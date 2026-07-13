-- mod-uac: revert starter trainer spawns (26 rows in current emission)

DELETE FROM `creature` WHERE `guid` BETWEEN 6000000 AND 6004999;
