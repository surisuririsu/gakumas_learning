import itertools
import math

from game_data.p_idols import PIdols
from game_data.p_items import PItems
from game_data.skill_cards import SkillCards


DEFAULT_CARDS_BY_PLAN = {
    "sense": [5, 7, 1, 1, 15, 15, 17, 17],
    "logic": [9, 11, 19, 19, 21, 21, 13, 13],
}


class IdolConfig:
    def __init__(
        self,
        params,
        support_bonus,
        p_item_ids,
        skill_card_id_groups,
        stage,
        fallback_plan,
        fallback_idol_id,
    ):
        skill_card_ids = list(itertools.chain.from_iterable(skill_card_id_groups))

        self.p_idol_id = self.infer_p_idol_id(p_item_ids, skill_card_ids)
        self.idol_id = (
            PIdols.get_by_id(self.p_idol_id) if self.p_idol_id else fallback_idol_id
        )
        self.plan = self.infer_plan(self.p_idol_id, stage["plan"], fallback_plan)
        self.recommended_effect = self.infer_recommended_effect(self.p_idol_id)

        [vo, da, vi, stamina] = [p or 0 for p in params]
        self.params = {
            "vocal": vo,
            "dance": da,
            "visual": vi,
            "stamina": stamina,
        }
        self.support_bonus = support_bonus or 0
        self.type_multipliers = self.get_type_multipliers(
            self.params, self.support_bonus, stage["criteria"]
        )

        self.p_item_ids = list(set([p for p in p_item_ids if p]))
        self.skill_card_ids = self.get_deduped_skill_card_ids(
            skill_card_ids + DEFAULT_CARDS_BY_PLAN[self.plan]
        )

    def infer_p_idol_id(self, p_item_ids, skill_card_ids):
        p_items = [PItems.get_by_id(id) for id in p_item_ids]
        signature_p_item = next(
            (p for p in p_items if p.get("sourceType") == "pIdol"), None
        )
        if signature_p_item:
            return signature_p_item["pIdolId"]

        skill_cards = [SkillCards.get_by_id(id) for id in skill_card_ids]
        signature_skill_card = next(
            (p for p in skill_cards if p.get("sourceType") == "pIdol"), None
        )
        if signature_skill_card:
            return signature_skill_card["pIdolId"]

        return None

    def infer_plan(self, p_idol_id, stage_plan, fallback_plan):
        if p_idol_id:
            p_idol = PIdols.get_by_id(p_idol_id)
            return p_idol["plan"]

        if stage_plan and stage_plan != "free":
            return stage_plan

        return fallback_plan

    def infer_recommended_effect(self, p_idol_id):
        if p_idol_id:
            p_idol = PIdols.get_by_id(p_idol_id)
            return p_idol["recommendedEffect"]

        return None

    def get_type_multipliers(self, params, support_bonus, criteria):
        multipliers = {}

        for key in criteria:
            param = min(params[key], 1800)
            criterion = criteria[key]

            multiplier = param
            for i in range(0, 5):
                if param > 300 * i:
                    multiplier += 300 * i
                else:
                    multiplier += param

            multiplier = multiplier * criterion + 100
            multiplier = math.ceil(multiplier) * (1 + support_bonus)
            multiplier = math.ceil(math.floor(multiplier * 10) / 10)
            multipliers[key] = multiplier / 100

        return multipliers

    # If the loadout contains dupes of a unique skill card,
    # keep only the most upgraded copy
    def get_deduped_skill_card_ids(self, skill_card_ids):
        sorted_skill_cards = [SkillCards.get_by_id(s) for s in skill_card_ids if s]
        sorted_skill_cards = sorted(
            sorted_skill_cards, key=lambda s: 1 if s["upgraded"] else 0
        )

        deduped_ids = []
        for skill_card in sorted_skill_cards:
            if skill_card["unique"]:
                base_id = (
                    skill_card["id"] - 1 if skill_card["upgraded"] else skill_card["id"]
                )
                if base_id in deduped_ids or base_id + 1 in deduped_ids:
                    continue
            deduped_ids.append(skill_card["id"])

        return deduped_ids
