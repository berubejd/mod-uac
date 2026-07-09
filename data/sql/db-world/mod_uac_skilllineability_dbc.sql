-- mod-uac: skilllineability_dbc racial ability grants (Unlock All Classes)
-- Class-variant racials (Blood Fury, Elusiveness, Arcane Torrent, Draenei kit)
-- for new combos; existing characters learn them on next login.
-- dbc max ID: 21980; db max ID: 0
-- overlay IDs: 21981, 21982, 21983, 21984, 21985, 21986, 21987, 21988, 21989, 21990

-- reapply-safe: clear mod-uac overlay IDs before insert
DELETE FROM `skilllineability_dbc` WHERE `ID` IN (21981, 21982, 21983, 21984, 21985, 21986, 21987, 21988, 21989, 21990);

-- Blood Fury (AP+SP) for (2, 2), (2, 11)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21981, 125, 33697, 2, 1026, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Blood Fury (spell power) for (2, 5), (2, 8)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21982, 125, 33702, 2, 144, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Elusiveness for (4, 2), (4, 7), (4, 8), (4, 9)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21983, 126, 21009, 8, 450, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Arcane Torrent (mana) for (10, 1), (10, 7), (10, 11)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21984, 756, 28730, 512, 1089, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Heroic Presence (melee/ranged hit) for (11, 4)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21985, 760, 6562, 1024, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Heroic Presence (spell hit) for (11, 9), (11, 11)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21986, 760, 28878, 1024, 1280, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Gift of the Naaru for (11, 4), (11, 9), (11, 11)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21987, 760, 28880, 1024, 1288, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Shadow Resistance for (11, 4)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21988, 760, 59221, 1024, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Shadow Resistance for (11, 11)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21989, 760, 59540, 1024, 1024, 0, 0, 1, 0, 2, 0, 0, 0, 0);
-- Shadow Resistance for (11, 9)
INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`, `ExcludeRace`, `ExcludeClass`, `MinSkillLineRank`, `SupercededBySpell`, `AcquireMethod`, `TrivialSkillLineRankHigh`, `TrivialSkillLineRankLow`, `CharacterPoints_1`, `CharacterPoints_2`) VALUES (21990, 760, 59541, 1024, 256, 0, 0, 1, 0, 2, 0, 0, 0, 0);
