import os
import pandas as pd
from model import BangladeshModel
from components import Bridge, Link, Intersection, Source, Sink, SourceSink

if not os.path.exists('../data/experiment'):
    os.makedirs('../data/experiment')

# ── Experiment settings ────────────────────────────────────────────────────
run_length = 7200   # ticks (= minutes; 7200 min = 120 hours)
seeds = [123, 456, 789, 101, 112]  # 5 replicaties

# ── Flood failure parameters ───────────────────────────────────────────────
# Base failure probabilities per bridge condition when a flood hits.
# Motivated by Mirza (2002): major Bangladesh floods damage 25-40% of rural
# infrastructure; structurally deficient (D) bridges in floodplains face up to
# 80% damage rates. Condition A bridges are largely intact; B/C progressively worse.
FLOOD_BASE_PROBS = {'A': 0.10, 'B': 0.25, 'C': 0.50, 'D': 0.80}

# Road-level flood risk multipliers (spatial differentiation).
# Source: Mirza (2002) & WRI Aqueduct (2023) riverine flood hazard data.
# N1 crosses the Jamuna/Brahmaputra floodplain (highest risk);
# N2 runs through the northeast hills near Sylhet (lower riverine risk).
ROAD_FLOOD_RISK = {
    'N1':   1.0,   # Jamuna floodplain — highest riverine flood exposure
    'N106': 0.9,   # N1 side road — same floodplain zone
    'N2':   0.4,   # Northeast hills (Sylhet) — lower riverine, flash flood only
    'N204': 0.4,   # N2 side road
    'N207': 0.4,   # N2 side road
    'N208': 0.5,   # Intermediate zone
}

# ── Scenario definitions ───────────────────────────────────────────────────
# Iterative design: each scenario builds on insight from the previous one.
#   Scenario 0: Baseline — establishes pre-flood travel times
#   Scenario 1: Small flood — moderate intensity (×0.5), reveals first damage signal
#   Scenario 2: High intensity flood — full spatial differentiation, maximises contrast
#
# All floods hit at tick 1440 (24 h into the simulation), giving a clean
# 24 h pre-flood window and 96 h post-flood window for comparison.
scenarios = {
    0: {'flood_event_ticks': [],      'flood_intensity': 0.0},  # baseline
    1: {'flood_event_ticks': [1440],  'flood_intensity': 0.5},  # small flood
    2: {'flood_event_ticks': [1440],  'flood_intensity': 1.0},  # high intensity flood
}

print("START EXPERIMENTEN")

for scenario_id, cfg in scenarios.items():
    print(f"\n--- Bezig met Scenario {scenario_id} ---")
    scenario_results = []
    infra_results    = []
    timeseries_rows  = []  # A4: ADDED — per-truck (tick, travel_time) for pre/post analysis

    for rep, current_seed in enumerate(seeds):
        sim_model = BangladeshModel(
            seed=current_seed,
            bridge_probabilities={'A': 0, 'B': 0, 'C': 0, 'D': 0},  # static failures off; flood handles this
            flood_event_ticks=cfg['flood_event_ticks'],
            flood_intensity=cfg['flood_intensity'],
            flood_base_probs=FLOOD_BASE_PROBS,
            road_flood_risk=ROAD_FLOOD_RISK,
        )

        for i in range(run_length):
            sim_model.step()

        # Summary per replication
        avg_time = (sum(sim_model.travel_times) / len(sim_model.travel_times)
                    if sim_model.travel_times else 0)

        scenario_results.append({
            'Scenario':        scenario_id,
            'Replication':     rep + 1,
            'Seed':            current_seed,
            'Avg_Travel_Time': avg_time,
            'Trucks_Arrived':  len(sim_model.travel_times),
        })

        # Per-infra data (criticality + flood outcome)
        for node_id in sim_model.G.nodes():
            agent = sim_model.G.nodes[node_id]['agent_object']
            infra_results.append({
                'Scenario':              scenario_id,
                'Replication':           rep + 1,
                'Seed':                  current_seed,
                'agent_id':              agent.unique_id,
                'agent_type':            type(agent).__name__,
                'name':                  agent.name,
                'road':                  agent.road_name,
                'condition':             getattr(agent, 'condition', None),
                'is_broken':             getattr(agent, 'is_broken', None),
                'broke_during_flood':    getattr(agent, 'broke_during_flood', None),  # A4: ADDED
                'total_vehicles_passed': agent.total_vehicles_passed,
                'length':                agent.length,
            })

        # A4: ADDED — time-series rows (tick of arrival + travel time)
        for tick, tt in sim_model.travel_time_log:
            timeseries_rows.append({
                'Scenario':    scenario_id,
                'Replication': rep + 1,
                'Seed':        current_seed,
                'tick':        tick,
                'travel_time': tt,
                'phase':       'pre_flood' if (cfg['flood_event_ticks'] and tick < cfg['flood_event_ticks'][0])
                                else ('post_flood' if cfg['flood_event_ticks'] else 'no_flood'),
            })

    # Save outputs
    pd.DataFrame(scenario_results).to_csv(
        f'../data/experiment/scenario{scenario_id}.csv', index=False)
    pd.DataFrame(infra_results).to_csv(
        f'../data/experiment/scenario{scenario_id}_infra.csv', index=False)
    pd.DataFrame(timeseries_rows).to_csv(
        f'../data/experiment/scenario{scenario_id}_timeseries.csv', index=False)  # A4: ADDED

    print(f"  Scenario {scenario_id} opgeslagen.")

print("\n ALLE EXPERIMENTEN VOLTOOID")
