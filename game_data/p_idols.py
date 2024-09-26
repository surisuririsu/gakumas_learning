import json

with open("game_data/json/p_idols.json", "r", encoding="utf-8") as f:
    p_idols = json.load(f)

p_idols_by_id = {p_idol["id"]: p_idol for p_idol in p_idols}


class PIdols:
    @staticmethod
    def get_all():
        return p_idols_by_id

    @staticmethod
    def get_by_id(id):
        return p_idols_by_id[id]

    @staticmethod
    def get_filtered(idol_ids, rarities, plans, recommended_effects):
        def filter_fn(p_idol):
            if idol_ids and not p_idol["idolId"] in idol_ids:
                return False
            if rarities and not p_idol["rarity"] in rarities:
                return False
            if plans and not p_idol["plan"] in plans:
                return False
            if (
                recommended_effects
                and not p_idol["recommendedEffect"] in recommended_effects
            ):
                return False
            return True

        return filter(filter_fn, p_idols)
