import copy
import math
import random
from constants import LOGGED_FIELDS
from constants import INCREASE_TRIGGER_FIELDS
from constants import DECREASE_TRIGGER_FIELDS
from constants import EOT_DECREMENT_FIELDS
from game_data.p_items import PItems
from game_data.skill_cards import SkillCards

KEYS_TO_DIFF = list(
    set(
        [
            *LOGGED_FIELDS,
            *INCREASE_TRIGGER_FIELDS,
            *DECREASE_TRIGGER_FIELDS,
            *EOT_DECREMENT_FIELDS,
        ]
    )
)


class Engine:
    def __init__(self, stage_config, idol_config, logger, debug):
        self.stage_config = stage_config
        self.idol_config = idol_config
        self.logger = logger
        self.debug = debug

    def get_initial_state(self):
        deck_card_ids = self.idol_config.skill_card_ids
        random.shuffle(deck_card_ids)
        deck_card_ids = sorted(
            deck_card_ids,
            key=lambda id: 1 if SkillCards.get_by_id(id)["forceInitialHand"] else 0,
        )

        return {
            "started": False,
            "turnTypes": self._generate_turn_types(),
            # General
            "turnsElapsed": 0,
            "turnsRemaining": self.stage_config.turn_count,
            "cardUsesRemaining": 0,
            "maxStamina": self.idol_config.params["stamina"],
            "fixedStamina": 0,
            "intermediateStamina": 0,
            "stamina": self.idol_config.params["stamina"],
            "fixedGenki": 0,
            "intermediateGenki": 0,
            "genki": 0,
            "cost": 0,
            "intermediateScore": 0,
            "score": 0,
            "clearRatio": 0,
            # Skill card piles
            "deckCardIds": deck_card_ids,
            "handCardIds": [],
            "discardedCardIds": [],
            "removedCardIds": [],
            "cardsUsed": 0,
            "turnCardsUsed": 0,
            # Phase effects
            "phase": None,
            "effects": [],
            # Buffs and debuffs
            "goodConditionTurns": 0,
            "perfectConditionTurns": 0,
            "concentration": 0,
            "goodImpressionTurns": 0,
            "motivation": 0,
            "halfCostTurns": 0,
            "doubleCostTurns": 0,
            "costReduction": 0,
            "costIncrease": 0,
            "doubleCardEffectCards": 0,
            "nullifyGenkiTurns": 0,
            "nullifyDebuff": 0,
            # Score buffs
            "scoreBuffs": [],
            # Used card
            "usedCardId": None,
            "cardEffects": [],
            # Buffs/debuffs protected from decrement when fresh
            "freshBuffs": {},
            # Effect modifiers
            "concentrationMultiplier": 1,
            "motivationMultiplier": 1,
        }

    def _generate_turn_types(self):
        turn_counts = self.stage_config.turn_counts
        first_turns = self.stage_config.first_turns
        criteria = self.stage_config.criteria
        remaining_turns = turn_counts.copy()

        rand = random.random()
        first_turn = "vocal"
        if rand > first_turns["vocal"]:
            first_turn = "dance"
        if rand > first_turns["vocal"] + first_turns["dance"]:
            first_turn = "visual"
        remaining_turns[first_turn] -= 1

        sorted_types = sorted(criteria.keys(), key=lambda k: criteria[k])
        last_three_turns = list(sorted_types)
        last_three_turns.reverse()
        for t in last_three_turns:
            remaining_turns[t] -= 1

        turn_pool = []
        for t in remaining_turns:
            turn_pool += [t for t in range(0, int(max(remaining_turns[t], 0)))]

        random_turns = []
        while len(turn_pool):
            index = math.floor(random.random() * len(turn_pool))
            turn = turn_pool[index]
            turn_pool = turn_pool[:index] + turn_pool[index + 1 :]
            random_turns.append(turn)

        return [first_turn] + random_turns + last_three_turns

    def start_stage(self, state):
        if self.debug and state["started"]:
            raise Exception("Stage already started!")

        self.logger.clear()

        next_state = copy.deepcopy(state)
        next_state["started"] = True

        # Set default effects
        next_state = self._set_effects(
            next_state,
            "default",
            "好印象",
            [
                {
                    "phase": "endOfTurn",
                    "conditions": ["goodImpressionTurns>=1"],
                    "actions": ["score+=goodImpressionTurns"],
                    "order": 100,
                }
            ],
        )

        # Set stage effects
        self.logger.debug("Setting stage effects", self.stage_config.effects)
        next_state = self._set_effects(
            next_state,
            "stage",
            None,
            self.stage_config.effects,
        )

        # Set p-item effects
        for id in self.idol_config.p_item_ids:
            p_item = PItems.get_by_id(id)
            self.logger.debug(
                "Setting p-item effects", p_item["name"], p_item["effects"]
            )
            next_state = self._set_effects(next_state, "pItem", id, p_item["effects"])

        next_state = self._trigger_effects_for_phase("startOfStage", next_state)

        self.logger.push_graph_data(next_state)

        next_state = self._start_turn(next_state)

        return next_state

    def _start_turn(self, state):
        self.logger.debug("Starting turn", state["turnsElapsed"] + 1)

        state["turnType"] = state["turnTypes"][
            min(state["turnsElapsed"], self.stage_config.turn_count - 1)
        ]

        self.logger.log(
            "startTurn",
            {
                "num": state["turnsElapsed"] + 1,
                "type": state["turnType"],
                "multiplier": self.idol_config.type_multipliers[state["turnType"]],
            },
        )

        # Draw cards
        for i in range(0, 3):
            state = self._draw_card(state)

        # Draw more cards if turn 1 and >3 forceInitialHand
        if state["turnsElapsed"] == 0:
            for i in range(0, 2):
                if SkillCards.get_by_id(self._peek_deck(state))["forceInitialHand"]:
                    state = self._draw_card(state)

        state["cardUsesRemaining"] = 1
        state = self._trigger_effects_for_phase("startOfTurn", state)

        return state

    def _peek_deck(self, state):
        return state["deckCardIds"][-1]

    def _draw_card(self, state):
        if not len(state["deckCardIds"]):
            if not len(state["discardedCardIds"]):
                return state
            state = self._recycle_discards(state)
        card_id = state["deckCardIds"].pop()
        state["handCardIds"].append(card_id)
        self.logger.debug("Drew card", SkillCards.get_by_id(card_id)["name"])
        self.logger.log("drawCard", {"type": "skillCard", "id": card_id})
        return state

    def _set_effects(self, state, source_type, source_id, effects):
        for i in range(0, len(effects)):
            effect = effects[i].copy()
            if not effect["actions"] and i < len(effects) - 1:
                i += 1
                effect["effects"] = [effects[i]]
            state["effects"].append(
                {**effect, "sourceType": source_type, "sourceId": source_id}
            )
        return state

    def _trigger_effects_for_phase(self, phase, state):
        parent_phase = state["phase"]
        state["phase"] = phase

        phase_effects = []
        for i in range(0, len(state["effects"])):
            effect = state["effects"][i]
            if effect["phase"] != phase:
                continue
            phase_effects.append(
                {
                    **effect,
                    "phase": None,
                    "index": i,
                }
            )
        phase_effects = sorted(phase_effects, key=lambda e: e.get("order", 0))

        self.logger.debug(phase, phase_effects)

        state = self._trigger_effects(phase_effects, state)

        state["phase"] = parent_phase

        for idx in state["triggeredEffects"]:
            effect_index = phase_effects[idx]["index"]
            if state["effects"][effect_index]["limit"]:
                state["effects"][effect_index]["limit"] -= 1

        state["triggeredEffects"] = []

        return state

    def _trigger_effects(self, effects, state):
        triggered_effects = []
        skip_next_effect = False

        for i in range(0, len(effects)):
            effect = effects[i]

            # Skip effect if condition is not satisfied
            if skip_next_effect:
                skip_next_effect = False
                continue

            if effect["phase"]:
                self.logger.log("setEffect")

                state = self._set_effects(
                    state,
                    "skillCardEffect" if state["_usedCardId"] else None,
                    state["_usedCardId"],
                    [effect],
                )
                continue

            # Check limit
            if "limit" in effect and effect["limit"] < 1:
                continue

            # Check ttl
            if "ttl" in effect and effect["ttl"] < 0:
                continue

            # Check conditions
            if "conditions" in effect:
                satisfied = True
                for condition in effect["conditions"]:
                    if not self._evaluate_condition(condition, state):
                        satisfied = False
                        break
                if not satisfied:
                    if not effect["actions"]:
                        skip_next_effect = True
                    continue

            if effect["sourceType"]:
                self.logger.log(
                    "entityStart",
                    {
                        "type": effect["sourceType"],
                        "id": effect["sourceId"],
                    },
                )

            # Execute actions
            if effect["actions"]:
                self.logger.debug("Executing actions", effect["actions"])

                state = self._execute_actions(effect["actions"], state)

                # Reset modifiers
                state["concentrationMultiplier"] = 1
                state["motivationMultiplier"] = 1

            # Set effects
            if effect["effects"]:
                self.logger.debug("Setting effects", effect["effects"])

                self.logger.log("setEffect")

                state = self._set_effects(
                    state, effect["sourceType"], effect["sourceId"], effect["effects"]
                )

            if effect["sourceType"]:
                self.logger.log(
                    "entityEnd",
                    {"type": effect["sourceType"], "id": effect["sourceId"]},
                )

            triggered_effects.append(i)

        state["triggeredEffects"] = triggered_effects

        return state

    def _execute_actions(self, actions, state):
        prev = {key: state[key] for key in KEYS_TO_DIFF}

        for action in actions:
            state = self._execute_action(action, state)
            if state["stamina"] < 0:
                state["stamina"] = 0

        # Log changed fields
        for key in LOGGED_FIELDS:
            if state[key] != prev[key]:
                self.logger.log(
                    "diff",
                    {
                        "field": key,
                        "prev": round(prev[key], 2),
                        "next": round(state[key], 2),
                    },
                )

        # Protect fresh states from decrement
        if state["phase"] not in ["startOfStage", "startOfTurn"]:
            for key in EOT_DECREMENT_FIELDS:
                if state[key] > 0 and prev[key] == 0:
                    state["freshBuffs"]["key"] = True

        # Trigger increase effects
        for key in INCREASE_TRIGGER_FIELDS:
            if state["phase"] == f"{key}Increased":
                continue
            if state[key] > prev[key]:
                state = self._trigger_effects_for_phase(f"{key}Increased", state)

        # Trigger decrease effects
        for key in DECREASE_TRIGGER_FIELDS:
            if state["phase"] == f"{key}Decreased":
                continue
            if state[key] > prev[key]:
                state = self._trigger_effects_for_phase(f"{key}Decreased", state)

        return state

    def _execute_action(self, action, state):
        pass
