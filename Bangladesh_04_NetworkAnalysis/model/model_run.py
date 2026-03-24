import os
import pandas as pd
from model import BangladeshModel
from components import Bridge, Link, Intersection, Source, Sink, SourceSink

if not os.path.exists('../data/experiment'):
    os.makedirs('../data/experiment')

# 2. Instellingen volgens Assignment 3
run_length =  7200
seeds = [123, 456, 789, 101, 112] # 5 replicaties

# Scenario's exact uit de Assignment 3 PDF
scenarios = {
    0: {'A': 0, 'B': 0, 'C': 0, 'D': 0},
    1: {'A': 0, 'B': 0, 'C': 0, 'D': 5},
    2: {'A': 0, 'B': 0, 'C': 5, 'D': 10},
    3: {'A': 0, 'B': 5, 'C': 10, 'D': 20},
    4: {'A': 5, 'B': 10, 'C': 20, 'D': 40}
}

print("START EXPERIMENTEN")
#print(f"Data bron: demo-4.csv | Reistijd: {run_length} minuten")

for scenario_id, probs in scenarios.items():
    print(f"\n--- Bezig met Scenario {scenario_id} ---")
    scenario_results = []
    infra_results = []  # A4: ADDED — per-infra criticality/vulnerability data

    for rep, current_seed in enumerate(seeds):
        # Initialiseer het model met de scenario-kansen
        sim_model = BangladeshModel(seed=current_seed, bridge_probabilities=probs)

        # Run de simulatie voor 7200 stappen
        for i in range(run_length):
            sim_model.step()

        # Bereken gemiddelde reistijd van alle aangekomen trucks
        if len(sim_model.travel_times) > 0:
            avg_time = sum(sim_model.travel_times) / len(sim_model.travel_times)
        else:
            avg_time = 0

        scenario_results.append({
            'Scenario': scenario_id,
            'Replication': rep + 1,
            'Seed': current_seed,
            'Avg_Travel_Time': avg_time,
            'Trucks_Arrived': len(sim_model.travel_times)
        })

        # A4: ADDED — collect per-infra criticality + vulnerability data after each run
        for node_id in sim_model.G.nodes():
            agent = sim_model.G.nodes[node_id]['agent_object']
            infra_results.append({
                'Scenario': scenario_id,
                'Replication': rep + 1,
                'Seed': current_seed,
                'agent_id': agent.unique_id,
                'agent_type': type(agent).__name__,
                'name': agent.name,
                'road': agent.road_name,
                'condition': getattr(agent, 'condition', None),
                'is_broken': getattr(agent, 'is_broken', None),
                'total_vehicles_passed': agent.total_vehicles_passed,
                'length': agent.length,
            })

    # Opslaan: summary per scenario
    df_output = pd.DataFrame(scenario_results)
    df_output.to_csv(f'../data/experiment/scenario{scenario_id}.csv', index=False)

    # A4: ADDED — opslaan: per-infra data for criticality/vulnerability analysis
    df_infra = pd.DataFrame(infra_results)
    df_infra.to_csv(f'../data/experiment/scenario{scenario_id}_infra.csv', index=False)

print("\n ALLE EXPERIMENTENVOLTOOID")