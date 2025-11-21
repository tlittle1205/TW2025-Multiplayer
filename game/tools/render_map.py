# render_map.py
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

plt.rcParams['font.family'] = ['DejaVu Sans', 'Segoe UI Symbol', 'sans-serif']


def render_galaxy_map(galaxy, player_sector=None, save_png=False):
    """
    Enhanced Galaxy Map (Dark Mode + Legend)
    """

    G = nx.Graph()

    # Build graph
    for sid, sector in galaxy.sectors.items():
        G.add_node(
            sid,
            type=sector.type,
            has_port=sector.port is not None,
            has_planet=sector.planet is not None
        )
        for n in sector.neighbors:
            if sid < n:
                G.add_edge(sid, n)

    # Bigger figure
    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor("black")

    # Spread-out physics layout
    pos = nx.spring_layout(G, seed=42, k=1.5, iterations=100)

    # Colors for nodes
    def node_color(sid):
        t = G.nodes[sid]["type"]
        if sid == player_sector:
            return "#339900"  
        if t == "STARDOCK":
            return "#FFCC33"
        if t == "FEDSPACE":
            return "#0000FF"
        if t == "PIRATE":
            return "#CA0533"
        if t == "DEADEND":
            return "#808080"
        return "#CC6600"

    colors = [node_color(n) for n in G.nodes()]

    # Icons for labeling
    def node_icon(n):
        data = G.nodes[n]
        if data["has_port"] and data["has_planet"]:
            return "◉◆"
        if data["has_port"]:
            return "◆"
        if data["has_planet"]:
            return "◉"
        return ""

    labels = {n: f"{n} {node_icon(n)}" for n in G.nodes()}

    # White edges
    nx.draw_networkx_edges(
        G, pos,
        width=2.0,
        alpha=0.7,
        edge_color="white"
    )

    # Larger nodes with white outline
    nx.draw_networkx_nodes(
        G, pos,
        node_color=colors,
        node_size=1500,
        edgecolors="white",
        linewidths=1
    )

    # Labels in white for dark mode
    nx.draw_networkx_labels(
        G, pos,
        labels,
        font_size=12,
        font_color="white"
    )

    
# ============================================================
# LEGEND — MATCHES ACTUAL COLORS & SHOWS PORT/PLANET ICONS
# ============================================================

    legend_patches = [
        mpatches.Patch(color="#339900", label="Player Sector"),
        mpatches.Patch(color="#FFCC33", label="Stardock"),
        mpatches.Patch(color="#0000FF", label="Fedspace"),
        mpatches.Patch(color="#CA0533", label="Pirate Sector"),
        mpatches.Patch(color="#808080", label="Dead End"),
        mpatches.Patch(color="#CC6600", label="Standard Sector"),
    ]

    # Additional symbol-based legend items
    legend_ports = mpatches.Patch(
        facecolor="black",
        edgecolor="white",
        label="◆  Port Present"
    )
    legend_planets = mpatches.Patch(
        facecolor="black",
        edgecolor="white",
        label="◉  Planet Present"
    )
    legend_both = mpatches.Patch(
        facecolor="black",
        edgecolor="white",
        label="◉◆  Planet + Port"
    )

    legend = plt.legend(
        handles=legend_patches + [legend_ports, legend_planets, legend_both],
        loc="upper left",
        framealpha=0.6,
        facecolor="black",
        edgecolor="white",
        labelcolor="white",
        fontsize=10
    )

    # Set legend text color to white
    for text in legend.get_texts():
        text.set_color("white")

    # Title
    plt.title("Galaxy Map", fontsize=16, fontweight="bold", color="white")
    plt.axis("off")

    if save_png:
        print("Close the map window to return to the game.")

    plt.show()


