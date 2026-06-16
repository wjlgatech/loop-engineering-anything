"""Scheduler / heartbeat (U14, R7).

Turns the one-off autonomous runner into a recurring cadence — Loop Engineering's
first primitive ("going to the beach" -> "always running"). The engine is an
optional, injected, cadence-driven collaborator wired like the History
Compression compressor (KTD7): it adds no controller state and drives the loop
only through an injected runner over registered targets.
"""

from .heartbeat import Heartbeat, ScheduledFire

__all__ = ["Heartbeat", "ScheduledFire"]
