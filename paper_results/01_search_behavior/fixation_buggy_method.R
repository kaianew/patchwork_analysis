# The search-vs-study GAZE-SHARE model (non-patch-AOI-normalized share).
#
# Each region's fixation duration is modeled as a share of the task's total
# fixation duration over the four NON-PATCH AOIs (Test-and-Runtime-Feedback,
# Tests, Source Code, Browser). This denominator matches Kaia's AOI fixation
# analyses in the manuscript (the aligned-ranks-transform ANOVA on non-patch AOI
# proportions and the Test-and-Runtime-Feedback survival model). This is the gaze
# half of the search-vs-study finding; the IDE-events half (navigation and
# files-opened counts) is in ide_navigation.R. The raw minutes
# columns in the input are descriptive only and are not modeled here.
#
# Three outcomes, each lmer ~ condition + (1|PID)+(1|bug) with the standard RE
# fallback and the two planned contrasts. BH within this finding's family.
#
# The finding: the other-method share drops under a patch and survives BH, the
# buggy-method share does not fall, so the effect is confined to non-buggy code.
#
# Run from repo root:
#   Rscript patchwork_analysis/paper_results/01_search_behavior/fixation_buggy_method.R

script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- sub("^--file=", "", args[grep("^--file=", args)])
  if (length(file_arg) == 1) return(dirname(normalizePath(file_arg)))
  # fallback if sourced interactively
  if (!is.null(sys.frames()[[1]]$ofile)) return(dirname(normalizePath(sys.frames()[[1]]$ofile)))
  getwd()
}
find_root <- function() {
  env <- Sys.getenv("PATCHWORK_ROOT", unset = "")
  if (nzchar(env)) return(normalizePath(env))
  d <- script_dir()
  repeat {
    if (basename(d) == "patchwork_analysis") return(dirname(d))
    parent <- dirname(d)
    if (parent == d) stop("Could not locate 'patchwork_analysis' above the script; set PATCHWORK_ROOT.")
    d <- parent
  }
}
ROOT <- find_root()
source(file.path(ROOT, "patchwork_analysis/paper_results/lib/model_helpers.R"))

IN <- file.path(script_dir(), "fixation_buggy_method_input.csv")
OUT <- file.path(ROOT, "patchwork_analysis/paper_results/results/results_fixation_buggy_method.json")

d <- read.csv(IN, stringsAsFactors = FALSE)
d <- prep_condition(d)
cat("N tasks:", nrow(d), "\n")
cat("Mean proportions (of non-patch fixation) by condition:\n")
print(aggregate(cbind(buggy_propfix, other_propfix, source_propfix) ~ condition,
                data = d, FUN = mean))

fit_y <- function(yname, outcome) {
  dd <- d[is.finite(d[[yname]]), ]
  dd$.y <- dd[[yname]]
  fit_contrasts(".y ~ condition + (1 | PID) + (1 | bug)", dd,
                finding = "fixation_buggy_method", outcome = outcome,
                model_label = "lmer prop-of-nonpatch-fixation")
}

recs <- rbind(
  fit_y("buggy_propfix",  "buggy_prop_of_nonpatch_fixation"),
  fit_y("other_propfix",  "other_prop_of_nonpatch_fixation"),
  fit_y("source_propfix", "source_prop_of_nonpatch_fixation")
)
finalize_family(recs, "fixation_buggy_method", OUT)
