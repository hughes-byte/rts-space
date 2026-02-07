This file documents architectural constraints and project conventions so that both humans and AI tools follow the same rules.

# Copilot instructions for rts-space

Purpose: Help an AI coding agent become productive quickly in this small Python client/server RTS.

Behavioral rules for Copilot
- Do NOT refactor or rename existing code unless explicitly asked.
- Prefer the smallest possible diff that satisfies the request.
- Do NOT introduce new abstractions, patterns, or files unless requested.
- Do NOT change message formats or protocol semantics without updating `rts/net/protocol.py`.
- If a change affects threading, locks, or shared state, explain the risk before suggesting code.
- Ask a clarification question if a request is ambiguous instead of guessing.

Quick start (local dev)
- Create venv and install deps: `python3 -m venv .venv` then `source .venv/bin/activate` and `pip install pygame`.
- Run server: `python3 run_server.py` (starts listener, spawns `sim_loop`).
- Run client: `python3 run_client.py` (Pygame fullscreen client).

Big picture
- Two-process architecture: a single-threaded Pygame client and a threaded TCP server.
- Networking lives in `rts/net/` and uses length-prefixed JSON via `send_msg`/`recv_msg` (`rts/net/transport.py`).
- Server (in `rts/server/`) runs a `sim_loop` (tick-based) on a separate thread and handles clients on per-connection threads (`rts/server/main.py`).
- Shared server state is `ServerState` (see `rts/server/state.py`) — mutations must go through the command queue or protected by `world_lock` / `clients_lock`.

Message & protocol tips
- Message types: `HELLO`, `MAP_INIT`, `SNAPSHOT` and client commands `CMD_MOVE`, `CMD_BUY_MINER`, `CMD_MINE` (see `rts/net/protocol.py`).
- Transport: always use `send_msg(sock, obj)` and `recv_msg(sock)`; payloads are JSON with a 4-byte big-endian length header (`rts/net/transport.py`).
- Client uses `NetClient` which places incoming messages on `inbox` (a `queue.Queue`) and sends `HELLO` on connect (`rts/client/netclient.py`).
- Never invent new message types or fields; all protocol changes must be declared in `rts/net/protocol.py` first.

Concurrency & state
- Server pattern: worker thread per connection -> push commands into `state.command_q`; `sim_loop` pops and applies them inside tick loop (`rts/server/simulation.py`).
- Never mutate `ServerState` from connection threads without acquiring the same locks used elsewhere (`world_lock`, `clients_lock`). Prefer enqueuing commands.

Config & timings
- Network host/port and tick/snapshot frequencies are in `rts/server/config.py` and `rts/client/config.py` (e.g. server port `5001`, `TICK_HZ=30`, `SNAPSHOT_HZ=20`).

Examples (concrete payloads)
- Connect (client): `{"type": "hello", "name": "player"}` (sent automatically by `NetClient.connect`).
- Buy miner (client -> server): `{"type": "cmd_buy_miner", "station_id": 12}`
- Move units (client -> server): `{"type": "cmd_move", "unit_ids": [3,4], "x": 123.4, "y": 987.6}`

Developer workflows & debugging
- Run locally with two terminals using the quick-start commands in README.md.
- The server prints connect/disconnect and basic errors to stdout (see `rts/server/main.py`).
- To reproduce network issues, add logging around `send_msg`/`recv_msg` (respecting the length-prefix framing).

Patterns and conventions specific to this repo
- Use simple `print()` for logging — tests and CI are not provided.
- Game state is passed to clients as snapshots; avoid sending ad-hoc network messages that bypass `rts/net/protocol.py` types.
- UI loop drains `NetClient.inbox` on the main thread — avoid blocking operations there.

Key files to inspect
- run_server.py — server entrypoint
- run_client.py — client entrypoint
- rts/net/transport.py — length-prefixed JSON transport
- rts/net/protocol.py — message types
- rts/server/main.py — connection handling, server accept loop
- rts/server/simulation.py — tick loop and snapshot timing
- rts/server/state.py — authoritative server state & locks
- rts/client/netclient.py — client networking and `inbox` queue
- rts/client/main.py — main game loop and input->network usage

How to propose changes
- When suggesting code, show the exact file and minimal diff.
- Prefer code blocks over prose.
- Do not assume permission to apply changes; wait for confirmation.

If anything here is unclear or you want more detail (examples of snapshot structure, state fields, or where to add new server commands), tell me which area to expand and I'll update this file.
