"""
Draw the research-paper figures as SVG from data/metrics.json and data/*.csv (no plotting library needed).
Run after compute_research_metrics.py:
    python reports/research_paper/scripts/make_figures.py
"""
import json
from html import escape
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1]
DATA, FIG = OUT / "data", OUT / "eda_visualizations"
FIG.mkdir(exist_ok=True)
M = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
BLUE, ORANGE, INK, INK2, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
FONT = 'system-ui, -apple-system, "Segoe UI", Arial, sans-serif'


def _bar(x0, y, w, h, color):
    if w <= 0:
        return ""
    r = min(4, w / 2, h / 2)
    return (f'<path d="M{x0},{y} H{x0 + w - r} Q{x0 + w},{y} {x0 + w},{y + r} V{y + h - r} '
            f'Q{x0 + w},{y + h} {x0 + w - r},{y + h} H{x0} Z" fill="{color}"/>')


def chart(name, title, subtitle, cats, series, fmt, note, label_w=None, width=760, colors=(BLUE, ORANGE)):
    """Horizontal bar chart. series: list of (series_name, values). One series -> one colour, no legend."""
    label_w = label_w or min(400, max(90, int(max(len(c) for c in cats) * 7.0) + 24))
    n_s = len(series)
    bar_h = 22 if n_s == 1 else 15
    group_h = bar_h * n_s + (2 * (n_s - 1))
    gap = 12
    top = 76 if n_s == 1 else 96
    vals = [v for _, vs in series for v in vs]
    vmax = max(max(vals), 1e-9)
    longest = max(len(fmt(v)) for v in vals)
    plot_w = width - label_w - (longest * 7.2 + 24)
    height = top + len(cats) * (group_h + gap) + 40
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family=\'{FONT}\' role="img" aria-label="{escape(title)}">',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         f'<text x="0" y="24" font-size="16.5" font-weight="600" fill="{INK}">{escape(title)}</text>',
         f'<text x="0" y="45" font-size="12" fill="{INK2}">{escape(subtitle)}</text>']
    if n_s > 1:
        lx = 0
        for k, (sn, _) in enumerate(series):
            s.append(f'<rect x="{lx}" y="60" width="12" height="12" rx="2" fill="{colors[k]}"/>'
                     f'<text x="{lx + 18}" y="70.5" font-size="12" fill="{INK}">{escape(sn)}</text>')
            lx += 30 + len(sn) * 7
    s.append(f'<line x1="{label_w}" y1="{top - 6}" x2="{label_w}" y2="{top + len(cats) * (group_h + gap) - gap + 6}" stroke="{GRID}"/>')
    for i, c in enumerate(cats):
        y0 = top + i * (group_h + gap)
        s.append(f'<text x="{label_w - 10}" y="{y0 + group_h / 2 + 4.5}" font-size="12.5" text-anchor="end" fill="{INK}">{escape(c)}</text>')
        for k, (_, vs) in enumerate(series):
            v = vs[i]
            y = y0 + k * (bar_h + 2)
            w = max(plot_w * v / vmax, 0)
            s.append(_bar(label_w, y, w, bar_h, colors[k] if n_s > 1 else BLUE))
            s.append(f'<text x="{label_w + w + 7}" y="{y + bar_h / 2 + 4.3}" font-size="12" fill="{INK}">{escape(fmt(v))}</text>')
    s.append(f'<text x="0" y="{height - 12}" font-size="11" fill="{MUTED}">{escape(note)}</text></svg>')
    (FIG / f"{name}.svg").write_text("\n".join(s), encoding="utf-8")


num = lambda v: f"{v:,.0f}"
products = pd.read_csv(DATA / "products.csv", index_col=0)
chart("fig01_sales_by_product", "Figure 1. Sales by product (USD)", "Observed, whole dataset. Bars sorted by sales.",
      list(products.index), [("Sales", products["sales"].tolist())], lambda v: f"${v:,.0f}",
      "Source: Sales column of the raw dataset.")

d = M["divisions"]
chart("fig02_division_lines", "Figure 2. Order lines by product division", f"{M['raw_rows']:,} order lines (observed).",
      list(d), [("Lines", list(d.values()))], lambda v: f"{v:,.0f} ({100 * v / M['raw_rows']:.1f}%)",
      "Source: Division column.")

opc = pd.read_csv(DATA / "order_ids_per_customer.csv")
b = {"1": 0, "2": 0, "3": 0, "4": 0, "5 or more": 0}
for _, r in opc.iterrows():
    b[str(int(r["order_ids"])) if r["order_ids"] < 5 else "5 or more"] += int(r["customers"])
chart("fig03_orders_per_customer", "Figure 3. Customers by number of distinct order IDs",
      f"{M['customers']:,} customers (observed). An order ID groups lines of one product for one customer.",
      [f"{k} order ID{'s' if k != '1' else ''}" for k in b], [("Customers", list(b.values()))],
      lambda v: f"{v:,.0f} ({100 * v / M['customers']:.1f}%)", "Source: Customer ID and Order ID columns.")

dest = pd.read_csv(DATA / "destinations.csv", index_col=0).head(10)
chart("fig04_top_destinations", "Figure 4. Top 10 destinations by order lines",
      f"{M['destinations']} destinations in total ({M['us_states_incl_dc']} US states incl. DC, {M['canadian_provinces']} Canadian provinces).",
      list(dest.index), [("Lines", dest["lines"].tolist())], num, "Source: State/Province column.")

r = M["regions"]
chart("fig05_regions", "Figure 5. Order lines by sales region", "Observed (Region column of each order line).",
      list(r), [("Lines", list(r.values()))], lambda v: f"{v:,.0f} ({100 * v / M['raw_rows']:.1f}%)", "Source: Region column.")

order = ["Same Day", "First Class", "Second Class", "Standard Class"]
sm = M["ship_modes"]
chart("fig06_ship_modes", "Figure 6. Order lines by shipping mode", "Observed.",
      order, [("Lines", [sm[m] for m in order])], lambda v: f"{v:,.0f} ({100 * v / M['raw_rows']:.1f}%)", "Source: Ship Mode column.")

rg = M["raw_gap_mean_by_ship_mode"]
chart("fig07_raw_gap_by_mode", "Figure 7. RAW gap (Ship Date − Order Date) by shipping mode, mean days",
      "The raw gap is 904–1,642 days for every mode; Same Day is not faster. It is not a lead time.",
      order, [("Mean raw gap", [rg[m] for m in order])], lambda v: f"{v:,.1f} days",
      f"Ship mode explains {M['eta2_ship_mode_raw_gap_pct']:.2f}% of the variance of the raw gap.")

vc = M["recovered_lead_value_counts"]
chart("fig08_recovered_lead_distribution", "Figure 8. Distribution of the RECONSTRUCTED lead time",
      "Derived: Ship Date − 2,000 days − (Order Date with the Order ID year). Not measured delivery time.",
      [f"{k} days" for k in vc], [("Lines", list(vc.values()))], num, "Source: lead_time_recovered_days (src/data_validation.py).")

rl = M["recovered_lead_mean_by_ship_mode"]
chart("fig09_recovered_lead_by_mode", "Figure 9. Mean RECONSTRUCTED lead time by shipping mode (days)",
      f"Derived. Ship mode explains {M['eta2_ship_mode_recovered_lead_pct']:.1f}% of the variance.",
      order, [("Mean days", [rl[m] for m in order])], lambda v: f"{v:.2f} days",
      "Typical ranges (0.5th–99.5th percentile): Same Day 0–1, First 1–3, Second 2–5, Standard 4–7 days.")

fl = M["factory_lines"]; fp = M["factory_products"]
chart("fig10_factory_lines", "Figure 10. Order lines by current factory", "Observed allocation (each product made at one factory).",
      [f"{k} ({fp[k]} products)" for k in fl], [("Lines", list(fl.values()))],
      lambda v: f"{v:,.0f} ({100 * v / M['raw_rows']:.1f}%)", "Source: baseline product-factory assignments applied to order lines.")

mc = pd.read_csv(DATA / "model_comparison.csv")
names = {"baseline_mean": "Overall mean (baseline)", "baseline_ship_mode_mean": "Per-ship-mode mean (selected)",
         "linear_regression": "Linear Regression", "random_forest": "Random Forest", "gradient_boosting": "Gradient Boosting"}
chart("fig11_model_mae", "Figure 11. Model error: validation vs test MAE (days, lower is better)",
      "Target: reconstructed lead time. Model chosen on validation MAE only; test set used for reporting.",
      [names[m] for m in mc["model"]], [("Validation MAE", mc["val_mae"].tolist()), ("Test MAE", mc["test_mae"].tolist())],
      lambda v: f"{v:.3f}", "Chronological split: train 2021-01 → 2024-03, validation → 2024-09, test → 2024-12 (rebuilt order dates).")

fi = pd.read_csv(DATA / "feature_importance.csv")
lr = fi[fi["model"] == "linear_regression"].sort_values("importance_mae_increase", ascending=False)
chart("fig12_permutation_importance", "Figure 12. Permutation importance, Linear Regression (validation set)",
      "Increase in MAE (days) when a feature is shuffled. Only Ship Mode matters; all others are ≈ 0 or negative.",
      lr["feature"].tolist(), [("MAE increase", lr["importance_mae_increase"].clip(lower=0).tolist())],
      lambda v: f"{v:.4f}", "Negative values (shuffling slightly helps) are drawn as zero-length bars.")

sc = M["scenarios"]
snames = {"current": "Current allocation", "alternative": "Best alternative (forced)", "distance": "Distance-based",
          "cost": "Cost-focused", "balanced": "Balanced (recommended)"}
chart("fig13_scenario_profit", "Figure 13. ESTIMATED profit impact by scenario (USD, historical period)",
      "Estimates under default analyst assumptions — not verified real-world savings.",
      [f"{snames[k]} — {v['products_moved']} moved" for k, v in sc.items()],
      [("Profit impact", [v["estimated_profit_impact"] for v in sc.values()])],
      lambda v: f"+${v:,.0f}" if v >= 0.5 else "$0", "Freight $0.0005/unit-mile; equal production cost at every factory; capacity not limited.")

cm = pd.read_csv(DATA / "cost_scenario_moves.csv").sort_values("profit_impact", ascending=False)
chart("fig14_cost_scenario_by_product", "Figure 14. ESTIMATED profit impact per move, cost-focused scenario (USD)",
      f"{len(cm)} moves; the top three account for {M['cost_top3_share_pct']:.1f}% of the total.",
      [f"{p} → {f}" for p, f in zip(cm["product_name"], cm["proposed_factory"])],
      [("Profit impact", cm["profit_impact"].tolist())], lambda v: f"+${v:,.2f}",
      "Estimates; small products rest on very few order lines (see Table 9).", width=900)
print(sorted(p.name for p in FIG.iterdir()))
