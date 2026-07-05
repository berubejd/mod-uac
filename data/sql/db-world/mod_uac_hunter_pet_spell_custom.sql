-- mod-uac: level-1 hunter pet spells for ALL hunters (optional — revert separately)
-- Requires worldserver.conf: PlayerStart.CustomSpells = 1
-- Pair with mod_uac_hunter_pet_spell_dbc.sql so Tame Beast is castable at level 1.

INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (0, 4, 1515, 'mod-uac: level-1 hunter pet kit (all hunters)');
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (0, 4, 883, 'mod-uac: level-1 hunter pet kit (all hunters)');
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (0, 4, 2641, 'mod-uac: level-1 hunter pet kit (all hunters)');
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (0, 4, 6991, 'mod-uac: level-1 hunter pet kit (all hunters)');
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES (0, 4, 982, 'mod-uac: level-1 hunter pet kit (all hunters)');
