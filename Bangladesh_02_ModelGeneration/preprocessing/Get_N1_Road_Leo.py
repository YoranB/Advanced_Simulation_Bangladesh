import pandas as pd


def load_data(filepath):
    """Loads data depending on if it's a CSV or an Excel file."""
    # Convert filepath to string just to be safe
    filepath_str = str(filepath).lower()
    
    if filepath_str.endswith('.xlsx'):
        # Use read_excel for the BMMS file
        return pd.read_excel(filepath)
    else:
        # Use read_csv for the roads file
        return pd.read_csv(filepath, low_memory=False)
    
def filter_by_road(df, road_name):
    """Filters the dataset to only include rows for a specific road."""
    return df[df['road'] == road_name].copy()


def calculate_segment_lengths(df):
    """Calculates the length of each road segment based on the chainage column."""
    # Ensure chainage is treated as a number
    df['chainage'] = pd.to_numeric(df['chainage'], errors='coerce')

    # Sort by chainage just in case the rows are out of order
    df = df.sort_values(by='chainage')

    # Calculate the difference between the current chainage and the previous one
    # .diff() leaves the first row as NaN, so we fill it with zero
    df['length'] = df['chainage'].diff().fillna(0)

    # Round to three decimal places
    df['length'] = df['length'].round(3)

    return df

def merge_bridge_data(df_roads, bmms_filepath):
    """Merges actual bridge conditions and exact lengths from the BMMS dataset."""
    df_bmms = load_data(bmms_filepath)
    
    # Filter to N1 only
    df_bmms = df_bmms[df_bmms['road'] == 'N1'].copy()
    
    # Handle L and R bridges at the same location
    df_bmms = df_bmms.sort_values(by='condition', ascending=False)
    df_bmms = df_bmms.drop_duplicates(subset=['LRPName'], keep='first')
    
    # Merge with the roads dataset
    df_merged = pd.merge(df_roads, 
                         df_bmms[['LRPName', 'condition', 'length']], 
                         left_on='lrp', 
                         right_on='LRPName', 
                         how='left', 
                         suffixes=('', '_bmms'))
                         
    # For bridges, overwrite the length
    df_merged['length'] = df_merged['length_bmms'].fillna(df_merged['length'])
    
    # Fill non-bridge conditions with 'Unknown'
    df_merged['condition'] = df_merged['condition'].fillna('A')

    # --- ADD THESE LINES ---
    # 1. Count total bridges in the N1 road dataset
    #total_bridges = len(df_merged[df_merged['model_type'] == 'bridge'])
    
    # 2. Count how many of those bridges ended up as 'Unknown'
   # unknown_count = len(df_merged[(df_merged['model_type'] == 'bridge') & (df_merged['condition'] == 'Unknown')])
    
    # 3. Calculate the percentage for extra insight
    #unknown_pct = (unknown_count / total_bridges) * 100 if total_bridges > 0 else 0
    
    #print(f"Bridge Data Match Results:")
   # print(f" - Total bridges found on N1: {total_bridges}")
   # print(f" - Bridges with 'Unknown' condition: {unknown_count} ({unknown_pct:.1f}%)")
    # -----------------------
    
    # Clean up the extra columns
    df_merged = df_merged.drop(columns=['LRPName', 'length_bmms'])
    
    return df_merged

def drop_unnecessary_columns(df):
    """Removes columns that are no longer needed."""
    # We drop chainage here because we already extracted the length from it.
    # We also drop the original 'type' column as it is replaced by 'model_type'.
    columns_to_drop = ['chainage', 'lrp', 'gap', 'type']
    
    # Only drop columns that actually exist in the dataframe to avoid errors
    existing_cols_to_drop = [col for col in columns_to_drop if col in df.columns]
    return df.drop(columns=existing_cols_to_drop)


def add_unique_id(df, start_id=1000000):
    """Adds a sequential unique ID to the dataset."""
    df['id'] = range(start_id, start_id + len(df))
    return df


def map_to_model_type(row_type):
    """Helper function to map the raw string type to the MESA model type."""
    type_str = str(row_type).lower()
    
    # Classify as a bridge if 'bridge' or 'culvert' is in the text
    if 'bridge' in type_str or 'culvert' in type_str:
        return 'bridge'
    else:
        return 'link'


def assign_model_types_and_names(df):
    """Maps the 'type' column to 'model_type' and 'name', and defines source/sink."""
    # Apply mapping
    if 'type' in df.columns:
        df['model_type'] = df['type'].apply(map_to_model_type)
    else:
        # Fallback in case 'type' is missing
        df['model_type'] = 'link'

    # Set the Source (First row) and Sink (Last row)
    if len(df) > 0:
        df.iloc[0, df.columns.get_loc('model_type')] = 'source'
        df.iloc[-1, df.columns.get_loc('model_type')] = 'sink'

    # Generate sequential names like "link 1", "bridge 1", "link 2"
    # Group by the 'model_type' and calculate a cumulative count (+1 so it starts at 1 instead of 0)
    counts = df.groupby('model_type').cumcount() + 1
    
    # Combine the type and the count into the 'name' column
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    
    return df


def format_final_dataframe(df):
    """Reorders the columns to exactly match the MESA expected format."""
    # Added 'condition' to the end of the list!
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition']
    
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
    
    # 1. Load data
    df = load_data(input_filepath)

    # 2. Filter data
    df = filter_by_road(df, road_name='N1')

    # 3. Calculate segment lengths from chainage 
    df = calculate_segment_lengths(df)
    
    # 4. Apply Model Types and Names
    df = assign_model_types_and_names(df)
    
    # --- NEW STEP: Merge Bridge Data ---
    df = merge_bridge_data(df, bmms_filepath)

    # 5. Add unique IDs
    df = add_unique_id(df)

    # 6. Drop unnecessary columns 
    df = drop_unnecessary_columns(df)
    
    # 7. Reorder columns perfectly for MESA
    df = format_final_dataframe(df)

    # 8. Save data
    save_data(df, output_filepath)


if __name__ == "__main__":
    main()