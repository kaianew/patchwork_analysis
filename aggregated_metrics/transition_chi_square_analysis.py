from __future__ import annotations

from pathlib import Path

import pandas as pd
import scipy.stats as stats


BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "transition_table_by_condition.csv"


def main() -> None:
	if not INPUT_CSV.exists():
		raise FileNotFoundError(
			"Missing transition_table_by_condition.csv. Run transition_tables.py first."
		)

	df = pd.read_csv(INPUT_CSV)

	# Filter out any transitions involving Patch
	df_no_patch = df[
		(df["from_aoi"] != "Patch") & (df["to_aoi"] != "Patch")
	].copy()

	print("=" * 70)
	print("AOI TRANSITION ANALYSIS (excluding Patch)")
	print("=" * 70)

	# Aggregate correct and overfitting
	had_patch_df = df_no_patch[df_no_patch["condition"].isin(["correct", "overfitting"])].copy()
	had_patch_total = int(had_patch_df["count"].sum())

	# Control condition
	control_df = df_no_patch[df_no_patch["condition"] == "control"].copy()
	control_total = int(control_df["count"].sum())

	print(f"\nTotal transitions (no Patch):")
	print(f"  Correct + Overfitting: {had_patch_total}")
	print(f"  Control: {control_total}")

	# Get all transition pairs that appear in either group
	all_pairs = (
		pd.concat([had_patch_df[["from_aoi", "to_aoi"]], control_df[["from_aoi", "to_aoi"]]])
		.drop_duplicates()
		.reset_index(drop=True)
	)

	# Build contingency table for chi-square test
	contingency_data = []
	for _, row in all_pairs.iterrows():
		from_aoi = row["from_aoi"]
		to_aoi = row["to_aoi"]

		had_patch_count = int(
			had_patch_df[(had_patch_df["from_aoi"] == from_aoi) & (had_patch_df["to_aoi"] == to_aoi)]["count"].sum()
		)
		control_count = int(
			control_df[(control_df["from_aoi"] == from_aoi) & (control_df["to_aoi"] == to_aoi)]["count"].sum()
		)

		contingency_data.append({
			"transition": f"{from_aoi} -> {to_aoi}",
			"had_patch": had_patch_count,
			"control": control_count,
		})

	contingency_df = pd.DataFrame(contingency_data)

	# Filter to transitions that appear in both groups (to avoid sparse data issues)
	contingency_df_both = contingency_df[
		(contingency_df["had_patch"] > 0) & (contingency_df["control"] > 0)
	].copy()

	if len(contingency_df_both) < 2:
		print("\nWARNING: Not enough transitions with counts in both groups for chi-square test.")
		print("Showing all transitions and their proportions instead.\n")
	else:
		contingency_table = contingency_df_both[["had_patch", "control"]].values

		try:
			chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)

			print(f"\n" + "=" * 70)
			print("Chi-Square Test of Independence")
			print("(Based on transitions appearing in both groups)")
			print("=" * 70)
			print(f"Chi-square statistic: {chi2:.4f}")
			print(f"p-value: {p_value:.6f}")
			print(f"Degrees of freedom: {dof}")

			if p_value < 0.05:
				print(f"\n*** SIGNIFICANT DIFFERENCE (p < 0.05) ***")
				print("The transition distributions ARE significantly different between groups.")
			else:
				print(f"\n*** NO SIGNIFICANT DIFFERENCE (p >= 0.05) ***")
				print("The transition distributions are NOT significantly different between groups.")
		except ValueError as e:
			print(f"\nChi-square test failed: {e}")
			print("See proportion differences below instead.\n")

	# Calculate proportions
	contingency_df["had_patch_prop"] = (contingency_df["had_patch"] / had_patch_total).round(4)
	contingency_df["control_prop"] = (contingency_df["control"] / control_total).round(4)
	contingency_df["prop_diff"] = (contingency_df["had_patch_prop"] - contingency_df["control_prop"]).abs()
	contingency_df["prop_diff_signed"] = contingency_df["had_patch_prop"] - contingency_df["control_prop"]

	# Post-hoc: Individual chi-square tests for transitions appearing in both groups
	contingency_df_both_with_tests = contingency_df_both.copy()
	
	# Copy proportions over
	contingency_df_both_with_tests["had_patch_prop"] = (
		contingency_df_both_with_tests["had_patch"] / had_patch_total
	).round(4)
	contingency_df_both_with_tests["control_prop"] = (
		contingency_df_both_with_tests["control"] / control_total
	).round(4)
	contingency_df_both_with_tests["prop_diff_signed"] = (
		contingency_df_both_with_tests["had_patch_prop"] - contingency_df_both_with_tests["control_prop"]
	)
	
	pval_list = []
	for _, row in contingency_df_both_with_tests.iterrows():
		had_patch_count = row["had_patch"]
		control_count = row["control"]
		had_patch_other = had_patch_total - had_patch_count
		control_other = control_total - control_count

		contingency_2x2 = [[had_patch_count, control_count], [had_patch_other, control_other]]
		chi2_ind, pval_ind, _, _ = stats.chi2_contingency(contingency_2x2)
		pval_list.append(pval_ind)

	contingency_df_both_with_tests["p_value"] = pval_list

	# Apply Benjamini-Hochberg FDR correction
	from scipy.stats import rankdata
	sorted_idx = contingency_df_both_with_tests["p_value"].argsort()
	sorted_pvals = contingency_df_both_with_tests["p_value"].iloc[sorted_idx].values
	n_tests = len(sorted_pvals)
	bh_threshold = (rankdata(sorted_pvals) / n_tests) * 0.05
	bh_reject = sorted_pvals < bh_threshold
	contingency_df_both_with_tests["bh_significant"] = False
	contingency_df_both_with_tests.loc[sorted_idx, "bh_significant"] = bh_reject
	contingency_df_both_with_tests["p_value"] = contingency_df_both_with_tests["p_value"].round(6)

	contingency_df_both_with_tests = contingency_df_both_with_tests.sort_values("p_value", ascending=True)

	print(f"\n" + "=" * 70)
	print("Post-Hoc Individual Transition Tests (Benjamini-Hochberg FDR)")
	print("=" * 70)
	significant = contingency_df_both_with_tests[contingency_df_both_with_tests["bh_significant"]]
	if len(significant) > 0:
		print(f"\nSignificant transitions (p < FDR threshold, α = 0.05): {len(significant)}\n")
		display_cols = ["transition", "had_patch", "had_patch_prop", "control", "control_prop", "p_value"]
		print(significant[display_cols].to_string(index=False))
	else:
		print("\nNo individual transitions are significant after FDR correction.\n")
		print(f"Note: {len(contingency_df_both_with_tests)} transitions tested.\n")

	print(f"\n" + "=" * 70)
	print("Top 10 Largest Proportion Differences")
	print("=" * 70)
	contingency_df_by_diff = contingency_df.sort_values("prop_diff", ascending=False)
	display_cols = ["transition", "had_patch", "had_patch_prop", "control", "control_prop", "prop_diff_signed"]
	print(contingency_df_by_diff[display_cols].head(10).to_string(index=False))

	# Save full analysis
	output_csv = BASE_DIR / "transition_chi_square_analysis.csv"
	contingency_df.to_csv(output_csv, index=False)
	print(f"\n\nFull analysis saved to {output_csv.name}")


if __name__ == "__main__":
	main()
