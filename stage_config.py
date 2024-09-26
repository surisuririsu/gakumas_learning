class StageConfig:
    def __init__(self, stage):
        self.turn_counts = stage["turnCounts"]
        self.first_turns = stage["firstTurns"]
        self.criteria = stage["criteria"]
        self.effects = stage["effects"]
        self.turn_count = (
            stage["turnCounts"]["vocal"]
            + stage["turnCounts"]["dance"]
            + stage["turnCounts"]["visual"]
        )
