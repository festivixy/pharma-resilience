import csv
import sys
from pathlib import Path

from src.instability import run_instability_experiment

COUNT = 100
SEED = 2026
LEVELS = [round(i * 0.05, 2) for i in range(11)]


def main(count=COUNT, seed=SEED, out_dir="results"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = run_instability_experiment(count, seed, LEVELS)

    with open(out / "instability.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "index", "scenarios", "reorderings", "pi_spread",
            "distinct_pi", "bound_holds", "beta_zero_reorderings",
        ])
        for row in summary["rows"]:
            writer.writerow([
                row["index"], row["scenarios"], row["reorderings"],
                row["pi_spread"], row["distinct_pi"],
                row["bound_holds"], row["beta_zero_reorderings"],
            ])

    unstable = sum(1 for row in summary["rows"] if row["reorderings"] > 0)
    print(f"{count} instances, {unstable} with at least one reordering")
    print(f"beta-zero invariance holds in "
          f"{summary['beta_zero_invariant_fraction']:.0%} of instances")
    print(f"spearman(pi spread, reorderings) = "
          f"{summary['spearman_spread_vs_reorderings']:.3f}")
    print(f"reorderings <= distinct pi values in {summary['bound_fraction']:.0%}")
    return summary


if __name__ == "__main__":
    main(count=int(sys.argv[1]) if len(sys.argv) > 1 else COUNT)
