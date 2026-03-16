import pandas as pd

def load_data(filepath):
    """Loads data depending on if it's a CSV or an Excel file."""
    filepath_str = str(filepath).lower()
    if filepath_str.endswith('.xlsx'):
        return pd.read_excel(filepath)
    else:
        return pd.read_csv(filepath, low_memory=False)

def filter_target_roads(df):
    """Filters for N1, N2, and their specific branches > 25km."""
    # Ensure chainage is numeric to calculate lengths
    df['chainage'] = pd.to_numeric(df['chainage'], errors='coerce')
    
    # Calculate total length of each road (max chainage - min chainage)
    road_lengths = df.groupby('road')['chainage'].max() - df.groupby('road')['chainage'].min()
    
    valid_roads = []
    for road, length in road_lengths.items():
        road_str = str(road)
        
        # Condition 1: Keep N1 and N2 explicitly
        if road_str in ['N1', 'N2']:
            valid_roads.append(road_str)
            
        # Condition 2: Keep branches of N1 or N2 that are longer than 25km
        elif (road_str.startswith('N1') or road_str.startswith('N2')) and length > 25:
            valid_roads.append(road_str)
            
    print(f"Roads included in model: {valid_roads}")
    return df[df['road'].isin(valid_roads)].copy()

def calculate_segment_lengths(df):
    """Calculates the length of each road segment per road."""
    # Sort by road first, then chainage, so roads don't mix!
    df = df.sort_values(by=['road', 'chainage'])
    
    # Calculate difference PER ROAD
    df['length'] = df.groupby('road')['chainage'].diff().fillna(0)
    
    # putting it in meters
    df['length'] = (df['length'] * 1000).round(3)
    return df

def merge_bridge_data(df_roads, bmms_filepath):
    """Merges actual bridge conditions AND official names from BMMS for ALL roads."""
    df_bmms = load_data(bmms_filepath)
    
    # 1. CLEAN NAMES: remove spaces 
    df_bmms['LRPName'] = df_bmms['LRPName'].astype(str).str.strip()
    df_roads['lrp'] = df_roads['lrp'].astype(str).str.strip()
    
    # 2. DROP DUPLICATES: Keep left/right bridge with worst condition per ROAD and LRP
    df_bmms = df_bmms.sort_values(by='condition', ascending=False)
    df_bmms = df_bmms.drop_duplicates(subset=['road', 'LRPName'], keep='first')
    
    # 3. MERGE: Match on BOTH 'road' and 'lrp'
    df_merged = pd.merge(df_roads, 
                         df_bmms[['road', 'LRPName', 'condition', 'length', 'name']], 
                         left_on=['road', 'lrp'], 
                         right_on=['road', 'LRPName'], 
                         how='left', 
                         suffixes=('', '_bmms'))
                         
    # 4. Make everything standard link
    df_merged['model_type'] = 'link'
    
    # If merge success --> type bridge 
    matched_bridges = df_merged['condition'].notna()
    df_merged.loc[matched_bridges, 'model_type'] = 'bridge'
    
    # 5. Length: Overwrite the length with BMMS length, if empty use GPS length
    df_merged['length'] = df_merged['length_bmms'].fillna(df_merged['length'])
    
    # 6. Real Name: Prioritize the official name from BMMS.
    df_merged['real_name'] = df_merged['name_bmms'].fillna(df_merged['name'])
    
    # 7. Condition: Fill in missing conditions with 'A' (or leave blank, both work)
    df_merged['condition'] = df_merged['condition'].fillna('A')

    # Remove helper columns
    df_merged = df_merged.drop(columns=['LRPName', 'length_bmms', 'name_bmms'])
    return df_merged

def assign_sourcesinks(df):
    """Assigns 'sourcesink' to the start and end of EACH road."""
    def set_road_ends(group):
        if len(group) > 0:
            group.iloc[0, group.columns.get_loc('model_type')] = 'sourcesink'
            group.iloc[-1, group.columns.get_loc('model_type')] = 'sourcesink'
        return group

    return df.groupby('road', group_keys=False).apply(set_road_ends)

def add_intersections(df):
    """Finds points where roads cross by looking for very close coordinates."""
    df['lat_round'] = df['lat'].round(3)
    df['lon_round'] = df['lon'].round(3)
    
    overlap_coords = df.groupby(['lat_round', 'lon_round'])['road'].nunique()
    intersections = overlap_coords[overlap_coords > 1].index
    
    is_intersection = df.set_index(['lat_round', 'lon_round']).index.isin(intersections)
    
    # Only overwrite if it's a standard link
    df.loc[is_intersection & (df['model_type'] == 'link'), 'model_type'] = 'intersection'
    df = df.drop(columns=['lat_round', 'lon_round'])
    
    print(f"Approximate intersections found: {is_intersection.sum()}")
    return df

def assign_model_types_and_names(df):
    """Generates names but removes them for standard links to keep visualization clean."""
    # Generate sequential names for everything first
    counts = df.groupby('model_type').cumcount() + 1
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    
    # Wipe the 'name' column blank for standard links so they don't print on the map
    df.loc[df['model_type'] == 'link', 'name'] = ''
    
    # Do the same for 'real_name' just to be safe
    if 'real_name' in df.columns:
        df.loc[df['model_type'] == 'link', 'real_name'] = ''
        
    return df

def drop_unnecessary_columns(df):
    """Removes columns that are no longer needed."""
    columns_to_drop = ['chainage', 'gap', 'type']
    existing_cols_to_drop = [col for col in columns_to_drop if col in df.columns]
    return df.drop(columns=existing_cols_to_drop)

def add_unique_id(df, start_id=1000000):
    """
    Adds a sequential unique ID, but ensures that roads overlapping 
    at the exact same coordinates get the SAME ID.
    """
    # 1. Give everyone a temporary unique ID based on their current order (just to have something to work with)
    df['id'] = range(start_id, start_id + len(df))
    
    # 2. Round the coordinates to find overlapping points (4 decimal places)
    df['lat_round'] = df['lat'].round(4)
    df['lon_round'] = df['lon'].round(4)
    
    # 3. Het Magische Trucje: groupon location and assign the same ID to all rows in the same group (the first ID in that group)
    df['id'] = df.groupby(['lat_round', 'lon_round'])['id'].transform('first')
    
    # 4. Cleanup: drop the helper columns
    df = df.drop(columns=['lat_round', 'lon_round'])
    return df


def format_final_dataframe(df):
    """Reorders the columns to exactly match the MESA expected format."""
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition', 'lrp', 'real_name']
    
    for col in expected_order:
        if col not in df.columns:
            df[col] = ''
            
    return df[expected_order]

def save_data(df, filepath):
    """Exports the processed dataset to a CSV file."""
    df.to_csv(filepath, index=False)
    print(f"\nSuccessfully exported {len(df)} rows to {filepath}")

def main():
    # Update these paths if your folders are named differently!
    input_filepath = "../data_cleaned_by_lecturer/_roads3.csv"
    bmms_filepath = "../data_cleaned_by_lecturer/BMMS_overview.xlsx" 
    output_filepath = "../data_processed/A3_network_roads.csv"
    
    print("Starting data processing...")
    df = load_data(input_filepath)
    df = filter_target_roads(df)
    df = calculate_segment_lengths(df)
    df = merge_bridge_data(df, bmms_filepath)
    df = assign_sourcesinks(df)
    df = add_intersections(df)
    df = assign_model_types_and_names(df)
    df = add_unique_id(df)
    df = drop_unnecessary_columns(df)
    df = format_final_dataframe(df)
    
    print("\n--- FINAL DATASET SUMMARY ---")
    print(f"Total components: {len(df)}")
    print(df['model_type'].value_counts().to_string())
    
    save_data(df, output_filepath)

if __name__ == "__main__":
    main()