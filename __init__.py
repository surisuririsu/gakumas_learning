from game_data.stages import Stages
from engine import Engine
from logger import Logger
from player import Player
from idol_config import IdolConfig
from stage_config import StageConfig
from strategies.manual_strategy import ManualStrategy

DEBUG = True

stage = Stages.get_by_id(26)
stage_config = StageConfig(stage)
idol_config = IdolConfig(
    params=[1009, 1422, 1474, 47],
    support_bonus=0.023,
    p_item_ids=[47, 75, 71],
    skill_card_id_groups=[[223, 45, 122, 125, 136, 181], [223, 45, 291, 96, 297, 179]],
    stage=stage,
    fallback_plan="logic",
    fallback_idol_id=3,
)


def simulate(stage_config, idol_config):
    logger = Logger(DEBUG)
    engine = Engine(stage_config, idol_config, logger, DEBUG)
    strategy = ManualStrategy(engine)
    result = Player(engine, strategy).play()
    print(result)


simulate(stage_config, idol_config)
