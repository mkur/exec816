"""Protocol-level oracle: identities and FIFO ownership, independent of links."""
from collections import deque


class Model:
    def __init__(self):
        self.queues = {}
        self.owner = {}

    def send(self, port, message, sender):
        assert self.owner.get(message, sender) == sender
        self.owner[message] = ('queue', port)
        self.queues.setdefault(port, deque()).append(message)

    def get(self, port, receiver):
        queue = self.queues.setdefault(port, deque())
        if not queue:
            return None
        message = queue.popleft()
        self.owner[message] = receiver
        return message


def exchange_trace():
    model = Model()
    trace = []
    for i in range(3): model.send('ignored', i, 'root')
    for _ in range(3): trace.append(model.get('ignored', 'root'))
    assert model.get('ignored', 'root') is None
    for i in range(3): model.send('requests', i, 'root')
    for _ in range(3):
        item = model.get('requests', 'worker')
        trace.append(item)
        model.send('replies', item, 'worker')
    for _ in range(3): trace.append(model.get('replies', 'root'))
    assert model.get('replies', 'root') is None
    assert set(model.owner.values()) == {'root'}
    return trace
