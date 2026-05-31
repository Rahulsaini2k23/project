import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt

G = ox.load_graphml(
    "nit_jalandhar.graphml"
)

def generate_route(
    start_lat,
    start_lon,
    dest_lat,
    dest_lon
):

    start_node = ox.distance.nearest_nodes(
        G,
        start_lon,
        start_lat
    )

    end_node = ox.distance.nearest_nodes(
        G,
        dest_lon,
        dest_lat
    )

    route = nx.shortest_path(
        G,
        start_node,
        end_node,
        weight="length"
    )

    route_length = nx.path_weight(
        G,
        route,
        weight="length"
    )

    fig, ax = ox.plot_graph_route(
        G,
        route,
        route_color="red",
        route_linewidth=4,
        node_size=0,
        show=False,
        close=False
    )

    plt.savefig(
        "route.png",
        dpi=300
    )

    return route, route_length
