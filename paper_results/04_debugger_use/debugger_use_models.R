# Gap 4 (RQ3) and the IDE corroboration for Gap 2 (RQ2): debugger use ~ condition.
#
# A patch reduces self-directed localization, visible as less debugger use. This
# fits the binary "any debugger use" logistic GLMM and emits a results JSON. The
# per-task IDE event counts are produced by build_debugger_use.py from the
# IntelliJ event logs (ide_tracking.xml); the count outcomes and the ordering
# test it also reports are descriptive context, not modeled here.
#
# Run from repo root: Rscript patchwork_analysis/paper_results/04_debugger_use/debugger_use_models.R

script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- sub("^--file=", "", args[grep("^--file=", args)])
  if (length(file_arg) == 1) return(dirname(normalizePath(file_arg)))
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

IN <- file.path(script_dir(), "ide_events.csv")
OUT <- file.path(ROOT, "patchwork_analysis/paper_results/results/results_debugger_use.json")

d <- read.csv(IN, stringsAsFactors = FALSE)
d <- prep_condition(d)
d$used_debugger <- as.integer(d$n_debugger > 0)

cat("IDE sample:", nrow(d), "tasks\n")
cat("Proportion using debugger by condition:\n")
print(round(tapply(d$used_debugger, d$condition, mean), 3))

recs <- fit_contrasts(
  "used_debugger ~ condition + (1 | PID) + (1 | bug)", d,
  finding = "debugger_use", outcome = "any_debugger_use",
  model_label = "logistic GLMM", gaussian = FALSE, family = binomial(),
  report_or = TRUE)

# Fisher exact (patch vs control) as a model-free corroboration, recorded too.
d$patch <- d$condition != "control"
ft <- fisher.test(table(d$patch, d$used_debugger))
fisher_rec <- data.frame(
  finding = "debugger_use", outcome = "any_debugger_use",
  model = "Fisher exact (patch vs control)", re_structure = "none",
  contrast = "patch_vs_control", estimate = round(unname(ft$estimate), 5),
  se = NA_real_, ci_low = round(ft$conf.int[1], 5), ci_high = round(ft$conf.int[2], 5),
  effect_scale = "odds_ratio", p_raw = ft$p.value, p_BH = NA_real_,
  n_tasks = nrow(d), per_condition_n = per_condition_n(d),
  stringsAsFactors = FALSE)

# BH within the family of the two planned GLMM contrasts only; Fisher is a
# model-free corroboration and is not part of the correction family.
recs$p_BH <- p.adjust(recs$p_raw, method = "BH")
all_recs <- rbind(recs, fisher_rec)
all_recs$p_raw <- round(all_recs$p_raw, 6)
all_recs$p_BH <- round(all_recs$p_BH, 6)
cat("\n===== results (BH over the 2 GLMM contrasts; Fisher uncorrected) =====\n")
print(all_recs[, c("model", "contrast", "estimate", "p_raw", "p_BH")])
write_results_json(all_recs, "debugger_use", OUT)
