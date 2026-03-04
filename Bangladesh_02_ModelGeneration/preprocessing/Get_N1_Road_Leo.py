import pandas as pd

def load_data(filepath):
    """Loads data depending on if it's a CSV or an Excel file."""
    filepath_str = str(filepath).lower()
    if filepath_str.endswith('.xlsx'):
        return pd.read_excel(filepath)
    else:
        return pd.read_csv(filepath, low_memory=False)
    
def filter_by_road(df, road_name):
    """Filters the dataset to only include rows for a specific road."""
    return df[df['road'] == road_name].copy()

def calculate_segment_lengths(df):
    """Calculates the length of each road segment based on the chainage column."""
    df['chainage'] = pd.to_numeric(df['chainage'], errors='coerce')
    df = df.sort_values(by='chainage')
    df['length'] = df['chainage'].diff().fillna(0)
    
    # putting it in meters
    df['length'] = df['length'] * 1000
    df['length'] = df['length'].round(3)
    
    return df

def merge_bridge_data(df_roads, bmms_filepath, road_name):
    """Merges actual bridge conditions AND official names from BMMS."""
    df_bmms = load_data(bmms_filepath)
    
    # Filter to current road using the provided variable
    df_bmms = df_bmms[df_bmms['road'] == road_name].copy()
    
    # 1. CLEAN NAMES: remove spaces 
    df_bmms['LRPName'] = df_bmms['LRPName'].astype(str).str.strip()
    df_roads['lrp'] = df_roads['lrp'].astype(str).str.strip()
    
    # 2. DROP DUPLICATES: Keep left or right bridge with worst condition
    df_bmms = df_bmms.sort_values(by='condition', ascending=False)
    df_bmms = df_bmms.drop_duplicates(subset=['LRPName'], keep='first')
    
    # 3. MERGE: Using suffixes to distinguish between the 'name' in road file and 'name' in BMMS
    df_merged = pd.merge(df_roads, 
                         df_bmms[['LRPName', 'condition', 'length', 'name']], 
                         left_on='lrp', 
                         right_on='LRPName', 
                         how='left', 
                         suffixes=('', '_bmms'))
                         
    # 4. Only BMMS determines if it is a bridge
    # make everything standard link (normal road)
    df_merged['model_type'] = 'link'
    
    # If merge success --> then it becomes type bridge 
    matched_bridges = df_merged['condition'].notna()
    df_merged.loc[matched_bridges, 'model_type'] = 'bridge'
    
    # 5. Length: Overwrite the length with BMMS length, if BMMS length empty use GPS length
    df_merged['length'] = df_merged['length_bmms'].fillna(df_merged['length'])
    
    # 6. Real Name: Prioritize the official name from BMMS. If it's a link (not in BMMS), keep the road name.
    df_merged['real_name'] = df_merged['name_bmms'].fillna(df_merged['name'])
    
    # 7. Condition: Fill in missing conditions with 'A'
    df_merged['condition'] = df_merged['condition'].fillna('A')

    # Remove helper columns and the temporary BMMS name column
    df_merged = df_merged.drop(columns=['LRPName', 'length_bmms', 'name_bmms'])
    
    return df_merged

def assign_model_types_and_names(df):
    """Defines source/sink and generates sequential names (e.g., bridge 1, link 2)."""
    
    # Set the Source (First row) and Sink (Last row)
    if len(df) > 0:
        df.iloc[0, df.columns.get_loc('model_type')] = 'source'
        df.iloc[-1, df.columns.get_loc('model_type')] = 'sink'

    # Generate sequential names like "link 1", "bridge 1", "link 2"
    # This 'name' column is for MESA, while 'real_name' holds the official bridge name
    counts = df.groupby('model_type').cumcount() + 1
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    
    return df

def drop_unnecessary_columns(df):
    """Removes columns that are no longer needed."""
    columns_to_drop = ['chainage', 'gap', 'type']
    existing_cols_to_drop = [col for col in columns_to_drop if col in df.columns]
    return df.drop(columns=existing_cols_to_drop)

def add_unique_id(df, start_id=1000000):
    """Adds a sequential unique ID to the dataset."""
    df['id'] = range(start_id, start_id + len(df))
    return df

def format_final_dataframe(df):
    """Reorders the columns to exactly match the MESA expected format."""
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition', 'lrp', 'real_name']
    
    # Safety check: fill missing columns with empty string
    for col in expected_order:
        if col not in df.columns:
            df[col] = ''
            
    return df[expected_order]

def save_data(df, filepath):
    """Exports the processed dataset to a CSV file."""
    df.to_csv(filepath, index=False)
    print(f"Successfully exported {len(df)} rows to {filepath}")
    print("\nPreview of final structure:")
    print(df.head())

def main():
    input_filepath = "../data_cleaned_by_lecturer/_roads3.csv"
    bmms_filepath = "../data_cleaned_by_lecturer/BMMS_overview.xlsx" 
    output_filepath = "../data_processed/N1_roads.csv"
    target_road = 'N1'
    
    # 1. Load data
    df = load_data(input_filepath)

    # 2. Filter data
    df = filter_by_road(df, road_name=target_road)

    # 3. Calculate segment lengths from chainage 
    df = calculate_segment_lengths(df)
    
    # 4. Merge Bridge Data (This now captures the official 'name' from BMMS)
    df = merge_bridge_data(df, bmms_filepath, road_name=target_road)

    # 5. Apply MESA Names and Source/Sink
    df = assign_model_types_and_names(df)
    
    # 6. Add unique IDs
    df = add_unique_id(df)

    # 7. Drop unnecessary columns 
    df = drop_unnecessary_columns(df)
    
    # 8. Reorder columns perfectly for MESA
    df = format_final_dataframe(df)

    # --- EXTRA PRINT STATEMENTS VOOR INZICHT ---
    print("\n--- FINAL DATASET SAMENVATTING ---")
    print(f"Total amount of objects on route (Nodes): {len(df)}")
    
    bridges = df[df['model_type'] == 'bridge']
    
    print(f" - Amount of real bridges in model: {len(bridges)}")
   
    if len(bridges) > 0:
        print("\nDivision of Bridge Conditions:")
        print(bridges['condition'].value_counts().to_string())
    # ------------------------------------------

    # 9. Save data
    save_data(df, output_filepath)

if __name__ == "__main__":
    main()