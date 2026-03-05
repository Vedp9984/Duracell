import geopandas as gpd
import pandas as pd
import os
import json

def process_subbasins():
    # Paths
    base_dir = "/home/aniket/sem-8/Hydro/ass-2"
    shp_path = os.path.join(base_dir, "zone-12-drainage-basins-vector.shp")
    csv_path = os.path.join(base_dir, "output", "catchment_characteristics.csv")
    output_path = "/home/aniket/sem-8/Hydro/ass-2/website/flood_das/geojson/layers/drainage_basins_enriched.geojson"

    print(f"Reading shapefile: {shp_path}")
    gdf = gpd.read_file(shp_path)

    # Ensure CRS is 4326 for Leaflet
    if gdf.crs != "EPSG:4326":
        print(f"Reprojecting from {gdf.crs} to EPSG:4326")
        gdf = gdf.to_crs("EPSG:4326")

    print(f"Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    # Convert Basin_ID to same type as DN for joining
    gdf['DN'] = gdf['DN'].astype(int)
    df['Basin_ID'] = df['Basin_ID'].astype(int)

    # Merge catchment characteristics
    print("Merging catchment characteristics...")
    merged_gdf = gdf.merge(df, left_on='DN', right_on='Basin_ID', how='inner')

    # Merge new hydrological data (watershed slope, channel data)
    hydro_csv_path = os.path.join(base_dir, "output", "subcatchment_hydrological_data.csv")
    if os.path.exists(hydro_csv_path):
        print(f"Reading hydrological CSV: {hydro_csv_path}")
        df_hydro = pd.read_csv(hydro_csv_path)
        df_hydro['Basin_ID'] = df_hydro['Basin_ID'].astype(int)
        # Only pick the new columns not already in the GeoJSON
        cols_to_add = ['Basin_ID', 'Watershed_Slope_m_m', 'Channel_Length_m', 'Channel_Slope_m_m', 'Total_Stream_Length_m']
        df_hydro = df_hydro[cols_to_add]
        print("Merging hydrological data...")
        merged_gdf = merged_gdf.merge(df_hydro, on='Basin_ID', how='left')
        print("  Added: Watershed_Slope_m_m, Channel_Length_m, Channel_Slope_m_m, Total_Stream_Length_m")
    else:
        print(f"  Warning: {hydro_csv_path} not found, skipping hydrological merge")

    # Save to GeoJSON
    print(f"Saving enriched GeoJSON to: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    merged_gdf.to_file(output_path, driver='GeoJSON')
    print("Success!")
    print(f"Final columns: {list(merged_gdf.columns)}")


if __name__ == "__main__":
    process_subbasins()
