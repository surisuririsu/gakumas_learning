import copy
import math
import random
import re

from constants import COST_FIELDS
from constants import DEBUFF_FIELDS
from constants import WHOLE_FIELDS
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
            turn_pool += [t for i in range(0, int(max(remaining_turns[t], 0)))]

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

    def is_card_usable(self, state, card_id):
        card = SkillCards.get_by_id(card_id)

        # Check conditions
        for condition in card["conditions"]:
            if not self._evaluate_condition(condition, state):
                return False

        # Check cost
        preview_state = state.copy()
        for cost in card["cost"]:
            preview_state = self._execute_action(cost, preview_state)
        for field in COST_FIELDS:
            if preview_state[field] < 0:
                return False

        return True

    def use_card(self, state, card_id):
        if self.debug:
            if not state["started"]:
                raise Exception("Stage not started!")
            if state["cardUsesRemaining"] < 1:
                raise Exception("No card uses remaining!")
            if state["turnsRemaining"] < 1:
                raise Exception("No turns remaining!")
            if card_id not in state["handCardIds"]:
                raise Exception("Card is not in hand!")
            if not self.is_card_usable(state, card_id):
                raise Exception("Card is not usable!")

        hand_index = state["handCardIds"].index(card_id)
        card = SkillCards.get_by_id(card_id)

        next_state = copy.deepcopy(state)

        self.logger.debug("Using card", card_id, card["name"])
        self.logger.log("entityStart", {"type": "skillCard", "id": card_id})

        # Set usedCard variables
        next_state["_usedCardId"] = card["id"]
        next_state["usedCardId"] = card["id"] - 1 if card["upgraded"] else card["id"]
        next_state["cardEffects"] = self._get_card_effects(card)

        # Apply card cost
        self.logger.debug("Applying cost", card["cost"])
        next_state = self._execute_actions(card["cost"], next_state)

        # Remove card from hand
        next_state["handCardIds"] = (
            next_state["handCardIds"][:hand_index]
            + next_state["handCardIds"][hand_index + 1 :]
        )
        next_state["cardUsesRemaining"] -= 1

        # Trigger events on card used
        next_state = self._trigger_effects_for_phase("cardUsed", next_state)
        if card["type"] == "active":
            next_state = self._trigger_effects_for_phase("activeCardUsed", next_state)
        elif card["type"] == "mental":
            next_state = self._trigger_effects_for_phase("mentalCardUsed", next_state)

        # Apply card effects
        if next_state["doubleCardEffectCards"]:
            next_state["doubleCardEffectCards"] -= 1
            next_state = self._trigger_effects(card["effects"], next_state)
        next_state = self._trigger_effects(card["effects"], next_state)

        next_state["cardsUsed"] += 1
        next_state["turnCardsUsed"] += 1

        # Trigger events after card used
        next_state = self._trigger_effects_for_phase("afterCardUsed", next_state)
        if card["type"] == "active":
            next_state = self._trigger_effects_for_phase(
                "afterActiveCardUsed", next_state
            )
        elif card["type"] == "mental":
            next_state = self._trigger_effects_for_phase(
                "afterMentalCardUsed", next_state
            )

        # Reset usedCard variables
        next_state["_usedCardId"] = None
        next_state["usedCardId"] = None
        next_state["cardEffects"] = []

        self.logger.log("entityEnd", {"type": "skillCard", "id": card_id})

        # Send card to discards or remove
        if card["limit"]:
            next_state["removedCardIds"].append(card["id"])
        else:
            next_state["discardedCardIds"].append(card["id"])

        # End turn if no card uses left
        if next_state["cardUsesRemaining"] < 1:
            next_state = self.end_turn(next_state)

        return next_state

    def end_turn(self, state):
        if self.debug:
            if not state["started"]:
                raise Exception("Stage not started!")
            if state["turnsRemaining"] < 1:
                raise Exception("No turns remaining!")

        # Recover stamina if turn ended by player
        if state["cardUsesRemaining"] > 0:
            state["stamina"] = min(
                state["stamina"] + 2, self.idol_config.params["stamina"]
            )

        state = self._trigger_effects_for_phase("endOfTurn", state)

        # Reduce buff turns
        for key in EOT_DECREMENT_FIELDS:
            if key in state["freshBuffs"]:
                del state["freshBuffs"][key]
            else:
                state[key] = max(state[key] - 1, 0)

        # Reduce score buff turns
        for i in range(0, len(state["scoreBuffs"])):
            if state["scoreBuffs"][i]["fresh"]:
                state["scoreBuffs"][i]["fresh"] = False
            elif state["scoreBuffs"][i]["turns"]:
                state["scoreBuffs"][i]["turns"] -= 1
        state["scoreBuffs"] = [b for b in state["scoreBuffs"] if b["turns"] != 0]

        # Reset one turn buffs
        state["cardUsesRemaining"] = 0
        state["turnCardsUsed"] = 0

        # Decrement effect ttl and expire
        for i in range(0, len(state["effects"])):
            if state["effects"][i].get("ttl") == None:
                continue
            state["effects"][i]["ttl"] = max(state["effects"][i]["ttl"] - 1, -1)

        # Discard hand
        state["discardedCardIds"] += state["handCardIds"]
        state["handCardIds"] = []

        state["turnsElapsed"] += 1
        state["turnsRemaining"] -= 1

        self.logger.push_graph_data(state)

        # Start next turn
        if state["turnsRemaining"] > 0:
            state = self._start_turn(state)

        return state

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
        if len(state["handCardIds"]) >= 5:
            return state
        if not len(state["deckCardIds"]):
            if not len(state["discardedCardIds"]):
                return state
            state = self._recycle_discards(state)
        card_id = state["deckCardIds"].pop()
        state["handCardIds"].append(card_id)
        self.logger.debug("Drew card", SkillCards.get_by_id(card_id)["name"])
        self.logger.log("drawCard", {"type": "skillCard", "id": card_id})
        return state

    def _recycle_discards(self, state):
        state["deckCardIds"] = state["discardedCardIds"]
        random.shuffle(state["deckCardIds"])
        state["discardedCardIds"] = []
        self.logger.debug("Recycled discard pile")
        return state

    def _upgrade_hand(self, state):
        for i in range(0, len(state["handCardIds"])):
            card = SkillCards.get_by_id(state["handCardIds"][i])
            if not card["upgraded"] and card["type"] != "trouble":
                state["handCardIds"][i] += 1
        self.logger.log("upgradeHand")
        return state

    def _exchange_hand(self, state):
        num_cards = len(state["handCardIds"])
        state["discardedCardIds"] += state["handCardIds"]
        state["handCardIds"] = []
        for i in range(0, num_cards):
            state = self._draw_card(state)
        return state

    def _add_random_upgraded_card_to_hand(self, state):
        valid_base_cards = [
            s
            for s in SkillCards.get_filtered(
                rarities=["R", "SR", "SSR"],
                plans=[self.idol_config.plan, "free"],
                source_types=["produce"],
            )
            if s["upgraded"]
        ]
        random_card = random.choice(valid_base_cards)
        state["handCardIds"].append(random_card["id"])
        self.logger.log(
            "addRandomUpgradedCardToHand",
            {
                "type": "skillCard",
                "id": random_card["id"],
            },
        )
        return state

    def _set_score_buff(self, state, amount, turns=None):
        existing_buff_index = next(
            (i for i, b in enumerate(state["scoreBuffs"]) if b["turns"] == turns), -1
        )
        if existing_buff_index != -1:
            state["scoreBuffs"][existing_buff_index]["amount"] += amount
        else:
            state["scoreBuffs"].append(
                {
                    "amount": amount,
                    "turns": turns,
                    "fresh": state["phase"] != "startOfTurn",
                }
            )
        self.logger.log(
            "setScoreBuff",
            {
                "amount": amount,
                "turns": turns,
            },
        )
        return state

    def _get_card_effects(self, card):
        card_effects = []
        for effect in card["effects"]:
            if "phase" in effect or "actions" not in effect:
                continue
            for action in effect["actions"]:
                tokens = re.split(r"([=!]?=|[<>]=?|[+\-*/%]=?|&)", action)
                if not len(tokens) or not len(tokens[0]):
                    continue
                card_effects.append(tokens[0])
        return card_effects

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
            if state["effects"][effect_index].get("limit"):
                state["effects"][effect_index]["limit"] -= 1

        state["triggeredEffects"] = []

        return state

    def _trigger_effects(self, effects, state):
        prevState = state.copy()
        triggered_effects = []
        skip_next_effect = False

        for i in range(0, len(effects)):
            effect = effects[i]

            # Skip effect if condition is not satisfied
            if skip_next_effect:
                skip_next_effect = False
                continue

            if effect.get("phase"):
                self.logger.log("setEffect")

                state = self._set_effects(
                    state,
                    "skillCardEffect" if "_usedCardId" in state else None,
                    state.get("_usedCardId"),
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
                    if not self._evaluate_condition(condition, prevState):
                        satisfied = False
                        break
                if not satisfied:
                    if not effect["actions"]:
                        skip_next_effect = True
                    continue

            if "sourceType" in effect:
                self.logger.log(
                    "entityStart",
                    {
                        "type": effect["sourceType"],
                        "id": effect["sourceId"],
                    },
                )

            # Execute actions
            if "actions" in effect:
                self.logger.debug("Executing actions", effect["actions"])

                state = self._execute_actions(effect["actions"], state)

                # Reset modifiers
                state["concentrationMultiplier"] = 1
                state["motivationMultiplier"] = 1

            # Set effects
            if "effects" in effect:
                self.logger.debug("Setting effects", effect["effects"])

                self.logger.log("setEffect")

                state = self._set_effects(
                    state, effect["sourceType"], effect["sourceId"], effect["effects"]
                )

            if "sourceType" in effect:
                self.logger.log(
                    "entityEnd",
                    {"type": effect["sourceType"], "id": effect["sourceId"]},
                )

            triggered_effects.append(i)

        state["triggeredEffects"] = triggered_effects

        return state

    def _evaluate_condition(self, condition, state):
        result = self._evaluate_expression(
            re.split(r"([=!]?=|[<>]=?|[+\-*/%]|&)", condition), state
        )
        self.logger.debug("Condition", condition, result)
        return result

    def _evaluate_expression(self, tokens, state):
        variables = {
            **state,
            "isVocalTurn": state["turnType"] == "vocal",
            "isDanceTurn": state["turnType"] == "dance",
            "isVisualTurn": state["turnType"] == "visual",
        }

        def evaluate(tokens):
            if len(tokens) == 1:
                # Numeric constants
                if re.search(r"^-?[\d]+(\.\d+)?$", tokens[0]):
                    return float(tokens[0])

                # Variables
                return variables[tokens[0]]

            # Set contains
            if "&" in tokens:
                if len(tokens) != 3:
                    print("Invalid set contains")
                return tokens[2] in variables[tokens[0]]

            # Comparators (boolean operators)
            cmp_index = next(
                (i for i, t in enumerate(tokens) if re.search(r"[=!]=|[<>]=?", t)), -1
            )
            if cmp_index != -1:
                lhs = evaluate(tokens[:cmp_index])
                cmp = tokens[cmp_index]
                rhs = evaluate(tokens[cmp_index + 1 :])

                if cmp == "==":
                    return lhs == rhs
                elif cmp == "!=":
                    return lhs != rhs
                elif cmp == "<":
                    return lhs < rhs
                elif cmp == "<=":
                    return lhs <= rhs
                elif cmp == ">":
                    return lhs > rhs
                elif cmp == ">=":
                    return lhs >= rhs
                print("Unrecognized comparator", cmp)

            # Add, subtract
            as_index = next(
                (i for i, t in enumerate(tokens) if re.search(r"[+\-]", t)), -1
            )
            if as_index != -1:
                lhs = evaluate(tokens[:as_index])
                op = tokens[as_index]
                rhs = evaluate(tokens[as_index + 1 :])

                if op == "+":
                    return lhs + rhs
                elif op == "-":
                    return lhs - rhs
                print("Unrecognized operator", op)

            # Multiply, divide, modulo
            md_index = next(
                (i for i, t in enumerate(tokens) if re.search(r"[*/%]", t)), -1
            )
            if md_index != -1:
                lhs = evaluate(tokens[:md_index])
                op = tokens[md_index]
                rhs = evaluate(tokens[md_index + 1 :])

                if op == "*":
                    return lhs * rhs
                elif op == "/":
                    return lhs / rhs
                elif op == "%":
                    return lhs % rhs
                print("Unrecognized operator", op)

        return evaluate(tokens)

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
        tokens = re.split(r"([=!]?=|[<>]=?|[+\-*/%]=?|&)", action)

        # Non-assignment actions
        if len(tokens) == 1:
            if tokens[0] == "drawCard":
                state = self._draw_card(state)
            elif tokens[0].startswith("setScoreBuff"):
                args = [float(m) for m in re.findall(r"[\d\.]+", tokens[0])]
                state = self._set_score_buff(state, *args)
            elif tokens[0] == "upgradeHand":
                state = self._upgrade_hand(state)
            elif tokens[0] == "exchangeHand":
                state = self._exchange_hand(state)
            elif tokens[0] == "addRandomUpgradedCardToHand":
                state = self._add_random_upgraded_card_to_hand(state)
            return state

        # Assignments
        assign_index = next(
            (i for i, t in enumerate(tokens) if re.search(r"[+\-*/%]?=", t)), -1
        )
        if assign_index == 1:
            lhs = tokens[0]
            op = tokens[1]
            rhs = self._evaluate_expression(tokens[2:], state)

            if state["nullifyDebuff"] and lhs in DEBUFF_FIELDS:
                state["nullifyDebuff"] -= 1
                return state

            if lhs == "score" and op == "+=":
                lhs = "intermediateScore"
            elif lhs == "genki" and op == "+=":
                lhs = "intermediateGenki"
            elif lhs == "stamina" and op == "-=":
                lhs = "intermediateStamina"

            if op == "=":
                state[lhs] = rhs
            elif op == "+=":
                state[lhs] += rhs
            elif op == "-=":
                state[lhs] -= rhs
            elif op == "*=":
                state[lhs] *= rhs
            elif op == "/=":
                state[lhs] /= rhs
            elif op == "%=":
                state[lhs] %= rhs
            else:
                print("Unrecognized assignment operator", op)

            if lhs == "cost":
                cost = state["cost"]
                if state["halfCostTurns"]:
                    cost *= 0.5
                if state["doubleCostTurns"]:
                    cost *= 2
                cost = math.ceil(cost)
                cost += state["costReduction"]
                cost -= state["costIncrease"]
                cost = min(cost, 0)

                state["genki"] += cost
                state["cost"] = 0
                if state["genki"] < 0:
                    state["stamina"] += state["genki"]
                    state["genki"] = 0
            elif lhs == "intermediateStamina":
                stamina = state["intermediateStamina"]
                if state["halfCostTurns"]:
                    stamina *= 0.5
                if state["doubleCostTurns"]:
                    stamina *= 2
                stamina = math.ceil(stamina)
                if stamina <= 0:
                    stamina += state["costReduction"]
                    stamina -= state["costIncrease"]
                    stamina = min(stamina, 0)
                state["stamina"] += stamina
                state["intermediateStamina"] = 0
            elif lhs == "intermediateScore":
                score = state["intermediateScore"]
                if score > 0:
                    # Apply concentration
                    score += state["concentration"] * state["concentrationMultiplier"]

                    # Apply good and perfect condition
                    if state["goodConditionTurns"]:
                        score *= 1.5 + (
                            (state["goodConditionTurns"] * 0.1)
                            if state["perfectConditionTurns"]
                            else 0
                        )

                    # Score buff effects
                    score *= 1 + sum(b["amount"] for b in state["scoreBuffs"])
                    score = math.ceil(score)

                    # Turn type multiplier
                    score *= self.idol_config.type_multipliers[state["turnType"]]
                    score = math.ceil(score)
                state["score"] += score
                state["intermediateScore"] = 0
            elif lhs == "intermediateGenki":
                genki = state["intermediateGenki"]

                # Apply motivation
                genki += state["motivation"] * state["motivationMultiplier"]

                if state["nullifyGenkiTurns"]:
                    genki = 0

                state["genki"] += genki
                state["intermediateGenki"] = 0
            elif lhs == "fixedGenki":
                state["genki"] += state["fixedGenki"]
                state["fixedGenki"] = 0
            elif lhs == "fixedStamina":
                state["stamina"] += state["fixedStamina"]
                state["fixedStamina"] = 0

            for key in WHOLE_FIELDS:
                state[key] = math.ceil(state[key])
        else:
            print("Invalid action", action)

        return state
