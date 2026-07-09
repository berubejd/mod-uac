-- mod-uac: revert skilllineability_dbc racial ability grants
-- removes exactly these IDs: 21981, 21982, 21983, 21984, 21985, 21986, 21987, 21988, 21989, 21990

DELETE FROM `skilllineability_dbc` WHERE `ID` IN (21981, 21982, 21983, 21984, 21985, 21986, 21987, 21988, 21989, 21990);
