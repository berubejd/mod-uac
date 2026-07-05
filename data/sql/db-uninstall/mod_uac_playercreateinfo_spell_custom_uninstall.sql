-- mod-uac: revert playercreateinfo_spell_custom grants

DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 8 AND `classmask` = 256 AND `Spell` = 688;
DELETE FROM `playercreateinfo_spell_custom` WHERE `racemask` = 1024 AND `classmask` = 256 AND `Spell` = 688;
