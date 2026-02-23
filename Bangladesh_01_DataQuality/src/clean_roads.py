# src/clean_roads.py
import pandas as pd
import numpy as np
from src.utils import haversine_dist


def clean_and_interpolate_road(group):
    """
    Takes a dataframe group (one specific road), identifies outliers based on
    rolling median deviation (>10km), and snaps them to the median.
    """
    # Sort by chainage
    group = group.sort_values(by='chainage')

    # Calculate Rolling Median
    # min_periods=1 ensures we get values even at the edges
    med_lat = group['lat'].rolling(window=5, center=True, min_periods=1).median()
    med_lon = group['lon'].rolling(window=5, center=True, min_periods=1).median()

    # Calculate Distance
    dist_error = haversine_dist(group['lat'], group['lon'], med_lat, med_lon)

    # Identify Outliers (> 10km)
    is_outlier = dist_error > 10

    # Fix Outliers
    fixed_lats = group['lat'].copy()
    fixed_lons = group['lon'].copy()

    # Snap outliers to the rolling median
    fixed_lats[is_outlier] = med_lat[is_outlier]
    fixed_lons[is_outlier] = med_lon[is_outlier]

    # Update columns
    group['lat'] = fixed_lats
    group['lon'] = fixed_lons

    return group


def get_outliers_only(group):
    """
    Returns only the rows identified as outliers for analysis/reporting.
    """
    group = group.sort_values(by='chainage')
    med_lat = group['lat'].rolling(window=5, center=True, min_periods=1).median()
    med_lon = group['lon'].rolling(window=5, center=True, min_periods=1).median()

    dist_error = haversine_dist(group['lat'], group['lon'], med_lat, med_lon)
    is_outlier = dist_error > 10

    group = group.copy()
    group['deviation_km'] = dist_error

    return group[is_outlier]