import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

AOI_COLORS = {
    "Patch": "#d7301f",
    "Browser": "#3182bd",
    "Test and Runtime Feedback": "#31a354",
    "Tests": "#fd8d3c",
    "Source Code": "#756bb1",
    "Missing": "#ffffff",
    "Other": "#d9d9d9",
}

AOI_ORDER = [
    "Patch",
    "Browser",
    "Test and Runtime Feedback",
    "Tests",
    "Source Code",
    "Other",
]

SCARF_INPUT_CSV = "aggregated_metrics/scarf_plot_input.csv"
PHASE_INPUT_CSV = "scarf_figures/P34t1_workshop.csv"
OUTPUT_PNG = "scarf_figures/P34t1_annotated_scarf.png"
TRIAL_PID = "P34"
TRIAL_TASK = 1
XMAX_MIN = 25.0
PLOT_SHIFT_MIN = 0.0


def parse_ts_to_min(ts: str):
    if pd.isna(ts):
        return None
    text = str(ts).strip()
    if not text:
        return None

    parts = text.split(":")
    if len(parts) != 2:
        return None

    mins = float(parts[0])
    secs = float(parts[1])
    return mins + secs / 60.0


def shifted_min(value: float) -> float:
    return max(0.0, float(value) - PLOT_SHIFT_MIN)


def load_trial_scarf_data() -> pd.DataFrame:
    df = pd.read_csv(SCARF_INPUT_CSV)
    trial_df = df[(df["PID"] == TRIAL_PID) & (df["task_no"] == TRIAL_TASK)].copy()

    if trial_df.empty:
        raise ValueError(f"No scarf rows found for {TRIAL_PID} task {TRIAL_TASK} in {SCARF_INPUT_CSV}")

    trial_df["scarf_aoi"] = trial_df["scarf_aoi"].fillna("Missing")
    trial_df["scarf_aoi"] = trial_df["scarf_aoi"].where(trial_df["scarf_aoi"].isin(AOI_ORDER), "Other")
    return trial_df


def load_phase_segments() -> pd.DataFrame:
    phases = pd.read_csv(PHASE_INPUT_CSV)

    # Keep only the annotation columns we need, regardless of the first extra column.
    required = ["start_ts", "end_ts", "Label"]
    missing = [c for c in required if c not in phases.columns]
    if missing:
        raise ValueError(f"Phase file is missing columns: {missing}")

    phases = phases[required].copy()
    phases["Label"] = phases["Label"].fillna("").astype(str).str.strip()
    phases = phases[phases["Label"] != ""]

    phases["start_min"] = phases["start_ts"].map(parse_ts_to_min)
    phases["end_min"] = phases["end_ts"].map(parse_ts_to_min)
    phases = phases.dropna(subset=["start_min", "end_min"]).copy()

    phases = phases[phases["end_min"] > phases["start_min"]].copy()
    phases = phases.sort_values(["start_min", "end_min"]).reset_index(drop=True)

    if phases.empty:
        raise ValueError("No valid phase segments found after parsing start_ts/end_ts/Label.")

    return phases


def load_special_events(phases: pd.DataFrame) -> pd.DataFrame:
    special_specs = [
        ("try_fix_start_ts", "try_fix_end_ts", "try fix"),
        (
            "triangulate_patch_start_ts",
            "triangulate_patch_end_ts",
            "triangulate patch",
        ),
    ]

    event_rows = []
    for row in phases.itertuples(index=False):
        for start_col, end_col, label in special_specs:
            if start_col not in phases.columns or end_col not in phases.columns:
                continue

            start_val = getattr(row, start_col)
            end_val = getattr(row, end_col)
            if pd.isna(start_val) or pd.isna(end_val):
                continue

            start_min = parse_ts_to_min(start_val)
            end_min = parse_ts_to_min(end_val)
            if start_min is None or end_min is None or end_min <= start_min:
                continue

            event_rows.append(
                {
                    "label": label,
                    "start_min": start_min,
                    "end_min": end_min,
                }
            )

    if not event_rows:
        return pd.DataFrame(columns=["label", "start_min", "end_min"])

    return pd.DataFrame(event_rows).sort_values(["start_min", "end_min"]).reset_index(drop=True)


def draw_trial_scarf_with_phases(trial_df: pd.DataFrame, phases: pd.DataFrame, special_events: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(16, 4))
    bar_y = 0.0
    bar_h = 0.11
    bar_bottom = bar_y - bar_h / 2
    bar_top = bar_y + bar_h / 2
    label_offset = 0.11
    special_label_offset = 0.20

    # Draw boundary ticks outside the scarf bar (above and below), not through it.
    boundaries = sorted(set(shifted_min(v) for v in phases["start_min"].tolist() + phases["end_min"].tolist()))
    for x in boundaries:
        if 0 <= x <= XMAX_MIN:
            ax.plot(
                [x, x],
                [bar_top + 0.01, bar_top + 0.07],
                color="#111111",
                linewidth=1.0,
                alpha=0.85,
                zorder=3,
                clip_on=False,
            )
            ax.plot(
                [x, x],
                [bar_bottom - 0.01, bar_bottom - 0.07],
                color="#111111",
                linewidth=1.0,
                alpha=0.85,
                zorder=3,
                clip_on=False,
            )

    for row in trial_df.itertuples(index=False):
        start = shifted_min(row.start_min)
        end = min(shifted_min(row.end_min), XMAX_MIN)
        if start >= XMAX_MIN or end <= start:
            continue

        ax.broken_barh(
            [(start, end - start)],
            (bar_y - bar_h / 2, bar_h),
            facecolors=AOI_COLORS.get(row.scarf_aoi, AOI_COLORS["Other"]),
            edgecolors="none",
            zorder=1,
        )

    # Thin outline around the scarf strip only.
    ax.add_patch(
        plt.Rectangle(
            (0, bar_bottom),
            XMAX_MIN,
            bar_h,
            fill=False,
            edgecolor="#666666",
            linewidth=0.7,
            zorder=2,
            clip_on=False,
        )
    )

    # Alternate labels above and below the scarf to reduce crowding.
    for idx, row in enumerate(phases.itertuples(index=False)):
        x_mid = (shifted_min(row.start_min) + shifted_min(row.end_min)) / 2.0
        if x_mid > XMAX_MIN:
            continue

        is_top = idx % 2 == 0
        y = bar_top + label_offset if is_top else bar_bottom - label_offset
        va = "bottom" if is_top else "top"
        ha = "center"

        ax.text(
            x_mid,
            y,
            str(row.Label),
            fontsize=8.5,
            fontweight="bold",
            rotation=0,
            ha=ha,
            va=va,
            color="#111111",
            zorder=4,
            clip_on=False,
        )

    # Special events get small arrow labels pointing to the middle of their own intervals.
    for idx, row in enumerate(special_events.itertuples(index=False)):
        x_mid = (shifted_min(row.start_min) + shifted_min(row.end_min)) / 2.0
        if x_mid > XMAX_MIN:
            continue

        is_top = idx % 2 == 0
        y_text = bar_top + special_label_offset if is_top else bar_bottom - special_label_offset

        ax.annotate(
            row.label,
            xy=(x_mid, bar_y),
            xytext=(x_mid, y_text),
            textcoords="data",
            ha="center",
            va="bottom" if is_top else "top",
            fontsize=7,
            color="#222222",
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.7, shrinkA=0, shrinkB=0),
            zorder=5,
            clip_on=False,
        )

    ax.set_xlim(0, XMAX_MIN)
    # Keep the frame narrow while leaving room for top and bottom labels.
    ax.set_ylim(bar_bottom - 0.22, bar_top + 0.22)
    ax.set_yticks([])
    ax.set_xlabel("Minutes from task start", labelpad=10)
    ax.grid(axis="x", alpha=0.25, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    handles = [Patch(facecolor=AOI_COLORS[a], edgecolor="#999999" if a == "Missing" else "none", label=a) for a in AOI_ORDER]
    ax.legend(
        handles=handles,
        title="AOI key",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        ncol=1,
        frameon=False,
        fontsize=8,
        borderaxespad=0.0,
    )

    fig.text(0.015, 0.58, "P34 overfitting", rotation=90, va="center", ha="left", fontsize=10)
    fig.subplots_adjust(left=0.065, right=0.80, bottom=0.30, top=0.72)
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    trial_df = load_trial_scarf_data()
    phases = load_phase_segments()
    special_events = load_special_events(pd.read_csv(PHASE_INPUT_CSV))
    draw_trial_scarf_with_phases(trial_df, phases, special_events)
    print(f"Wrote {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
