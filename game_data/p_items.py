import json

from effects import deserialize_effect_sequence


with open("game_data/json/p_items.json", "r", encoding="utf-8") as f:
    p_items = json.load(f)

for p_item in p_items:
    p_item["effects"] = deserialize_effect_sequence(p_item["effects"])
    p_item["pIdolId"] = p_item.get("pIdolId", None)

p_items_by_id = {p_item["id"]: p_item for p_item in p_items}


class PItems:
    @staticmethod
    def get_all():
        return p_items_by_id

    @staticmethod
    def get_by_id(id):
        return p_items_by_id[id]

    @staticmethod
    def get_filtered(rarities, types, plans, unlock_plvs, source_types, p_idol_ids):
        def filter_fn(p_item):
            if rarities and not p_item["rarity"] in rarities:
                return False
            if types and not p_item["type"] in types:
                return False
            if plans and not p_item["plan"] in plans:
                return False
            if unlock_plvs and not p_item["unlockPlv"] in unlock_plvs:
                return False
            if source_types and not p_item["sourceType"] in source_types:
                return False
            if p_idol_ids and not p_item["pIdolId"] in p_idol_ids:
                return False
            return True

        return filter(filter_fn, p_items)
