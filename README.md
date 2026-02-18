
# EPA133a Assignment 1: Advanced Simulation Bangladesh
**Data Quality & Preprocessing Pipeline**

This repository contains the data cleaning, interpolation, and validation pipeline for the Bangladesh road and bridge network. The goal of this project is to process raw, inconsistent infrastructure data into a robust, strictly formatted dataset.

## 1. Project Overview & Methodology

The pipeline processes raw `csv` and `xlsx` files to resolve geospatial inaccuracies, missing coordinates, and formatting inconsistencies. 

**Exploration & Prototyping (`notebooks/`)**
Initial data exploration and algorithm testing were conducted within Jupyter Notebooks. Before processing the entire dataset, we prototyped our cleaning and interpolation algorithms on a single road to visually verify that our logic worked.  Once the outlier detection and coordinate snapping were successfully validated on this micro-level, the code was scaled and modularized into the Python scripts described below.

**Road Network Processing (`src/clean_roads.py`)**
* **Outlier Detection:** Uses a 5-window rolling median and Haversine distance calculations to detect coordinate jumps greater than 10km.
* **Correction & Interpolation:** Snaps severe outliers back to the rolling median and linearly interpolates remaining small gaps to ensure strict monotonic chainage.

**Bridge Network Processing (`src/clean_bridges.py`)**
* **Hierarchical Repair Algorithm:** Resolves missing or broken bridge coordinates using a prioritized logic system:
    1.  *Exact Match:* Maps to Location Reference Points (LRPs) on the validated road network.
    2.  *Chainage Interpolation:* Estimates coordinates using valid chainage (km) along the cleaned road paths. 
    3.  *Typo Correction:* Identifies and resolves human-entry factor-10 scale errors (e.g., meters inputted as kilometers).
    4.  *Terminus Snapping:* Bridges that slightly overshoot road bounds are snapped to the road terminus to maintain simulation connectivity.

---

## 2. Project Structure

The repository follows a standard data science project hierarchy to separate raw data, source code, and analysis notebooks.

```text
EPA133a-Gxx-Assignment1/
├── data/
│   ├── raw/                 # Immutable original data files
│   │   ├── _roads.tsv
│   │   ├── BMMS_overview.xlsx
│   │   └── Roads_InfoAboutEachLRP.csv
│   └── processed/           # Pipeline outputs (DO NOT EDIT MANUALLY)
│       ├── _roads3.csv
│       ├── outliers_report.csv
│       └── BMMS_overview_CLEANED.xlsx
├── notebooks/               # Jupyter notebooks for EDA and validation
│   ├── 01_eda_roads.ipynb  
│   ├── 02_eda_bridges.ipynb 
│   └── 03_validation.ipynb  
├── src/                     # Core pipeline modules
│   ├── __init__.py
│   ├── clean_roads.py       # Road filtering and interpolation logic
│   ├── clean_bridges.py     # Bridge location repair logic
│   └── utils.py             # Geospatial math functions (e.g., Haversine)
├── main.py                  # Primary execution script
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
└── .gitignore              

```

---

## 3. Usage & Execution

To execute the data cleaning pipeline and generate the files required for the Java simulation:

**1. Install Dependencies**
Ensure you have Python 3.8+ installed, then run:

```bash
pip install -r requirements.txt

```

**2. Run the Pipeline**
Execute the main script from the root directory. This will process the raw data and populate the `data/processed/` folder.

```bash
python main.py

```

**3. Outputs Generated**

* `_roads3.csv`: The cleaned, interpolated road network.
* `BMMS_overview_CLEANED.xlsx`: The repaired bridge network, formatted strictly for the Java model.
* `outliers_report.csv`: A diagnostic report of all corrected road outliers.

### To run the java visualisation go to data -> Processed and copy the _roads3.csv and BMMS_overview_CLEANED.xlsx
