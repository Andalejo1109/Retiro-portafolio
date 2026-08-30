#!/usr/bin/env python3
"""
Backtest de retiro sobre una asignación tipo portafolio eToro.

Simula tres patrimonios iniciales (150k / 300k / 500k) que retiran
una renta mensual. El retiro del año 1 es fijo; a partir del año 2
crece a una tasa anual (COLA), por defecto 3%.

Ejemplo:
    python simular_retiro.py
    python simular_retiro.py --start 2006-09-01 --cola 0.03 --gif
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

WEIGHTS = pd.Series(
    {
        "SPYG": 0.33,
        "SMH": 0.21,
        "BRK-B": 0.21,
        "IEMG": 0.16,
        "VTI": 0.09,
    }
)
WEIGHTS = WEIGHTS / WEIGHTS.sum()

INITIALS = {
    "500k": 500_000.0,
    "300k": 300_000.0,
    "150k": 150_000.0,
}
COLORS = {
    "500k": "#3DDB8A",
    "300k": "#F5B042",
    "150k": "#FF6B81",
}
SPENT_COLOR = "#8B93A7"
BG = "#0B1020"
GRID = "#1C2438"
TEXT = "#E8ECF4"
MUTED = "#8B93A7"


def download_prices(start: str, end: str) -> pd.DataFrame:
    """Precios ajustados (total return). IEMG usa EEM como proxy antes de oct-2012."""
    import yfinance as yf

    tickers = ["SPYG", "SMH", "BRK-B", "IEMG", "VTI", "EEM"]
    start_dl = pd.Timestamp(start) - pd.Timedelta(days=40)
    frames = {}
    last_err = None
    for t in tickers:
        for attempt in range(3):
            try:
                s = yf.download(
                    t,
                    start=start_dl,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                if s is None or s.empty:
                    raise RuntimeError(f"sin datos {t}")
                frames[t] = s["Close"] if "Close" in s.columns else s.xs("Close", axis=1, level=0)
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                import time as _time
                _time.sleep(1.2 * (attempt + 1))
        if t not in frames:
            raise RuntimeError(f"No se pudo descargar {t}: {last_err}")
    raw = pd.concat(frames, axis=1)
    raw.columns = tickers

    iemg = raw["IEMG"].copy()
    eem_ret = raw["EEM"].pct_change()
    first = iemg.first_valid_index()
    if first is None:
        raise RuntimeError("No hay historia de IEMG para construir el proxy.")
    proxy = iemg.copy()
    idx = raw.index
    pos = int(idx.get_loc(first))
    for i in range(pos - 1, -1, -1):
        r = eem_ret.iloc[i + 1]
        if pd.isna(r) or r <= -0.99:
            proxy.iloc[i] = proxy.iloc[i + 1]
        else:
            proxy.iloc[i] = proxy.iloc[i + 1] / (1.0 + r)

    prices = pd.DataFrame(
        {
            "SPYG": raw["SPYG"],
            "SMH": raw["SMH"],
            "BRK-B": raw["BRK-B"],
            "IEMG": proxy,
            "VTI": raw["VTI"],
        }
    ).dropna()
    prices = prices.loc[start:]
    if prices.empty:
        raise RuntimeError(f"No hay precios entre {start} y {end}.")
    return prices


def monthly_withdrawal(n_prev_withdrawals: int, base: float, cola: float) -> float:
    """Año 1 (retiros 0-11): base. Año 2+: base * (1+cola)**(año-1)."""
    year_index = n_prev_withdrawals // 12
    return float(base * ((1.0 + cola) ** year_index))


def simulate(
    prices: pd.DataFrame,
    base_withdrawal: float = 1000.0,
    cola: float = 0.03,
) -> tuple[pd.DataFrame, dict]:
    rets = prices.pct_change()
    dates = prices.index
    month_starts = set(dates.to_series().groupby(dates.to_period("M")).head(1).index)

    values = {k: np.zeros(len(dates)) for k in INITIALS}
    holdings = {k: (INITIALS[k] * WEIGHTS).copy() for k in INITIALS}
    depleted_at: dict[str, pd.Timestamp] = {}
    withdrawals_done = {k: 0.0 for k in INITIALS}
    n_calendar = 0
    wd_path = np.zeros(len(dates))
    spent_path = np.zeros(len(dates))
    running_spent = 0.0
    current_wd = 0.0

    for i, dt in enumerate(dates):
        if i > 0:
            r = rets.iloc[i].reindex(WEIGHTS.index).fillna(0.0)
            for k in INITIALS:
                if k in depleted_at:
                    values[k][i] = 0.0
                    continue
                holdings[k] = holdings[k] * (1.0 + r)

        if dt in month_starts:
            current_wd = monthly_withdrawal(n_calendar, base_withdrawal, cola)
            n_calendar += 1
            wd_path[i] = current_wd
            running_spent += current_wd
        spent_path[i] = running_spent

        for k in INITIALS:
            if k in depleted_at:
                values[k][i] = 0.0
                continue
            total = float(holdings[k].sum())
            if dt in month_starts:
                amount = current_wd
                if total <= amount:
                    withdrawals_done[k] += max(total, 0.0)
                    holdings[k][:] = 0.0
                    values[k][i] = 0.0
                    depleted_at[k] = dt
                    continue
                total -= amount
                withdrawals_done[k] += amount
                holdings[k] = total * WEIGHTS
            values[k][i] = float(holdings[k].sum())

    df = pd.DataFrame(values, index=dates)
    df["spent"] = spent_path
    df["withdrawal"] = pd.Series(wd_path, index=dates).replace(0, np.nan).ffill()
    meta = {
        "depleted_at": depleted_at,
        "withdrawals_done": withdrawals_done,
        "n_withdrawals": n_calendar,
        "final": {k: float(df[k].iloc[-1]) for k in INITIALS},
        "final_monthly_withdrawal": float(df["withdrawal"].iloc[-1]),
        "total_spent_calendar": float(df["spent"].iloc[-1]),
        "base_withdrawal": base_withdrawal,
        "cola": cola,
        "start": str(dates[0].date()),
        "end": str(dates[-1].date()),
        "weights": WEIGHTS.round(4).to_dict(),
    }
    return df, meta


def fmt_money(x: float) -> str:
    # Evitar "$...$" porque matplotlib lo interpreta como mathtext.
    if abs(x) >= 1_000_000:
        txt = f"USD {x/1_000_000:.2f}M"
        return txt.replace(".00M", "M")
    if abs(x) >= 1_000:
        return f"USD {x/1_000:.0f}K"
    return f"USD {x:.0f}"


def _style(ax) -> None:
    ax.set_facecolor(BG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7, alpha=0.9)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)


def build_figure(df: pd.DataFrame, meta: dict, upto=None, show_end_labels=True, dpi=160):
    plot_df = df if upto is None else df.loc[:upto]
    fig, ax = plt.subplots(figsize=(10.2, 12.8), dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    start_lbl = pd.Timestamp(meta["start"]).strftime("%b %Y")
    end_lbl = pd.Timestamp(meta["end"]).strftime("%b %Y")
    cola_pct = meta["cola"] * 100

    fig.text(0.5, 0.965, "Made for eToro  ·  simulación histórica", ha="center", va="top",
             color=MUTED, fontsize=9, fontname="DejaVu Sans")
    fig.text(0.5, 0.932, "¿CUÁNTO PORTAFOLIO NECESITAS", ha="center", va="top",
             color=TEXT, fontsize=18, fontweight="bold", fontname="DejaVu Sans")
    fig.text(0.5, 0.905, "PARA RETIRAR $1.000 AL MES?", ha="center", va="top",
             color=TEXT, fontsize=18, fontweight="bold", fontname="DejaVu Sans")
    fig.text(
        0.5, 0.878,
        f"{start_lbl} – {end_lbl}   ·   retiro +{cola_pct:.0f}% anual desde el año 2   ·   "
        "SPYG 33% · SMH 21% · BRK.B 21% · IEMG 16% · VTI 9%",
        ha="center", va="top", color=MUTED, fontsize=7.6, fontname="DejaVu Sans",
    )

    ax.set_position([0.11, 0.12, 0.70, 0.72])
    x = plot_df.index
    ax.plot(x, plot_df["spent"], linestyle=(0, (5, 5)), color=SPENT_COLOR, linewidth=1.6, zorder=2, alpha=0.85)
    for k in ("500k", "300k", "150k"):
        ax.plot(x, plot_df[k], color=COLORS[k], linewidth=2.15, solid_capstyle="round", zorder=3)

    for k, dt in meta["depleted_at"].items():
        if upto is not None and dt > plot_df.index[-1]:
            continue
        ax.scatter([dt], [0], s=90, color="#F5B042", zorder=5, edgecolors="white", linewidths=0.6)
        ax.annotate("✕✕  Game over", xy=(dt, 0), xytext=(8, 12), textcoords="offset points",
                    color="#F5B042", fontsize=8, fontweight="bold")

    trough_idx = plot_df["150k"].idxmin() if len(plot_df) else None
    if trough_idx is not None:
        tv = float(plot_df.loc[trough_idx, "150k"])
        if 0 < tv < INITIALS["150k"] * 0.7:
            ax.scatter([trough_idx], [tv], s=28, color=COLORS["150k"], zorder=6,
                       edgecolors="white", linewidths=0.4)
            ax.annotate(
                f"{trough_idx.strftime('%b-%Y')}\n{fmt_money(tv)}",
                xy=(trough_idx, tv), xytext=(14, 14), textcoords="offset points",
                color=COLORS["150k"], fontsize=7.5, ha="left", va="bottom",
            )

    _style(ax)
    ax.set_xlim(df.index[0], df.index[-1])
    ymax = float(df[["500k", "300k", "150k", "spent"]].max().max()) * 1.12
    ax.set_ylim(-ymax * 0.02, ymax)

    def _ytick(v, _p):
        if v >= 1_000_000:
            return f"${v/1_000_000:.1f}M".replace(".0M", "M")
        if v >= 1_000:
            return f"${v/1_000:.0f}K"
        return "$0"

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_ytick))
    years = max(1, (df.index[-1].year - df.index[0].year) // 5)
    ax.xaxis.set_major_locator(mdates.YearLocator(max(2, years)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    if show_end_labels and upto is None:
        last = plot_df.iloc[-1]
        ax.text(plot_df.index[-1], last["spent"], f"  gastado {fmt_money(last['spent'])}",
                color=SPENT_COLOR, fontsize=8.2, ha="left", va="center")
        for k in ("500k", "300k", "150k"):
            y = last[k] if last[k] > 0 else ymax * 0.015
            end = fmt_money(last[k]) if last[k] > 0 else "$0"
            ax.text(plot_df.index[-1], y, f"  ${k.upper()} → {end}",
                    color=COLORS[k], fontsize=9.5, ha="left", va="center", fontweight="bold")
        for k, cap in INITIALS.items():
            ax.text(df.index[0], cap, f"${k.upper()}  ", color=COLORS[k],
                    fontsize=9, ha="right", va="bottom")

    if upto is not None:
        last = plot_df.iloc[-1]
        fig.text(0.88, 0.86, upto.strftime("%Y"), ha="right", color=TEXT,
                 fontsize=22, fontweight="bold", alpha=0.9)
        for k in ("500k", "300k", "150k"):
            y = last[k] if last[k] > 0 else ymax * 0.015
            ax.text(df.index[-1], y, f"  {fmt_money(last[k])}", color=COLORS[k],
                    fontsize=9, ha="left", va="center", fontweight="bold")
        for k, cap in INITIALS.items():
            ax.text(df.index[0], cap, f"${k.upper()}  ", color=COLORS[k],
                    fontsize=9, ha="right", va="bottom")

    n_years = (pd.Timestamp(meta["end"]) - pd.Timestamp(meta["start"])).days / 365.25
    if meta["depleted_at"]:
        bits = [f"${k} se agota en {dt.strftime('%b %Y')}" for k, dt in meta["depleted_at"].items()]
        line1 = "  ·  ".join(bits) + ".  Game over."
    else:
        final_150 = meta["final"]["150k"]
        if final_150 < INITIALS["150k"] * 0.5:
            line1 = (
                f"$150k termina en {fmt_money(final_150)} y se va agotando. "
                f"$300k y $500k sí sostienen el retiro +{cola_pct:.0f}%."
            )
        else:
            line1 = f"Los tres niveles sobreviven {n_years:.1f} años con retiro indexado al {cola_pct:.0f}%."
    fig.text(
        0.5, 0.048,
        line1 + "\n"
        f"Año 1: US\\${meta['base_withdrawal']:,.0f}/mes  ·  último retiro: "
        f"US\\${meta['final_monthly_withdrawal']:,.0f}/mes  ·  sin impuestos  ·  rebalance mensual",
        ha="center", va="center", color=MUTED, fontsize=7.3, linespacing=1.45,
    )
    fig.text(
        0.5, 0.018,
        "Backtest hipotético de la asignación actual. Rentabilidades pasadas no garantizan resultados futuros.",
        ha="center", color="#5C6478", fontsize=6.6,
    )
    return fig, ax


def save_static(df: pd.DataFrame, meta: dict, path: Path) -> Path:
    fig, _ = build_figure(df, meta, show_end_labels=True, dpi=160)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return path


def save_gif(df: pd.DataFrame, meta: dict, path: Path, n_frames: int = 72) -> Path:
    from PIL import Image

    tmp = path.parent / "_frames"
    tmp.mkdir(exist_ok=True)
    idx = df.index
    picks = np.unique(np.linspace(10, len(idx) - 1, n_frames).astype(int))
    files = []
    for i, p in enumerate(picks):
        fig, _ = build_figure(df, meta, upto=idx[p], show_end_labels=False, dpi=110)
        fp = tmp / f"f{i:03d}.png"
        fig.savefig(fp, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.22)
        plt.close(fig)
        files.append(fp)

    imgs = [Image.open(f).convert("P", palette=Image.ADAPTIVE, colors=80) for f in files]
    w = min(im.size[0] for im in imgs)
    h = min(im.size[1] for im in imgs)
    imgs = [im.crop((0, 0, w, h)) for im in imgs]
    durations = [85] * (len(imgs) - 1) + [1800]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=durations, loop=0, disposal=2)
    for f in files:
        f.unlink()
    tmp.rmdir()
    return path


def print_summary(df: pd.DataFrame, meta: dict) -> None:
    print(f"Periodo     : {meta['start']} → {meta['end']}")
    print(f"COLA        : {meta['cola']*100:.1f}% anual desde el año 2")
    print(f"Retiro año 1: ${meta['base_withdrawal']:,.0f}/mes")
    print(f"Retiro final: ${meta['final_monthly_withdrawal']:,.0f}/mes")
    print(f"Gastado     : ${meta['total_spent_calendar']:,.0f}")
    print("-" * 56)
    print(f"{'Nivel':<8} {'Final':>12} {'Mínimo':>12} {'Retirado':>12} {'Estado':>16}")
    for k in ("150k", "300k", "500k"):
        mn = df[k].min()
        estado = f"agotado {meta['depleted_at'][k].date()}" if k in meta["depleted_at"] else "sobrevive"
        print(f"{k:<8} {fmt_money(meta['final'][k]):>12} {fmt_money(mn):>12} "
              f"{fmt_money(meta['withdrawals_done'][k]):>12} {estado:>16}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simula retiro indexado sobre el portafolio.")
    p.add_argument("--start", default="2006-09-01")
    p.add_argument("--end", default="2026-08-28")
    p.add_argument("--base", type=float, default=1000.0, help="Retiro mensual del año 1")
    p.add_argument("--cola", type=float, default=0.03, help="Incremento anual del retiro desde el año 2")
    p.add_argument("--gif", action="store_true", help="También genera GIF animado")
    p.add_argument("--outdir", default="output")
    p.add_argument("--frames", type=int, default=72)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    print("Descargando precios…")
    prices = download_prices(args.start, args.end)
    df, meta = simulate(prices, base_withdrawal=args.base, cola=args.cola)
    print_summary(df, meta)
    stem = f"retiro_{int(args.base)}_{int(args.cola*100)}pct_{args.start[:4]}"
    png = save_static(df, meta, out / f"{stem}.png")
    print("PNG:", png)
    df.to_csv(out / f"{stem}.csv")
    if args.gif:
        gif = save_gif(df, meta, out / f"{stem}.gif", n_frames=args.frames)
        print("GIF:", gif)


if __name__ == "__main__":
    main()
