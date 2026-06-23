import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


INPUT_SCARF_CSV = "scarf_plot_input.csv"
INPUT_TIMING_CSV = "../timing_correctness_data.csv"
OUTPUT_DIR = Path(".")
OUTPUT_BY_CONDITION = OUTPUT_DIR / "gaze_proportion_by_condition.png"
OUTPUT_BY_CORRECTNESS = OUTPUT_DIR / "gaze_proportion_by_correctness.png"
BIN_WIDTH = 0.05

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

CONDITION_ORDER = ["control", "overfitting", "correct"]
CORRECTNESS_ORDER = ["Incorrect", "Correct"]


def load_data(scarf_csv: str, timing_csv: str) -> pd.DataFrame:
	scarf_df = pd.read_csv(scarf_csv)
	timing_df = pd.read_csv(timing_csv, usecols=["PID", "task_no", "correct"])

	timing_df["correct"] = timing_df["correct"].map({"Y": "Correct", "N": "Incorrect"})

	merged = scarf_df.merge(timing_df, on=["PID", "task_no"], how="left")
	merged = merged.dropna(subset=["correct"])
	merged["task_span_min"] = merged["end_min"].groupby([merged["PID"], merged["task_no"]]).transform("max")
	merged["task_progress_start"] = merged["start_min"] / merged["task_span_min"]
	merged["task_progress_end"] = merged["end_min"] / merged["task_span_min"]
	merged["task_progress_start"] = merged["task_progress_start"].clip(0, 1)
	merged["task_progress_end"] = merged["task_progress_end"].clip(0, 1)
	return merged


def explode_to_bins(df: pd.DataFrame, bin_width: float) -> pd.DataFrame:
	bins = np.arange(0, 1 + bin_width, bin_width)
	bin_labels = bins[:-1]
	rows = []

	for row in df.itertuples(index=False):
		if row.scarf_aoi not in AOI_ORDER:
			continue

		start = float(row.task_progress_start)
		end = float(row.task_progress_end)
		if end <= start:
			continue

		for bin_start in bin_labels:
			bin_end = min(bin_start + bin_width, 1.0)
			overlap = max(0.0, min(end, bin_end) - max(start, bin_start))
			if overlap > 0:
				rows.append(
					{
						"PID": row.PID,
						"task_no": row.task_no,
						"condition": row.condition,
						"correct": row.correct,
						"AOI": row.scarf_aoi,
						"bin_start": bin_start,
						"weight": overlap,
					}
				)

	return pd.DataFrame(rows)


def summarize_bin_occupancy(exploded: pd.DataFrame, facet_col: str, facet_order: list[str]) -> pd.DataFrame:
	grouped = (
		exploded.groupby([facet_col, "bin_start", "AOI"], as_index=False)["weight"]
		.sum()
	)

	totals = grouped.groupby([facet_col, "bin_start"], as_index=False)["weight"].sum().rename(
		columns={"weight": "total_weight"}
	)

	out = grouped.merge(totals, on=[facet_col, "bin_start"], how="left")
	out["proportion"] = out["weight"] / out["total_weight"]
	out[facet_col] = pd.Categorical(out[facet_col], categories=facet_order, ordered=True)
	out["AOI"] = pd.Categorical(out["AOI"], categories=AOI_ORDER, ordered=True)
	return out.sort_values([facet_col, "bin_start", "AOI"])


def plot_stacked_area(summary: pd.DataFrame, facet_col: str, facet_order: list[str], output_path: Path, title: str):
	n_panels = len(facet_order)
	fig, axes = plt.subplots(n_panels, 1, figsize=(14, max(4, 3.8 * n_panels)), sharex=True, sharey=True)
	if n_panels == 1:
		axes = [axes]

	x = np.arange(0, 1, BIN_WIDTH)

	for ax, facet_value in zip(axes, facet_order):
		panel = summary[summary[facet_col] == facet_value]
		if panel.empty:
			ax.set_axis_off()
			continue

		stacked = []
		for aoi in AOI_ORDER:
			series = (
				panel[panel["AOI"] == aoi]
				.set_index("bin_start")["proportion"]
				.reindex(x, fill_value=0)
				.to_numpy()
			)
			stacked.append(series)

		ax.stackplot(x, stacked, colors=[AOI_COLORS[aoi] for aoi in AOI_ORDER], alpha=0.95)
		ax.set_ylim(0, 1)
		ax.set_ylabel("AOI share")
		ax.set_title(str(facet_value))
		ax.grid(axis="y", alpha=0.2)

	axes[-1].set_xlabel("Normalized task progress")
	axes[-1].set_xticks(np.linspace(0, 1, 6))
	axes[-1].set_xticklabels(["0%", "20%", "40%", "60%", "80%", "100%"])
	fig.suptitle(title, y=0.995)
	handles = [plt.Line2D([0], [0], color=AOI_COLORS[aoi], lw=8) for aoi in AOI_ORDER]
	fig.legend(handles, AOI_ORDER, loc="upper right", frameon=False)
	plt.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def main():
	data = load_data(INPUT_SCARF_CSV, INPUT_TIMING_CSV)
	exploded = explode_to_bins(data, BIN_WIDTH)

	if exploded.empty:
		raise ValueError("No occupancy data produced from the current scarf input.")

	by_condition = summarize_bin_occupancy(exploded, "condition", CONDITION_ORDER)
	by_correctness = summarize_bin_occupancy(exploded, "correct", CORRECTNESS_ORDER)

	plot_stacked_area(
		by_condition,
		facet_col="condition",
		facet_order=CONDITION_ORDER,
		output_path=OUTPUT_BY_CONDITION,
		title="Normalized-time AOI occupancy by condition",
	)
	plot_stacked_area(
		by_correctness,
		facet_col="correct",
		facet_order=CORRECTNESS_ORDER,
		output_path=OUTPUT_BY_CORRECTNESS,
		title="Normalized-time AOI occupancy by correctness",
	)

	print(f"Wrote {OUTPUT_BY_CONDITION}")
	print(f"Wrote {OUTPUT_BY_CORRECTNESS}")


if __name__ == "__main__":
	main()
