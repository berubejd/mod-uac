-- mod-uac: revert playercreateinfo_skills overlays for new combos

DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 1 AND `classMask` = 4 AND `skill` IN (46);
DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 8 AND `classMask` = 2 AND `skill` IN (160);
DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 16 AND `classMask` = 4 AND `skill` IN (45);
DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 32 AND `classMask` = 8 AND `skill` IN (173);
DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 64 AND `classMask` = 2 AND `skill` IN (160);
DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 64 AND `classMask` = 4 AND `skill` IN (46);
DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = 1024 AND `classMask` = 8 AND `skill` IN (173);
