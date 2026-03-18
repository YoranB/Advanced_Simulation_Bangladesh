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
    Identificeert kruispunten, behoudt brug-prioriteit en zorgt dat 
    gewone wegsegmenten niet in elkaar fuseren.
    """
    # 1. Geef ELKE rij eerst een compleet uniek ID (behoudt weglengtes)
    df['id'] = range(start_id, start_id + len(df))
    
    # 2. Bepaal overlappen met 3 decimalen (~110m). 
    df['lat_round'] = df['lat'].round(3)
    df['lon_round'] = df['lon'].round(3)
    df['coord_key'] = df['lat_round'].astype(str) + "_" + df['lon_round'].astype(str)
    
    # 3. Zoek 'keys' (plekken) waar MEERDERE wegen in hetzelfde vakje vallen
    road_counts = df.groupby('coord_key')['road'].nunique()
    inter_keys = road_counts[road_counts > 1].index
    
    # Markeer als intersection (alleen als het een normale link was)
    df.loc[df['coord_key'].isin(inter_keys) & (df['model_type'] == 'link'), 'model_type'] = 'intersection'

    # 4. SourceSink verschuiven (je bestaande logica)
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
                if not is_bridge and not is_shared:
                    group.loc[curr, 'model_type'] = 'sourcesink'
                    break
                curr += direction
        processed_roads.append(group)
    
    df = pd.concat(processed_roads).reset_index(drop=True)

    # 5. ID'S GELIJKTREKKEN (Alleen voor de kruispunten!)
    priority_map = {'bridge': 1, 'sourcesink': 2, 'intersection': 3, 'link': 4}
    df['type_prio'] = df['model_type'].map(priority_map)
    
    for key in inter_keys:
        mask = df['coord_key'] == key
        # Pak de 'belangrijkste' rij op dit kruispunt
        best_row = df[mask].sort_values('type_prio').iloc[0]
        
        # Forceer alle wegen op dit kruispunt om exact dit ID en Type te gebruiken
        df.loc[mask, 'id'] = best_row['id']
        df.loc[mask, 'model_type'] = best_row['model_type']
        
        # Zet ze exact op dezelfde pixel voor een strakke visuele kaart
        df.loc[mask, 'lat'] = best_row['lat']
        df.loc[mask, 'lon'] = best_row['lon']
        
    # 6. VERWIJDER ZELF-LUSSEN
    # Als een weg heel veel bochten had op 1 kruispunt, kan hij nu twee keer hetzelfde 
    # ID achter elkaar hebben. Dat droppen we, zodat de truck soepel doorrijdt.
    df['prev_id'] = df.groupby('road')['id'].shift(1)
    df = df[df['id'] != df['prev_id']].copy()
    
    # Opschonen
    cols_to_drop = ['lat_round', 'lon_round', 'coord_key', 'type_prio', 'prev_id']
    return df.drop(columns=[c for c in cols_to_drop if c in df.columns])


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