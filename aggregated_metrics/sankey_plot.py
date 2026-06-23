from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath


BASE_DIR = Path(__file__).resolve().parent
SCARF_INPUT_CSV = BASE_DIR / "scarf_plot_input.csv"
TIMING_CSV = BASE_DIR.parent / "timing_correctness_data.csv"

AOI_ORDER = [
	"Patch",
	"Browser",
	"Test and Runtime Feedback",
	"Tests",
	"Source Code",
]

AOI_COLORS = {
	"Patch": "#d7301f",
	"Browser": "#3182bd",
	"Test and Runtime Feedback": "#31a354",
	"Tests": "#fd8d3c",
	"Source Code": "#756bb1",
}

CONDITION_ORDER = ["control", "overfitting", "correct"]
CORRECT_ORDER = ["Incorrect", "Correct"]


@dataclass(frozen=True)
class SankeyNode:
	label: str
	total: float
	y0: float
	y1: float


def load_data(scarf_csv: Path, timing_csv: Path) -> pd.DataFrame:
	scarf_df = pd.read_csv(scarf_csv)
	timing_df = pd.read_csv(timing_csv, usecols=["PID", "task_no", "correct"])

	required = ["PID", "task_no", "condition", "start_min", "end_min", "scarf_aoi"]
	missing = [col for col in required if col not in scarf_df.columns]
	if missing:
		raise ValueError(f"Missing required scarf columns: {missing}")

	scarf_df = scarf_df.copy()
	scarf_df["PID"] = scarf_df["PID"].astype(str)
	scarf_df["task_no"] = scarf_df["task_no"].astype(int)
	scarf_df["condition"] = pd.Categorical(scarf_df["condition"], categories=CONDITION_ORDER, ordered=True)
	scarf_df["trial_id"] = scarf_df["PID"] + "_t" + scarf_df["task_no"].astype(str)

	timing_df = timing_df.copy()
	timing_df["PID"] = timing_df["PID"].astype(str)
	timing_df["task_no"] = timing_df["task_no"].astype(int)
	timing_df["correct_label"] = timing_df["correct"].map({"Y": "Correct", "N": "Incorrect"})

	merged = scarf_df.merge(
		timing_df[["PID", "task_no", "correct_label"]],
		on=["PID", "task_no"],
		how="left",
		validate="many_to_one",
	)

	if merged["correct_label"].isna().any():
		missing_trials = (
			merged.loc[merged["correct_label"].isna(), ["PID", "task_no"]]
			.drop_duplicates()
			.astype(str)
			.to_dict("records")
		)
		raise ValueError(f"Missing correctness labels for trials: {missing_trials}")

	merged["condition"] = merged["condition"].astype(str)
	merged["correct_label"] = pd.Categorical(merged["correct_label"], categories=CORRECT_ORDER, ordered=True)
	merged["scarf_aoi"] = merged["scarf_aoi"].fillna("Missing")
	# Any non-core AOI is treated as missing so it does not appear in the Sankey.
	merged["scarf_aoi"] = merged["scarf_aoi"].where(merged["scarf_aoi"].isin(AOI_ORDER), "Missing")

	return merged


def collapse_sequence(seq: Iterable[str]) -> list[str]:
	out: list[str] = []
	prev = object()
	for item in seq:
		if item == "Missing":
			continue
		if item not in AOI_ORDER:
			continue
		if item != prev:
			out.append(item)
			prev = item
	return out


def build_transition_matrix(df: pd.DataFrame, facet_col: str, facet_value: str) -> pd.DataFrame:
	facet_df = df[df[facet_col] == facet_value].copy()
	if facet_df.empty:
		return pd.DataFrame(0, index=AOI_ORDER, columns=AOI_ORDER)

	matrix = pd.DataFrame(0, index=AOI_ORDER, columns=AOI_ORDER, dtype=float)

	for (_, _), trial in facet_df.sort_values(["PID", "task_no", "start_min", "fixation_group_id"]).groupby(["PID", "task_no"], sort=False):
		seq = collapse_sequence(trial["scarf_aoi"].tolist())
		for src, dst in zip(seq[:-1], seq[1:]):
			matrix.loc[src, dst] += 1

	return matrix


def build_node_layout(matrix: pd.DataFrame, side: str, total_height: float = 1.0, top_margin: float = 0.04, bottom_margin: float = 0.04) -> dict[str, SankeyNode]:
	totals = matrix.sum(axis=1) if side == "left" else matrix.sum(axis=0)
	total_weight = float(totals.sum())
	usable_height = total_height - top_margin - bottom_margin
	gap = 0.018
	present = [label for label in AOI_ORDER if totals.get(label, 0) > 0]

	if not present or total_weight <= 0:
		return {}

	total_gaps = gap * (len(present) - 1)
	scale = usable_height - total_gaps
	scale = max(scale, usable_height * 0.65)
	unit = scale / total_weight

	y = 1.0 - top_margin
	nodes: dict[str, SankeyNode] = {}
	for label in present:
		h = float(totals[label]) * unit
		nodes[label] = SankeyNode(label=label, total=float(totals[label]), y0=y - h, y1=y)
		y -= h + gap

	return nodes


def ribbon_path(x0: float, x1: float, y0_top: float, y0_bottom: float, y1_top: float, y1_bottom: float, curvature: float = 0.35) -> MplPath:
	c = curvature * (x1 - x0)
	verts = [
		(x0, y0_top),
		(x0 + c, y0_top),
		(x1 - c, y1_top),
		(x1, y1_top),
		(x1, y1_bottom),
		(x1 - c, y1_bottom),
		(x0 + c, y0_bottom),
		(x0, y0_bottom),
		(x0, y0_top),
	]
	codes = [
		MplPath.MOVETO,
		MplPath.CURVE4,
		MplPath.CURVE4,
		MplPath.CURVE4,
		MplPath.LINETO,
		MplPath.CURVE4,
		MplPath.CURVE4,
		MplPath.CURVE4,
		MplPath.CLOSEPOLY,
	]
	return MplPath(verts, codes)


def draw_sankey(ax: plt.Axes, matrix: pd.DataFrame, title: str):
	left_nodes = build_node_layout(matrix, "left")
	right_nodes = build_node_layout(matrix, "right")

	if not left_nodes or not right_nodes:
		ax.set_axis_off()
		ax.text(0.5, 0.5, "No transitions available", ha="center", va="center")
		return

	x_left = 0.12
	x_right = 0.88
	node_w = 0.06
	ribbon_alpha = 0.42

	left_offsets = {label: left_nodes[label].y1 for label in left_nodes}
	right_offsets = {label: right_nodes[label].y1 for label in right_nodes}

	for src in AOI_ORDER:
		if src not in left_nodes:
			continue
		for dst in AOI_ORDER:
			value = float(matrix.loc[src, dst])
			if value <= 0:
				continue

			src_total = left_nodes[src].total
			dst_total = right_nodes[dst].total
			if src_total <= 0 or dst_total <= 0:
				continue

			src_h = (left_nodes[src].y1 - left_nodes[src].y0) * (value / src_total)
			dst_h = (right_nodes[dst].y1 - right_nodes[dst].y0) * (value / dst_total)

			y0_top = left_offsets[src]
			y0_bottom = y0_top - src_h
			y1_top = right_offsets[dst]
			y1_bottom = y1_top - dst_h

			path = ribbon_path(x_left + node_w, x_right, y0_top, y0_bottom, y1_top, y1_bottom)
			patch = PathPatch(path, facecolor=AOI_COLORS[src], edgecolor="none", alpha=ribbon_alpha)
			ax.add_patch(patch)

			left_offsets[src] = y0_bottom
			right_offsets[dst] = y1_bottom

	for label, node in left_nodes.items():
		rect = Rectangle((x_left, node.y0), node_w, node.y1 - node.y0, facecolor=AOI_COLORS[label], edgecolor="white", linewidth=1.0)
		ax.add_patch(rect)
		ax.text(x_left - 0.02, (node.y0 + node.y1) / 2, label, ha="right", va="center", fontsize=9)

	for label, node in right_nodes.items():
		rect = Rectangle((x_right, node.y0), node_w, node.y1 - node.y0, facecolor=AOI_COLORS[label], edgecolor="white", linewidth=1.0)
		ax.add_patch(rect)
		ax.text(x_right + node_w + 0.02, (node.y0 + node.y1) / 2, label, ha="left", va="center", fontsize=9)

	ax.set_xlim(0, 1)
	ax.set_ylim(0, 1)
	ax.set_axis_off()
	ax.set_title(title, loc="left", fontweight="bold")


def save_faceted_sankey(df: pd.DataFrame, facet_col: str, facet_order: list[str], output_path: Path, title: str):
	fig_h = max(4.0, 3.8 * len(facet_order))
	fig, axes = plt.subplots(len(facet_order), 1, figsize=(16, fig_h), constrained_layout=True)
	if len(facet_order) == 1:
		axes = [axes]

	for ax, facet_value in zip(axes, facet_order):
		matrix = build_transition_matrix(df, facet_col, facet_value)
		draw_sankey(ax, matrix, f"{facet_value}")

	fig.suptitle(title, y=1.01, fontweight="bold")
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def main():
	df = load_data(SCARF_INPUT_CSV, TIMING_CSV)

	save_faceted_sankey(
		df=df,
		facet_col="condition",
		facet_order=CONDITION_ORDER,
		output_path=BASE_DIR / "sankey_by_condition.png",
		title="AOI Transition Sankey by Condition",
	)
	save_faceted_sankey(
		df=df,
		facet_col="correct_label",
		facet_order=CORRECT_ORDER,
		output_path=BASE_DIR / "sankey_by_correctness.png",
		title="AOI Transition Sankey by Correctness",
	)

	print("Wrote sankey_by_condition.png")
	print("Wrote sankey_by_correctness.png")


if __name__ == "__main__":
	main()
