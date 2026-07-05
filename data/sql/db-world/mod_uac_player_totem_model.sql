-- mod-uac: totem display models for off-race shamans
-- races: 1, 4, 5, 7, 10 (Alliance -> Dwarf models, Horde -> Orc models)

DELETE FROM `player_totem_model` WHERE `RaceID` IN (1, 4, 5, 7, 10);
INSERT INTO `player_totem_model` (`TotemID`, `RaceID`, `ModelID`) VALUES
(1, 1, 30754),
(2, 1, 30753),
(3, 1, 30755),
(4, 1, 30736),
(1, 4, 30754),
(2, 4, 30753),
(3, 4, 30755),
(4, 4, 30736),
(1, 5, 30758),
(2, 5, 30757),
(3, 5, 30759),
(4, 5, 30756),
(1, 7, 30754),
(2, 7, 30753),
(3, 7, 30755),
(4, 7, 30736),
(1, 10, 30758),
(2, 10, 30757),
(3, 10, 30759),
(4, 10, 30756);
