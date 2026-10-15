"""Small drawing helpers for the SRS diagrams (matplotlib). Coordinates are in inches so layouts are easy to reason about."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

TEAL, TEAL_LIGHT, DARK, GRAY, AMBER, GREEN, BLUE, VIOLET = "#0e7490", "#e6f9fc", "#0f2a3d", "#64748b", "#fff4d6", "#e3f6ec", "#e3effd", "#efe9fb"
OUT = "D:/helth_wise_AI/docs/srs_build/img/"
plt.rcParams["font.family"] = "DejaVu Sans"


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return fig, ax


def save(fig, name):
    fig.savefig(OUT + name, dpi=200, facecolor="white")
    plt.close(fig)
    print("saved", name)


def box(ax, x, y, w, h, text="", fc=TEAL_LIGHT, ec=TEAL, fs=8, bold=False, round_=0.08, lw=1.3, z=3, color=DARK, ha="center"):
    """Rounded rectangle centred at (x, y)."""
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle=f"round,pad=0,rounding_size={round_}", fc=fc, ec=ec, lw=lw, zorder=z))
    if text:
        ax.text(x, y, text, ha=ha, va="center", fontsize=fs, fontweight="bold" if bold else "normal", color=color, zorder=z + 1, linespacing=1.25)


def ellipse(ax, x, y, w, h, text="", fc="white", ec=TEAL, fs=7.5, z=3, lw=1.2, bold=False):
    ax.add_patch(Ellipse((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=z))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, zorder=z + 1, linespacing=1.2, color=DARK, fontweight="bold" if bold else "normal")


def circle(ax, x, y, r, text="", fc=TEAL_LIGHT, ec=TEAL, fs=9, z=3, lw=1.8, bold=True):
    ax.add_patch(Circle((x, y), r, fc=fc, ec=ec, lw=lw, zorder=z))
    if text:
        ax.text(x, y, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", color=DARK, zorder=z + 1, linespacing=1.25)


def diamond(ax, x, y, w, h, text="", fc=AMBER, ec="#c58a00", fs=7, z=3):
    ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True, fc=fc, ec=ec, lw=1.2, zorder=z))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, zorder=z + 1, linespacing=1.15, color=DARK)


def actor(ax, x, y, label, fs=8):
    """Stick figure with its head at about (x, y + 0.42)."""
    ax.add_patch(Circle((x, y + 0.42), 0.12, fc="white", ec=DARK, lw=1.4, zorder=4))
    ax.plot([x, x], [y + 0.30, y - 0.05], color=DARK, lw=1.4, zorder=4)
    ax.plot([x - 0.2, x + 0.2], [y + 0.20, y + 0.20], color=DARK, lw=1.4, zorder=4)
    ax.plot([x, x - 0.16], [y - 0.05, y - 0.3], color=DARK, lw=1.4, zorder=4)
    ax.plot([x, x + 0.16], [y - 0.05, y - 0.3], color=DARK, lw=1.4, zorder=4)
    ax.text(x, y - 0.5, label, ha="center", va="top", fontsize=fs, fontweight="bold", color=DARK, zorder=4, linespacing=1.15)


def arrow(ax, p1, p2, label=None, ls="-", color=GRAY, rad=0.0, fs=6.8, lpos=0.5, loff=(0, 0.1), head="-|>", lw=1.1, z=2, ha="center", bg=True):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=head, mutation_scale=9, lw=lw, color=color, linestyle=ls, connectionstyle=f"arc3,rad={rad}", zorder=z))
    if label:
        x = p1[0] + (p2[0] - p1[0]) * lpos + loff[0]
        y = p1[1] + (p2[1] - p1[1]) * lpos + loff[1]
        ax.text(x, y, label, ha=ha, va="center", fontsize=fs, color="#334155", zorder=z + 5, linespacing=1.15,
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9) if bg else None)


def line(ax, p1, p2, color=GRAY, lw=1.0, ls="-", z=1):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, lw=lw, linestyle=ls, zorder=z)
