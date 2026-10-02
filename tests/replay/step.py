"""One request of the replay scenario. Lives apart from scenario.py so the steps_* modules can import it without a cycle."""

from collections import namedtuple

Step = namedtuple(
    "Step",
    ["key", "t", "host", "path", "body", "status", "chunks", "expect", "method"],
    defaults=["POST"],
)
