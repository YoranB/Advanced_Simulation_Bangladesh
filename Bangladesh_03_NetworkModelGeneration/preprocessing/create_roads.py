import pandas as pd
import numpy as np
import os

# this code is based on the original create_roads.py from assignment 2, but has been heavily refactored and extended to meet the requirements of Assignment 3. 



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
    df = df.sort_values(by=['road', 'chainage'])
    df['length'] = df.groupby('road')['chainage'].diff().fillna(0)
    df['length'] = (df['length'] * 1000).round(3)
    return df

def merge_bridge_data(df_roads, bmms_filepath):
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


#this part is new: 
def process_network_topology(df, start_id=1000000):
    """
     This function is the glue of the network:
    1. Identify intersection on the road network based on shared coordinates (rounded to 2 decimals) and mark them as 'intersection'.
    2. guarantee bridges have highest priority never move bridges, but move sourcesinks if they are on the same location as a bridge or intersection.
    3. move sourcesinks if they are at the same location as an intersection (but not a bridge) to the nearest link segment on the same road, so that they are not on top of each other.
    4. assign unique IDs to each location (intersection, bridge, sourcesink, link) based on the rounded coordinates, so that N1 and N2 get the same ID for the same location.
    """
    # define location key based on rounded coordinates
    df['lat_round'] = df['lat'].round(2)
    df['lon_round'] = df['lon'].round(2)
    df['coord_key'] = df['lat_round'].astype(str) + "_" + df['lon_round'].astype(str)
    
    # We geven prioriteit aan model_types: bridge > sourcesink > intersection > link
    priority_map = {'bridge': 1, 'sourcesink': 2, 'intersection': 3, 'link': 4}
    
    # identify intersections: locaitons where multiple roads share the same rounded coordinates (coord_key)
    overlap = df.groupby('coord_key')['road'].nunique()
    inter_keys = overlap[overlap > 1].index
    df.loc[df['coord_key'].isin(inter_keys) & (df['model_type'] == 'link'), 'model_type'] = 'intersection'

    #move sourse sing if the sourse sink point is also a intersection or bridge, we move the source sink point to the nearest link segment on the same road. We keep moving until we find a link that is not an intersection or bridge.
    processed_roads = []
    for road_name, group in df.groupby('road'):
        group = group.sort_values('chainage').reset_index(drop=True)
        
        # determine the indices to check for sourcesinks at the start and end of the road
        indices = [0, len(group)-1]
        for idx in indices:
            curr = idx
            direction = 1 if idx == 0 else -1
            # move the sourcesink if it is on the same location as a bridge or intersection, keep moving until we find a link that is not an intersection or bridge
            while 0 <= curr < len(group):
                is_bridge = (group.loc[curr, 'model_type'] == 'bridge')
                is_shared = (group.loc[curr, 'coord_key'] in inter_keys)
                
                if not is_bridge and not is_shared:
                    group.loc[curr, 'model_type'] = 'sourcesink'
                    break
                curr += direction
        processed_roads.append(group)
    
    df = pd.concat(processed_roads).reset_index(drop=True)

    # assign unique IDs to each location (intersection, bridge, sourcesink, link) based on the rounded coordinates, so that N1 and N2 get the same ID for the same location. We sorteren op prioriteit zodat de 'beste' model_type per locatie wint
    # we sort on priority so that the 'best' model_type per location wins, and we create a  list of unique locations based on the rounded coordinates, which we then use to assign unique IDs and model types to the full dataframe (so that N1 and N2 get the same ID for the same location). This way we ensure that bridges keep their location, and sourcesinks are moved if they are on the same location as a bridge or intersection, but they get the same ID as the original location.
    df['type_prio'] = df['model_type'].map(priority_map)
    location_master = df.sort_values('type_prio').groupby('coord_key').first().reset_index()
    
    # unique ID's to each location (intersection, bridge, sourcesink, link) based on the rounded coordinates, so that N1 and N2 get the same ID for the same location. We sorteren op prioriteit zodat de 'beste' model_type per locatie wint
    location_master['final_id'] = range(start_id, start_id + len(location_master))
    
    # mappings
    id_map = location_master.set_index('coord_key')['final_id'].to_dict()
    type_map = location_master.set_index('coord_key')['model_type'].to_dict()
    
    # do it on the whole  dataframe
    df['id'] = df['coord_key'].map(id_map)
    df['model_type'] = df['coord_key'].map(type_map)
    
    return df

def format_final_dataframe(df):
    # generate names for the sub parts
    counts = df.groupby('model_type').cumcount() + 1
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    df.loc[df['model_type'] == 'link', 'name'] = ''
    
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition', 'lrp', 'real_name']
    for col in expected_order:
        if col not in df.columns:
            df[col] = ''
    return df[expected_order] 



#we found out the above code lead to still a disconnected network as the N106 does not have a perfect intersection with the N1, so we hardcode the N106 to be connected to the nearest point on the N1. This is a bit of a hack, but it ensures that the network is fully connected and that the N106 can be used as a source/sink in the model. We do this after merging the BMMS data, but before processing the network topology, so that we can ensure that the N106 is connected to the correct point on the N1 (and not moved later by the topology processing).

def hardcode_n106_connection(df):
    """
    Hardcode:Takes the start point of N106 and moves this to the closest point on the N1 
    So a perfect intersection is created between N106 and N1. This is a bit of a hack, but it ensures that the network is fully connected and that the N106 can be used as a source/sink in the model. We do this after merging the BMMS data, but before processing the network topology, so that we can ensure that the N106 is connected to the correct point on the N1 (and not moved later by the topology processing). We identify the start point of the N106 and move it
    """
    n106_mask = df['road'] == 'N106'
    if not n106_mask.any():
        return df
        
    n106_start_idx = df[n106_mask].index[0]
    n106_lat = df.loc[n106_start_idx, 'lat']
    n106_lon = df.loc[n106_start_idx, 'lon']
    
    n1_df = df[df['road'] == 'N1']
    if n1_df.empty:
        return df
        
    # calculate distances to all points on N1 and find the nearest one
    distances = ((n1_df['lat'] - n106_lat)**2 + (n1_df['lon'] - n106_lon)**2)**0.5
    nearest_n1_idx = distances.idxmin()
    
    # overwrite the lat and lon of the N106 start point to match the nearest point on the N1
    df.loc[n106_start_idx, 'lat'] = df.loc[nearest_n1_idx, 'lat']
    df.loc[n106_start_idx, 'lon'] = df.loc[nearest_n1_idx, 'lon']
    
    print(f"HARDCODE SUCCES: N106 vastgeplakt aan N1")
    return df

def main():
    input_csv = "../data_cleaned_by_lecturer/_roads3.csv"
    bmms_xlsx = "../data_cleaned_by_lecturer/BMMS_overview.xlsx"
    output_csv = "../data_processed/A3_network_roads.csv"

    print("Bezig met verwerken...")
    df = load_data(input_csv)
    df = filter_target_roads(df)
    df = calculate_segment_lengths(df)
    df = merge_bridge_data(df, bmms_xlsx)
    
    df = hardcode_n106_connection(df)
    # new logic to process the network topology, identify intersections, and assign unique IDs based on location, while ensuring that bridges keep their location and sourcesinks are moved if they are on the same location as a bridge or intersection.
    df = process_network_topology(df)
    
    df = format_final_dataframe(df)
    
    # We save the complete list ( including all dublle ID's for cross roads)
    # So mesa can loop over all roads and see interconnections
    df.to_csv(output_csv, index=False)
    print(f"Klaar! Bestand opgeslagen: {output_csv}")

if __name__ == "__main__":
    main()