-- mod-uac: revert level-1 hunter pet spell grants
-- (stock hunters return to level-10 quest gate)

DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 0 AND `classmask` = 4 AND `Spell` = 1515;
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 0 AND `classmask` = 4 AND `Spell` = 883;
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 0 AND `classmask` = 4 AND `Spell` = 2641;
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 0 AND `classmask` = 4 AND `Spell` = 6991;
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 0 AND `classmask` = 4 AND `Spell` = 982;
