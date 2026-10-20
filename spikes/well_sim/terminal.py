def ask(prompt, default, cast=float):
    raw = input(f"{prompt} [{default}]: ").strip()
    return cast(raw) if raw else default


def ask_optional(prompt):
    raw = input(f"{prompt} [none]: ").strip()
    return float(raw) if raw else None


def ask_choice(prompt, options, default):
    while True:
        raw = input(f"{prompt} ({'/'.join(options)}) [{default}]: ").strip().lower() or default
        if raw in options:
            return raw
        print(f"Choose one of: {', '.join(options)}")


def read_parameters(for_sweep=False):
    p = {}
    print("Reservoir geometry (field units)")
    p["rw"] = ask("Well radius rw (ft)", 0.354)
    p["re"] = ask("Drainage radius re (ft)", 1000.0)
    p["h"] = ask("Producing thickness h (ft)", 50.0)
    p["Nr"] = ask("Radial cells Nr", 40, int)
    p["Nz"] = ask("Vertical cells Nz", 10, int)

    print("Rock properties")
    p["kh"] = ask("Horizontal permeability kh (md)", 100.0)
    p["kv_kh"] = ask("Anisotropy kv/kh", 0.1)
    p["phi"] = ask("Porosity phi (fraction)", 0.20)
    p["cf"] = ask("Rock compressibility cf (1/psi)", 4e-6)
    p["pi"] = ask("Initial reservoir pressure pi at mid-depth (psi)", 4000.0)

    print("Oil properties")
    p["pb"] = ask("Bubble point pressure pb (psi)", round(0.5 * p["pi"]))
    p["mu"] = ask("Oil viscosity mu (cP)", 1.5)
    p["Bo"] = ask("Formation volume factor Bo (rb/STB)", 1.2)
    p["co"] = ask("Oil compressibility co (1/psi)", 1e-5)
    p["rho"] = ask("Oil density rho (lb/ft3)", 50.0)
    p["kro"] = ask("Oil relative permeability kro (fraction)", 1.0)

    print("Well")
    p["skin"] = ask("Skin factor S (negative values use effective radius)", 0.0)
    p["perf_top"] = ask("Perforated interval top (ft below top of layer)", 0.0)
    p["perf_bot"] = ask("Perforated interval bottom (ft below top of layer)", p["h"])
    if not for_sweep:
        p["well_mode"] = ask_choice("Well control", ("rate", "bhp"), "rate")
        if p["well_mode"] == "rate":
            p["q"] = ask("Target rate q (STB/d)", 1000.0)
        else:
            p["pwf"] = ask("Target flowing BHP pwf (psi)", float(round(0.6 * p["pi"])))

    print("Operating constraints (blank = none)")
    p["pwf_min"] = ask_optional("Operating minimum BHP pwf_min (psi)")
    p["max_drawdown"] = ask_optional("Maximum drawdown pi - pwf (psi)")
    p["q_max"] = ask_optional("Facility rate limit q_max (STB/d)")
    p["q_abandon"] = ask_optional("Economic limit rate q_abandon (STB/d)")
    p["enforce_pb"] = ask_choice("Keep pressure above the bubble point", ("yes", "no"), "yes") == "yes"

    print("Boundaries (pressures referred to mid-depth)")
    p["outer_bc"] = ask_choice("Outer boundary at re", ("closed", "pressure"), "closed")
    if p["outer_bc"] == "pressure":
        p["pe"] = ask("Pressure at re (psi)", p["pi"])
    p["top_bc"] = ask_choice("Top boundary", ("noflow", "pressure"), "noflow")
    if p["top_bc"] == "pressure":
        p["p_top"] = ask("Pressure at top (psi)", p["pi"])
    p["bottom_bc"] = ask_choice("Bottom boundary", ("noflow", "pressure"), "noflow")
    if p["bottom_bc"] == "pressure":
        p["p_bot"] = ask("Pressure at bottom (psi)", p["pi"])

    print("Time discretization")
    p["T"] = ask("Simulated horizon T (days)", 365.0)
    p["Nt"] = ask("Number of time steps N", 100, int)
    p["dt_mode"] = ask_choice("Time step spacing", ("uniform", "geometric"), "geometric")
    if p["dt_mode"] == "geometric":
        p["dt0"] = ask("First time step dt0 (days)", 1e-3)
    p["theta"] = ask("Time scheme theta (1.0 implicit, 0.5 Crank-Nicolson with implicit start-up)", 1.0)
    raw = input("Np checkpoints in days, comma separated [none]: ").strip()
    p["checkpoints"] = [float(x) for x in raw.split(",")] if raw else []
    return p


def read_sweep_options():
    print("Sweep options")
    o = {}
    choice = ask_choice("Controls to sweep", ("both", "rate", "bhp"), "both")
    o["controls"] = ["rate", "bhp"] if choice == "both" else [choice]
    o["n_rate"] = ask("Coarse rate grid size", 10, int)
    o["n_bhp"] = ask("BHP grid size", 8, int)
    rate_min = ask_optional("Lowest rate to try (STB/d)")
    rate_max = ask_optional("Highest rate to try (STB/d)")
    if rate_min is not None:
        o["rate_min"] = rate_min
    if rate_max is not None:
        o["rate_max"] = rate_max
    o["tolerance"] = ask("Recovery tolerance for the recommended rate (fraction)", 0.01)
    o["refine_rounds"] = ask("Refinement rounds around the knee", 2, int)
    o["discount_rate"] = ask("Annual discount rate (fraction)", 0.10)
    return o
