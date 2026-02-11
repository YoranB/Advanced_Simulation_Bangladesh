# main.py
import pandas as pd
from pathlib import Path

# Import your custom functions
from src.clean_roads import clean_and_interpolate_road, get_outliers_only


def main():
    # 1. SETUP PATHS (Relative to this script)
    base_dir = Path(__file__).parent
    input_path = base_dir / 'data' / 'raw' / 'Roads_InfoAboutEachLRP.csv'
    output_clean_path = base_dir / 'data' / 'processed' / '_roads3.csv'
    output_outliers_path = base_dir / 'data' / 'processed' / 'outliers_report.csv'

    print(f"Loading data from: {input_path}")
    df = pd.read_csv(input_path, low_memory=False)

    # 2. PREPROCESSING (Type conversion)
    cols = ['chainage', 'lat', 'lon']
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # 3. REPORTING (Save the bad data first)
    print("identifying outliers for report...")
    outliers_df = df.groupby('road', group_keys=False).apply(get_outliers_only)
    outliers_df = outliers_df.sort_values(by='deviation_km', ascending=False)

    # Save outliers to processed folder (never save to raw!)
    outliers_df.to_csv(output_outliers_path, index=False)
    print(f"Saved {len(outliers_df)} outliers to {output_outliers_path}")

    # 4. CLEANING (Fix the data)
    print("Cleaning and Interpolating roads...")
    df_clean = df.groupby('road', group_keys=False).apply(clean_and_interpolate_road)

    #this column is needed for the Java visualization
    if 'type' in df_clean.columns:
        insert_position = df_clean.columns.get_loc('type')
        df_clean.insert(insert_position, 'gap', np.nan)
        print("Inserted 'gap' column successfully.")
    else:
        print("Warning: Column 'type' not found. 'gap' column added at the end.")
        df_clean['gap'] = np.nan

    # 5. EXPORT
    df_clean.to_csv(output_clean_path, index=False)
    print(f"Success! Cleaned data saved to: {output_clean_path}")


if __name__ == "__main__":
    main()