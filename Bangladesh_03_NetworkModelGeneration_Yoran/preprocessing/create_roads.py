import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os


# ==========================================
# DATA PROCESSING FUNCTIES
# ==========================================

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


def calculate_initial_lengths(df):
    df = df.sort_values(by=['road', 'chainage'])
    df['length'] = (df.groupby('road')['chainage'].diff().fillna(0) * 1000).round(3)
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


def hardcode_n106_connection(df):
    n106_mask = df['road'] == 'N106'
    if not n106_mask.any():
        return df

    n106_start_idx = df[n106_mask].index[0]
    n106_lat = df.loc[n106_start_idx, 'lat']
    n106_lon = df.loc[n106_start_idx, 'lon']

    n1_df = df[df['road'] == 'N1']
    if n1_df.empty:
        return df

    distances = ((n1_df['lat'] - n106_lat) ** 2 + (n1_df['lon'] - n106_lon) ** 2) ** 0.5
    nearest_n1_idx = distances.idxmin()

    df.loc[n106_start_idx, 'lat'] = df.loc[nearest_n1_idx, 'lat']
    df.loc[n106_start_idx, 'lon'] = df.loc[nearest_n1_idx, 'lon']
    return df


def densify_roads(df, interval_m=1000):
    print(f"Densifying roads (punt elke {interval_m}m toevoegen)...")
    interval_km = interval_m / 1000.0
    densified_rows = []

    for road_name, group in df.groupby('road'):
        group = group.sort_values('chainage').reset_index(drop=True)

        for i in range(len(group)):
            densified_rows.append(group.iloc[i].to_dict())
            if i < len(group) - 1:
                curr_pt = group.iloc[i]
                next_pt = group.iloc[i + 1]
                chainage_diff = next_pt['chainage'] - curr_pt['chainage']

                if chainage_diff > interval_km:
                    num_intervals = int(np.ceil(chainage_diff / interval_km))
                    for j in range(1, num_intervals):
                        fraction = j / num_intervals
                        densified_rows.append({
                            'road': road_name,
                            'chainage': curr_pt['chainage'] + (chainage_diff * fraction),
                            'lat': curr_pt['lat'] + ((next_pt['lat'] - curr_pt['lat']) * fraction),
                            'lon': curr_pt['lon'] + ((next_pt['lon'] - curr_pt['lon']) * fraction),
                            'model_type': 'link',
                            'condition': 'A',
                            'name': '', 'real_name': '', 'lrp': '', 'length': 0
                        })

    return pd.DataFrame(densified_rows)


def process_network_topology(df, start_id=1000000, snap_dist_deg=0.0005):
    print("Netwerktopologie berekenen (met behoud van originele source/sinks)...")
    df = df.copy().reset_index(drop=True)
    df['id'] = range(start_id, start_id + len(df))
    roads = df['road'].unique()

    # Pre-compute indices voor snelle lookups
    road_indices_map = {r: df[df['road'] == r].sort_values('chainage').index.tolist() for r in roads}

    # ==========================================
    # 1. ORIGINELE SOURCE/SINKS ZETTEN
    # ==========================================
    # Kijk naar de originele data in de 'lrp' kolom ('LRPS' = start, 'LRPE' = end)
    mask_ss = df['lrp'].astype(str).str.upper().isin(['LRPS', 'LRPE'])
    df.loc[mask_ss & (df['model_type'] != 'bridge'), 'model_type'] = 'sourcesink'

    # Zorg als fallback dat de uiterste punten van wegen ook altijd sourcesink zijn
    for road_name in roads:
        idx_list = road_indices_map[road_name]
        if df.loc[idx_list[0], 'model_type'] == 'link': df.loc[idx_list[0], 'model_type'] = 'sourcesink'
        if df.loc[idx_list[-1], 'model_type'] == 'link': df.loc[idx_list[-1], 'model_type'] = 'sourcesink'

    # HELPER: Schuif het punt op als het een brug is
    def find_nearest_non_bridge(df, road, current_idx):
        road_idxs = road_indices_map[road]
        pos = road_idxs.index(current_idx)
        for shift in range(1, 15):  # Zoek tot ~375m verderop
            if pos + shift < len(road_idxs) and df.loc[road_idxs[pos + shift], 'model_type'] != 'bridge':
                return road_idxs[pos + shift]
            if pos - shift >= 0 and df.loc[road_idxs[pos - shift], 'model_type'] != 'bridge':
                return road_idxs[pos - shift]
        return current_idx

    # HELPER: Schuif de sourcesink op als deze wordt overschreven door een kruispunt
    def shift_sourcesink(df, road, conflict_idx):
        road_idxs = road_indices_map[road]
        pos = road_idxs.index(conflict_idx)
        direction = 1 if pos < (
                    len(road_idxs) / 2) else -1  # Startpunt? Schuif naar voren. Eindpunt? Schuif naar achteren.

        curr = pos + direction
        while 0 <= curr < len(road_idxs):
            if df.loc[road_idxs[curr], 'model_type'] == 'link':
                df.loc[road_idxs[curr], 'model_type'] = 'sourcesink'
                print(f"➜ Source/Sink op {road} botste met nieuw kruispunt en is opgeschoven naar de volgende link.")
                break
            curr += direction

    # ==========================================
    # 2. INTERSECTIONS ZOEKEN & CONFLICTEN OPLOSSEN
    # ==========================================
    for i in range(len(roads)):
        for j in range(i + 1, len(roads)):
            road_a = roads[i]
            road_b = roads[j]

            mask_a = df['road'] == road_a
            mask_b = df['road'] == road_b

            lat_a, lon_a = df.loc[mask_a, 'lat'].values, df.loc[mask_a, 'lon'].values
            lat_b, lon_b = df.loc[mask_b, 'lat'].values, df.loc[mask_b, 'lon'].values

            dist_sq = (lat_a[:, np.newaxis] - lat_b) ** 2 + (lon_a[:, np.newaxis] - lon_b) ** 2
            close_pairs = np.where(dist_sq < (snap_dist_deg ** 2))

            processed_a_rels = []

            for a_rel, b_rel in zip(close_pairs[0], close_pairs[1]):
                # Cooldown: voorkom dat we 10 knooppunten maken voor dezelfde fysieke kruising
                if any(abs(a_rel - p) < 10 for p in processed_a_rels):
                    continue

                idx_a = df.index[mask_a][a_rel]
                idx_b = df.index[mask_b][b_rel]

                # CONFLICT 1: BRUGGEN
                if df.loc[idx_a, 'model_type'] == 'bridge':
                    print(f"⚠️ Kruising op brug ({road_a}). Kruispunt wordt verplaatst naar naastgelegen punt.")
                    idx_a = find_nearest_non_bridge(df, road_a, idx_a)
                if df.loc[idx_b, 'model_type'] == 'bridge':
                    print(f"⚠️ Kruising op brug ({road_b}). Kruispunt wordt verplaatst naar naastgelegen punt.")
                    idx_b = find_nearest_non_bridge(df, road_b, idx_b)

                # CONFLICT 2: SOURCE/SINKS
                if df.loc[idx_a, 'model_type'] == 'sourcesink':
                    shift_sourcesink(df, road_a, idx_a)
                if df.loc[idx_b, 'model_type'] == 'sourcesink':
                    shift_sourcesink(df, road_b, idx_b)

                # MAAK HET KRUISPUNT
                df.loc[idx_a, 'model_type'] = 'intersection'
                df.loc[idx_b, 'model_type'] = 'intersection'
                df.loc[idx_b, 'lat'] = df.loc[idx_a, 'lat']
                df.loc[idx_b, 'lon'] = df.loc[idx_a, 'lon']
                df.loc[idx_b, 'id'] = df.loc[idx_a, 'id']  # ID overschrijven zodat het netwerk koppelt

                processed_a_rels.append(a_rel)

    # Verwijder dubbele (overlappende) nodes achter elkaar op dezelfde weg
    df['prev_id'] = df.groupby('road')['id'].shift(1)
    df = df[df['id'] != df['prev_id']].copy()

    return df.drop(columns=['prev_id'])


def recalculate_segment_lengths_haversine(df):
    print("Lengtes van aangepaste wegen herberekenen (Haversine)...")
    df = df.sort_values(by=['road', 'chainage']).copy()

    prev_lat = df.groupby('road')['lat'].shift(1)
    prev_lon = df.groupby('road')['lon'].shift(1)

    # Haversine Formule in meters
    R = 6371000.0
    phi1, phi2 = np.radians(prev_lat), np.radians(df['lat'])
    dphi = np.radians(df['lat'] - prev_lat)
    dlambda = np.radians(df['lon'] - prev_lon)

    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    dists = R * c

    dists = dists.fillna(0).round(3)

    mask = df['model_type'] != 'bridge'
    df.loc[mask, 'length'] = dists[mask]

    return df


def format_final_dataframe(df):
    counts = df.groupby('model_type').cumcount() + 1
    df['name'] = df['model_type'] + ' ' + counts.astype(str)
    df.loc[df['model_type'] == 'link', 'name'] = ''

    expected_order = ['road', 'id', 'model_type', 'name', 'lat', 'lon', 'length', 'condition', 'lrp', 'real_name']
    for col in expected_order:
        if col not in df.columns:
            df[col] = ''
    return df[expected_order]


def plot_network(df, output_path):
    print("Maken van de netwerk plot...")
    plt.figure(figsize=(14, 10))

    links = df[df['model_type'] == 'link']
    plt.scatter(links['lon'], links['lat'], s=2, c='darkgray', label='Link', alpha=0.6)

    # bridges = df[df['model_type'] == 'bridge']
    # plt.scatter(bridges['lon'], bridges['lat'], s=30, c='dodgerblue', marker='s', label='Bridge', edgecolors='k',
    #             linewidths=0.5)

    intersections = df[df['model_type'] == 'intersection']
    plt.scatter(intersections['lon'], intersections['lat'], s=80, c='crimson', marker='*', label='Intersection',
                edgecolors='k', linewidths=0.5)

    # sourcesinks = df[df['model_type'] == 'sourcesink']
    # plt.scatter(sourcesinks['lon'], sourcesinks['lat'], s=80, c='limegreen', marker='^', label='Source/Sink',
    #             edgecolors='k', linewidths=0.5)

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Road Network Topology (Docent Rules Applied)')
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.5)

    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    print(f"Plot opgeslagen: {output_path}")


# ==========================================
# MAIN EXECUTIE
# ==========================================

def main():
    input_csv = "../data_cleaned_by_lecturer/_roads3.csv"
    bmms_xlsx = "../data_cleaned_by_lecturer/BMMS_overview.xlsx"

    output_dir = "../data_processed"
    os.makedirs(output_dir, exist_ok=True)

    output_csv = os.path.join(output_dir, "A3_network_roads.csv")
    output_plot = os.path.join(output_dir, "A3_network_roads_plot.png")

    print("Bezig met het inladen van de data...")
    df = load_data(input_csv)
    df = filter_target_roads(df)

    df = calculate_initial_lengths(df)
    df = merge_bridge_data(df, bmms_xlsx)
    df = hardcode_n106_connection(df)
    df = densify_roads(df, interval_m=1000)

    # Gebruikt nu expliciet de originele LRPS/LRPE locaties en lost alle conflicten op
    df = process_network_topology(df)

    # Docent Regel: Herbereken lengte!
    df = recalculate_segment_lengths_haversine(df)

    df = format_final_dataframe(df)
    df.to_csv(output_csv, index=False)
    print(f"Klaar! CSV Bestand opgeslagen: {output_csv}")

    plot_network(df, output_plot)


if __name__ == "__main__":
    main()