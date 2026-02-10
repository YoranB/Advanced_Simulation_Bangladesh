# Advanced_Simulation_Bangladesh

# EPA133a Assignment 1: Data Quality Project

## 1. Project Structure

We will follow a standard data science project structure to keep our work organized and avoid merge conflicts.

```text
EPA133a-Gxx-Assignment1/
├── data/
│   ├── raw/                 # PUT ORIGINAL FILES HERE (Do not edit these!)
│   │   ├── _roads.tsv
│   │   ├── BMMS_overview.xlsx
│   │   └── Roads_InfoAboutEachLRP.csv
│   └── processed/           # OUTPUT FILES GO HERE
│       ├── _roads3.csv
│       └── BMMS_overview.csv
├── notebooks/               # For experimentation and graphs
│   ├── 01_eda_roads.ipynb   # Analysis of Road issues (Member 1)
│   ├── 02_eda_bridges.ipynb # Analysis of Bridge issues (Member 2)
│   └── 03_validation.ipynb  # Checking final files (Member 3)
├── src/                     # Source code (The actual "Program")
│   ├── __init__.py
│   ├── clean_roads.py       # Functions to clean road data
│   ├── clean_bridges.py     # Functions to clean bridge data
│   └── utils.py             # Shared math (e.g., interpolation formulas)
├── report/                  # Drafts of your PDF report
│   ├── images/              # Plots saved from notebooks
│   └── draft_text.md
├── main.py                  # Master script that runs the whole cleaning pipeline
├── README.md                # Instructions on how to run the code
├── requirements.txt         # List of libraries (pandas, numpy, openpyxl)
└── .gitignore               # Ignore temp files

```
## 2. Work Division
We are splitting the work into three distinct roles to allow us to work in parallel.

#### Member A: The Road Specialist

Focus: _roads.tsv → _roads3.csv

Coding Tasks:

Handle file parsing (fix tab-separated vs comma-separated issues).


Implement logic to convert "wide" format to "long" format or rename columns.

Crucial: Write sorting logic to ensure chainage is monotonic (increasing).

Crucial: Fix Latitude/Longitude outliers (jumps).

Report Contribution: Write the "Diagnosis" and "Strategy" paragraphs for Road Data issues.

### Member B: The Bridge Specialist

Focus: BMMS_overview.xlsx → Intermediate Cleaned Bridge Data

Coding Tasks:

Load the Excel file correctly.

Clean categorical columns (e.g., standardize condition to A/B/C/D, fix typos in structure type).

Identify which bridges are missing coordinates vs. which ones are missing chainage.

Report Contribution: Write the "Diagnosis" and "Strategy" paragraphs for Bridge Data issues.

### Member C: The Integrator & Analyst

Focus: Merging Data & Interpolation

Coding Tasks:

Algorithm: Write the interpolate_coordinates() function in src/utils.py. This function takes a bridge's chainage, looks at the cleaned road data, finds the two nearest road points, and calculates the estimated Lat/Lon.

Create main.py that imports functions from Member A and B and runs the full flow.

Report Contribution: Write the "Prioritization" section (why interpolation matters) and the "Reflection".

## 3. Workflow
To avoid overwriting each other's work, we will follow this Git workflow:

### Phase 1: Setup (Day 1)

Initialize: One person creates the repo and uploads the data/raw files.

Protect Main: Treat the main branch as "production ready". Do not push broken code there.

### Phase 2: Development (Days 2-4)

Branching:

Member A works on branch feature/road-cleaning.

Member B works on branch feature/bridge-cleaning.

Member C works on branch feature/interpolation-logic.

Communication: When Member A finishes cleaning road names/sorting, merge into main so Member C can use that clean data to test interpolation.

### Phase 3: Integration (Day 5)

Merge: Pull everyone's branches into main.

Run main.py: Ensure that running this one script produces the final files in data/processed/.

Validate: Member C runs a final check (using notebooks/03_validation.ipynb) to ensure no bridges were lost during the merge and that coordinates look correct on a map plot.

### Phase 4: Reporting (Day 6)

Use the Issues tab in GitHub to list specific data errors found (e.g., "Found typo in N1 chainage").

Copy these notes directly into the "Diagnosis" section of the report.