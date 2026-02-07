# RTS Space (Python)

Minimal client/server RTS space prototype using TCP sockets and Pygame.

## Requirements
- Python 3.10+
- pygame

Create and activate venv:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
python3 -m pip install -r requirements.txt
```

## Project Structure
- run_server.py — start the server
- run_client.py — start the client
- rts/ — core package
  - rts/net/ — networking and protocol
  - rts/server/ — server simulation
  - rts/client/ — pygame client

## Running
From the project root, open two terminals.

Terminal 1:
```bash
python3 run_server.py
```

Terminal 2:
```bash
python3 run_client.py
```

## Controls
- Mouse to move camera (edge scrolling)
- Left click / drag: select units
- Left click: move selected units
- Select miner(s) + click asteroid: mine
- Right click: deselect
- M: buy miner
- ESC: quit