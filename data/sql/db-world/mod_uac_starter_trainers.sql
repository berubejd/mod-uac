-- mod-uac: curated starter-list class trainers for new race/class combos.
-- One faction-matched starter trainer per uncovered class per starter zone.
DELETE FROM `creature` WHERE `guid` BETWEEN 6000000 AND 6009999;

INSERT INTO `creature` (`guid`, `id`, `map`, `zoneId`, `areaId`, `spawnMask`, `phaseMask`, `equipment_id`, `position_x`, `position_y`, `position_z`, `orientation`, `spawntimesecs`, `wander_distance`, `currentwaypoint`, `curhealth`, `curmana`, `MovementType`, `npcflag`, `unit_flags`, `dynamicflags`, `ScriptName`, `VerifiedBuild`, `CreateObject`, `Comment`) VALUES
(6000000, 895, 0, 0, 0, 1, 1, 1, -8865.383, -210.32, 80.755, 4.4157, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Northshire Hunter trainer'),
(6000001, 17089, 0, 0, 0, 1, 1, 1, -8852.472, -191.678, 82.116, 2.5482, 180, 0, 0, 115, 126, 0, 0, 0, 0, '', 0, 0, 'mod-uac Northshire Shaman trainer'),
(6000002, 3597, 0, 0, 0, 1, 1, 1, -8854.708, -194.994, 82.116, 2.5482, 180, 0, 0, 222, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Northshire Druid trainer'),
(6000003, 17089, 0, 0, 0, 1, 1, 1, -6057.77, 395.262, 392.843, 3.6827, 180, 0, 0, 115, 126, 0, 0, 0, 0, '', 0, 0, 'mod-uac Coldridge Shaman trainer'),
(6000004, 3597, 0, 0, 0, 1, 1, 1, -6055.71, 391.834, 392.843, 3.6827, 180, 0, 0, 222, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Coldridge Druid trainer'),
(6000005, 925, 1, 0, 0, 1, 1, 1, 10527.831, 779.662, 1329.68, 2.4784, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Shadowglen Paladin trainer'),
(6000006, 17089, 1, 0, 0, 1, 1, 1, 10464.484, 831.479, 1381.02, 2.8973, 180, 0, 0, 115, 126, 0, 0, 0, 0, '', 0, 0, 'mod-uac Shadowglen Shaman trainer'),
(6000007, 198, 1, 0, 0, 1, 1, 1, 10457.653, 803.261, 1346.84, 3.7525, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Shadowglen Mage trainer'),
(6000008, 459, 1, 0, 0, 1, 1, 1, 10459.947, 799.985, 1346.84, 3.7525, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Shadowglen Warlock trainer'),
(6000009, 915, 530, 0, 0, 1, 1, 1, -4143.399, -13753.989, 74.632, 6.1785, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac AmmenVale Rogue trainer'),
(6000010, 459, 530, 0, 0, 1, 1, 1, -4119.426, -13740.016, 74.715, 4.9218, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac AmmenVale Warlock trainer'),
(6000011, 3597, 530, 0, 0, 1, 1, 1, -4129.28, -13727.235, 74.758, 4.7298, 180, 0, 0, 222, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac AmmenVale Druid trainer'),
(6000012, 15280, 1, 0, 0, 1, 1, 1, -640.404, -4231.886, 38.56, 5.7247, 180, 0, 0, 103, 115, 0, 0, 0, 0, '', 0, 0, 'mod-uac ValleyOfTrials Paladin trainer'),
(6000013, 3060, 1, 0, 0, 1, 1, 1, -625.378, -4205.269, 38.428, 5.4803, 180, 0, 0, 176, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac ValleyOfTrials Druid trainer'),
(6000014, 15280, 1, 0, 0, 1, 1, 1, -2882.425, -212.88, 54.904, 4.6426, 180, 0, 0, 103, 115, 0, 0, 0, 0, '', 0, 0, 'mod-uac CampNarache Paladin trainer'),
(6000015, 2122, 1, 0, 0, 1, 1, 1, -2865.33, -223.732, 54.962, 3.1067, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac CampNarache Rogue trainer'),
(6000016, 2123, 1, 0, 0, 1, 1, 1, -2874.94, -263.013, 54.007, 3.7001, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac CampNarache Priest trainer'),
(6000017, 2124, 1, 0, 0, 1, 1, 1, -2872.82, -266.405, 54.007, 3.7001, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac CampNarache Mage trainer'),
(6000018, 2126, 1, 0, 0, 1, 1, 1, -2950.7625, -143.74812, 67.069466, 4.708466, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac CampNarache Warlock trainer'),
(6000019, 15280, 0, 0, 0, 1, 1, 1, 1849.2815, 1644.8954, 97.62823, 4.066793, 180, 0, 0, 103, 115, 0, 0, 0, 0, '', 0, 0, 'mod-uac Deathknell Paladin trainer'),
(6000020, 3061, 0, 0, 0, 1, 1, 1, 1875.4225, 1567.0908, 94.31241, 2.5329106, 180, 0, 0, 222, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Deathknell Hunter trainer'),
(6000021, 3062, 0, 0, 0, 1, 1, 1, 1847.938, 1629.593, 97.017, 3.3336, 180, 0, 0, 198, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Deathknell Shaman trainer'),
(6000022, 3060, 0, 0, 0, 1, 1, 1, 1848.702, 1625.667, 97.017, 3.3336, 180, 0, 0, 176, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Deathknell Druid trainer'),
(6000023, 2119, 530, 0, 0, 1, 1, 1, 10368.038, -6433.016, 38.616, 0.733, 180, 0, 0, 102, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Sunstrider Warrior trainer'),
(6000024, 3062, 530, 0, 0, 1, 1, 1, 10372.018, -6426.877, 38.615, 3.3336, 180, 0, 0, 198, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Sunstrider Shaman trainer'),
(6000025, 3060, 530, 0, 0, 1, 1, 1, 10372.782, -6430.803, 38.615, 3.3336, 180, 0, 0, 176, 0, 0, 0, 0, 0, '', 0, 0, 'mod-uac Sunstrider Druid trainer');
