import pandas as pd
import numpy as np
import os 
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

def load_data(filepath):
    filepath_str = str(filepath).lower()
    if filepath_str.endswith('.xlsx'):
        return pd.read_excel(filepath)
    else:
        return pd.read_csv(filepath, low_memory=False)


def filter_target_roads(df):
    df['chainage'] = pd.to_numeric(df['chainage'], errors='coerce')
    road_lengths = df.groupby('road')['chainage'].max() - df.groupby('road')['chainage'].min()
    valid_roads = []
    for road, length in road_lengths.items():
        road_str = str(road)
        if road_str in ['N1', 'N2'] or ((road_str.startswith('N1') or road_str.startswith('N2')) and length > 25):
            valid_roads.append(road_str)
    return df[df['road'].isin(valid_roads)].copy()


def calculate_segment_lengths(df):
    #Calculates the length of each road segment based on the chainage column
    df = df.sort_values(by=['road', 'chainage'])
    df['length'] = df.groupby('road')['chainage'].diff().fillna(0)  
    #putting it in meters`

    df['length'] = (df['length'] * 1000).round(3)
    return df


def merge_bridge_data(df_roads, bmms_filepath): 
    #merges actual bridge conditions AND official names from BMMS, using both 'road' and 'lrp' as keys for a more accurate merge
    df_bmms = load_data(bmms_filepath)
    df_bmms['LRPName'] = df_bmms['LRPName'].astype(str).str.strip()
    df_roads['lrp'] = df_roads['lrp'].astype(str).str.strip()
    
    df_bmms = df_bmms.sort_values(by='condition', ascending=False)
    df_bmms = df_bmms.drop_duplicates(subset=['road', 'LRPName'], keep='first')
    
    df_merged = pd.merge(df_roads, 
                         df_bmms[['road', 'LRPName', 'condition', 'length', 'name']], 
                         left_on=['road', 'lrp'], 
                         right_on=['road', 'LRPName'], 
                         how='left', 
                         suffixes=('', '_bmms'))
    
    df_merged['model_type'] = 'link'
    df_merged.loc[df_merged['condition'].notna(), 'model_type'] = 'bridge'
    
    df_merged['length'] = df_merged['length_bmms'].fillna(df_merged['length']) 
    df_merged['real_name'] = df_merged['name_bmms'].fillna(df_merged['name'])
    df_merged['condition'] = df_merged['condition'].fillna('A')
    return df_merged.drop(columns=['LRPName', 'length_bmms', 'name_bmms'])


def hardcode_n106_connection(df): 
    #hard coded n106 as this was far away from the N1 that it didn't snap, but we know it should be connected. We connect it to the nearest N1 point.
    n106_mask = df['road'] == 'N106'
    if not n106_mask.any(): return df
    
   
    n106_start_idx = df[n106_mask].index[0]
    n106_lat = df.loc[n106_start_idx, 'lat']
    n106_lon = df.loc[n106_start_idx, 'lon']
    
    # searches for all N1 points and calculates the distance to the N106 start point, then finds the nearest one
    n1_df = df[(df['road'] == 'N1') & (df['model_type'] != 'bridge')]
    if n1_df.empty: return df
        
    distances = ((n1_df['lat'] - n106_lat)**2 + (n1_df['lon'] - n106_lon)**2)**0.5
    nearest_n1_idx = distances.idxmin()
    
    df.loc[n106_start_idx, 'lat'] = df.loc[nearest_n1_idx, 'lat']
    df.loc[n106_start_idx, 'lon'] = df.loc[nearest_n1_idx, 'lon']
    return df 

def hardcode_n1_n2_connection(df):
    #with our snapping logic, N1 and N2 ended up very close but not connected. We know they should be connected, so we hardcode the connection by snapping the start of N2 to the nearest point on N1.
    n2_mask = df['road'] == 'N2'
    if not n2_mask.any(): return df
        
    # take the first point of N2 as the start point to connect to N1 (this is based on the chainage, which should be 0 at the start)
    n2_start_idx = df[n2_mask].index[0]
    n2_lat = df.loc[n2_start_idx, 'lat']
    n2_lon = df.loc[n2_start_idx, 'lon']
    
    # search all N1 points and calculate the distance to the N2 start point, then find the nearest one
    n1_df = df[df['road'] == 'N1']
    if n1_df.empty: return df
        
    # Calculate the distance from the N2 start point to all N1 points and find the nearest one
    distances = ((n1_df['lat'] - n2_lat)**2 + (n1_df['lon'] - n2_lon)**2)**0.5
    nearest_n1_idx = distances.idxmin()
    
    # merge the N2 start point with the nearest N1 point by setting its lat/lon to be the same as that N1 point
    df.loc[n2_start_idx, 'lat'] = df.loc[nearest_n1_idx, 'lat']
    df.loc[n2_start_idx, 'lon'] = df.loc[nearest_n1_idx, 'lon']
    print(f"HARDCODE SUCCES: N2 vastgeplakt aan N1")
    return df


def snap_side_roads(df, threshold=0.005): 
    #connecting the side roads to the main roads by snapping their endpoints to the nearest point on any other road (except bridges). We use a distance threshold to avoid incorrect snapping, but this can be adjusted based on the coordinate scale.
    for road in df['road'].unique():
        if road in ['N1', 'N2', 'N106']: 
            continue 
            
        road_mask = df['road'] == road
        road_indices = df[road_mask].index
        
        # We only want to snap the endpoints of the road, so we take the first and last index of that road's segments
        endpoints = [road_indices[0], road_indices[-1]]
        
        
        for ep_idx in endpoints:
            ep_lat = df.loc[ep_idx, 'lat']
            ep_lon = df.loc[ep_idx, 'lon']
            
            # We calculate the distance from this endpoint to all points on other roads (excluding bridges) and find the nearest one. If the nearest point is within the threshold distance, we snap to it. (as we do not want to mess with bridges as it is our main point of interest)
            other_roads_mask = (df['road'] != road) & (df['model_type'] != 'bridge')
            if not other_roads_mask.any():
                continue
            
            # Calculate the distance from the endpoint to all points on other roads and find the nearest one
            distances = ((df.loc[other_roads_mask, 'lat'] - ep_lat)**2 + 
                         (df.loc[other_roads_mask, 'lon'] - ep_lon)**2)**0.5
            
            min_dist = distances.min()
            
            # if the nearest point is within the threshold distance, snap to it by setting the endpoint's lat/lon to be the same as that nearest point
            if min_dist < threshold:
                nearest_idx = distances.idxmin()
                target_road = df.loc[nearest_idx, 'road']
                
                df.loc[ep_idx, 'lat'] = df.loc[nearest_idx, 'lat']
                df.loc[ep_idx, 'lon'] = df.loc[nearest_idx, 'lon']
                print(f"  > {road} vastgeplakt aan {target_road} (Afstand: {min_dist:.4f})")
                
    return df


def process_network_topology(df, start_id=1000000): 
    # This function identifies intersections (where multiple roads share the same coordinates) and ensures that bridges take priority in the ID assignment. It also marks the first non-bridge, non-intersection point of each road as a 'sourcesink' to satisfy the MESA requirement for having sources and sinks in the network.
    df['id'] = range(start_id, start_id + len(df))
    
    # if multiple roads share the same coordinates, we consider that an intersection. We create a 'coord_key' by rounding lat/lon to 3 decimals and concatenating them, then count how many unique roads share that key. If more than 1 road shares the same key, we mark those points as 'intersection' in the model_type (but only if they are not already marked as 'bridge', as bridges should take priority).
    df['lat_round'] = df['lat'].round(3)
    df['lon_round'] = df['lon'].round(3)
    df['coord_key'] = df['lat_round'].astype(str) + "_" + df['lon_round'].astype(str)
    
    road_counts = df.groupby('coord_key')['road'].nunique()
    inter_keys = road_counts[road_counts > 1].index
    
    # mark all points that share coordinates with another road as 'intersection', but only if they are not already marked as 'bridge' (as bridges should take priority)
    df.loc[df['coord_key'].isin(inter_keys) & (df['model_type'] == 'link'), 'model_type'] = 'intersection'

    # For each road, we want to find the first point that is not a bridge and not an intersection, and mark it as 'sourcesink'. We do this by iterating through each road group, checking the endpoints first (as those are most likely to be sources/sinks), and then moving inward until we find a suitable point to mark as 'sourcesink'.
    processed_roads = []
    for road_name, group in df.groupby('road'):
        group = group.sort_values('chainage').reset_index(drop=True)
        indices = [0, len(group)-1]
        for idx in indices:
            curr = idx
            direction = 1 if idx == 0 else -1
            while 0 <= curr < len(group):
                is_bridge = (group.loc[curr, 'model_type'] == 'bridge')
                is_shared = (group.loc[curr, 'coord_key'] in inter_keys)
                # We want to mark the first point that is not a bridge and not shared as 'sourcesink'
                if not is_bridge and not is_shared:
                    group.loc[curr, 'model_type'] = 'sourcesink'
                    break
                curr += direction
        processed_roads.append(group)
    
    df = pd.concat(processed_roads).reset_index(drop=True)

    # Finally, we want to ensure that if multiple roads share the same coordinates (intersection), they all get the same ID and lat/lon, and that if one of those roads is a bridge, it takes priority in determining the model_type and coordinates for that intersection point. We do this by iterating through each unique 'coord_key' that is shared by multiple roads, finding the "best" row among those (where bridges take priority over sources/sinks, which take priority over intersections, which take priority over links), and then assigning that best row's ID and coordinates to all rows that share that 'coord_key'.
    priority_map = {'bridge': 1, 'sourcesink': 2, 'intersection': 3, 'link': 4}
    df['type_prio'] = df['model_type'].map(priority_map)
    

    for key in inter_keys:
        mask = df['coord_key'] == key
        best_row = df[mask].sort_values('type_prio').iloc[0]
        
        df.loc[mask, 'id'] = best_row['id']
        df.loc[mask, 'model_type'] = best_row['model_type']
        df.loc[mask, 'lat'] = best_row['lat']
        df.loc[mask, 'lon'] = best_row['lon']
 
    df['prev_id'] = df.groupby('road')['id'].shift(1)
    df = df[df['id'] != df['prev_id']].copy()
    
    cols_to_drop = ['lat_round', 'lon_round', 'coord_key', 'type_prio', 'prev_id']
    return df.drop(columns=[c for c in cols_to_drop if c in df.columns])


def recalculate_lengths(df):
    #because we have done a lot of snapping and merging, the original chainage-based lengths are no longer accurate. We recalculate the lengths based on the actual lat/lon coordinates using the Haversine formula to get the real-world distance between points. However, if a segment is marked as a 'bridge', we keep its original length from BMMS, as that is a physical measurement that should not change based on our snapping.
    #we use haversine formula to calculate the distance between two lat/lon points, which gives us the length in meters. We then update the 'length' column with this new calculated length, but only for segments that are not bridges (as we want to keep the original BMMS length for bridges). For links and intersections, we use the new calculated length based on the snapped coordinates.
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000 # radius of Earth in meters
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    # sort by road and chainage to ensure we are calculating lengths in the correct order along the road
    df = df.sort_values(by=['road', 'chainage']).reset_index(drop=True)
    
    # Move lon/lat of the previous point up so we can calculate distance to the previous point
    df['prev_lat'] = df.groupby('road')['lat'].shift(1)
    df['prev_lon'] = df.groupby('road')['lon'].shift(1)
    
    # calculate the Haversine distance from the previous point to the current point, which gives us the new length of that segment based on the snapped coordinates
    df['new_length'] = haversine(df['prev_lat'], df['prev_lon'], df['lat'], df['lon'])
    
    # the starting point of each road will have NaN for the new_length because there is no previous point to compare to. We can fill those NaN values with 0, as the length from the starting point to itself is 0. We also round the new_length to 3 decimals for consistency.
    df['new_length'] = df['new_length'].fillna(0).round(3)
    
    # Update lenght, however keep the bridge lenght intact if it is a bridge 
    df['length'] = np.where(df['model_type'] == 'bridge', df['length'], df['new_length'])
    
    return df.drop(columns=['prev_lat', 'prev_lon', 'new_length'])


def format_final_dataframe(df):
    counts = df.groupby('model_type').cumcount() + 1
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    df.loc[df['model_type'] == 'link', 'name'] = ''
    
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition', 'lrp', 'real_name']
    for col in expected_order:
        if col not in df.columns:
            df[col] = ''
    return df[expected_order] 


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Added "data" to the paths to match the new folder structure
    input_csv = os.path.join(script_dir, "..", "data", "data_cleaned_by_lecturer", "_roads3.csv")
    bmms_xlsx = os.path.join(script_dir, "..", "data", "data_cleaned_by_lecturer", "BMMS_overview.xlsx")
    output_csv = os.path.join(script_dir, "..", "data", "data_processed", "A3_network_roads.csv")

    print("Bezig met verwerken...")

    # Fallback paths (e.g., if you are running the script from the root directory instead of the preprocessing directory)
    if not os.path.exists(input_csv):
        input_csv = "data/data_cleaned_by_lecturer/_roads3.csv"
        bmms_xlsx = "data/data_cleaned_by_lecturer/BMMS_overview.xlsx"
        output_csv = "data/data_processed/A3_network_roads.csv"

    df = load_data(input_csv)
    df = filter_target_roads(df)
    
    # calculate initial length
    df = calculate_segment_lengths(df)
    
    df = merge_bridge_data(df, bmms_xlsx)
    
    df = hardcode_n106_connection(df) 
    df = hardcode_n1_n2_connection(df)
    df = snap_side_roads(df)
    df = process_network_topology(df)
    
    # calculate new lenght
    df = recalculate_lengths(df)
    
    df = format_final_dataframe(df)
    
    if not os.path.exists(os.path.dirname(output_csv)):
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        
    df.to_csv(output_csv, index=False)
    print(f"Klaar! Bestand opgeslagen: {output_csv}")

   
   #visualisation
    print("\n--- Generating Network Map ---")
    
    #search for all linkages
    road_counts_per_id = df.groupby('id')['road'].nunique()
    echte_kruispunt_ids = road_counts_per_id[road_counts_per_id > 1].index
    intersections = df[df['id'].isin(echte_kruispunt_ids)].drop_duplicates(subset=['id'])
    
    print(f"Total amount of real intersections: {len(intersections)}\n")

    fig, ax = plt.subplots(figsize=(10, 10), facecolor='white')

    for road_name, road_data in df.groupby('road'):
        lons = road_data['lon'].values
        lats = road_data['lat'].values
        
        if road_name == 'N1':
            ax.plot(lons, lats, color='blue', linewidth=5, zorder=2)
        elif road_name == 'N2':
            ax.plot(lons, lats, color='green', linewidth=5, zorder=3)
        else:
            ax.plot(lons, lats, color='gray', linewidth=3, zorder=1)

    if not intersections.empty:
        ax.scatter(intersections['lon'], intersections['lat'], 
                   color='red', marker='X', s=150, zorder=4, edgecolors='black')

    for road_name, road_data in df.groupby('road'):
        mid_idx = len(road_data) // 2
        pt_x = road_data.iloc[mid_idx]['lon']
        pt_y = road_data.iloc[mid_idx]['lat']
        
        weight = 'bold' if road_name in ['N1', 'N2'] else 'normal'
        color = 'blue' if road_name == 'N1' else 'green' if road_name == 'N2' else 'black'
        
        ax.annotate(road_name, (pt_x, pt_y), color=color, fontsize=9, fontweight=weight,
                    ha='center', va='center',
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray', boxstyle='round,pad=0.2'),
                    zorder=5)

    plt.title("N1 & N2 Network with intersections", fontsize=16, fontweight='bold')
    plt.xlabel("Longitude", fontsize=12)
    plt.ylabel("Latitude", fontsize=12)

    custom_legend = [
        Line2D([0], [0], color='blue', lw=5, label='N1 Highway'),
        Line2D([0], [0], color='green', lw=5, label='N2 Highway'),
        Line2D([0], [0], color='gray', lw=3, label='Connected Branches'),
        Line2D([0], [0], color='white', marker='X', markerfacecolor='red', markeredgecolor='black', markersize=10, label='Kruispunten')
    ]
    ax.legend(handles=custom_legend, loc='lower right', fontsize=11, shadow=True)
    
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()

    try:
        save_path = os.path.join(os.path.dirname(output_csv), "Assignment_3_Network_Filtered.png")
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    except:
        pass
        
    plt.show()

if __name__ == "__main__":
    main()