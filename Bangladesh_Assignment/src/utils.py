# src/utils.py
import numpy as np

def haversine_dist(lat1, lon1, lat2, lon2):
    """
    Calculates distance in KM between two lat/lon arrays using Haversine formula.
    Vectorized for pandas series or numpy arrays.
    """
    R = 6371.0  # Earth radius in kilometers

    # Convert degrees to radians
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    # The Math
    a = np.sin(dphi / 2)**2 + \
        np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c