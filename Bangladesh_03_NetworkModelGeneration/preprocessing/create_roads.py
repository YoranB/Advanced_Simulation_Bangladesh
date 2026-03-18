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
    """
    Stap 1 lengte-berekening (vereist om de dataframe te vullen voor de merge met bruggen).
    """
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
    
    # Hier was de error! Omdat we calculate_segment_lengths nu wel draaien, gaat dit goed:
    df_merged['length'] = df_merged['length_bmms'].fillna(df_merged['length']) 
    df_merged['real_name'] = df_merged['name_bmms'].fillna(df_merged['name'])
    df_merged['condition'] = df_merged['condition'].fillna('A')
    return df_merged.drop(columns=['LRPName', 'length_bmms', 'name_bmms'])


def hardcode_n106_connection(df):
    n106_mask = df['road'] == 'N106'
    if not n106_mask.any(): return df
        
    n106_start_idx = df[n106_mask].index[0]
    n106_lat = df.loc[n106_start_idx, 'lat']
    n106_lon = df.loc[n106_start_idx, 'lon']
    
    # Docent feedback: Negeer bruggen!
    n1_df = df[(df['road'] == 'N1') & (df['model_type'] != 'bridge')]
    if n1_df.empty: return df
        
    distances = ((n1_df['lat'] - n106_lat)**2 + (n1_df['lon'] - n106_lon)**2)**0.5
    nearest_n1_idx = distances.idxmin()
    
    df.loc[n106_start_idx, 'lat'] = df.loc[nearest_n1_idx, 'lat']
    df.loc[n106_start_idx, 'lon'] = df.loc[nearest_n1_idx, 'lon']
    return df 

def hardcode_n1_n2_connection(df):
    """
    Trekt het startpunt van de N2 naar het dichtstbijzijnde punt op de N1.
    """
    n2_mask = df['road'] == 'N2'
    if not n2_mask.any(): return df
        
    # Pak het eerste punt van de N2
    n2_start_idx = df[n2_mask].index[0]
    n2_lat = df.loc[n2_start_idx, 'lat']
    n2_lon = df.loc[n2_start_idx, 'lon']
    
    # Zoek alle N1 punten
    n1_df = df[df['road'] == 'N1']
    if n1_df.empty: return df
        
    # Bereken afstand en zoek de dichtstbijzijnde
    distances = ((n1_df['lat'] - n2_lat)**2 + (n1_df['lon'] - n2_lon)**2)**0.5
    nearest_n1_idx = distances.idxmin()
    
    # Koppel N2 startpunt aan N1
    df.loc[n2_start_idx, 'lat'] = df.loc[nearest_n1_idx, 'lat']
    df.loc[n2_start_idx, 'lon'] = df.loc[nearest_n1_idx, 'lon']
    print(f"HARDCODE SUCCES: N2 vastgeplakt aan N1")
    return df


def snap_side_roads(df, threshold=0.005): 
    print("\n--- Verbinden van overige zijwegen (snapping) ---")
    for road in df['road'].unique():
        if road in ['N1', 'N2', 'N106']: 
            continue 
            
        road_mask = df['road'] == road
        road_indices = df[road_mask].index
        
        endpoints = [road_indices[0], road_indices[-1]]
        
        for ep_idx in endpoints:
            ep_lat = df.loc[ep_idx, 'lat']
            ep_lon = df.loc[ep_idx, 'lon']
            
            # Docent feedback: Zoek in alle andere wegen, MAAR negeer de bruggen!
            other_roads_mask = (df['road'] != road) & (df['model_type'] != 'bridge')
            if not other_roads_mask.any():
                continue
                
            distances = ((df.loc[other_roads_mask, 'lat'] - ep_lat)**2 + 
                         (df.loc[other_roads_mask, 'lon'] - ep_lon)**2)**0.5
            
            min_dist = distances.min()
            
            if min_dist < threshold:
                nearest_idx = distances.idxmin()
                target_road = df.loc[nearest_idx, 'road']
                
                df.loc[ep_idx, 'lat'] = df.loc[nearest_idx, 'lat']
                df.loc[ep_idx, 'lon'] = df.loc[nearest_idx, 'lon']
                print(f"  > {road} vastgeplakt aan {target_road} (Afstand: {min_dist:.4f})")
                
    return df


def process_network_topology(df, start_id=1000000):
    df['id'] = range(start_id, start_id + len(df))
    
    df['lat_round'] = df['lat'].round(3)
    df['lon_round'] = df['lon'].round(3)
    df['coord_key'] = df['lat_round'].astype(str) + "_" + df['lon_round'].astype(str)
    
    road_counts = df.groupby('coord_key')['road'].nunique()
    inter_keys = road_counts[road_counts > 1].index
    
    # Markeer als intersection
    df.loc[df['coord_key'].isin(inter_keys) & (df['model_type'] == 'link'), 'model_type'] = 'intersection'

    # SOURCESINKS VERSCHUIVEN (Dit doet al precies wat de docent vroeg!)
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
                # Plant SourceSink op het eerste punt dat géén brug en géén kruispunt is
                if not is_bridge and not is_shared:
                    group.loc[curr, 'model_type'] = 'sourcesink'
                    break
                curr += direction
        processed_roads.append(group)
    
    df = pd.concat(processed_roads).reset_index(drop=True)

    # ID'S GELIJKTREKKEN (Bruggen winnen hier de prioriteit!)
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
    """
    DOCENT FEEDBACK FIX: Omdat we wegen hebben vastgeplakt (coördinaten veranderd),
    moeten we de lengte in meters opnieuw berekenen via de Haversine formule.
    """
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000 # Straal van de aarde in meters
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    # Sorteer netjes per weg
    df = df.sort_values(by=['road', 'chainage']).reset_index(drop=True)
    
    # Verschuif de lat/lon zodat we de afstand tot het vorige punt kunnen berekenen
    df['prev_lat'] = df.groupby('road')['lat'].shift(1)
    df['prev_lon'] = df.groupby('road')['lon'].shift(1)
    
    # Bereken nieuwe lengte in meters
    df['new_length'] = haversine(df['prev_lat'], df['prev_lon'], df['lat'], df['lon'])
    
    # Het startpunt van elke weg heeft geen vorig punt, lengte is daar 0
    df['new_length'] = df['new_length'].fillna(0).round(3)
    
    # Update de lengte, MAAR laat de bruglengte intact als het een brug is (want dat is fysiek)
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
    input_csv = os.path.join(script_dir, "..", "data_cleaned_by_lecturer", "_roads3.csv")
    bmms_xlsx = os.path.join(script_dir, "..", "data_cleaned_by_lecturer", "BMMS_overview.xlsx")
    output_csv = os.path.join(script_dir, "..", "data_processed", "A3_network_roads.csv")

    print("Bezig met verwerken...")
    if not os.path.exists(input_csv):
        input_csv = "../data_cleaned_by_lecturer/_roads3.csv"
        bmms_xlsx = "../data_cleaned_by_lecturer/BMMS_overview.xlsx"
        output_csv = "../data_processed/A3_network_roads.csv"

    df = load_data(input_csv)
    df = filter_target_roads(df)
    
    # 0. DE FIX: Bereken eerst de initiële segmentlengtes (zodat pandas niet crasht!)
    df = calculate_segment_lengths(df)
    
    df = merge_bridge_data(df, bmms_xlsx)
    
    df = hardcode_n106_connection(df) 
    df = hardcode_n1_n2_connection(df)
    df = snap_side_roads(df)
    df = process_network_topology(df)
    
    # --- DE NIEUWE LENGTE BEREKENING (Docent feedback) ---
    df = recalculate_lengths(df)
    
    df = format_final_dataframe(df)
    
    if not os.path.exists(os.path.dirname(output_csv)):
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        
    df.to_csv(output_csv, index=False)
    print(f"Klaar! Bestand opgeslagen: {output_csv}")

    # =========================================================================
    # VISUALIZATION
    # =========================================================================
    print("\n--- Generating Network Map ---")
    
    # Zoek alle wiskundige kruispunten (waar 2 wegen dezelfde coördinaten delen)
    # Zelfs als het woordje 'bridge' er staat, krijgt het hier een rood kruisje als het snijdt.
    road_counts_per_id = df.groupby('id')['road'].nunique()
    echte_kruispunt_ids = road_counts_per_id[road_counts_per_id > 1].index
    intersections = df[df['id'].isin(echte_kruispunt_ids)].drop_duplicates(subset=['id'])
    
    print(f"Totaal échte kruispunten getekend: {len(intersections)}\n")

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

    plt.title("N1 & N2 Network met Intersections", fontsize=16, fontweight='bold')
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