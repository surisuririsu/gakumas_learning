from constants import GRAPHED_FIELDS


class Logger:
    def __init__(self, debugging_enabled):
        self.disabled = False
        self.debugging_enabled = debugging_enabled
        self.clear()

    def disable(self):
        self.disabled = True

    def enable(self):
        self.disabled = False

    def log(self, log_type, data):
        if self.disabled:
            return

        self.logs.append(
            {
                "logType": log_type,
                "data": data,
            }
        )

    def debug(self, *args):
        if not self.debugging_enabled or self.disabled:
            return

        print(*args)

    def push_graph_data(self, state):
        if self.disabled:
            return

        for field in GRAPHED_FIELDS:
            self.graph_data[field].append(state[field])

    def clear(self):
        self.logs = []
        self.graph_data = {field: [] for field in GRAPHED_FIELDS}
