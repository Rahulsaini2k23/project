import osmnx as ox
import matplotlib.pyplot as plt

G = ox.load_graphml("nit_jalandhar.graphml")

fig, ax = ox.plot_graph(
    G,
    bgcolor="white",
    node_color="red",
    edge_color="blue",
    node_size=10,
    show=False,
    close=False
)

plt.savefig(
    "nit_graph_colored.png",
    dpi=300,
    bbox_inches="tight"
)

print("Colored graph saved")
