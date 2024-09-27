import json

from effects import deserialize_effect
from effects import deserialize_effect_sequence


with open("game_data/json/skill_cards.json", "r", encoding="utf-8") as f:
    skill_cards = json.load(f)

for skill_card in skill_cards:
    skill_card["conditions"] = deserialize_effect(skill_card["conditions"]).get(
        "conditions", []
    )
    skill_card["cost"] = deserialize_effect(skill_card["cost"]).get("actions", [])
    skill_card["effects"] = deserialize_effect_sequence(skill_card["effects"])
    skill_card["limit"] = skill_card.get("limit", None)
    skill_card["pIdolId"] = skill_card.get("pIdolId", None)

skill_cards_by_id = {skill_card["id"]: skill_card for skill_card in skill_cards}


class SkillCards:
    @staticmethod
    def get_all():
        return skill_cards_by_id

    @staticmethod
    def get_by_id(id):
        return skill_cards_by_id[id]

    @staticmethod
    def get_filtered(rarities, types, plans, unlock_plvs, source_types, p_idol_ids):
        def filter_fn(skill_card):
            if rarities and not skill_card["rarity"] in rarities:
                return False
            if types and not skill_card["type"] in types:
                return False
            if plans and not skill_card["plan"] in plans:
                return False
            if unlock_plvs and not skill_card["unlockPlv"] in unlock_plvs:
                return False
            if source_types and not skill_card["sourceType"] in source_types:
                return False
            if p_idol_ids and not skill_card["pIdolId"] in p_idol_ids:
                return False
            return True

        return filter(filter_fn, skill_cards)
