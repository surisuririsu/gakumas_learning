import re


def deserialize_effect(effect_string):
    if not len(effect_string):
        return {}

    expressions = re.split(r",(?![^()]*\))", effect_string)
    effect = {}
    for expression in expressions:
        key, value = expression.split(":")
        if key == "at":
            effect["phase"] = value
        elif key == "if":
            if not "conditions" in effect:
                effect["conditions"] = []
            effect["conditions"].append(value)
        elif key == "do":
            if not "actions" in effect:
                effect["actions"] = []
            effect["actions"].append(value)
        elif key == "order":
            effect["order"] = int(value)
        elif key == "limit":
            effect["limit"] = int(value)
        elif key == "ttl":
            effect["ttl"] = int(value)
        else:
            print("Unrecognized effect segment", effect_string)
    return effect


def deserialize_effect_sequence(effect_sequence_string):
    if not len(effect_sequence_string):
        return []
    return [
        deserialize_effect(effect_string)
        for effect_string in effect_sequence_string.split(";")
    ]
