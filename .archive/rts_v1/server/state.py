import socket
import threading
import queue
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class Asteroid:
    id: int
    x: float
    y: float
    r: float

@dataclass
class Entity:
    id: int
    type: str               # "station"|"fighter"|"miner"
    owner: int              # player_id
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    angle: float = 0.0
    hp: float = 100.0
    hp_max: float = 100.0

    # movement / intent
    tx: Optional[float] = None
    ty: Optional[float] = None

    # miner state
    miner_state: str = "idle"         # idle,to_asteroid,mining,returning
    mine_asteroid_id: Optional[int] = None
    mine_timer: float = 0.0
    cargo: int = 0
    home_station_id: Optional[int] = None

class ServerState:
    def __init__(self):
        self.running = True

        self.next_player_id = 1
        self.next_entity_id = 1
        self.next_asteroid_id = 1

        self.clients_lock = threading.Lock()
        self.clients: Dict[socket.socket, int] = {}  # conn -> player_id

        self.world_lock = threading.Lock()
        self.entities: Dict[int, Entity] = {}
        self.asteroids: Dict[int, Asteroid] = {}

        self.credits: Dict[int, int] = {}

        self.command_q: "queue.Queue[tuple[int, dict]]" = queue.Queue()

def alloc_entity_id(state: ServerState) -> int:
    eid = state.next_entity_id
    state.next_entity_id += 1
    return eid
