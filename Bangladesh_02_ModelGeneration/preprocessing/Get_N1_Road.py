import pandas as pd

input_filepath = "../data_cleaned_by_lecturer/_roads3.csv"
output_filepath = "../data_processed/N1_roads.csv"

df = pd.read_csv(input_filepath)

df_filtered = df[df['road'] == 'N1']
df_filtered.to_csv(output_filepath, index=False)

print(f"Successfully exported {len(df_filtered)} rows to {output_filepath}")