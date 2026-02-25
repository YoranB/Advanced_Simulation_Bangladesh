import pandas as pd


def load_data(filepath):
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
    # MESA required format: road, id, model_type, name, lat, lon, length
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length']
    
    # Reorder and filter down to just these required columns
    return df[expected_order]


def save_data(df, filepath):
    """Exports the processed dataset to a CSV file."""
    df.to_csv(filepath, index=False)
    print(f"Successfully exported {len(df)} rows to {filepath}")
    print("\nPreview of final structure:")
    print(df.head())


def main():
    # File paths relative to the preprocessing directory
    input_filepath = "../data_cleaned_by_lecturer/_roads3.csv"
    output_filepath = "../data_processed/N1_roads.csv"

    # --- Preprocessing Pipeline ---

    # 1. Load data
    df = load_data(input_filepath)

    # 2. Filter data
    df = filter_by_road(df, road_name='N1')

    # 3. Calculate segment lengths from chainage 
    # (Important: This also sorts the dataframe geographically, which is required before setting source/sink)
    df = calculate_segment_lengths(df)
    
    # 4. Apply Model Types (Source, Sink, Bridge, Link) and Names
    df = assign_model_types_and_names(df)

    # 5. Add unique IDs
    df = add_unique_id(df)

    # 6. Drop unnecessary columns (removes the old 'type' column)
    df = drop_unnecessary_columns(df)
    
    # 7. Reorder columns perfectly for MESA
    df = format_final_dataframe(df)

    # 8. Save data
    save_data(df, output_filepath)


if __name__ == "__main__":
    main()