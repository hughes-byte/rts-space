from .state import ServerState

def build_map_init(state: ServerState, player_id: int) -> dict:
    from . import config as cfg
    with state.world_lock:
        ast_list = [{"id": a.id, "x": a.x, "y": a.y, "r": a.r} for a in state.asteroids.values()]
    return {
        "type": "map_init",
        "player_id": player_id,
        "map_w": cfg.MAP_W,
        "map_h": cfg.MAP_H,
        "map_seed": cfg.MAP_SEED,
        "asteroids": ast_list,
    }

def build_snapshot(state: ServerState, tick: int) -> dict:
    with state.world_lock:
        ents = []
        for e in state.entities.values():
            if e.hp <= 0:
                continue
            ents.append({
                "id": e.id,
                "type": e.type,
                "owner": e.owner,
                "x": e.x,
                "y": e.y,
                "angle": e.angle,
                "hp": e.hp,
                "hp_max": e.hp_max,
                "miner_state": e.miner_state if e.type == "miner" else None,
                "mine_asteroid_id": e.mine_asteroid_id if e.type == "miner" else None,
            })
        credits = dict(state.credits)
    return {"type": "snapshot", "tick": tick, "entities": ents, "credits": credits}
