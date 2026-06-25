from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Patch


BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "scarf_plot_input.csv"
OUTPUT_PDF = BASE_DIR / "five_participants_by_condition_scarf.pdf"

N_PARTICIPANTS = 5
XMAX_MIN = 25.0

REQUIRED_CONDITIONS = ["control", "overfitting", "correct"]
PLOT_CONDITION_ORDER = ["correct", "overfitting", "control"]

AOI_ORDER = [
    "Patch",
    "Browser",
    "Test and Runtime Feedback",
    "Tests",
    "Source Code",
    "Other",
]

AOI_COLORS = {
    "Patch": "#d7301f",
    "Browser": "#3182bd",
    "Test and Runtime Feedback": "#31a354",
    "Tests": "#fd8d3c",
    "Source Code": "#756bb1",
    "Other": "#bdbdbd",
}


def load_scarf_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = ["PID", "task_no", "condition", "start_min", "end_min", "scarf_aoi"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df["PID"] = df["PID"].astype(str)
    df["task_no"] = df["task_no"].astype(int)
    df["condition"] = df["condition"].astype(str)
    df["trial_id"] = df["PID"] + "_t" + df["task_no"].astype(str)
    df["scarf_aoi"] = df["scarf_aoi"].where(df["scarf_aoi"].isin(AOI_ORDER), "Other")

    return df


def pick_participants(df: pd.DataFrame, n: int) -> list[str]:
    trial_map = (
        df[["PID", "condition"]]
        .drop_duplicates()
        .groupby("PID")["condition"]
        .apply(set)
    )

    selected = [
        pid for pid, conds in trial_map.items() if set(REQUIRED_CONDITIONS).issubset(conds)
    ]
    selected = sorted(selected)
    return selected[:n]


def compute_draw_window(start_min: float, end_min: float, xmax: float):
    draw_start = float(start_min)
    draw_end = min(float(end_min), xmax)
    if draw_start >= xmax:
        return None
    if draw_end <= draw_start:
        return None
    return draw_start, draw_end


def draw_trial_scarf(ax: plt.Axes, trial_df: pd.DataFrame, title: str) -> None:
    trial_order = (
        trial_df[["trial_id", "task_no"]]
        .drop_duplicates()
        .sort_values("task_no")
        ["trial_id"]
        .tolist()
    )

    y_lookup = {trial_id: i for i, trial_id in enumerate(trial_order)}
    bar_h = 0.8

    for row in trial_df.itertuples(index=False):
        window = compute_draw_window(row.start_min, row.end_min, XMAX_MIN)
        if window is None:
            continue

        draw_start, draw_end = window
        color = AOI_COLORS.get(row.scarf_aoi, AOI_COLORS["Other"])
        ax.broken_barh(
            [(draw_start, draw_end - draw_start)],
            (y_lookup[row.trial_id] - bar_h / 2, bar_h),
            facecolors=color,
            edgecolors="none",
        )

    ax.set_xlim(0, XMAX_MIN)
    ax.set_yticks(range(len(trial_order)))
    ax.set_yticklabels(trial_order, fontsize=8)
    ax.grid(axis="x", alpha=0.2)
    ax.set_xlabel("Minutes from task start")
    ax.set_title(title, fontsize=11, fontweight="bold")


def draw_empty_panel(ax: plt.Axes, title: str) -> None:
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlim(0, XMAX_MIN)
    ax.set_yticks([])
    ax.set_xlabel("Minutes from task start")
    ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center", fontsize=10)
    ax.grid(axis="x", alpha=0.2)


def add_shared_legend(fig: plt.Figure) -> None:
    handles = [Patch(facecolor=AOI_COLORS[a], label=a) for a in AOI_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.02))


def make_pdf(df: pd.DataFrame, participants: list[str], output_pdf: Path) -> None:
    with PdfPages(output_pdf) as pdf:
        for pid in participants:
            person_df = df[df["PID"] == pid].copy()

            fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=True)

            for ax, condition in zip(axes, PLOT_CONDITION_ORDER):
                cond_df = person_df[person_df["condition"] == condition].copy()
                panel_title = condition.title()
                if cond_df.empty:
                    draw_empty_panel(ax, panel_title)
                else:
                    draw_trial_scarf(ax, cond_df, panel_title)

            fig.suptitle(f"Participant {pid}: Scarf Plots by Condition", fontsize=14, fontweight="bold")
            add_shared_legend(fig)
            fig.tight_layout(rect=[0.02, 0.08, 0.98, 0.92])

            pdf.savefig(fig)
            plt.close(fig)


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_CSV}")

    df = load_scarf_data(INPUT_CSV)
    participants = pick_participants(df, N_PARTICIPANTS)

    if len(participants) < N_PARTICIPANTS:
        raise ValueError(
            f"Found only {len(participants)} participants with all required conditions; "
            f"need {N_PARTICIPANTS}."
        )

    make_pdf(df, participants, OUTPUT_PDF)
    print(f"Wrote {OUTPUT_PDF.name} for participants: {', '.join(participants)}")


if __name__ == "__main__":
    main()
