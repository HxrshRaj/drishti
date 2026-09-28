# Drishti Drone Gateway (Simulated)

**This service does not control any real drone or robot.** It simulates a
small fleet's state (position, battery, status) and serves images from
the licensed aerial-imagery catalog (`../data/images`) in response to
"capture" requests, in place of a live camera feed. It also supports
injecting failures (`drone_offline`, `capture_timeout`,
`low_battery_critical`) so the orchestrator's fallback protocols can be
tested against real HTTP error responses.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8100
```

API docs: http://localhost:8100/docs

## Tests

```bash
pytest -q
```

9 tests, run against the real sampled dataset (`../data/images`,
`../data/labels/labels.jsonl`) — no mocks.

## Fleet model

3 drones, one stationed at each of 3 fictional sites
(`meridian-substation`, `harbor-industrial-park`, `north-ridge-corridor`),
each with 10 waypoints and 3 zones (Class A no-fly, Class B restricted,
Class C caution — see `../data/sops/SOP-001-restricted-zones.md`). Each
waypoint has multiple candidate images assigned so a re-capture (SOP-005's
low-confidence fallback) returns a different image than the first capture.
