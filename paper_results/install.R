# R dependencies for the paper_results model scripts.
#
# Install:  Rscript patchwork_analysis/paper_results/install.R
#
# Installs any missing packages from the list below. Last run with R 4.3.1 and
# lme4 1.1.34, emmeans 1.11.1, jsonlite 1.8.7, MASS 7.3.60; newer versions are
# expected to work. If a number ever shifts, install these tested versions.
#
# NOTE: lme4 needs a working C/C++/Fortran toolchain to compile. On macOS install
# the Xcode command-line tools; on Linux install r-base-dev (or equivalent). The
# project deliberately avoids glmmTMB / Stan, which need a heavier toolchain.

pkgs <- c(
  "lme4",      # glmer / lmer mixed models, glmer.nb
  "lmerTest",  # Satterthwaite df / p-values for lmer
  "emmeans",   # planned contrasts over condition
  "jsonlite",  # write results_<finding>.json
  "MASS"       # negative-binomial GLM fallback for count models
)

missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) == 0) {
  cat("All required R packages already installed.\n")
} else {
  cat("Installing:", paste(missing, collapse = ", "), "\n")
  install.packages(missing, repos = "https://cloud.r-project.org")
}
