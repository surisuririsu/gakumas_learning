class ManualStrategy:
    def __init__(self, engine):
        self.engine = engine

    def evaluate(self, state):
        # scores = [self.get_score(state, id) for id in state["handCardIds"]]

        # selected_card_id = None
        # max_score = max(*scores)
        # if max_score > 0:
        #   max_index = scores.index(max_score)
        #   selected_card_id = state['handCardIds'][max_index]

        scores = []
        selected_card_id = int(input("Select card:"))

        return scores, selected_card_id

    def getScore(self, state, card_id):
        raise NotImplementedError()
