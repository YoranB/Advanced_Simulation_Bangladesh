from model import BangladeshModel
import pandas as pd
import os

# Create the experiment folder if it doesn't exist
if not os.path.exists('../experiment'):
    os.makedirs('../experiment')

# 5 days x 24 hours x 60 minutes = 7200 ticks
run_length = 100

# 10 random seeds for 10 replications
seeds = [123, 456, 789, 101, 112, 131, 415, 161, 718, 192]

scenarios = {
    0: {'A': 0, 'B': 0, 'C': 0, 'D': 0},
    1: {'A': 0, 'B': 0, 'C': 0, 'D': 5},
    2: {'A': 0, 'B': 0, 'C': 5, 'D': 10},
    3: {'A': 0, 'B': 5, 'C': 10, 'D': 20},
    4: {'A': 5, 'B': 10, 'C': 20, 'D': 40}
}

print("Starting experiments...")

for scenario_id, probabilities in scenarios.items():
    print(f"\n--- Running Scenario {scenario_id} ---")

    scenario_data = []

    for rep, seed in enumerate(seeds):
        print(f"  Replication {rep + 1}/10 (Seed: {seed})")

        # Initialize the model with the scenario's probabilities
        sim_model = BangladeshModel(seed=seed, bridge_probabilities=probabilities)

        # Run the model
        for _ in range(run_length):
            sim_model.step()

        # Gather the metrics
        completed_trucks = len(sim_model.travel_times)
        if completed_trucks > 0:
            avg_travel_time = sum(sim_model.travel_times) / completed_trucks
        else:
            avg_travel_time = None

        scenario_data.append({
            'Scenario': scenario_id,
            'Replication': rep + 1,
            'Seed': seed,
            'Average_Travel_Time_mins': avg_travel_time,
            'Trucks_Finished': completed_trucks
        })

    # Export the scenario data to a CSV file
    df_output = pd.DataFrame(scenario_data)
    filename = f'../experiment/scenario_{scenario_id}.csv'
    df_output.to_csv(filename, index=False)
    print(f"Saved {filename}")

print("\nAll experiments completed successfully!")