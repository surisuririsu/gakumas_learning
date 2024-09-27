import json

from effects import deserialize_effect_sequence


with open("game_data/json/stages.json", "r", encoding="utf-8") as f:
    stages = json.load(f)

for stage in stages:
    [vo, da, vi] = [float(criterion) for criterion in stage["criteria"].split(",")]
    stage["criteria"] = {"vocal": vo, "dance": da, "visual": vi}
    [voT, daT, viT] = [
        float(turn_count) for turn_count in stage["turnCounts"].split(",")
    ]
    stage["turnCounts"] = {"vocal": voT, "dance": daT, "visual": viT}
    [voFt, daFt, viFt] = [
        float(first_turn) for first_turn in stage["firstTurns"].split(",")
    ]
    stage["firstTurns"] = {"vocal": voFt, "dance": daFt, "visual": viFt}
    stage["effects"] = deserialize_effect_sequence(stage["effects"])

stages_by_id = {stage["id"]: stage for stage in stages}


class Stages:
    @staticmethod
    def get_all():
        return stages_by_id

    @staticmethod
    def get_by_id(id):
        return stages_by_id[id]
