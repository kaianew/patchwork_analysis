from __future__ import annotations

from pathlib import Path
from textwrap import fill

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "transition_table_by_condition.csv"
OUTPUT_PDF = BASE_DIR / "transition_ranked_by_condition.pdf"
CONDITION_ORDER = ["control", "overfitting", "correct"]


def format_table(df: pd.DataFrame) -> pd.DataFrame:
	work = df.copy()
	work = work[work["count"] > 0].copy()
	work = work.sort_values(["proportion", "count", "from_aoi", "to_aoi"], ascending=[False, False, True, True]).reset_index(drop=True)
	work = work.head(10).copy()
	work["rank"] = work.index + 1
	work["transition"] = (work["from_aoi"] + " -> " + work["to_aoi"]).map(lambda s: fill(s, width=28))
	work["proportion"] = (work["proportion"] * 100).round(2).astype(str) + "%"
	return work[["rank", "transition", "count", "proportion"]]


def draw_condition_table(ax: plt.Axes, condition_df: pd.DataFrame, title: str) -> None:
	ax.axis("off")
	table_df = format_table(condition_df)

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

	conditions = [c for c in CONDITION_ORDER if c in df["condition"].unique()]
	if not conditions:
		raise ValueError("No known conditions found in transition_table_by_condition.csv")

	fig = plt.figure(figsize=(18, 16), constrained_layout=True)
	grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], hspace=0.22, wspace=0.08)

	# Top row: overfitting and correct. Bottom row: control spanning both columns.
	axes_map = {
		"overfitting": fig.add_subplot(grid[0, 0]),
		"correct": fig.add_subplot(grid[0, 1]),
		"control": fig.add_subplot(grid[1, :]),
	}

	for condition in conditions:
		if condition not in axes_map:
			continue
		cond_df = df[df["condition"] == condition].copy()
		draw_condition_table(axes_map[condition], cond_df, condition.title())

	fig.suptitle("Ranked AOI Transitions by Condition", fontsize=16, fontweight="bold", y=0.98)
	fig.savefig(OUTPUT_PDF, format="pdf")
	plt.close(fig)

	print(f"Wrote {OUTPUT_PDF.name}")


if __name__ == "__main__":
	main()