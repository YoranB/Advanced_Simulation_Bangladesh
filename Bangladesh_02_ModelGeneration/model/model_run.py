#Changed completely to run the experiments for all 8 scenarios and 10 replications, and to save the results in CSV files in the experiment folder. See comments in code for details.

from model import BangladeshModel
import pandas as pd
import os

# Create the experiment folder if it doesn't exist
if not os.path.exists('../experiment'):
    os.makedirs('../experiment')

# 5 days x 24 hours x 60 minutes = 7200 ticks
run_length = 5 * 24 * 60 

# 10 random seeds for 10 replications
seeds = [123, 456, 789, 101, 112, 131, 415, 161, 718, 192]

# Define the 8 scenarios from the assignment table (Percentages for Cat A, B, C, D)
scenarios = {
    0: {'A': 0, 'B': 0, 'C': 0, 'D': 0},   # Business as usual
    1: {'A': 0, 'B': 0, 'C': 0, 'D': 5},
    2: {'A': 0, 'B': 0, 'C': 0, 'D': 10},
    3: {'A': 0, 'B': 0, 'C': 5, 'D': 10},
    4: {'A': 0, 'B': 0, 'C': 10, 'D': 20},
    5: {'A': 0, 'B': 5, 'C': 10, 'D': 20},
    6: {'A': 0, 'B': 10, 'C': 20, 'D': 40},
    7: {'A': 5, 'B': 10, 'C': 20, 'D': 40},
    8: {'A': 20, 'B': 10, 'C': 80, 'D': 40}
}

print("Starting experiments...")

for scenario_id, probabilities in scenarios.items():
    print(f"--- Running Scenario {scenario_id} ---")
    
    scenario_data = [] # Store data for all replications of this scenario
    
    for rep, seed in enumerate(seeds):
        print(f"  Replication {rep + 1}/10 (Seed: {seed})")
        
        # Initialize the model with the scenario's probabilities
        sim_model = BangladeshModel(seed=seed, bridge_probabilities=probabilities)
        
        # Run the model for the required number of ticks
        for i in range(run_length):
            sim_model.step()
            
        # Gather the driving times [cite: 164, 169]
        if len(sim_model.travel_times) > 0:
            avg_travel_time = sum(sim_model.travel_times) / len(sim_model.travel_times)
        else:
            avg_travel_time = None # In case traffic is so bad no one arrives!
            
        scenario_data.append({
            'Scenario': scenario_id,
            'Replication': rep + 1,
            'Seed': seed,
            'Average_Travel_Time_mins': avg_travel_time,
            'Trucks_Finished': len(sim_model.travel_times)
        })
        
    # Export the scenario data to a CSV file in the experiment folder 
    df_output = pd.DataFrame(scenario_data)
    filename = f'../experiment/scenario{scenario_id}.csv'
    df_output.to_csv(filename, index=False)
    print(f"Saved {filename}")

print("All experiments completed successfully!")