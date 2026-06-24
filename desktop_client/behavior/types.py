from dataclasses import dataclass


class LostGroundError(RuntimeError):
    pass


@dataclass
class Anchor:
    x: int
    y: int


@dataclass
class CandidateRef:
    name: str
    frequency: int
    params: dict[str, str]
