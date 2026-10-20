import matplotlib.pyplot as plt
import numpy as np


def set_lnr_axis(ax, grid):
    ticks = [r for r in (0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000)
             if grid.r_cell[0] <= r <= grid.r_cell[-1]]
    ax.set_xticks(np.log(ticks))
    ax.set_xticklabels([f"{r:g}" for r in ticks])
    ax.set_xlabel("r (ft, log scale)")
    ax.set_ylabel("z (ft)")


def plot_grid(res):
    inp, gr = res.inp, res.sim.grid
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    for r in gr.r_face:
        ax.plot([r, r], [0.0, inp.h], color="tab:blue", lw=0.6)
    for z in gr.z_face:
        ax.plot([gr.r_face[0], gr.r_face[-1]], [z, z], color="tab:blue", lw=0.6)
    ax.plot([gr.rw, gr.rw], [inp.perf_top, inp.perf_bot], "r-", lw=4, label="perforations")
    ax.set_xscale("log")
    ax.invert_yaxis()
    ax.set_xlabel("r (ft, log scale)")
    ax.set_ylabel("z (ft)")
    ax.set_title("Logarithmic radial grid (r-z)")
    ax.legend(loc="lower right")

    ax = axes[1]
    ax.semilogy(np.arange(1, gr.Nr + 1), gr.dr, "o-", ms=3)
    ax.set_xlabel("Radial cell index")
    ax.set_ylabel("dr (ft)")
    ax.set_title("Radial cell width")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def plot_matrix(res):
    gr = res.sim.grid
    plt.figure(figsize=(8, 8))
    plt.spy(res.sim.A_last, markersize=1.5)
    plt.title(f"Coefficient matrix {gr.N + 1}x{gr.N + 1}: diagonals at 0, +-1, +-{gr.Nz}, "
              f"plus well row and column", fontsize=10)
    plt.xlabel("Column")
    plt.ylabel("Row")
    plt.show()


def plot_fields(res):
    sim, gr, inp = res.sim, res.sim.grid, res.inp
    press, u_r, u_z = sim.fields()
    speed = np.hypot(u_r, u_z)
    log_speed = np.log10(speed + 1e-30)
    R, Z = np.meshgrid(gr.r_cell, gr.z_cell)
    X = np.log(R)
    ux = (u_r / gr.r_cell[:, None]).T
    uy = u_z.T

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle(f"Fields at t = {sim.t[-1]:.4g} days")

    ax = axes[0, 0]
    drop = (inp.pi + gr.gamma * (gr.z_cell[None, :] - gr.z_ref) - press).T
    cs = ax.pcolormesh(gr.r_face, gr.z_face, drop, shading="flat", cmap="viridis")
    ax.contour(R, Z, drop, levels=10, colors="white", alpha=0.4, linewidths=0.5)
    ax.plot([gr.rw, gr.rw], [inp.perf_top, inp.perf_bot], "r-", lw=4)
    ax.set_xscale("log")
    ax.set_xlim(gr.rw, inp.re)
    ax.invert_yaxis()
    fig.colorbar(cs, ax=ax, label="Pressure drop pi - p (psi)")
    ax.set_xlabel("r (ft, log scale)")
    ax.set_ylabel("z (ft)")
    ax.set_title("Pressure drop field (initial hydrostatic p removed)")

    ax = axes[0, 1]
    cs = ax.pcolormesh(gr.r_face, gr.z_face, log_speed.T, shading="flat", cmap="plasma")
    ax.set_xscale("log")
    ax.set_xlim(gr.rw, inp.re)
    ax.invert_yaxis()
    fig.colorbar(cs, ax=ax, label="log10 |u| (ft/d)")
    ax.set_xlabel("r (ft, log scale)")
    ax.set_ylabel("z (ft)")
    ax.set_title("Darcy velocity magnitude")

    ax = axes[1, 0]
    sr = max(1, gr.Nr // 20)
    sz = max(1, gr.Nz // 12)
    Lx = X.max() - X.min()
    Ly = gr.z_cell.max() - gr.z_cell.min() if gr.Nz > 1 else inp.h
    norm = np.hypot(ux / Lx, uy / Ly) + 1e-300
    dx = 0.035 * Lx * (ux / Lx) / norm
    dy = 0.035 * Ly * (uy / Ly) / norm
    ax.quiver(X[::sz, ::sr], Z[::sz, ::sr], dx[::sz, ::sr], dy[::sz, ::sr],
              log_speed.T[::sz, ::sr], angles="xy", scale_units="xy", scale=1,
              pivot="mid", cmap="cool")
    set_lnr_axis(ax, gr)
    ax.invert_yaxis()
    ax.set_title("Flow direction (colored by log10 |u|)")

    ax = axes[1, 1]
    if gr.Nz >= 3:
        strm = ax.streamplot(X[0], gr.z_cell, ux, uy, color=log_speed.T,
                             cmap="cool", density=1.5, linewidth=1.3)
        fig.colorbar(strm.lines, ax=ax, label="log10 |u| (ft/d)")
    else:
        ax.text(0.5, 0.5, "Streamlines need Nz >= 3", ha="center", transform=ax.transAxes)
    set_lnr_axis(ax, gr)
    ax.invert_yaxis()
    ax.set_title("Streamlines")

    plt.tight_layout()
    plt.show()


def plot_profiles(res):
    sim, gr, inp = res.sim, res.sim.grid, res.inp
    n_steps = len(sim.t)
    k_mid = gr.Nz // 2
    steps = np.unique(np.round(np.geomspace(1, n_steps, 8)).astype(int)) - 1

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    for s in steps:
        pot = sim.pot_hist[s + 1].reshape(gr.Nr, gr.Nz)
        ax.semilogx(gr.r_cell, inp.pi - pot[:, k_mid], label=f"t = {sim.t[s]:.3g} d")
    ax.set_xlabel("r (ft, log scale)")
    ax.set_ylabel("Drawdown pi - p (psi)")
    ax.set_title(f"Drawdown vs radius at z = {gr.z_cell[k_mid]:.1f} ft")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1]
    pot = sim.pot_hist[-1].reshape(gr.Nr, gr.Nz)
    for i in sorted(set([0, gr.Nr // 4, gr.Nr // 2, 3 * gr.Nr // 4])):
        ax.plot(inp.pi - pot[i, :], gr.z_cell, "o-", ms=3, label=f"r = {gr.r_cell[i]:.1f} ft")
    ax.invert_yaxis()
    ax.set_xlabel("Drawdown pi - p (psi)")
    ax.set_ylabel("z (ft)")
    ax.set_title(f"Vertical drawdown profile at t = {sim.t[-1]:.4g} d")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    plt.tight_layout()
    plt.show()


def plot_production(res):
    sim, inp = res.sim, res.inp
    t = sim.t
    floor = inp.pwf_floor
    limited = any(m != "target" for m in sim.modes)
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    ax = axes[0]
    ax.semilogx(t, sim.pwf, label="pwf (numerical)")
    ax.semilogx(t, sim.p_avg, label="average pressure")
    if sim.ei_applies():
        m = t <= 2.0 * sim.t_ia
        if m.any():
            ax.semilogx(t[m], sim.analytic_ei(t[m]), "k--", lw=1.2, label="line source (Ei)")
        if sim.closed and len(t) > 1:
            slope = -inp.q / sim.C.sum()
            m = t >= t[-1] / 4.0
            ax.semilogx(t[m], sim.pwf[-1] + slope * (t[m] - t[-1]),
                        "r:", lw=1.5, label="pseudo-steady slope")
    if limited or sim.pwf.min() < 1.5 * floor:
        ax.axhline(floor, color="gray", ls=":", label=f"pwf floor ({inp.floor_source})")
    for e in res.events[1:]:
        ax.axvline(max(e["t_days"], t[0]), color="gray", ls="--", lw=0.8)
    ax.set_xlabel("Time (days)")
    ax.set_ylabel("Pressure (psi)")
    ax.set_title("Pressure drawdown at the well")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1]
    ax.semilogx(t, sim.q)
    if inp.q_max is not None:
        ax.axhline(inp.q_max, color="gray", ls=":", label="q_max")
    if inp.q_abandon is not None:
        ax.axhline(inp.q_abandon, color="tab:red", ls=":", label="economic limit")
    for e in res.events[1:]:
        ax.axvline(max(e["t_days"], t[0]), color="gray", ls="--", lw=0.8)
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel("Time (days)")
    ax.set_ylabel("Oil rate (STB/d)")
    ax.set_title("Production rate")
    ax.grid(True, alpha=0.3)
    if inp.q_max is not None or inp.q_abandon is not None:
        ax.legend(fontsize=8)

    ax = axes[2]
    ax.plot(t, sim.Np)
    ax.set_xlabel("Time (days)")
    ax.set_ylabel("Np (STB)")
    ax.set_title(f"Cumulative production, RF = {res.summary['recovery_factor']:.2%}")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def plot_sweep(sw):
    rate = [r for r in sw.rows if r["control"] == "rate"]
    bhp = [r for r in sw.rows if r["control"] == "bhp"]
    limit = sw.bounds["np_depletion_limit_stb"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    ax = axes[0]
    if rate:
        q = [r["target"] for r in rate]
        ax.plot(q, [r["np_stb"] for r in rate], "o-", ms=4, label="Np at horizon")
        ax.plot(q, [r["discounted_np_stb"] for r in rate], "s--", ms=3, label="discounted Np")
        ax.axhline(limit, color="gray", ls=":", label="material-balance limit")
        if sw.recommended_rate is not None:
            rec = sw.recommended_rate["target"]
            ax.axvline(rec, color="tab:green", ls="--", label=f"recommended {rec:,.0f} STB/d")
        if sw.best_discounted_rate is not None:
            ax.axvline(sw.best_discounted_rate["target"], color="tab:orange", ls="--",
                       label=f"best discounted {sw.best_discounted_rate['target']:,.0f} STB/d")
        if sw.inputs["q_max_stb_d"] is not None:
            ax.axvline(sw.inputs["q_max_stb_d"], color="tab:red", ls=":", label="q_max")
        ax.legend(fontsize=8)
    ax.set_xlabel("Target rate (STB/d)")
    ax.set_ylabel("Oil produced (STB)")
    ax.set_title(f"Recovery vs rate at T = {sw.inputs['horizon_days']:g} d")
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    if bhp:
        ax.plot([r["target"] for r in bhp], [r["np_stb"] for r in bhp], "o-", ms=4)
        ax.axhline(limit, color="gray", ls=":", label="material-balance limit")
        ax.axvline(sw.inputs["pwf_floor_psi"], color="tab:red", ls=":",
                   label=f"pwf floor ({sw.inputs['floor_source']})")
        ax.legend(fontsize=8)
    ax.set_xlabel("Target flowing BHP (psi)")
    ax.set_ylabel("Oil produced (STB)")
    ax.set_title("Recovery vs bottomhole pressure")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    if rate:
        cmap = plt.get_cmap("viridis")
        qs = [r["target"] for r in rate]
        span = max(max(qs) - min(qs), 1e-12)
        for r in rate:
            t, cum = sw.curves[("rate", r["target"])]
            ax.plot(t, cum, color=cmap((r["target"] - min(qs)) / span), lw=0.9)
        if sw.recommended_rate is not None:
            t, cum = sw.curves[("rate", sw.recommended_rate["target"])]
            ax.plot(t, cum, color="tab:green", lw=2.5, label="recommended")
            ax.legend(fontsize=8)
    ax.set_xlabel("Time (days)")
    ax.set_ylabel("Np (STB)")
    ax.set_title("Cumulative production by rate (dark = low rate)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()
