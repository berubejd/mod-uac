-- mod-uac: creation spell grants for cross-continent class combos (Phase 1g tier C)

-- reapply-safe: clear mod-uac grants before insert
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 8 AND `classmask` = 256 AND `Spell` = 688;
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 1024 AND `classmask` = 256 AND `Spell` = 688;

INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (8, 256, 688, 'mod-uac: 4/9 cross-continent class quest fallback');
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (1024, 256, 688, 'mod-uac: 11/9 cross-continent class quest fallback');
