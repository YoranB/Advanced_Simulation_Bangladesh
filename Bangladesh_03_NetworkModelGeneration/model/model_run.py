import os
import pandas as pd
# Omdat model_run.py in dezelfde map staat als model.py:
from model import BangladeshModel

# 1. Maak de experimentenmap aan op het hoofdniveau (../)
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

print("=== START EXPERIMENTEN ASSIGNMENT 3 ===")
#print(f"Data bron: demo-4.csv | Reistijd: {run_length} minuten")

for scenario_id, probs in scenarios.items():
    print(f"\n--- Bezig met Scenario {scenario_id} ---")
    scenario_results = []
    
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
        
       # print(f"  > Rep {rep+1} (Seed {current_seed}) klaar. Gemiddelde reistijd: {avg_time:.2f}")

    # 3. Opslaan in de experiment map (gelegen in de hoofdmap boven 'model')
    df_output = pd.DataFrame(scenario_results)
    file_path = f'../data/experiment/scenario{scenario_id}.csv'
    df_output.to_csv(file_path, index=False)
    #print(f"Resultaten opgeslagen in: {file_path}")

print("\n=== ALLE EXPERIMENTEN VOOR ASSIGNMENT 3 VOLTOOID ===")