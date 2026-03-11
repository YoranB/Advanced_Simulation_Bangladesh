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

    def __init__(self, seed=None, x_max=500, y_max=500, x_min=0, y_min=0):

        self.schedule = BaseScheduler(self)
        self.running = True
        self.path_ids_dict = defaultdict(lambda: pd.Series())
        self.space = None
        self.sources = []
        self.sinks = []

        self.G = nx.Graph()

        self.generate_model()

    def generate_model(self):
        """
        generate the simulation model according to the csv file component information

        Warning: the labels are the same as the csv column labels
        """

        df = pd.read_csv(self.file_name)

        # a list of names of roads to be generated
        # TODO You can also read in the road column to generate this list automatically 
        #we changed this, so take all roads
        roads = df['road'].unique().tolist()

        df_objects_all = []
        for road in roads:
            # Select all the objects on a particular road in the original order as in the cvs
            df_objects_on_road = df[df['road'] == road]

            if not df_objects_on_road.empty:
                df_objects_all.append(df_objects_on_road)

                # --- NETWORKX: Build the road ---
                # Get the sequence of IDs on this road as a list
                path_ids = df_objects_on_road['id'].tolist()

                # Link each node to the next one to form a continuous road
                for i in range(len(path_ids) - 1):
                    # We add an edge between component i and component i+1
                    self.G.add_edge(path_ids[i], path_ids[i + 1])

                # """
                # Set the path
                # 1. get the serie of object IDs on a given road in the cvs in the original order
                # 2. add the (straight) path to the path_ids_dict
                # 3. put the path in reversed order and reindex
                # 4. add the path to the path_ids_dict so that the vehicles can drive backwards too
                # """
                # path_ids = df_objects_on_road['id']
                # path_ids.reset_index(inplace=True, drop=True)
                # self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                # self.path_ids_dict[path_ids[0], None] = path_ids
                # path_ids = path_ids[::-1]
                # path_ids.reset_index(inplace=True, drop=True)
                # self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                # self.path_ids_dict[path_ids[0], None] = path_ids

        # put back to df with selected roads so that min and max and be easily calculated
        df = pd.concat(df_objects_all)
        y_min, y_max, x_min, x_max = set_lat_lon_bound(
            df['lat'].min(),
            df['lat'].max(),
            df['lon'].min(),
            df['lon'].max(),
            0.05
        )

        # --- NETWORKX: Connect the intersections ---
        # --- NETWORKX: The Ultimate Island Connector ---
        import math

        # 1. Ask NetworkX to find all the disconnected pieces of the map
        islands = list(nx.connected_components(self.G))

        if len(islands) > 1:
            print(f"\n--- DEBUG: Graph is broken into {len(islands)} separate islands. Stitching them together! ---")

            # Sort them by size. The biggest one is our main N1/N2 highway.
            islands.sort(key=len, reverse=True)
            main_island = set(islands[0])

            # 2. For every smaller disconnected side road...
            for small_island in islands[1:]:
                island_nodes = list(small_island)

                # Let's take one end of the disconnected road (the first node)
                floating_node = island_nodes[0]
                row1 = df[df['id'] == floating_node].iloc[0]
                lat1, lon1 = row1['lat'], row1['lon']
                road_name = row1['road']

                best_dist = float('inf')
                best_main_node = None

                # 3. Find the absolute closest node on the main highway
                for main_node in main_island:
                    row2 = df[df['id'] == main_node].iloc[0]
                    # Calculate distance
                    dist = math.hypot(lat1 - row2['lat'], lon1 - row2['lon'])

                    if dist < best_dist:
                        best_dist = dist
                        best_main_node = main_node

                # 4. Glue them together!
                self.G.add_edge(floating_node, best_main_node)
                # Add the new node to the main island so subsequent roads can connect to it too
                main_island.add(floating_node)

                print(f"SUCCESS: Glued {road_name} (Node {floating_node}) to main network (Node {best_main_node})")
        else:
            print("\n--- DEBUG: Network is already perfectly connected! ---")

        # ContinuousSpace from the Mesa package;
        # not to be confused with the SimpleContinuousModule visualization
        self.space = ContinuousSpace(x_max, y_max, True, x_min, y_min)

        for df in df_objects_all:
            for _, row in df.iterrows():  # index, row in ...

                # create agents according to model_type
                model_type = row['model_type'].strip()
                agent = None

                name = row['name']
                if pd.isna(name):
                    name = ""
                else:
                    name = name.strip()

                if model_type == 'source':
                    agent = Source(row['id'], self, row['length'], name, row['road'])
                    self.sources.append(agent.unique_id)
                elif model_type == 'sink':
                    agent = Sink(row['id'], self, row['length'], name, row['road'])
                    self.sinks.append(agent.unique_id)
                elif model_type == 'sourcesink':
                    agent = SourceSink(row['id'], self, row['length'], name, row['road'])
                    self.sources.append(agent.unique_id)
                    self.sinks.append(agent.unique_id)
                elif model_type == 'bridge':
                    agent = Bridge(row['id'], self, row['length'], name, row['road'], row['condition'])
                elif model_type == 'link':
                    agent = Link(row['id'], self, row['length'], name, row['road'])
                elif model_type == 'intersection':
                    if not row['id'] in self.schedule._agents:
                        agent = Intersection(row['id'], self, row['length'], name, row['road'])

                if agent:
                    self.schedule.add(agent)
                    y = row['lat']
                    x = row['lon']
                    self.space.place_agent(agent, (x, y))
                    agent.pos = (x, y)

    def get_random_route(self, source):
        # 1. Ask NetworkX to find sinks that are ACTUALLY connected!
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

# EOF -----------------------------------------------------------
