
# EPA133a Assignment 2: Advanced Simulation Bangladesh
**Model Generation & Simulation Pipeline**

This repository contains the data preprocessing, the agent-based simulation model, and the experimental setup for the Bangladesh transport network. The goal of this project is to load the cleaned infrastructure network from the previous assignment into a MESA model to simulate and analyze transport flows and vulnerabilities (such as failing bridges).

## 1. Project Overview & Methodology

The pipeline takes the cleaned data and transforms it into a functioning simulation model where vehicles navigate the network.

**Exploration & Preprocessing (`Notebooks/` & `preprocessing/`)**
Before the data enters the simulation, it undergoes further preparation. We filter the massive network down to the specific road relevant for this part which is the N1 road.

**MESA Simulation Model (`model/`)**
* **Network Generation:** The main model (`model.py`) reads the filtered CSV files (e.g., `N1_roads.csv`) and automatically builds a continuous spatial network. The first and last components on a route are automatically assigned as `Source` and `Sink`, respectively.
* **Agent-Based Components:** The infrastructure consists of various agent classes (`components.py`), including bridges (`Bridge`) and road segments (`Link`). Bridges have specific failure probabilities based on their condition.
* **Continuous Space:** Utilizes a custom module (`ContinuousSpace`) to simulate objects and transport with fluid geographic coordinates (latitude and longitude) on an HTML5 canvas.

**Experimentation (`experiment/`)**
* **Scenario Testing:** Simulations can be run with different failure probabilities for bridges (defined in `scenario0.csv` through `scenario8.csv`) to evaluate the robustness of the supply chain.

---

## 2. Project Structure

The repository structure follows a logical separation between network data, the MESA simulation model, and experimental scenarios.

```text
Bangladesh_02_ModelGeneration/
├── data_cleaned_by_lecturer/  # Validation data provided by the lecturer (baseline)
│   ├── _roads3.csv
│   └── BMMS_overview.csv
├── data_processed/            # Output of the preprocessing, ready for the simulation
│   └── N1_roads.csv
├── data_example/              # Demo datasets for testing purposes
├── experiment/                # Scenario configurations for batch runs
│   ├── scenario0.csv to scenario8.csv
│   └── bonus_top_5_bridges.csv
├── Notebooks/                 # Jupyter notebooks for network EDA
│   ├── EDA_notebook_preprocess.ipynb
│   └── EDA_notebook_preprocess_Leo.ipynb
├── preprocessing/             # Scripts for N1 road cleaing
│   └── Get_N1_Road_Leo.py
├── model/                     # The core MESA simulation environment
│   ├── ContinuousSpace/       # Visualization module for continuous coordinates
│   ├── components.py          # Definitions of Source, Sink, Bridge, and Link agents
│   ├── model.py               # Main MESA model (BangladeshModel)
│   ├── model_run.py           # Script for batch runs without visualization
│   ├── A2_model_viz.py        # Script to start the server with visualization
│   └── bonus_analysis.py      # Bonus assignment
├── README.md                  # Project documentation
└── requirements.txt           # Python dependencies

```

---

## 3. Usage & Execution

Follow these steps to run the data preparation and start the MESA simulation:

**1. Install Dependencies**
Ensure you are using a virtual environment (e.g., Python 3.11) and install the required packages (such as `pandas` and `Mesa`):

```bash
pip install -r requirements.txt

```

**2. Data Preprocessing**
Not nececary as the dataset is already in data_processed:

```bash
python preprocessing/Get_N1_Road_Leo.py

```

*(This will output the resulting `N1_roads.csv` file into the `data_processed/` folder)*

**3. Run the Simulation (With Visualization)**
Navigate to the `model/` directory and start the visualization server. This opens a local HTML5 canvas in your web browser where you can see the infrastructure and agents:

```bash
cd model
python A2_model_viz.py

```

**4. Run Batch Experiments (Without Visualization)**
To test the network's performance under various scenarios (e.g., measuring travel times when bridges fail), use the batch run script. This reads configurations from the `experiment/` folder:

```bash
cd model
python model_run.py

```
