# EPA133a Assignment 4: Advanced Simulation Bangladesh
**Network Analysis & Vulnerability Assessment**

This repository contains the data preprocessing, the agent-based simulation model, and the extensive analysis notebooks for the Bangladesh transport network. The goal of this project is to integrate real-world traffic volumes (AADT) into the MESA model, simulate multiple flood scenarios, and critically assess the resilience, criticality, and vulnerability of the country's transport infrastructure.

## 1. Project Overview & Methodology

The pipeline takes raw empirical traffic data, processes it for the simulation, runs targeted flood scenarios, and uses the resulting output to identify the most critical and vulnerable links in the network.

**Exploration & Preprocessing (`preprocessing/`)**
Before the simulation is executed, real-world traffic data must be prepared. We parse hundreds of raw HTML traffic reports to extract the Annual Average Daily Traffic (AADT) for different vehicle types, generating a structured dataset (`traffic_aadt.csv`) used to calibrate the transport model's vehicle generation rates.

**MESA Simulation Model (`model/`)**
* **Traffic Integration:** The main model (`model.py`) is enhanced to utilize the parsed AADT data, generating realistic traffic loads (truck flows) across the network.
* **Agent-Based Components:** The infrastructure classes (`components.py`) manage routing and driving behaviors while keeping track of bridge states and traversal times.
* **Batch Logging:** The batch runner (`model_run.py`) has been expanded to output highly detailed metrics per scenario, including infrastructure state logs (`_infra.csv`) and system-level performance over time (`_timeseries.csv`).

**Analysis & Assessment (`analysis/`)**
* **Experiment Evaluation:** Targeted Jupyter notebooks load the simulation outputs to evaluate the impact of different flood scenarios on network performance.
* **Criticality & Vulnerability:** Computes metrics to determine which bridges are the most *critical* (highest impact when failed) and most *vulnerable* (highest likelihood of failure coupled with impact), generating comprehensive vulnerability matrices and geographical maps.

---

## 2. Project Structure

The repository structure follows a logical separation between empirical data extraction, the MESA simulation model, and post-simulation analysis.

```text
Bangladesh_04_NetworkAnalysis/
├── analysis/                      # Notebooks for post-simulation analysis
│   ├── criticality_vulnerability.ipynb # Computes bridge criticality and vulnerability
│   ├── flood_experiment_results.ipynb  # Analyzes timeseries and scenario impacts
│   └── visualise.ipynb                 # Generates geo-spatial maps of network flows
├── data/
│   ├── data_processed/            # Output of preprocessing and generated visualizations
│   │   ├── A3_network_roads.csv
│   │   ├── bridge_analysis.csv
│   │   ├── traffic_aadt.csv       # Extracted empirical traffic flows
│   │   └── *.png                  # Flow maps, criticality maps, flood charts
│   ├── data_raw/                  # Raw input datasets and HTML traffic reports
│   │   ├── BMMS_overview.csv
│   │   └── traffic/               # Raw HTML reports for traffic volumes (N, R, Z routes)
│   └── experiment/                # Scenario configurations and simulation outputs
│       ├── scenario0.csv to scenario4.csv
│       ├── scenario*_infra.csv    # Bridge state outputs per scenario
│       └── scenario*_timeseries.csv # System-level performance over time
├── model/                         # The core MESA simulation environment
│   ├── ContinuousSpace/           # Visualization module for continuous coordinates
│   ├── components.py              # Definitions of Source, Sink, Bridge, and Link agents
│   ├── model.py                   # Main MESA model adapted for empirical flows
│   ├── model_run.py               # Script for batch runs generating experiment data
│   └── model_viz.py               # Script to start the server with visualization
├── preprocessing/                 # Scripts for extracting empirical data
│   └── parse_traffic.ipynb        # Extracts AADT from raw HTML traffic reports
└── README.md                      # Project documentation
```

---

## 3. Usage & Execution

Follow these steps to run the data preparation, execute the simulation, and perform the vulnerability analysis:

**1. Install Dependencies**
Ensure you are using a virtual environment (e.g., Python 3.11) and install the required packages (such as `pandas`, `Mesa`, `geopandas`, and `matplotlib`). If you haven't already, install them via the root `requirements.txt`:

```bash
pip install -r requirements.txt
```

**2. Data Preprocessing (Traffic Parsing)**
If you need to rebuild the AADT dataset from the raw HTML files, open and run the Jupyter notebook located in the preprocessing directory:

* Open `preprocessing/parse_traffic.ipynb` and execute all cells to generate `data/data_processed/traffic_aadt.csv`.

**3. Run Batch Experiments (Without Visualization)**
To test the network's performance under various flood scenarios and generate the necessary output files for the analysis notebooks, use the batch run script:

```bash
cd model
python model_run.py
```
*(This will read the configurations from `data/experiment/` and output the corresponding `_timeseries.csv` and `_infra.csv` results)*

**4. Run the Simulation (With Visualization)**
To visually inspect the real-time traffic flows and bridge states on the interactive HTML5 canvas:

```bash
cd model
python model_viz.py
```

**5. Post-Simulation Analysis**
Once the experiments have finished running, navigate to the `analysis/` folder and open the Jupyter notebooks (e.g., `criticality_vulnerability.ipynb` and `flood_experiment_results.ipynb`) to explore the generated insights, view the vulnerability matrices, and analyze the flood impacts.