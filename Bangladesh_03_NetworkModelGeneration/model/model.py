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
        self.G = nx.Graph() # the network graph, so we can do path modeling

        self.generate_model()

    def generate_model(self):
        df = pd.read_csv(self.file_name)
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
                    main_island.update(small_island) # Nu hoort dit eiland bij het hoofdnetwerk

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

        # 2. Beveiliging: als de Source nergens aan vast zit, blijf dan stilstaan
        if not reachable_sinks:
            print(f"Waarschuwing: Node {source} is isolated. Truck will stay parked.")
            return [source]

        # 3. Kies een willekeurige bereikbare bestemming
        sink = self.random.choice(reachable_sinks)

        # 4. Check de cache (Snelheid!)
        # Let op: we gebruiken f-strings als key, zodat we niet per ongeluk 
        # botsen met de oude Pandas logica van de docent!
        cache_key = f"route_{source}_{sink}"
        if cache_key in self.path_ids_dict:
            return self.path_ids_dict[cache_key]

        # 5. Bereken de route in meters (weight='weight')
        path = nx.shortest_path(self.G, source=source, target=sink, weight='weight')
        
        # Sla de schone Python-lijst op in de cache
        self.path_ids_dict[cache_key] = path
        return path

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