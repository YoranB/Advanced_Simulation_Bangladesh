# main.py
import pandas as pd
from pathlib import Path
import numpy as np

# Import functions
from src.clean_roads import clean_and_interpolate_road, get_outliers_only
from src.clean_bridges import clean_bridges_pipeline


def main():
    # SETUP PATHS (Relative to this script)
    base_dir = Path(__file__).parent

    # Road paths
    input_roads_path = base_dir / 'data' / 'raw' / 'Roads_InfoAboutEachLRP.csv'
    output_clean_roads_path = base_dir / 'data' / 'processed' / '_roads.csv'
    output_outliers_path = base_dir / 'data' / 'processed' / 'outliers_report.csv'

    # Bridge paths (Added these)
    input_bridges_path = base_dir / 'data' / 'raw' / 'BMMS_overview.xlsx'
    output_clean_bridges_path = base_dir / 'data' / 'processed' / 'BMMS_overview.xlsx'

    print(f"Loading road data from: {input_roads_path}")
    df = pd.read_csv(input_roads_path, low_memory=False)

    # LOG & REMOVE DUPLICATES ROADS
    count_before = len(df)
    df = df.drop_duplicates()
    count_removed = count_before - len(df)
    print(f"   -> Log: {count_removed} duplicate rows removed from roads dataset.")

    # PREPROCESSING ROADS (Type conversion)
    cols = ['chainage', 'lat', 'lon']
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # REPORTING ROAD errors
    print("identifying outliers for report...")
    outliers_df = df.groupby('road', group_keys=False).apply(get_outliers_only)
    outliers_df = outliers_df.sort_values(by='deviation_km', ascending=False)

    # Save outliers to processed folder
    outliers_df.to_csv(output_outliers_path, index=False)
    print(f"Saved {len(outliers_df)} road outliers to {output_outliers_path}")

    # CLEANING ROADS
    print("Cleaning and Interpolating roads...")
    df_clean = df.groupby('road', group_keys=False).apply(clean_and_interpolate_road)

    # this column is needed for the Java visualization
    if 'type' in df_clean.columns:
        insert_position = df_clean.columns.get_loc('type')
        df_clean.insert(insert_position, 'gap', np.nan)
        print("Inserted 'gap' column successfully.")

    # EXPORT ROADS
    df_clean.to_csv(output_clean_roads_path, index=False)
    print(f"Success! Cleaned road data saved to: {output_clean_roads_path}")

    ### Bridges start here ###

    # LOAD BRIDGES
    print(f"Loading bridge data from: {input_bridges_path}")
    try:
        # Check file extension to use correct loader
        if input_bridges_path.suffix == '.csv':
            df_bridges = pd.read_csv(input_bridges_path)
        else:
            df_bridges = pd.read_excel(input_bridges_path)

        # LOG & REMOVE DUPLICATES BRIDGES
        count_before_bridges = len(df_bridges)
        df_bridges = df_bridges.drop_duplicates()
        count_removed_bridges = count_before_bridges - len(df_bridges)
        print(f"   -> Log: {count_removed_bridges} duplicate rows removed from bridges dataset.")

    except Exception as e:
        print(f"Error loading bridges: {e}")
        return

    # CLEAN BRIDGES
    # We pass the raw bridges AND the cleaned roads (df_clean) from step 4
    print("Cleaning and fixing bridge locations...")
    df_bridges_clean, stats = clean_bridges_pipeline(df_bridges, df_clean)

    print("Bridge repair statistics:")
    print(stats)

    # EXPORT BRIDGES
    # Must be Excel with specific sheet name for Java
    df_bridges_clean.to_excel(output_clean_bridges_path, index=False, sheet_name="BMMS_overview")
    print(f"Success! Cleaned bridge data saved to: {output_clean_bridges_path}")


if __name__ == "__main__":
    main()