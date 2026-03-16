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
            prev_agent = None  # We keep track of what the previour agent was on this road so we can put a line in the netwerk
            for _, row in df_road.iterrows():
                
                # 1. Forse clean agend ID
                agent_id = int(row['id']) 
                
                # 2. check if we already put it on network
                if self.G.has_node(agent_id):
                    # If already exists we just get the agent object from the node and move on (we only want to create one agent per unique ID, even if it appears on multiple roads due to intersections)
                    agent = self.G.nodes[agent_id]['agent_object']
                else:
                    # It does not exist yet so create agents according to model_type like teacher did
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
                        agent = Bridge(agent_id, self, row['length'], name, row['road'], condition =row['condition']) 
                    elif model_type == 'link':
                        agent = Link(agent_id, self, row['length'], name, row['road'])
                    elif model_type == 'intersection':
                        agent = Intersection(agent_id, self, row['length'], name, row['road'])

                    # Omdat we ZEKER weten dat dit een nieuwe agent is, 
                    # voegen we hem nu veilig toe aan de simulatie:
                    y = row['lat']
                    x = row['lon']
                    self.space.place_agent(agent, (x, y))
                    agent.pos = (x, y) 

                    # add node to the NetworkX netwerk
                    self.G.add_node(agent.unique_id, agent_object=agent) 

                # always add an edge to the previous agent on the same road, if it exists (So also at intersection ))
                if prev_agent is not None: # We check this after the potential creation of the agent, because we want to connect the intersection node to the road nodes, even if the intersection node was created in a previous loop iteration
                    self.G.add_edge(prev_agent.unique_id, agent.unique_id, weight=row['length'])
                
                prev_agent = agent

        #island connector #WHY DO WE DO THIS /NEED THIS???
        import math
        islands = list(nx.connected_components(self.G)) # We check how many islands we have in the netwerk, and if there are more than 1, we connect them by adding edges between the closest nodes of the different islands. This is a simple heuristic to ensure that all nodes are reachable, but it can be improved by considering the actual geography and road layout.
        
        if len(islands) > 1: # Only do this if we actually have multiple islands, otherwise we might mess up the network unnecessarily
            islands.sort(key=len, reverse=True)
            main_island = set(islands[0])  # We take the largest island as the main one, and connect all smaller islands to it. This is a simple heuristic, but it works well in practice because usually the largest island contains the main road network and the smaller islands are just disconnected nodes or small clusters of nodes.

            for small_island in islands[1:]:# We loop over the smaller islands, and for each of them we find the closest pair of nodes between the small island and the main island, and we add an edge between them. This way we ensure that all nodes are reachable from each other, even if they were originally disconnected due to missing data or errors in the input.
                best_dist = float('inf')# We initialize the best distance to infinity, so any real distance will be smaller. We will update this variable whenever we find a closer pair of nodes between the small island and the main island.
                connection = None
                
                # Check ALL nodes in the small island against ALL nodes in the main island, and find the closest pair. This is a brute-force approach, but it works well for small islands and ensures that we find the best possible connection. We calculate the distance using the Euclidean formula, and we multiply by 111 to convert from degrees to kilometers (assuming a rough average latitude of Bangladesh). This way we can add a realistic weight to the edge that reflects the actual distance between the nodes.
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
                    main_island.update(small_island) # Nu hoort dit eiland bij het hoofdnetwerk


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
#if __name__ == "__main__":
    # 1. Maak een instantie van het model aan
    # We geven even een dummy bestand mee (zorg dat de naam klopt met jouw CSV)
   # test_model = BangladeshModel()
    
    # Zodra dit model wordt aangemaakt, roept de __init__ automatisch 
    # generate_model() aan, en dán pas zie je jouw prints!
   # print("\nTest run succesvol afgerond!")