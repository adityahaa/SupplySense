"""Reproducible, descriptive comparisons of fixed forecasts and inventory policies.

No model training or policy fitting happens here. Forecast scores use recorded sales;
inventory outcomes are conditional simulations in assumed cost units (CU).
"""
from dataclasses import asdict, replace
from itertools import combinations, product

import numpy as np
import pandas as pd

from .forecast import point_metrics
from .inventory import Assumptions, simulate


BASELINE = "seasonal_naive"


def validate_comparison(predictions, baseline=BASELINE):
    """Require identical observations across models; never silently intersect rows.

    The result is a sorted copy. Multiple chronological windows are permitted for
    forecast scoring, but compare_models requires a single simulation window.
    """
    required = {"model", "id", "date", "sales", "prediction"}
    if not isinstance(predictions, pd.DataFrame) or predictions.empty:
        raise ValueError("Select nonempty saved predictions for comparison.")
    if not required.issubset(predictions):
        raise ValueError(f"Missing comparison columns: {sorted(required - set(predictions))}.")
    p = predictions.copy()
    if p[["model", "id", "date"]].isna().any().any():
        raise ValueError("Comparison keys cannot be missing.")
    p["date"] = pd.to_datetime(p["date"], errors="raise")
    if p["date"].isna().any() or not p["date"].eq(p["date"].dt.normalize()).all():
        raise ValueError("Use complete daily dates for comparison.")
    if p.duplicated(["model", "id", "date"]).any():
        raise ValueError("Each model must have unique series/date observations.")
    if baseline is not None and baseline not in set(p.model):
        raise ValueError(f"Baseline model {baseline!r} is unavailable in this selection.")
    for field in ["sales", "prediction"]:
        try:
            p[field] = pd.to_numeric(p[field], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if not np.isfinite(p[field].to_numpy(float)).all() or p[field].lt(0).any():
            raise ValueError("Sales and forecasts must be finite and nonnegative.")
    p = p.sort_values(["model", "id", "date"]).reset_index(drop=True)
    reference = None
    compare_columns = ["id", "date", "sales"] + [c for c in ["day", "origin", "horizon", "store_id", "cat_id"] if c in p]
    for model, g in p.groupby("model", sort=True):
        observations = g[compare_columns].reset_index(drop=True)
        if reference is not None and not observations.equals(reference):
            raise ValueError("Models must cover identical series, dates, actual sales and forecast origins.")
        reference = observations
        if len(g) != g.id.nunique() * g.date.nunique():
            raise ValueError("Every series must cover the same evaluation dates.")
        for bound in ["lower", "upper"]:
            if bound not in g or g[bound].isna().all():
                continue
            values = pd.to_numeric(g[bound], errors="coerce").to_numpy(float)
            if not np.isfinite(values).all() or (values < 0).any():
                raise ValueError(f"Model {model!r} has incomplete or invalid {bound} bounds.")
            if bound == "lower" and (values > g.prediction.to_numpy()).any():
                raise ValueError("Lower interval bounds cannot exceed point forecasts.")
            if bound == "upper" and (values < g.prediction.to_numpy()).any():
                raise ValueError("Upper interval bounds cannot be below point forecasts.")
    return p


def _forecast_summary(p):
    rows = []
    for model, g in p.groupby("model", sort=True):
        error = g.prediction - g.sales
        intervals = all(c in g and g[c].notna().all() for c in ["lower", "upper"])
        rows.append({"model": model, **point_metrics(g),
            "series": g.id.nunique(), "days": g.date.nunique(),
            "start": g.date.min().date().isoformat(), "end": g.date.max().date().isoformat(),
            "coverage": float(g.sales.between(g.lower, g.upper).mean()) if intervals else None,
            "mean_interval_width": float((g.upper - g.lower).mean()) if intervals else None,
            "intervals_available": intervals,
            "underprediction_fraction": float(error.lt(0).mean()),
            "underprediction_units": float((-error).clip(lower=0).sum()),
            "overprediction_units": float(error.clip(lower=0).sum()),
            "forecast_volume_difference": float(error.sum()),
            "actual_sales_units": float(g.sales.sum()),
        })
    result = pd.DataFrame(rows)
    result["mae_rank"] = result.MAE.rank(method="min").astype(int)
    return result.sort_values(["MAE", "model"]).reset_index(drop=True)


def forecast_summary(predictions):
    """Measured forecast metrics on exactly matched observations, with no simulation."""
    return _forecast_summary(validate_comparison(predictions, baseline=None))


def pareto_front(frame, cost="simulated_total_cost", service="fill_rate"):
    """Mark nondominated rows: minimize cost and maximize service within this frame.

    Equal points are both nondominated. Undefined service is not a Pareto result.
    Call separately for each scenario; cross-scenario comparisons change conditions.
    """
    out = frame.copy()
    if not {cost, service}.issubset(out):
        raise ValueError("Pareto comparison needs cost and fill-rate columns.")
    values = out[[cost, service]].to_numpy(dtype=float)
    finite = np.isfinite(values).all(axis=1)
    flags = np.zeros(len(out), dtype=bool)
    for i, (c, s) in enumerate(values):
        if finite[i]:
            dominates = finite & (values[:, 0] <= c) & (values[:, 1] >= s)
            strict = (values[:, 0] < c) | (values[:, 1] > s)
            flags[i] = not np.any(dominates & strict)
    out["is_pareto"] = flags
    return out


def _compare_validated(p, summary, assumptions, baseline, scenario_id, family):
    if "origin" in p and p.origin.nunique() != 1:
        raise ValueError("Simulate one fixed-origin window at a time; reset stock and budget for each window.")
    dates = pd.DatetimeIndex(sorted(p.date.unique()))
    if len(dates) > 1 and not (dates[1:] - dates[:-1] == pd.Timedelta(days=1)).all():
        raise ValueError("Inventory comparisons require consecutive daily observations.")
    rows = []
    for model, g in p.groupby("model", sort=True):
        g = g.copy()
        has_upper = "upper" in g and g.upper.notna().all()
        if assumptions.safety_weight > 0 and not has_upper:
            raise ValueError(f"Model {model!r} has no upper bounds; use safety weight 0 for this comparison.")
        # A point-only placeholder is solely a simulator input when safety=0.
        # It is never reported as an interval or included in coverage metrics.
        if not has_upper:
            g["upper"] = g.prediction
        trace, totals = simulate(g, assumptions)
        measured = summary[summary.model.eq(model)].iloc[0].to_dict()
        rows.append({"scenario_id": str(scenario_id), "family": str(family),
                     "baseline_model": baseline, **asdict(assumptions), **measured,
                     **totals,
                     "stockout_series_days": int(trace.lost_units.gt(0).sum()),
                     "stockout_series_day_rate": float(trace.lost_units.gt(0).mean()),
                     "ordered_units": float(trace.ordered_units.sum()),
                     "holding_plus_shortage_cost": float(totals["holding_cost"] + totals["shortage_cost"]),
                     "assumed_holding_cost_per_unit_day": assumptions.holding_cost,
                     "assumed_shortage_penalty_per_unit": assumptions.shortage_penalty,
                     "assumed_starting_stock_per_series": assumptions.starting_stock,
                     })
    result = pd.DataFrame(rows)
    # Simulator totals use holding_cost/shortage_cost. Preserve input rate explicitly.
    base = result[result.model.eq(baseline)].iloc[0]
    for metric in ["simulated_total_cost", "fill_rate", "lost_units", "holding_cost", "shortage_cost", "procurement_spend", "order_fees"]:
        result[f"{metric}_delta_vs_baseline"] = result[metric] - base[metric]
    result["cost_reduction_pct_vs_baseline"] = (
        100 * (base.simulated_total_cost - result.simulated_total_cost) / base.simulated_total_cost
        if base.simulated_total_cost > 0 else np.nan)
    result["mae_improvement_pct_vs_baseline"] = (
        100 * (base.MAE - result.MAE) / base.MAE if base.MAE > 0 else np.nan)
    result["fill_rate_delta_percentage_points"] = 100 * result.fill_rate_delta_vs_baseline
    result["cost_rank"] = result.simulated_total_cost.rank(method="min").astype(int)
    result["rank_shift"] = result.cost_rank - result.mae_rank
    return pareto_front(result).sort_values(["cost_rank", "model"]).reset_index(drop=True)


def compare_models(predictions, assumptions=Assumptions(), baseline=BASELINE,
                   scenario_id="interactive", family="interactive"):
    """Run every available model under identical conditions and seasonal-naive policy.

    Forecast MAE always scores the original recorded sales. demand_multiplier affects
    simulated demand only, and never turns the historic forecast metric into a new one.
    """
    p = validate_comparison(predictions, baseline)
    return _compare_validated(p, _forecast_summary(p), assumptions, baseline, scenario_id, family)


def default_scenarios(base=Assumptions()):
    """34 bounded scenarios: 27 factorial cells and seven one-factor sensitivities."""
    scenarios = []
    for lead, penalty, safety in product([1, 3, 7], [1.0, 5.0, 10.0], [0.0, 0.5, 1.0]):
        a = replace(base, lead_days=lead, shortage_penalty=penalty, safety_weight=safety)
        name = "default" if a == base else f"grid_l{lead}_p{penalty:g}_s{safety:g}"
        scenarios.append({"scenario_id": name, "family": "factorial", "assumptions": a})
    for name, values in [("holding_cost", [0.0, 0.15]), ("review_days", [1, 14]),
                         ("budget", [0.0, 1500.0, 6000.0])]:
        for value in values:
            scenarios.append({"scenario_id": f"{name}_{value:g}", "family": name,
                              "assumptions": replace(base, **{name: value})})
    return scenarios


def run_sensitivity(predictions, scenarios=None, baseline=BASELINE):
    """Execute a bounded scenario list, reusing validated observations and metrics."""
    scenarios = default_scenarios() if scenarios is None else list(scenarios)
    if not scenarios or len(scenarios) > 100:
        raise ValueError("Choose between 1 and 100 scenarios per run.")
    names = [str(s["scenario_id"]) for s in scenarios]
    if len(set(names)) != len(names):
        raise ValueError("Scenario identifiers must be unique.")
    p = validate_comparison(predictions, baseline)
    summary = _forecast_summary(p)
    return pd.concat([_compare_validated(p, summary, s["assumptions"], baseline,
                                       s["scenario_id"], s.get("family", "custom"))
                      for s in scenarios], ignore_index=True)


def rank_reversals(results, tolerance=1e-9):
    """List strictly lower-error forecasts that have strictly higher simulated cost."""
    columns = ["scenario_id", "family", "more_accurate_model", "lower_cost_model",
               "more_accurate_MAE", "lower_cost_model_MAE", "MAE_gap",
               "more_accurate_cost", "lower_cost", "cost_difference_CU",
               "more_accurate_fill_rate", "lower_cost_model_fill_rate"]
    rows = []
    for scenario, g in results.groupby("scenario_id", sort=True):
        for a, b in combinations(g.to_dict("records"), 2):
            if a["MAE"] > b["MAE"]:
                a, b = b, a
            if b["MAE"] - a["MAE"] > tolerance and a["simulated_total_cost"] - b["simulated_total_cost"] > tolerance:
                rows.append({"scenario_id": scenario, "family": a["family"],
                    "more_accurate_model": a["model"], "lower_cost_model": b["model"],
                    "more_accurate_MAE": a["MAE"], "lower_cost_model_MAE": b["MAE"],
                    "MAE_gap": b["MAE"] - a["MAE"],
                    "more_accurate_cost": a["simulated_total_cost"], "lower_cost": b["simulated_total_cost"],
                    "cost_difference_CU": a["simulated_total_cost"] - b["simulated_total_cost"],
                    "more_accurate_fill_rate": a["fill_rate"], "lower_cost_model_fill_rate": b["fill_rate"]})
    return pd.DataFrame(rows, columns=columns)


def sensitivity_summary(results):
    """Descriptive spread across chosen assumptions; these are not confidence intervals."""
    return (results.groupby("model", as_index=False).agg(
        scenarios=("scenario_id", "nunique"), MAE=("MAE", "first"),
        minimum_cost=("simulated_total_cost", "min"), maximum_cost=("simulated_total_cost", "max"),
        median_cost=("simulated_total_cost", "median"),
        minimum_fill_rate=("fill_rate", "min"), maximum_fill_rate=("fill_rate", "max"),
        cost_rank_min=("cost_rank", "min"), cost_rank_max=("cost_rank", "max"),
        minimum_cost_scenarios=("cost_rank", lambda s: int(s.eq(1).sum())),
        pareto_scenarios=("is_pareto", "sum")))
