import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class ClientModel:
    player_id: Optional[int] = None
    MAP_W: int = 15000
    MAP_H: int = 10000
    MAP_SEED: int = 1337

    asteroids: Dict[int, dict] = field(default_factory=dict)
    entities: Dict[int, dict] = field(default_factory=dict)
    credits: Dict[int, int] = field(default_factory=dict)
    tick: int = 0

    lock: threading.Lock = field(default_factory=threading.Lock)

    def apply_map_init(self, msg: dict):
        with self.lock:
            self.player_id = int(msg["player_id"])
            self.MAP_W = int(msg["map_w"])
            self.MAP_H = int(msg["map_h"])
            self.MAP_SEED = int(msg["map_seed"])
            self.asteroids = {int(a["id"]): a for a in msg["asteroids"]}
            # entities/credits remain until snapshots arrive

    def apply_snapshot(self, msg: dict):
        new_credits = {int(k): int(v) for k, v in msg.get("credits", {}).items()}
        new_entities = {int(e["id"]): e for e in msg.get("entities", [])}
        with self.lock:
            self.tick = int(msg["tick"])
            self.credits = new_credits
            self.entities = new_entities
