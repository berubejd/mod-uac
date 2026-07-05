-- mod-uac: revert player_totem_model rows for off-race shamans

DELETE FROM `player_totem_model` WHERE `RaceID` IN (1, 4, 5, 7, 10);
