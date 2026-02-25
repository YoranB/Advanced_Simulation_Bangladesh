import pandas as pd


def load_data(filepath):
    return pd.read_csv(filepath)


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
    columns_to_drop = ['chainage', 'lrp', 'gap']
    return df.drop(columns=columns_to_drop)


def add_unique_id(df, start_id=1000001):
    """Adds a sequential unique ID to the dataset."""
    df['id'] = range(start_id, start_id + len(df))
    return df


def save_data(df, filepath):
    """Exports the processed dataset to a CSV file."""
    df.to_csv(filepath, index=False)
    print(f"Successfully exported {len(df)} rows to {filepath}")


def main():
    # File paths relative to the preprocessing directory
    input_filepath = "../data_cleaned_by_lecturer/_roads3.csv"
    output_filepath = "../data_processed/N1_roads.csv"

    # --- Preprocessing Pipeline ---

    # Load data
    df = load_data(input_filepath)

    # Filter data
    df = filter_by_road(df, road_name='N1')

    # Calculate segment lengths from chainage
    df = calculate_segment_lengths(df)

    # Drop unnecessary columns
    df = drop_unnecessary_columns(df)

    # Add unique IDs
    df = add_unique_id(df)

    # Save data
    save_data(df, output_filepath)


if __name__ == "__main__":
    main()