import pandas as pd
import numpy as np


def normalize_text(df, col_name):
    """
    Helper function to normalize text columns (uppercase, stripped of whitespace).
    """
    return df[col_name].astype(str).str.strip().str.upper()


def repair_bridge_location(row, road_dict, road_max_lengths):
    """
    Determines the best possible coordinates for a bridge based on a hierarchy of logic:
    1. LRP Match (Gold): Matches exact LRP name with road database.
    2. Chainage Match (Silver): Interpolates position based on valid chainage.
    3. Typo Correction: Detects if chainage is a factor-10 error (e.g., 42.3km on 8km road).
    4. Snap to End (Fallback): Snaps bridges exceeding road length to the road terminus.
    """
    # 1. PRIORITY: GOLDEN MATCH (LRP NAME)
    # If we successfully merged coordinates based on LRP name in the pipeline, use them.
    if not pd.isna(row['lat_matched']):
        return row['lat_matched'], row['lon_matched'], "Fixed: Matched on LRP Name"
    
    # Retrieve road data
    road_id = row['road_norm']
    km = row['km']
    
    # Error Handling: If road doesn't exist in our clean roads file (should be filtered already)
    if pd.isna(km) or road_id not in road_dict:
        return row['lat'], row['lon'], "Error: Road data missing"

    road_data = road_dict[road_id]
    max_len = road_max_lengths[road_id]

    # 2. PRIORITY: VALID CHAINAGE INTERPOLATION
    # If the bridge chainage fits within the road length, interpolate logically.
    if 0 <= km <= max_len:
        new_lat = np.interp(km, road_data['chainage'], road_data['lat'])
        new_lon = np.interp(km, road_data['chainage'], road_data['lon'])
        return new_lat, new_lon, "Fixed: Interpolated by Chainage"

    # 3. PRIORITY: HANDLE CHAINAGE ERRORS (km > max_len)
    
    # Case A: Small Deviation (Measurement Noise)
    # If the overshoot is small (< 10% or < 1km), it's likely not a typo but a measurement discrepancy.
    # Action: Snap to the end of the road.
    if km < (max_len * 1.1) or (km - max_len) < 1.0:
        lat_end = np.interp(max_len, road_data['chainage'], road_data['lat'])
        lon_end = np.interp(max_len, road_data['chainage'], road_data['lon'])
        return lat_end, lon_end, "Fixed: Snapped to End (Small deviation)"

    # Case B: Large Deviation - Typo Detection (Factor 10)
    # If overshoot is large, check if dividing by 10 makes it fit. 
    # (Common error: inputting meters instead of km, or misplaced decimal).
    km_div_10 = km / 10.0
    if km_div_10 <= max_len:
        lat_10 = np.interp(km_div_10, road_data['chainage'], road_data['lat'])
        lon_10 = np.interp(km_div_10, road_data['chainage'], road_data['lon'])
        return lat_10, lon_10, "Fixed: Typo detected (Chainage / 10)"

    # Case C: Fallback (Snap to End)
    # If it's not a typo and not a small deviation, the road data is likely incomplete/short.
    # Action: Snap to end to ensure connectivity in simulation.
    used_km = max(0, min(km, max_len)) # Clamp values
    new_lat = np.interp(used_km, road_data['chainage'], road_data['lat'])
    new_lon = np.interp(used_km, road_data['chainage'], road_data['lon'])
    
    return new_lat, new_lon, "Fixed: Snapped to End (Road too short)"


def clean_bridges_pipeline(df_bridges, df_roads_clean):
    """
    Main pipeline to clean bridge data using the clean road network.
    Returns the cleaned dataframe and a statistics summary.
    """
    print("   -> Normalizing text and data types...")
    # 1. Normalize Columns
    df_bridges['road_norm'] = normalize_text(df_bridges, 'road')
    df_bridges['lrp_norm'] = normalize_text(df_bridges, 'LRPName')
    df_bridges['km'] = pd.to_numeric(df_bridges['km'], errors='coerce')

    # Ensure clean roads are also normalized (safety check)
    df_roads_clean['road_norm'] = normalize_text(df_roads_clean, 'road')
    if 'lrp' in df_roads_clean.columns:
        df_roads_clean['lrp_norm'] = normalize_text(df_roads_clean, 'lrp')
    else:
        df_roads_clean['lrp_norm'] = normalize_text(df_roads_clean, 'LRPName')

    # 2. Filter Unknown Roads
    # We can only fix bridges on roads that exist in our clean road network
    known_roads = set(df_roads_clean['road_norm'].unique())
    df_final = df_bridges[df_bridges['road_norm'].isin(known_roads)].copy()

    # 3. Build Lookup Tables (Optimization)
    # Creates fast lookup dictionaries for road length and coordinates
    road_max_lengths = df_roads_clean.groupby('road_norm')['chainage'].max().to_dict()
    road_dict = {r: g[['chainage', 'lat', 'lon']] for r, g in df_roads_clean.groupby('road_norm')}

    # 4. Prepare Golden Match (LRP Merge)
    print("   -> Executing LRP Match & Smart Repair Algorithm...")
    df_final = df_final.merge(
        df_roads_clean[['road_norm', 'lrp_norm', 'lat', 'lon']], 
        on=['road_norm', 'lrp_norm'], 
        how='left', 
        suffixes=('', '_matched')
    )

    # 5. Execute Repair Function
    # Apply the repair logic row by row
    results = df_final.apply(repair_bridge_location, axis=1, args=(road_dict, road_max_lengths), result_type='expand')
    df_final[['lat_clean', 'lon_clean', 'fix_method']] = results

    # 6. Format for Export (Java Compatibility)
    print("   -> Formatting for Excel export...")
    
    # Define exact columns required by the Java simulation
    original_columns = [
        'road', 'km', 'type', 'LRPName', 'name', 'length', 'condition', 'structureNr', 
        'roadName', 'chainage', 'width', 'constructionYear', 'spans', 'zone', 
        'circle', 'division', 'sub-division', 'lat', 'lon', 'EstimatedLoc'
    ]

    df_export = df_final.copy()
    
    # Update coordinates with cleaned values
    df_export['lat'] = df_export['lat_clean']
    df_export['lon'] = df_export['lon_clean']
    
    # Store the fix method in 'EstimatedLoc' for debugging/visualization purposes
    df_export['EstimatedLoc'] = df_export['fix_method']
    
    # Ensure numeric columns are clean (no strings)
    for col in ['lat', 'lon', 'km', 'length']:
        df_export[col] = pd.to_numeric(df_export[col], errors='coerce')

    # Select only the required columns
    df_export = df_export[original_columns]
    
    return df_export, df_final['fix_method'].value_counts()
