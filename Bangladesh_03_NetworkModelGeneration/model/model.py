from mesa import Model
from mesa.time import BaseScheduler
from mesa.space import ContinuousSpace
from components import Source, Sink, SourceSink, Bridge, Link, Intersection
import pandas as pd
from collections import defaultdict
import networkx as nx 
import matplotlib.pyplot as plt

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
    #added the bridge probabilities here in init again for the experiments

    def __init__(self, seed=None, x_max=500, y_max=500, x_min=0, y_min=0,  bridge_probabilities=None):

        self.schedule = BaseScheduler(self)
        self.running = True
        self.path_ids_dict = defaultdict(lambda: pd.Series())
        self.space = None
        self.sources = []
        self.sinks = [] 
        self.G = nx.Graph() # the network graph, so we can do path modeling



        # Store the probabilities for the current scenario (defaults to Scenario 0)
        if bridge_probabilities is None:
            self.bridge_probabilities = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'D': 0.0}
        else:
            self.bridge_probabilities = bridge_probabilities 

        self.travel_times = []

        self.generate_model()

    def generate_model(self): 
        """
        generate the simulation model according to the csv file component information

        Warning: the labels are the same as the csv column labels
        """
        df = pd.read_csv('../data/demo-4.csv')
        # a list of names of roads to be generated
        # TODO You can also read in the road column to generate this list automatically 
        #we changed this, so take all roads 

        #did this it now takes road unique to list
        roads = df['road'].unique().tolist()

        df_objects_all = []
        for road in roads: 
            # Select all the objects on a particular road in the original order as in the cvs
            df_objects_on_road = df[df['road'] == road]

            if not df_objects_on_road.empty:
                df_objects_all.append(df_objects_on_road)
                
                """
                Set the path 
                1. get the serie of object IDs on a given road in the cvs in the original order
                2. add the (straight) path to the path_ids_dict
                3. put the path in reversed order and reindex
                4. add the path to the path_ids_dict so that the vehicles can drive backwards too
                """
                
                path_ids = df_objects_on_road['id']
                path_ids.reset_index(inplace=True, drop=True)
                self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                self.path_ids_dict[path_ids[0], None] = path_ids
                path_ids = path_ids[::-1]
                path_ids.reset_index(inplace=True, drop=True)
                self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                self.path_ids_dict[path_ids[0], None] = path_ids 



        
        # put back to df with selected roads so that min and max and be easily calculated
        df_combined = pd.concat(df_objects_all)
        y_min, y_max, x_min, x_max = set_lat_lon_bound(
            df_combined['lat'].min(),
            df_combined['lat'].max(),
            df_combined['lon'].min(), 
            df_combined['lon'].max(), 0.05 
        )
        # ContinuousSpace from the Mesa package;
        # not to be confused with the SimpleContinuousModule visualization
        self.space = ContinuousSpace(x_max, y_max, True, x_min, y_min)
        
#:This was changed: building the roads and the network in one go, instead of building the roads first and then trying to connect them with a separate loop. This way we can use NetworkX to check if a node already exists before creating it, which is crucial for correctly handling intersections and avoiding duplicates.
        for df_road in df_objects_all:
            prev_agent = None  
            for _, row in df_road.iterrows():
                agent_id = int(row['id']) 
                
                # Check of agent al bestaat (cruciaal voor kruispunten!)
                if self.G.has_node(agent_id):
                    agent = self.G.nodes[agent_id]['agent_object']
                else:
                    model_type = row['model_type'].strip()
                    name = str(row['name']).strip() if pd.notna(row['name']) else ""

                    # Maak de juiste agent aan
                    if model_type == 'sourcesink':
                        agent = SourceSink(agent_id, self, row['length'], name, row['road'])
                        self.sources.append(agent.unique_id)
                        self.sinks.append(agent.unique_id)
                    elif model_type == 'source':
                        agent = Source(agent_id, self, row['length'], name, row['road'])
                        self.sources.append(agent.unique_id)
                    elif model_type == 'sink':
                        agent = Sink(agent_id, self, row['length'], name, row['road'])
                        self.sinks.append(agent.unique_id)
                    elif model_type == 'bridge':
                        agent = Bridge(agent_id, self, row['length'], name, row['road'], condition=row['condition']) 
                    elif model_type == 'intersection':
                        agent = Intersection(agent_id, self, row['length'], name, row['road'])
                    else: # link
                        agent = Link(agent_id, self, row['length'], name, row['road'])

                    # Voeg toe aan Mesa
                    self.schedule.add(agent)
                    self.space.place_agent(agent, (row['lon'], row['lat']))
                    agent.pos = (row['lon'], row['lat']) 

                    # Voeg node toe aan NetworkX
                    self.G.add_node(agent.unique_id, agent_object=agent, pos=(row['lon'], row['lat'])) 

                # Maak de verbinding (edge) met het vorige punt op de weg
                if prev_agent is not None:
                    # Gebruik de lengte van de huidige row als gewicht voor Dijkstra
                    self.G.add_edge(prev_agent.unique_id, agent.unique_id, weight=row['length'])
                
                prev_agent = agent

        # --- NETWORK CHECK & VISUALISATIE (NA de loops!) ---
        self.check_network_connectivity()

    def check_network_connectivity(self):
        # --- NETWORK DIAGNOSTICS ---
        islands = list(nx.connected_components(self.G))
        print(f"Netwerk analyse: {len(islands)} eiland(en) gevonden.")

        # Kleuren voor de eilanden (Eiland 1 = Blauw, Eiland 2 = Rood)
        colors = ['skyblue', 'red', 'green', 'orange', 'purple']
        node_color_map = {}
        for i, island in enumerate(islands):
            color = colors[i % len(colors)]
            for node in island:
                node_color_map[node] = color

        # Haal posities en kleuren op
        pos = nx.get_node_attributes(self.G, 'pos')
        node_colors = [node_color_map[n] for n in self.G.nodes()]

        plt.figure(figsize=(12, 8))
        
        # 1. Teken de verbindingen (edges) heel licht
        nx.draw_networkx_edges(self.G, pos, alpha=0.3, edge_color='gray')
        
        # 2. Teken de nodes zonder labels en heel klein
        nx.draw_networkx_nodes(self.G, pos, 
                               node_size=10, 
                               node_color=node_colors,
                               alpha=0.8)

        plt.title(f"Netwerk Connectiviteit: {len(islands)} eilanden")
        plt.show()

    

    def get_random_route(self, source):
        """
        pick up a random route given an origin
        """
        while True:
            # different source and sink
            sink = self.random.choice(self.sinks)
            if sink is not source:
                break
        return self.path_ids_dict[source, sink]
      
    def get_route(self, source):
        """
        Calculates a random route using NetworkX and Dijkstra's algorithm.
        """
        # 1 find all reachable sinks from the source (we only want to pick a sink that is actually reachable, otherwise the truck will get stuck and that's no fun for anyone)
        reachable_sinks = []
        for sink in self.sinks:
            if sink != source and nx.has_path(self.G, source, sink):
                reachable_sinks.append(sink)

        # 2 If the node is completely isolated, stay parked. We return a list with only the source, so that the truck will stay on its place and not move at all. We also print a warning in the console, so we can keep track of how many nodes are isolated and maybe investigate why.
        if not reachable_sinks:
            print(f"Waarschuwing: Node {source} is isolated. Truck will stay parked.")
            return [source]

        # 3 Pick a random sink ONLY from the reachable ones
        sink = self.random.choice(reachable_sinks)

        # 4. Check de cache 
        # We check if we already calculated the route between this source and sink before, and if so, we return the cached route. This way we avoid redundant calculations and improve performance, especially if there are many trucks that need to calculate routes between the same pairs of nodes.
        cache_key = f"route_{source}_{sink}"
        if cache_key in self.path_ids_dict:
            return self.path_ids_dict[cache_key]

        # 5 Calculate the route using Dijkstra's algorithm, and we use the edge weights (lengths) to find the shortest path. This way we ensure that the trucks take the most efficient route between their origin and destination, which is more realistic and leads to more interesting dynamics in the simulation.
        path = nx.shortest_path(self.G, source=source, target=sink, weight='weight')
        
        # Save the calculated path in the cache, so we can reuse it later if needed. We use a unique key for each source-sink pair, so we can easily retrieve the correct path when needed.
        self.path_ids_dict[cache_key] = path
        return path 
    
    def get_straight_route(self, source):
        """
        pick up a straight route given an origin
        """
        return self.path_ids_dict[source, None]

    def step(self):
        """
        Advance the simulation by one step.
        """
        self.schedule.step()

# EOF -----------------------------------------------------------
if __name__ == "__main__":
    # 1. Maak een instantie van het model aan
    # We geven even een dummy bestand mee (zorg dat de naam klopt met jouw CSV)
    test_model = BangladeshModel()
    
    # Zodra dit model wordt aangemaakt, roept de __init__ automatisch 
    # generate_model() aan, en dán pas zie je jouw prints!
    print("\nTest run succesvol afgerond!")