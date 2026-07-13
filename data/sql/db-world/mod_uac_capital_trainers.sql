-- mod-uac: capital-city class trainers for new combos whose home capital lacks them.
-- Snapshot-driven: a full class trainer beside each capital's existing trainer cluster.
DELETE FROM `creature` WHERE `guid` BETWEEN 6005000 AND 6009999;

INSERT INTO `creature` (`guid`, `id`, `map`, `zoneId`, `areaId`, `spawnMask`, `phaseMask`, `equipment_id`, `position_x`, `position_y`, `position_z`, `orientation`, `spawntimesecs`, `wander_distance`, `currentwaypoint`, `curhealth`, `curmana`, `MovementType`, `npcflag`, `unit_flags`, `dynamicflags`, `ScriptName`, `VerifiedBuild`, `CreateObject`, `Comment`) VALUES
(6005000, 4217, 0, 0, 0, 1, 1, 0, -4721.417, -1148.439, 502.448, 3.7584, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Ironforge Druid trainer'),
(6005001, 17204, 1, 0, 0, 1, 1, 0, 10177.521, 2584.374, 1326.05, 4.3633, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Darnassus Shaman trainer'),
(6005002, 461, 1, 0, 0, 1, 1, 0, 9663.184, 2527.052, 1360.08, 5.6549, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Darnassus Warlock trainer'),
(6005003, 917, 530, 0, 0, 1, 1, 0, -4234.914, -11555.351, -126.032, 4.3284, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Exodar Rogue trainer'),
(6005004, 461, 530, 0, 0, 1, 1, 0, -4056.482, -11558.132, -138.468, 0.2618, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Exodar Warlock trainer'),
(6005005, 3033, 1, 0, 0, 1, 1, 0, 1936.636, -4221.243, 42.422, 3.7874, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Orgrimmar Druid trainer'),
(6005006, 3038, 0, 0, 0, 1, 1, 0, 1408.177, 57.056, -62.195, 0.4538, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Undercity Hunter trainer'),
(6005007, 3030, 0, 0, 0, 1, 1, 0, 1756.432, 418.79, -57.131, 3.4034, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Undercity Shaman trainer'),
(6005008, 3033, 0, 0, 0, 1, 1, 0, 1757.468, 414.926, -57.131, 3.4034, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Undercity Druid trainer'),
(6005009, 16275, 1, 0, 0, 1, 1, 0, -1446.588, -83.136, 159.101, 4.1015, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac ThunderBluff Paladin trainer'),
(6005010, 3327, 1, 0, 0, 1, 1, 0, -1452.488, -100.642, 159.101, 1.4835, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac ThunderBluff Rogue trainer'),
(6005011, 3324, 1, 0, 0, 1, 1, 0, -994.619, 252.278, 101.834, 0.6632, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac ThunderBluff Warlock trainer'),
(6005012, 3041, 530, 0, 0, 1, 1, 0, 9852.97, -7517.68, 19.814, 1.5708, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Silvermoon Warrior trainer'),
(6005013, 3030, 530, 0, 0, 1, 1, 0, 9707.681, -7263.316, 16.617, 0.5951, 180, 0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Silvermoon Shaman trainer');
