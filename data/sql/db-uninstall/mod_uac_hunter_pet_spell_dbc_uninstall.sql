-- mod-uac: remove hunter pet spell_dbc overlays (revert to client Spell.dbc)

DELETE FROM `spell_dbc` WHERE `ID` IN (1515, 883, 2641, 6991, 982);
