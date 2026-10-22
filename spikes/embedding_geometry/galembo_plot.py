"""Local 3-D PCA of the 23 Galembo chunks; run with conda base (matplotlib).

    ~/anaconda3/bin/python galembo_plot.py pca3.npz [out.png]

Point colour = cosine to the quick question; numbers = chunk seq in the paper.
"""
import sys

import matplotlib.pyplot as plt
import numpy as np

TMAX_SEQ = 17
CITED_QUICK = {16, 17, 18}
CITED_RESEARCH = {9, 10, 18}


def main() -> None:

    data = np.load(sys.argv[1], allow_pickle=False)
    xyz = data["g_coords"]
    seq = data["g_seq"]
    ev = data["g_explained"] * 100
    cos_quick = data["g_q_cos"][1]

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(projection="3d")

    ax.plot(*xyz.T, c="#999999", lw=.6, alpha=.6, label="reading order (seq)")
    pts = ax.scatter(*xyz.T, s=90, c=cos_quick, cmap="viridis",
                     edgecolors="k", linewidths=.4, depthshade=False)
    fig.colorbar(pts, ax=ax, shrink=.6, pad=.08,
                 label="cosine to Quick Q (EN)")

    for (x, y, z), s in zip(xyz, seq):
        weight = "bold" if s in CITED_QUICK | CITED_RESEARCH else "normal"
        ax.text(x, y, z, f" {s}", fontsize=9, fontweight=weight)

    t = xyz[seq == TMAX_SEQ][0]
    ax.scatter(*t, s=260, facecolors="none", edgecolors="#d62728",
               linewidths=2, label="17: Tmax 439-448 °C, PI 0.02-0.1")
    for s_set, color, name in ((CITED_QUICK, "#ff7f0e", "cited by Quick"),
                               (CITED_RESEARCH, "#9467bd",
                                "cited by Research")):
        m = np.isin(seq, list(s_set))
        ax.scatter(*xyz[m].T, s=170, facecolors="none", edgecolors=color,
                   linewidths=1.2, label=name)

    for (x, y, z), name, color in zip(data["g_q_coords"], data["q_names"],
                                      ("#9467bd", "#ff7f0e")):
        ax.scatter(x, y, z, s=380, marker="*", c=color, edgecolors="k",
                   label=str(name))
        ax.text(x, y, z, f"  {name}", fontsize=9)

    ax.set_xlabel(f"local PC1 ({ev[0]:.1f} %)")
    ax.set_ylabel(f"local PC2 ({ev[1]:.1f} %)")
    ax.set_zlabel(f"local PC3 ({ev[2]:.1f} %)")
    ax.set_title("Galembo Member paper (Casadiego-Quintero & Ríos-Reyes, "
                 f"2016)\n23 chunks, local PCA ({ev.sum():.1f} % of "
                 "within-paper variance)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()

    if len(sys.argv) > 2:
        fig.savefig(sys.argv[2], dpi=150)
    plt.show()


if __name__ == "__main__":
    main()
