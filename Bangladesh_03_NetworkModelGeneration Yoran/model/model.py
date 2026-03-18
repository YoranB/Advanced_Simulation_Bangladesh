from mesa import Model
from mesa.time import BaseScheduler
from mesa.space import ContinuousSpace
from components import Source, Sink, SourceSink, Bridge, Link, Intersection
import pandas as pd
from collections import defaultdict
import networkx as nx


# ---------------------------------------------------------------
def set_lat_lon_bound(lat_min, lat_max, lon_min, lon_max, edge_ratio=0.02):
    """
    Set the HTML continuous space canvas bounding box (for visualization)
    give the min and max latitudes and Longitudes in Decimal Degrees (DD)

    Add white borders at edges (default 2%) of the bounding box
    """

    lat_edge = (lat_max - lat_min) * edge_ratio
    lon_edge = (lon_max - lon_min) * edge_ratio

    x_max = lon_max + lon_edge
    y_max = lat_min - lat_edge
    x_min = lon_min - lon_edge
    y_min = lat_max + lat_edge
    return y_min, y_max, x_min, x_max


def optimize_network_data(df):
    """
    Merges consecutive 'link' segments on the same road into a single link,
    summing their lengths to drastically reduce the number of agents.
    """
    optimized_rows = []

    # We do this per road so we never accidentally merge links from different roads
    for road in df['road'].unique():
        road_df = df[df['road'] == road]

        current_link = None

        for _, row in road_df.iterrows():
            model_type = row['model_type'].strip().lower()

            if model_type == 'link':
                if current_link is None:
                    # Start a new combined link
                    current_link = row.to_dict()
                else:
                    # Add the length of this segment to the running total
                    current_link['length'] += row['length']
                    # We keep the 'lat' and 'lon' of the very first segment,
                    # which is fine since visual exactness matters less than logical length.
            else:
                # We hit a bridge, intersection, source, or sink!
                # 1. Save the accumulated link if we were building one
                if current_link is not None:
                    optimized_rows.append(current_link)
                    current_link = None

                # 2. Save this special feature exactly as it is
                optimized_rows.append(row.to_dict())

        # If the road ends with a link, make sure to save it!
        if current_link is not None:
            optimized_rows.append(current_link)

    # Return a clean, heavily reduced DataFrame
    return pd.DataFrame(optimized_rows)


def print_dataframe_status(df, stage="BEFORE"):
    """
    Analyzes the DataFrame to count the number of nodes (intersections,
    bridges, etc.) and edges (links) based on the 'model_type'.
    """
    # Clean up the string to ensure accurate counting
    model_types = df['model_type'].astype(str).str.strip().str.lower()

    # Links are edges, everything else is a node
    edges = (model_types == 'link').sum()
    nodes = (model_types != 'link').sum()

    print(f"\n=== DATAFRAME STATUS: {stage.upper()} ===")
    print(f"Nodes (Special features): {nodes} | Edges (Links): {edges}")
    print(f"Total Rows in DataFrame:  {len(df)}")
    print(f"====================================\n")


# ---------------------------------------------------------------
class BangladeshModel(Model):
    """
    The main (top-level) simulation model

    One tick represents one minute; this can be changed
    but the distance calculation need to be adapted accordingly

    Class Attributes:
    -----------------
    step_time: int
        step_time = 1 # 1 step is 1 min

    path_ids_dict: defaultdict
        Key: (origin, destination)
        Value: the shortest path (Infra component IDs) from an origin to a destination

        Only straight paths in the Demo are added into the dict;
        when there is a more complex network layout, the paths need to be managed differently

    sources: list
        all sources in the network

    sinks: list
        all sinks in the network

    """

    step_time = 1

    file_name = '../data/demo-4.csv'

    def __init__(self, seed=None, x_max=500, y_max=500, x_min=0, y_min=0, bridge_probabilities=None):

        self.schedule = BaseScheduler(self)
        self.running = True
        self.path_ids_dict = defaultdict(lambda: pd.Series())
        self.space = None
        self.sources = []
        self.sinks = []
        self.G = nx.Graph()  # the network graph, so we can do path modeling

        # Save the probabilities and initialize data collection ---
        self.bridge_probabilities = bridge_probabilities if bridge_probabilities is not None else {'A': 0, 'B': 0,
                                                                                                   'C': 0, 'D': 0}
        self.travel_times = []

        self.generate_model()

    def generate_model(self):
        df = pd.read_csv(self.file_name)

        # --- NEW: Print BEFORE status ---
        print_dataframe_status(df, stage="BEFORE OPTIMIZATION")

        df = optimize_network_data(df)

        # --- NEW: Print AFTER status ---
        print_dataframe_status(df, stage="AFTER OPTIMIZATION")

        roads = df['road'].unique().tolist()

        df_objects_all = []
        for road in roads:
            df_objects_on_road = df[df['road'] == road]
            if not df_objects_on_road.empty:
                df_objects_all.append(df_objects_on_road)

                # Oude pad-logica (nodig voor get_straight_route)
                path_ids = df_objects_on_road['id']
                path_ids.reset_index(inplace=True, drop=True)
                self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                self.path_ids_dict[path_ids[0], None] = path_ids
                path_ids = path_ids[::-1]
                path_ids.reset_index(inplace=True, drop=True)
                self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                self.path_ids_dict[path_ids[0], None] = path_ids

        df_combined = pd.concat(df_objects_all)
        y_min, y_max, x_min, x_max = set_lat_lon_bound(
            df_combined['lat'].min(), df_combined['lat'].max(),
            df_combined['lon'].min(), df_combined['lon'].max(), 0.05
        )
        self.space = ContinuousSpace(x_max, y_max, True, x_min, y_min)

        # --- STAP 1: BOUW DE WEGEN (De Schone Manier) ---
        for df_road in df_objects_all:
            prev_agent = None
            for _, row in df_road.iterrows():

                # 1. Forceer een schoon, normaal getal voor het ID
                agent_id = int(row['id'])

                # 2. Check of we deze punaise al op het bord hebben geprikt via NetworkX!
                if self.G.has_node(agent_id):
                    # Hij bestaat al! Pak de bestaande agent uit het netwerk
                    agent = self.G.nodes[agent_id]['agent_object']
                else:
                    # Hij bestaat nog niet. Maak een verse agent aan!
                    model_type = row['model_type'].strip()
                    name = str(row['name']).strip() if pd.notna(row['name']) else ""

                    if model_type == 'source':
                        agent = Source(agent_id, self, row['length'], name, row['road'])
                        self.sources.append(agent.unique_id)
                    elif model_type == 'sink':
                        agent = Sink(agent_id, self, row['length'], name, row['road'])
                        self.sinks.append(agent.unique_id)
                    elif model_type == 'sourcesink':
                        agent = SourceSink(agent_id, self, row['length'], name, row['road'])
                        self.sources.append(agent.unique_id)
                        self.sinks.append(agent.unique_id)
                    elif model_type == 'bridge':
                        agent = Bridge(agent_id, self, row['length'], name, row['road'], row['condition'])
                    elif model_type == 'link':
                        agent = Link(agent_id, self, row['length'], name, row['road'])
                    elif model_type == 'intersection':
                        agent = Intersection(agent_id, self, row['length'], name, row['road'])

                    # Omdat we ZEKER weten dat dit een nieuwe agent is,
                    # voegen we hem nu veilig toe aan de simulatie:
                    self.schedule.add(agent)
                    y, x = row['lat'], row['lon']
                    self.space.place_agent(agent, (x, y))
                    agent.pos = (x, y)

                    # Voeg de node toe aan het NetworkX netwerk
                    self.G.add_node(agent.unique_id, agent_object=agent)

                # 3. Trek ALTIJD het lijntje naar de vorige agent op deze weg
                if prev_agent is not None:
                    self.G.add_edge(prev_agent.unique_id, agent.unique_id, weight=row['length'])

                prev_agent = agent

        # --- STAP 2: DE ROBUUSTE EILAND-CONNECTOR ---
        import math
        islands = list(nx.connected_components(self.G))

        if len(islands) > 1:
            print(f"DEBUG: {len(islands)} eilanden gevonden. Bezig met koppelen...")
            islands.sort(key=len, reverse=True)
            main_island = set(islands[0])

            for small_island in islands[1:]:
                best_dist = float('inf')
                connection = None

                # Check ALLE nodes van het kleine eilandje tegen de hoofdweg
                # Dit garandeert dat we het raakpunt vinden!
                for small_node_id in small_island:
                    agent_s = self.G.nodes[small_node_id]['agent_object']

                    for main_node_id in main_island:
                        agent_m = self.G.nodes[main_node_id]['agent_object']
                        dist = math.hypot(agent_s.pos[0] - agent_m.pos[0], agent_s.pos[1] - agent_m.pos[1])

                        if dist < best_dist:
                            best_dist = dist
                            connection = (small_node_id, main_node_id)

                if connection:
                    self.G.add_edge(connection[0], connection[1], weight=best_dist * 111)
                    main_island.update(small_island)  # Nu hoort dit eiland bij het hoofdnetwerk

        print(f"\n=== NETWORKX STATUS REPORT ===")
        print(f"Nodes: {self.G.number_of_nodes()} | Edges: {self.G.number_of_edges()}")
        print(f"Eilanden: {len(list(nx.connected_components(self.G)))}")
        print(f"==============================\n")

    def get_route(self, source):
        """
        Calculates a random route using NetworkX and Dijkstra's algorithm.
        This replaces the old TODO and straight_route logic.
        """
        # 1. Vind haalbare bestemmingen (Sinks)
        reachable_sinks = []
        for sink in self.sinks:
            if sink != source and nx.has_path(self.G, source, sink):
                reachable_sinks.append(sink)

        # 2. If the node is completely isolated, stay parked.
        if not reachable_sinks:
            print(f"Node {source} is isolated. Truck will stay parked.")
            # We return a massive list so the truck never runs out of "steps" and crashes
            return [source] * 100000

            # 3. Pick a random sink ONLY from the reachable ones
        sink = self.random.choice(reachable_sinks)

        # 4. Check the cache
        if (source, sink) in self.path_ids_dict:
            return self.path_ids_dict[(source, sink)]

        # 5. Calculate the path and cache it
        path = nx.shortest_path(self.G, source=source, target=sink)
        self.path_ids_dict[(source, sink)] = path
        return path

    def get_route(self, source):
        return self.get_random_route(source)

# CAN BE DELETED
    # def get_straight_route(self, source):
    #     """
    #     pick up a straight route given an origin
    #     """
    #     return self.path_ids_dict[source, None]

    def step(self):
        """
        Advance the simulation by one step.
        """
        self.schedule.step()


import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


def visualize_network(model):
    """
    Plots the NetworkX graph. Nodes are colored by their road name,
    and the name of the road is plotted near the middle of its segment.
    """
    G = model.G
    pos = {}

    # 1. Identify all unique roads to create a color palette
    unique_roads = set()
    for node_id in G.nodes():
        agent = G.nodes[node_id]['agent_object']
        unique_roads.add(agent.road_name)

    unique_roads = list(unique_roads)

    # 2. Generate a distinct color for each road
    # Using the 'tab20' colormap which has 20 highly distinct colors
    colors = plt.cm.tab20(np.linspace(0, 1, len(unique_roads)))
    road_color_map = dict(zip(unique_roads, colors))

    node_colors = []
    # Dictionary to collect all positions per road so we can label them
    road_positions = {road: [] for road in unique_roads}

    # 3. Assign positions and colors
    for node_id in G.nodes():
        agent = G.nodes[node_id]['agent_object']
        pos[node_id] = agent.pos
        road = agent.road_name

        node_colors.append(road_color_map[road])
        road_positions[road].append(agent.pos)

    # 4. Set up the plot
    plt.figure(figsize=(14, 12))

    # Draw the network
    nx.draw(
        G,
        pos=pos,
        node_color=node_colors,
        node_size=35,
        edge_color='gray',
        with_labels=False,
        alpha=0.8
    )

    # 5. Plot the road names
    for road, positions in road_positions.items():
        # Skip labeling if the road name is somehow blank
        if not road or road == 'Unknown' or str(road) == 'nan':
            continue

        # Pick the middle node of this road to place the label
        # This ensures the text actually sits on the road line
        middle_index = len(positions) // 2
        label_pos = positions[middle_index]

        # Add the text label with a slight white background for readability
        plt.text(
            label_pos[0], label_pos[1],
            road,
            fontsize=9,
            fontweight='bold',
            ha='center',
            va='center',
            bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1.5)
        )

    plt.title("Bangladesh Model - Road Network", fontsize=16)
    plt.show()


# EOF -----------------------------------------------------------
if __name__ == "__main__":
    # 1. Maak een instantie van het model aan
    test_model = BangladeshModel()

    print("\nTest run succesvol afgerond!")

    # 2. Visualize the generated network
    print("Generating visualization...")
    visualize_network(test_model)