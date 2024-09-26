from constants import LOGGED_FIELDS


class Player:
    def __init__(self, engine, strategy):
        self.engine = engine
        self.strategy = strategy

    def play(self):
        state = self.engine.get_initial_state()
        state = self.engine.start_stage(state)

        while state["turnsRemaining"] > 0:
            self.engine.logger.disable()
            scores, selected_card_id = self.strategy.evaluate(state)
            self.engine.logger.enable()

            self.engine.logger.log(
                "hand",
                {
                    "handCardIds": state["handCardIds"],
                    "scores": scores,
                    "selectedCardId": selected_card_id,
                    "state": self._get_hand_state_for_logging(state),
                },
            )

            if selected_card_id:
                state = self.engine.use_card(state, selected_card_id)
            else:
                state = self.engine.end_turn(state)

        return {
            "score": state["score"],
            "logs": self.engine.logger.logs,
            "graphData": self.engine.logger.graph_data,
        }

    def _get_hand_state_for_logging(self, state):
        res = {field: state[field] for field in LOGGED_FIELDS if state[field]}

        if len(state["scoreBuffs"]):
            res["scoreBuffs"] = state["scoreBuffs"]

        del res["turnsRemaining"]
        del res["cardUsesRemaining"]

        return res
