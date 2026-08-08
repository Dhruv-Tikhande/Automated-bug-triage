class LamportClock:
    def __init__(self):
        self.time = 0

    def increment(self):
        self.time += 1
        return self.time

    def send_event(self):
        self.time += 1
        return self.time

    def receive_event(self, received):
        self.time = max(self.time, received) + 1
        return self.time