"""3-D PCA plot of the Crocol vector space; run with conda base (matplotlib).

    ~/anaconda3/bin/python pca_plot.py pca3.npz [out.png]
"""
import sys

import matplotlib.pyplot as plt
import numpy as np

GALEMBO = "Casadiego-Quintero & Ríos-Reyes, 2016"
TMAX_CHUNK = "8be32c0bf964bad4"
COLLECTION_COLORS = {
    "VMM_Basin": "#b0b7c3",
    "ANH_Contracts": "#e3a857",
    "ANH_Regulatory": "#c97b84",
    "ANH_Reserves": "#7fb069",
}


def main() -> None:

    data = np.load(sys.argv[1], allow_pickle=False)
    xyz = data["coords"]
    ev = data["explained"] * 100
    coll = data["collection"]
    galembo = data["citation"] == GALEMBO
    topk = data["in_topk"]
    tmax = data["chunk_id"] == TMAX_CHUNK

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(projection="3d")

    for name, color in COLLECTION_COLORS.items():
        m = (coll == name) & ~galembo & ~topk
        ax.scatter(*xyz[m].T, s=2, c=color, alpha=0.25, depthshade=False,
                   label=f"{name} ({m.sum()})")

    m = galembo & ~tmax
    ax.scatter(*xyz[m].T, s=28, c="#1f77b4", edgecolors="k", linewidths=.3,
               label=f"Galembo paper chunks ({galembo.sum()})")
    m = topk & ~galembo
    ax.scatter(*xyz[m].T, s=28, marker="^", c="#2ca02c", edgecolors="k",
               linewidths=.3, label="Quick top-k, other docs")
    ax.scatter(*xyz[tmax].T, s=140, marker="D", c="#d62728",
               edgecolors="k", label="Chunk 17 (Tmax 439-448 °C)")

    for (x, y, z), name, color in zip(data["q_coords"], data["q_names"],
                                      ("#9467bd", "#ff7f0e")):
        ax.scatter(x, y, z, s=320, marker="*", c=color, edgecolors="k",
                   label=str(name))
        ax.text(x, y, z, f"  {name}", fontsize=9)

    ax.set_xlabel(f"PC1 ({ev[0]:.1f} %)")
    ax.set_ylabel(f"PC2 ({ev[1]:.1f} %)")
    ax.set_zlabel(f"PC3 ({ev[2]:.1f} %)")
    ax.set_title("Crocol vector space: 11,420 chunks, text-embedding-3-large "
                 f"1536-d -> 3 PCs ({ev.sum():.1f} % of variance)")
    ax.legend(loc="upper left", fontsize=8, markerscale=1.5)
    fig.tight_layout()

    if len(sys.argv) > 2:
        fig.savefig(sys.argv[2], dpi=150)
    plt.show()


if __name__ == "__main__":
    main()
