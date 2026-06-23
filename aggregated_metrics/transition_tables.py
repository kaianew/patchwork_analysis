from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


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


def load_data() -> pd.DataFrame:
	scarf_df = pd.read_csv(SCARF_INPUT_CSV)
	timing_df = pd.read_csv(TIMING_CSV, usecols=["PID", "task_no", "correct"])

	scarf_df = scarf_df.copy()
	scarf_df["PID"] = scarf_df["PID"].astype(str)
	scarf_df["task_no"] = scarf_df["task_no"].astype(int)
	scarf_df["scarf_aoi"] = scarf_df["scarf_aoi"].fillna("Missing")
	# Unknown AOIs are treated as missing and excluded from transitions.
	scarf_df["scarf_aoi"] = scarf_df["scarf_aoi"].where(scarf_df["scarf_aoi"].isin(AOI_ORDER), "Missing")

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
		raise ValueError("Some trials are missing correctness labels in timing_correctness_data.csv")

	sort_cols = ["PID", "task_no", "start_min"]
	if "fixation_group_id" in merged.columns:
		sort_cols.append("fixation_group_id")

	return merged.sort_values(sort_cols)


def build_transition_rows(df: pd.DataFrame) -> pd.DataFrame:
	rows: list[dict[str, str]] = []
	group_cols = ["PID", "task_no", "condition", "correct_label"]

	for (_, _, condition, correct_label), trial_df in df.groupby(group_cols, sort=False):
		seq = collapse_sequence(trial_df["scarf_aoi"].tolist())
		for src, dst in zip(seq[:-1], seq[1:]):
			rows.append(
				{
					"condition": condition,
					"correct_label": correct_label,
					"from_aoi": src,
					"to_aoi": dst,
				}
			)

	if not rows:
		return pd.DataFrame(columns=["condition", "correct_label", "from_aoi", "to_aoi"])

	return pd.DataFrame(rows)


def full_transition_space(facet_df: pd.DataFrame, facet_cols: list[str]) -> pd.DataFrame:
	aoi_pairs = pd.MultiIndex.from_product([AOI_ORDER, AOI_ORDER], names=["from_aoi", "to_aoi"]).to_frame(index=False)

	if not facet_cols:
		return aoi_pairs

	facets = facet_df[facet_cols].drop_duplicates().reset_index(drop=True)
	return facets.merge(aoi_pairs, how="cross")


def build_table(transitions: pd.DataFrame, facet_cols: list[str]) -> pd.DataFrame:
	group_cols = facet_cols + ["from_aoi", "to_aoi"]
	counts = transitions.groupby(group_cols, dropna=False).size().reset_index(name="count")

	space = full_transition_space(transitions, facet_cols)
	table = space.merge(counts, on=group_cols, how="left")
	table["count"] = table["count"].fillna(0).astype(int)

	if facet_cols:
		totals = table.groupby(facet_cols)["count"].transform("sum")
		table["proportion"] = (table["count"] / totals.where(totals > 0, 1)).fillna(0.0)
	else:
		total = int(table["count"].sum())
		table["proportion"] = table["count"] / (total if total > 0 else 1)

	order_cols = facet_cols + ["count", "from_aoi", "to_aoi"]
	ascending = [True] * len(facet_cols) + [False, True, True]
	table = table.sort_values(order_cols, ascending=ascending).reset_index(drop=True)
	table["proportion"] = table["proportion"].round(6)

	return table


def main() -> None:
	df = load_data()
	transitions = build_transition_rows(df)

	overall = build_table(transitions, [])
	by_condition = build_table(transitions, ["condition"])
	by_correctness = build_table(transitions, ["correct_label"])

	overall_path = BASE_DIR / "transition_table_overall.csv"
	condition_path = BASE_DIR / "transition_table_by_condition.csv"
	correctness_path = BASE_DIR / "transition_table_by_correctness.csv"

	overall.to_csv(overall_path, index=False)
	by_condition.to_csv(condition_path, index=False)
	by_correctness.to_csv(correctness_path, index=False)

	print(f"Wrote {overall_path.name}")
	print(f"Wrote {condition_path.name}")
	print(f"Wrote {correctness_path.name}")


if __name__ == "__main__":
	main()