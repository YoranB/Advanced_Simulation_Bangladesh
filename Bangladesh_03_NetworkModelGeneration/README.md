
# EPA133a Assignment 3: Advanced Simulation Bangladesh
**Network Model Generation & Simulation Pipeline**

This repository contains the data preprocessing, the agent-based simulation model, and the experimental setup for the expanded Bangladesh transport network. The goal of this project is to load the complex infrastructure network into a MESA model to simulate, route, and analyze transport flows and vulnerabilities (such as failing bridges) across a larger scale.

## 1. Project Overview & Methodology

The pipeline takes the cleaned data and transforms it into a functioning simulation model where vehicles navigate the broader road network.

**Exploration & Preprocessing (`notebooks/` & `preprocessing/`)**
Before the data enters the simulation, it undergoes extensive preparation. We expand upon the previous assignment by constructing a more complex interconnected road network, saving the final output as a comprehensive network CSV. 

**MESA Simulation Model (`model/`)**
* **Network Generation:** The main model (`model.py`) reads the processed network files (e.g., `A3_network_roads.csv`) and automatically builds a continuous spatial network. Sources and Sinks are assigned to facilitate vehicle routing across multiple pathways.
* **Agent-Based Components:** The infrastructure consists of various agent classes (`components.py`), including bridges (`Bridge`) and road segments (`Link`). Bridges have specific failure probabilities based on their structural condition.
* **Continuous Space:** Utilizes a custom module (`ContinuousSpace`) to simulate objects and transport with fluid geographic coordinates (latitude and longitude) on an HTML5 canvas.

**Experimentation (`data/experiment/`)**
* **Scenario Testing:** Simulations can be run with different failure probabilities for bridges (defined in `scenario0.csv` through `scenario4.csv`) to evaluate the resilience and routing alternatives of the transport network.

---

## 2. Project Structure

The repository structure follows a logical separation between network data, the MESA simulation model, and experimental scenarios.

```text
Bangladesh_03_NetworkModelGeneration/
├── data/
│   ├── data_cleaned_by_lecturer/  # Validation data provided by the lecturer (baseline)
│   │   ├── _roads3.csv
│   │   └── BMMS_overview.csv
│   ├── data_processed/            # Output of the preprocessing, ready for the simulation
│   │   ├── A3_network_roads.csv
│   │   └── Assignment_3_Network_Filtered.png
│   ├── data_use/                  # Shapefiles and demo datasets for testing purposes
│   │   ├── demo-4*.csv            # Various demo network configurations
│   │   └── roads.* # Road shapefiles (.shp, .dbf, .prj, .shx, .cpg)
│   └── experiment/                # Scenario configurations for batch runs
│       └── scenario0.csv to scenario4.csv
├── img/                           # Output visualisations of the network structures
│   ├── N1.png
│   ├── N1N2.png
│   └── demo-4.png
├── notebooks/                     # Jupyter notebooks for network EDA
│   └── EDA.ipynb
├── preprocessing/                 # Scripts for generating the full routing network
│   └── create_roads.py
├── model/                         # The core MESA simulation environment
│   ├── ContinuousSpace/           # Visualization module for continuous coordinates
│   ├── components.py              # Definitions of Source, Sink, Bridge, and Link agents
│   ├── model.py                   # Main MESA model (BangladeshModel)
│   ├── model_run.py               # Script for batch runs without visualization
│   ├── model_viz.py               # Script to start the server with visualization
│   └── bonus3                     # Bonus assignment implementation/data
└── README.md                      # Project documentation
```

---

## 3. Usage & Execution

Follow these steps to run the data preparation and start the MESA simulation:

**1. Install Dependencies**
Ensure you are using a virtual environment (e.g., Python 3.11) and install the required packages (such as `pandas` and `Mesa`). If you haven't already, install them via the root `requirements.txt`:

```bash
pip install -r requirements.txt
```

**2. Data Preprocessing**
Not strictly necessary as the dataset is already generated in `data/data_processed/`, but to rebuild the network from scratch:

```bash
python preprocessing/create_roads.py
```

*(This will output the resulting `A3_network_roads.csv` file into the `data/data_processed/` folder)*

**3. Run the Simulation (With Visualization)**
Navigate to the `model/` directory and start the visualization server. This opens a local HTML5 canvas in your web browser where you can see the expansive infrastructure and agents navigating routes:

```bash
cd model
python model_viz.py
```

**4. Run Batch Experiments (Without Visualization)**
To test the network's performance under various scenarios (e.g., measuring travel times, alternative routing, and delays when bridges fail), use the batch run script. This reads configurations from the `data/experiment/` folder:

```bash
cd model
python model_run.py
```
```