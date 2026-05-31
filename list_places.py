import osmnx as ox

latitude = 31.3960
longitude = 75.5350

tags = {
    "name": True
}

gdf = ox.features_from_point(
    (latitude, longitude),
    tags=tags,
    dist=1200
)

names = gdf["name"].dropna().unique()

for name in sorted(names):
    print(name)
