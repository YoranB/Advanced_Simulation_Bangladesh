import pandas as pd
import numpy as np
import os

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

def process_network_topology(df, start_id=1000000):
    """
    Deze functie regelt de 'lijm' van het netwerk:
    1. Identificeert intersections (coördinaten op >1 weg).
    2. Garandeert dat bruggen voorrang hebben op intersections.
    3. Schuift SourceSinks op als ze op een kruispunt of brug liggen.
    4. Kent unieke ID's toe op basis van locatie.
    """
    # Stap 1: Definieer locatie-sleutel (3 decimalen)
    df['lat_round'] = df['lat'].round(2)
    df['lon_round'] = df['lon'].round(2)
    df['coord_key'] = df['lat_round'].astype(str) + "_" + df['lon_round'].astype(str)
    
    # Stap 2: Prioriteit bepalen (Brug > SourceSink > Intersection > Link)
    priority_map = {'bridge': 1, 'sourcesink': 2, 'intersection': 3, 'link': 4}
    
    # Markeer potentiële intersections
    overlap = df.groupby('coord_key')['road'].nunique()
    inter_keys = overlap[overlap > 1].index
    df.loc[df['coord_key'].isin(inter_keys) & (df['model_type'] == 'link'), 'model_type'] = 'intersection'

    # Stap 3: SourceSinks verschuiven indien nodig
    processed_roads = []
    for road_name, group in df.groupby('road'):
        group = group.sort_values('chainage').reset_index(drop=True)
        
        # Bepaal begin en eind
        indices = [0, len(group)-1]
        for idx in indices:
            curr = idx
            direction = 1 if idx == 0 else -1
            # Schuif op als het een brug is OF als het punt gedeeld wordt met een andere weg (intersection)
            while 0 <= curr < len(group):
                is_bridge = (group.loc[curr, 'model_type'] == 'bridge')
                is_shared = (group.loc[curr, 'coord_key'] in inter_keys)
                
                if not is_bridge and not is_shared:
                    group.loc[curr, 'model_type'] = 'sourcesink'
                    break
                curr += direction
        processed_roads.append(group)
    
    df = pd.concat(processed_roads).reset_index(drop=True)

    # Stap 4: Master Mapping maken voor ID's en Types
    # We sorteren op prioriteit zodat de 'beste' model_type per locatie wint
    df['type_prio'] = df['model_type'].map(priority_map)
    location_master = df.sort_values('type_prio').groupby('coord_key').first().reset_index()
    
    # Unieke ID's uitdelen aan de locaties
    location_master['final_id'] = range(start_id, start_id + len(location_master))
    
    # Mappings maken
    id_map = location_master.set_index('coord_key')['final_id'].to_dict()
    type_map = location_master.set_index('coord_key')['model_type'].to_dict()
    
    # Toepassen op de volledige dataframe (zodat N1 en N2 hetzelfde ID krijgen)
    df['id'] = df['coord_key'].map(id_map)
    df['model_type'] = df['coord_key'].map(type_map)
    
    return df

def format_final_dataframe(df):
    # Namen genereren voor de onderdelen
    counts = df.groupby('model_type').cumcount() + 1
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    df.loc[df['model_type'] == 'link', 'name'] = ''
    
    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition', 'lrp', 'real_name']
    for col in expected_order:
        if col not in df.columns:
            df[col] = ''
    return df[expected_order]

def main():
    input_csv = "../data_cleaned_by_lecturer/_roads3.csv"
    bmms_xlsx = "../data_cleaned_by_lecturer/BMMS_overview.xlsx"
    output_csv = "../data_processed/A3_network_roads.csv"

    print("Bezig met verwerken...")
    df = load_data(input_csv)
    df = filter_target_roads(df)
    df = calculate_segment_lengths(df)
    df = merge_bridge_data(df, bmms_xlsx)
    
    # De nieuwe topologie logica
    df = process_network_topology(df)
    
    df = format_final_dataframe(df)
    
    # We slaan de volledige lijst op (inclusief dubbele ID's voor kruispunten)
    # Zodat je Mesa loop over 'roads' alle verbindingen ziet.
    df.to_csv(output_csv, index=False)
    print(f"Klaar! Bestand opgeslagen: {output_csv}")

if __name__ == "__main__":
    main()