from model import BangladeshModel
import pandas as pd
from components import Bridge
import os

# We only run Scenarios 1 through 7, as requested by the bonus question
scenarios = {
    1: {'A': 0, 'B': 0, 'C': 0, 'D': 5},
    2: {'A': 0, 'B': 0, 'C': 0, 'D': 10},
    3: {'A': 0, 'B': 0, 'C': 5, 'D': 10},
    4: {'A': 0, 'B': 0, 'C': 10, 'D': 20},
    5: {'A': 0, 'B': 5, 'C': 10, 'D': 20},
    6: {'A': 0, 'B': 10, 'C': 20, 'D': 40},
    7: {'A': 5, 'B': 10, 'C': 20, 'D': 40}
}

seeds = [123, 456, 789, 101, 112, 131, 415, 161, 718, 192]
run_length = 5 * 24 * 60

bridge_data = []

print("Starting Bonus Analysis for Scenarios 1-7...")

for scenario_id, probs in scenarios.items():
    print(f"Running Scenario {scenario_id} (10 Replications)...")
    for seed in seeds:
        # Initialize model
        sim_model = BangladeshModel(seed=seed, bridge_probabilities=probs)
        
        # Run simulation
        for _ in range(run_length):
            sim_model.step()
        
        # Extract the stopwatch data_use from every bridge
        for agent in sim_model.schedule.agents:
            if isinstance(agent, Bridge):
                bridge_data.append({
                    'Scenario': scenario_id,
                    'Seed': seed,
                    'Bridge_ID': agent.unique_id,
                    'Bridge_Name': agent.name,
                    'Length': agent.length,
                    'Condition': agent.condition,
                    'Total_Delay_Caused_mins': agent.total_delay_time
                })

# Convert to DataFrame
df = pd.DataFrame(bridge_data)

# Aggregate: Sum up the total delay caused by each bridge across ALL scenarios and replications.
# Because every scenario is run exactly 10 times, they are naturally weighted equally!
summary = df.groupby(['Bridge_ID', 'Bridge_Name', 'Length', 'Condition'])['Total_Delay_Caused_mins'].sum().reset_index()

# ==========================================
# --- THE NEW PANDAS TRICK ---
# 1. Load the N1 file that you perfectly prepared in the previous step
roads_df = pd.read_csv('../data_processed/N1_roads.csv')

# 2. Merge the 'real_name' and 'lrp' into your summary (matching 'Bridge_Name' with 'name')
summary = pd.merge(summary, 
                   roads_df[['name', 'real_name', 'lrp']], 
                   left_on='Bridge_Name', 
                   right_on='name', 
                   how='left')

# 3. Clean up the columns so real_name is nicely in the middle
summary = summary.drop(columns=['name']) # Drop the duplicate name column
column_order = ['Bridge_ID', 'Bridge_Name', 'lrp', 'real_name', 'Length', 'Condition', 'Total_Delay_Caused_mins']
summary = summary[column_order]
# ==========================================

# Find the 5 worst bottlenecks (Now with .head(5) to actually get the top 5!)
top_5_bridges = summary.sort_values(by='Total_Delay_Caused_mins', ascending=False).head(5)

print("\n=========================================================================")
print("🏆 TOP 5 BRIDGES FOR GOVERNMENT INVESTMENT (BASED ON TOTAL DELAY MINS) 🏆")
print("=========================================================================")
print(top_5_bridges.to_string(index=False))

# Save the results
top_5_bridges.to_csv('../experiment/bonus_top_5_bridges.csv', index=False)
print("\nResults saved to experiment/bonus_top_5_bridges.csv")