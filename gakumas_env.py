import numpy as np

import gymnasium as gym
from gymnasium.spaces import Box, Dict, Discrete, Sequence
from gymnasium.spaces.utils import flatten_space, flatten

from engine import Engine
from game_data.skill_cards import SkillCards
from game_data.stages import Stages
from idol_config import IdolConfig
from logger import Logger
from player import Player
from stage_config import StageConfig


DEBUG = False

TURN_TYPE_MAPPING = {
    "vocal": 0,
    "dance": 1,
    "visual": 2,
}

PHASE_MAPPING = {
    "startOfStage": 0,
    "startOfTurn": 1,
    "cardUsed": 2,
    "activeCardUsed": 3,
    "mentalCardUsed": 4,
    "afterCardUsed": 5,
    "afterActiveCardUsed": 6,
    "afterMentalCardUsed": 7,
    "endOfTurn": 8,
    "goodImpressionTurnsIncreased": 9,
    "motivationIncreased": 10,
    "goodConditionTurnsIncreased": 11,
    "concentrationIncreased": 12,
    "staminaDecreased": 13,
}

total_num_cards = len(SkillCards.get_all())


class GakumasEnv(gym.Env):
    def __init__(self):
        self._observation_space = Dict(
            {
                "turnTypes": Box(0, 16, shape=(3,)),
                "turnsElapsed": Box(0, 1),
                "turnsRemaining": Box(0, 1),
                "cardUsesRemaining": Box(0, 1),
                "maxStamina": Box(0, 1),
                "stamina": Box(0, 1),
                "genki": Box(0, 1),
                "score": Box(0, 1),
                "deckCardIds": Box(
                    0,
                    2,
                    shape=(total_num_cards,),
                ),
                "handCardIds": Box(
                    0,
                    2,
                    shape=(total_num_cards,),
                ),
                "discardedCardIds": Box(
                    0,
                    2,
                    shape=(total_num_cards,),
                ),
                "removedCardIds": Box(
                    0,
                    2,
                    shape=(total_num_cards,),
                ),
                "cardsUsed": Box(0, 1),
                "turnCardsUsed": Box(0, 1),
                "effects": Box(0, 1, shape=(16,)),
                "goodConditionTurns": Box(0, 1),
                "perfectConditionTurns": Box(0, 1),
                "concentration": Box(0, 1),
                "goodImpressionTurns": Box(0, 1),
                "motivation": Box(0, 1),
                "halfCostTurns": Box(0, 1),
                "doubleCostTurns": Box(0, 1),
                "costReduction": Box(0, 1),
                "costIncrease": Box(0, 1),
                "doubleCardEffectCards": Box(0, 1),
                "nullifyGenkiTurns": Box(0, 1),
                "nullifyDebuff": Box(0, 1),
                "scoreBuffs": Box(0, 1, shape=(16,)),
            }
        )
        self.observation_space = flatten_space(self._observation_space)
        self.action_space = Discrete(total_num_cards)

    def _get_obs(self):
        state = self.game_state

        deck_cards = np.zeros(total_num_cards)
        for card in state["deckCardIds"]:
            deck_cards[card] += 1

        hand_cards = np.zeros(total_num_cards)
        for card in state["handCardIds"]:
            hand_cards[card] += 1

        discarded_cards = np.zeros(total_num_cards)
        for card in state["discardedCardIds"]:
            discarded_cards[card] += 1

        removed_cards = np.zeros(total_num_cards)
        for card in state["removedCardIds"]:
            removed_cards[card] += 1

        effects = np.zeros(16)
        for effect in state["effects"]:
            phase = PHASE_MAPPING[effect["phase"]]
            effects[phase] += min(effect.get("limit", 16), 0) / 16

        score_buffs = np.zeros(16)
        for score_buff in state["scoreBuffs"]:
            turns = int(min(score_buff.get("turns"), 16))
            score_buffs[turns] += min(score_buff["amount"], 16)

        return flatten(
            self._observation_space,
            {
                "turnTypes": np.array(
                    [
                        state["turnTypes"].count("vocal"),
                        state["turnTypes"].count("dance"),
                        state["turnTypes"].count("visual"),
                    ]
                ),
                "turnsElapsed": min(state["turnsElapsed"], 16) / 16,
                "turnsRemaining": min(state["turnsRemaining"], 16) / 16,
                "cardUsesRemaining": min(state["cardUsesRemaining"], 8) / 8,
                "maxStamina": min(state["maxStamina"], 100) / 100,
                "stamina": min(state["stamina"], 100) / 100,
                "genki": min(state["genki"], 400) / 400,
                "score": min(state["score"], 100000) / 100000,
                "deckCardIds": deck_cards,
                "handCardIds": hand_cards,
                "discardedCardIds": discarded_cards,
                "removedCardIds": removed_cards,
                "cardsUsed": min(state["cardsUsed"], 400) / 400,
                "turnCardsUsed": min(state["turnCardsUsed"], 64) / 64,
                "effects": effects,
                "goodConditionTurns": min(state["goodConditionTurns"], 400) / 400,
                "perfectConditionTurns": min(state["perfectConditionTurns"], 100) / 100,
                "concentration": min(state["concentration"], 400) / 400,
                "goodImpressionTurns": min(state["goodImpressionTurns"], 400) / 400,
                "motivation": min(state["motivation"], 400) / 400,
                "halfCostTurns": min(state["halfCostTurns"], 16) / 16,
                "doubleCostTurns": min(state["doubleCostTurns"], 16) / 16,
                "costReduction": min(state["costReduction"], 16) / 16,
                "costIncrease": min(state["costIncrease"], 16) / 16,
                "doubleCardEffectCards": min(state["doubleCardEffectCards"], 16) / 16,
                "nullifyGenkiTurns": min(state["nullifyGenkiTurns"], 16) / 16,
                "nullifyDebuff": min(state["nullifyDebuff"], 16) / 16,
                "scoreBuffs": score_buffs,
            },
        )

    def _get_info(self):
        return {"score": self.game_state["score"]}

    def reset(self, seed=None, options=None):
        # We need the following line to seed self.np_random
        super().reset(seed=seed)

        stage = Stages.get_by_id(26)
        stage_config = StageConfig(stage)
        idol_config = IdolConfig(
            params=[1009, 1422, 1474, 47],
            support_bonus=0.023,
            p_item_ids=[47, 75, 71],
            skill_card_id_groups=[
                [223, 45, 122, 125, 136, 181],
                [223, 45, 291, 96, 297, 179],
            ],
            stage=stage,
            fallback_plan="logic",
            fallback_idol_id=3,
        )
        logger = Logger(DEBUG)
        self.engine = Engine(stage_config, idol_config, logger, DEBUG)

        self.game_state = self.engine.get_initial_state()
        self.game_state = self.engine.start_stage(self.game_state)

        observation = self._get_obs()
        info = self._get_info()

        return observation, info

    def step(self, action):
        if action:
            self.game_state = self.engine.use_card(self.game_state, action)
        else:
            self.game_state = self.engine.end_turn(self.game_state)

        # An episode is done iff the agent has reached the target
        terminated = self.game_state["turnsRemaining"] == 0
        reward = self.game_state["score"] if terminated else 0
        observation = self._get_obs()
        info = self._get_info()

        return observation, reward, terminated, False, info

    def render(self):
        return

    def close(self):
        return
