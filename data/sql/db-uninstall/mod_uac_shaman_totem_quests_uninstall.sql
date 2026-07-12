-- mod-uac: revert synthetic Call of Earth quests and Draenei chain re-narrow.

DELETE FROM `creature_queststarter` WHERE `quest` BETWEEN 6000000 AND 6009999;
DELETE FROM `creature_questender` WHERE `quest` BETWEEN 6000000 AND 6009999;
DELETE FROM `quest_offer_reward` WHERE `ID` BETWEEN 6000000 AND 6009999;
DELETE FROM `quest_template_addon` WHERE `ID` BETWEEN 6000000 AND 6009999;
DELETE FROM `quest_template` WHERE `ID` BETWEEN 6000000 AND 6009999;

-- Restore the vanilla Call of Earth chains to their stock masks.
UPDATE `quest_template` SET `AllowableRaces` = 130 WHERE `ID` = 1516;
UPDATE `quest_template` SET `AllowableRaces` = 130 WHERE `ID` = 1517;
UPDATE `quest_template` SET `AllowableRaces` = 130 WHERE `ID` = 1518;
UPDATE `quest_template` SET `AllowableRaces` = 32 WHERE `ID` = 1519;
UPDATE `quest_template` SET `AllowableRaces` = 32 WHERE `ID` = 1520;
UPDATE `quest_template` SET `AllowableRaces` = 32 WHERE `ID` = 1521;
UPDATE `quest_template` SET `AllowableRaces` = 1101 WHERE `ID` = 9449;
UPDATE `quest_template` SET `AllowableRaces` = 1101 WHERE `ID` = 9450;
UPDATE `quest_template` SET `AllowableRaces` = 1101 WHERE `ID` = 9451;
