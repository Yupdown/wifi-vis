from dataclasses import dataclass, field
import math

MAX_SOURCES = 32


@dataclass
class Transmitter:
    id: int
    x: float
    y: float
    power: float = 1.0
    frequency: float = 2.4
    phase: float = 0.0
    enabled: bool = True


@dataclass
class Scene:
    sources: list[Transmitter] = field(default_factory=lambda: [Transmitter(1, .80, .45)])
    selected: int = 1
    next_id: int = 2

    def add(self, x=.5, y=.5):
        if len(self.sources) >= MAX_SOURCES:
            return None
        source = Transmitter(self.next_id, min(.985, max(.015, x)), min(.985, max(.015, y)))
        self.next_id += 1
        self.sources.append(source)
        self.selected = source.id
        return source

    def remove_selected(self):
        if len(self.sources) <= 1:
            return False
        self.sources = [s for s in self.sources if s.id != self.selected]
        self.selected = self.sources[0].id
        return True

    def current(self):
        return next(s for s in self.sources if s.id == self.selected)

    def move(self, identifier, x, y):
        source = next(s for s in self.sources if s.id == identifier)
        source.x = min(.985, max(.015, x))
        source.y = min(.985, max(.015, y))

    def hit_test(self, x, y, width, height, radius=17):
        distances = [(math.hypot((s.x-x)*width, (s.y-y)*height), s.id) for s in self.sources]
        distance, identifier = min(distances)
        return identifier if distance <= radius else None
