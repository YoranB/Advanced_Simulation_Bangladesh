# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent-based simulation of Bangladesh's road transport network using the Mesa framework. The project is structured as three sequential assignments, each building on the previous.

## Running the Code

### Assignment 3 (Active — Full Network Simulation)

```bash
# Data preprocessing: generates data/demo-4.csv from Assignment 1 cleaned data
cd Bangladesh_03_NetworkModelGeneration/preprocessing
python create_roads.py

# Run with browser visualization (port 8521)
cd Bangladesh_03_NetworkModelGeneration/model
python model_viz.py

# Run batch experiments (no visualization) — outputs experiment/scenario0-4.csv
cd Bangladesh_03_NetworkModelGeneration/model
python model_run.py
```

### Assignment 1 (Data Cleaning Pipeline)

```bash
cd Bangladesh_01_DataQuality
pip install -r requirements.txt
python main.py
```

### Assignment 2 (N1 Single-Road Simulation)

```bash
cd Bangladesh_02_ModelGeneration
pip install -r requirements.txt
python preprocessing/Get_N1_Road_Leo.py
python model/A2_model_viz.py   # with visualization
python model/model_run.py      # batch runs
```

## Architecture

### Data Pipeline

```
Assignment 1 (raw CSV/XLSX) → cleaned _roads3.csv + BMMS_overview_CLEANED.xlsx
         ↓
Assignment 2 preprocessing → N1_roads.csv (single road)
         ↓
Assignment 3 preprocessing (create_roads.py) → data/demo-4.csv (full network)
         ↓
BangladeshModel (model.py) → MESA simulation → experiment/scenarioN.csv
```

### Assignment 3 Key Files

- **`model/model.py`** — `BangladeshModel`: loads `demo-4.csv`, optimizes the network (merges consecutive links), builds a NetworkX graph, runs the simulation tick-by-tick (1 tick = 1 minute)
- **`model/components.py`** — Infrastructure agents (`Bridge`, `Link`, `Intersection`, `Source`, `Sink`, `SourceSink`) and `Vehicle` agent (trucks at 48 km/h = 800 m/min)
- **`model/model_viz.py`** — Mesa `ModularServer` visualization on port 8521
- **`model/model_run.py`** — Batch runner: 5 scenarios × 5 seeds × 7200 ticks (120 hours)
- **`preprocessing/create_roads.py`** — Road/bridge data processing: filters to N1, N2, N106; snaps intersections; resolves intersection-bridge conflicts; outputs `demo-4.csv`

### Simulation Data Format (`demo-4.csv`)

Columns: `road | id | model_type | name | lat | lon | length | condition`

- `model_type`: `Source`, `Sink`, `SourceSink`, `Bridge`, `Link`, `Intersection`
- `condition`: bridge condition A/B/C/D (affects failure probability and delay)
- Rows with shared `lat`/`lon` indicate intersections between roads

### Bridge Failure Scenarios (model_run.py)

| Scenario | Failure probabilities |
|----------|-----------------------|
| 0 | None (baseline) |
| 1 | D: 5% |
| 2 | C: 5%, D: 10% |
| 3 | B: 5%, C: 10%, D: 20% |
| 4 | A: 5%, B: 10%, C: 20%, D: 40% |

### Key Design Decisions

- **Network optimization**: `optimize_network_data()` merges consecutive `Link` segments into single agents, reducing agent count significantly
- **Routing**: Dijkstra's algorithm via NetworkX with route caching per `(source, sink)` pair
- **Intersection handling**: Duplicate coordinates in the CSV mark intersections; if an intersection falls on a bridge, the side road connection is shifted to the next segment
- **Multiple CSV variants**: `demo-4.csv` has several versions (`demo-4_teacher.csv`, `demo-4_ours.csv`) — the active one is `demo-4.csv` in the `data/` folder
