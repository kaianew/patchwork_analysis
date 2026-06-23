from __future__ import annotations

from pathlib import Path
from textwrap import fill

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "transition_table_by_condition.csv"
OUTPUT_PDF = BASE_DIR / "transition_correct_vs_control.pdf"


def format_table(df: pd.DataFrame, total_transitions: int) -> pd.DataFrame:
	work = df.copy()
	work = work[work["count"] > 0].copy()
	work = work.sort_values(["count"], ascending=[False]).reset_index(drop=True)
	work = work.head(10).copy()
	work["rank"] = work.index + 1
	work["transition"] = (work["from_aoi"] + " -> " + work["to_aoi"]).map(lambda s: fill(s, width=28))
	# Proportion out of total transitions across all conditions
	work["proportion"] = ((work["count"] / total_transitions) * 100).round(2).astype(str) + "%"
	return work[["rank", "transition", "count", "proportion"]]


def draw_table(ax: plt.Axes, table_df: pd.DataFrame, title: str) -> None:
	ax.axis("off")

	if table_df.empty:
		ax.text(0.5, 0.5, "No transitions", ha="center", va="center", fontsize=11)
		ax.set_title(title, fontweight="bold", fontsize=12, pad=10)
		return

	table = ax.table(
		cellText=table_df.values,
		colLabels=table_df.columns,
		loc="center",
		cellLoc="left",
		colLoc="left",
		colWidths=[0.10, 0.56, 0.12, 0.22],
	)
	table.auto_set_font_size(False)
	table.set_fontsize(9)
	table.scale(1, 1.6)

	for (row, col), cell in table.get_celld().items():
		if row == 0:
			cell.set_text_props(weight="bold")
			cell.set_facecolor("#e9edf5")
		else:
			cell.set_facecolor("#ffffff" if row % 2 else "#f8f9fc")
		if col in (0, 2, 3):
			cell._loc = "right"

	ax.set_title(title, fontweight="bold", fontsize=12, pad=10)


def main() -> None:
	if not INPUT_CSV.exists():
		raise FileNotFoundError(
			"Missing transition_table_by_condition.csv. Run transition_tables.py first."
		)

	df = pd.read_csv(INPUT_CSV)
	required = {"condition", "from_aoi", "to_aoi", "count", "proportion"}
	missing = required.difference(df.columns)
	if missing:
		raise ValueError(f"Input CSV is missing required columns: {sorted(missing)}")

	# Total transitions across all conditions
	total_transitions = int(df["count"].sum())

	# Aggregate correct and overfitting
	had_patch_df = df[df["condition"].isin(["correct", "overfitting"])].copy()
	had_patch_agg = (
		had_patch_df.groupby(["from_aoi", "to_aoi"], as_index=False)["count"].sum()
	)

	# Control condition
	control_df = df[df["condition"] == "control"].copy()
	control_agg = control_df[["from_aoi", "to_aoi", "count"]].copy()

	# Format both tables with global proportion normalization
	had_patch_table = format_table(had_patch_agg, total_transitions)
	control_table = format_table(control_agg, total_transitions)

	# Create side-by-side PDF
	fig = plt.figure(figsize=(16, 12), constrained_layout=True)
	ax1 = fig.add_subplot(1, 2, 1)
	ax2 = fig.add_subplot(1, 2, 2)

	draw_table(ax1, had_patch_table, "Correct + Overfitting")
	draw_table(ax2, control_table, "Control")

	fig.suptitle("Top 10 AOI Transitions: Correct+Overfitting vs Control", fontsize=16, fontweight="bold")
	fig.savefig(OUTPUT_PDF, format="pdf")
	plt.close(fig)

	print(f"Wrote {OUTPUT_PDF.name}")


if __name__ == "__main__":
	main()
