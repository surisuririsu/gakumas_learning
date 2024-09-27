class ManualStrategy:
    def __init__(self, engine):
        self.engine = engine

    def evaluate(self, state):
        print(state)
        print(
            "Actions: ",
            list(
                c for c in state["handCardIds"] if self.engine.is_card_usable(state, c)
            ),
        )
        selected_card_id = int(input("Select card: "))
        scores = [1 if c == selected_card_id else 0 for c in state["handCardIds"]]

        return scores, selected_card_id
