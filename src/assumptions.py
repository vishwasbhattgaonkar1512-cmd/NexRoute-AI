"""
Single source of truth for analyst assumptions and objective weights.

Precedence: explicit overrides  >  database (financial_assumptions / optimization_settings)  >  src/config.py.
Each value remembers where it came from (`provenance`) so every result can say which assumptions it used.
None of these values come from the source data.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from src.config import (
    FINANCIAL_ASSUMPTIONS, LEGACY_ASSUMPTIONS, COMPATIBILITY_RULES, DEFAULT_COMPATIBILITY_RULE,
    WEIGHT_PRESETS, DEFAULT_WEIGHT_PRESET,
)

NUMERIC_KEYS = [k for k in FINANCIAL_ASSUMPTIONS]


@dataclass
class Assumptions:
    alt_factory_cost_multiplier: float = FINANCIAL_ASSUMPTIONS["alt_factory_cost_multiplier"]["value"]
    freight_cost_per_unit_mile: float = FINANCIAL_ASSUMPTIONS["freight_cost_per_unit_mile"]["value"]
    transit_days_per_1000_miles: float = FINANCIAL_ASSUMPTIONS["transit_days_per_1000_miles"]["value"]
    factory_capacity_headroom_pct: float = FINANCIAL_ASSUMPTIONS["factory_capacity_headroom_pct"]["value"]
    minimum_profit_threshold: float = FINANCIAL_ASSUMPTIONS["minimum_profit_threshold"]["value"]
    reassignment_penalty_points: float = FINANCIAL_ASSUMPTIONS["reassignment_penalty_points"]["value"]
    compatibility_rule: str = DEFAULT_COMPATIBILITY_RULE
    provenance: dict = field(default_factory=dict)

    def validate(self) -> "Assumptions":
        errors = []
        if not self.alt_factory_cost_multiplier > 0:
            errors.append("alt_factory_cost_multiplier must be > 0")
        if self.freight_cost_per_unit_mile < 0:
            errors.append("freight_cost_per_unit_mile must be >= 0")
        if self.transit_days_per_1000_miles < 0:
            errors.append("transit_days_per_1000_miles must be >= 0")
        if self.factory_capacity_headroom_pct < 0 and self.factory_capacity_headroom_pct != -1:
            errors.append("factory_capacity_headroom_pct must be >= 0, or -1 for no capacity limit")
        if self.reassignment_penalty_points < 0:
            errors.append("reassignment_penalty_points must be >= 0")
        if self.compatibility_rule not in COMPATIBILITY_RULES:
            errors.append(f"compatibility_rule must be one of {sorted(COMPATIBILITY_RULES)}")
        for k in NUMERIC_KEYS:
            v = getattr(self, k)
            if v is None or v != v:  # None or NaN
                errors.append(f"{k} is missing")
        if errors:
            raise ValueError("Invalid assumptions: " + "; ".join(errors))
        return self

    @property
    def capacity_enabled(self) -> bool:
        return self.factory_capacity_headroom_pct >= 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("provenance")
        return d

    def describe(self) -> list[dict]:
        """Rows for display: name, value, unit, source label, where the value came from."""
        rows = []
        for k in NUMERIC_KEYS:
            cfg = FINANCIAL_ASSUMPTIONS[k]
            rows.append({"assumption": k, "value": getattr(self, k), "unit": cfg["unit"],
                         "source": cfg["source"], "loaded_from": self.provenance.get(k, "config default")})
        rows.append({"assumption": "compatibility_rule", "value": self.compatibility_rule,
                     "unit": "rule", "source": "ANALYST ASSUMPTION: " + COMPATIBILITY_RULES[self.compatibility_rule],
                     "loaded_from": self.provenance.get("compatibility_rule", "config default")})
        return rows


def load_assumptions(overrides: dict | None = None, use_database: bool = True) -> Assumptions:
    a = Assumptions()
    prov = {k: "config default" for k in NUMERIC_KEYS + ["compatibility_rule"]}
    if use_database:
        try:
            from database.connection import get_session
            from database.models import FinancialAssumption, OptimizationSetting
            with get_session() as s:
                for row in s.query(FinancialAssumption).all():
                    if row.assumption_name in LEGACY_ASSUMPTIONS:
                        continue
                    if row.assumption_name in NUMERIC_KEYS and row.assumption_value is not None:
                        setattr(a, row.assumption_name, float(row.assumption_value))
                        prov[row.assumption_name] = "database"
                setting = s.query(OptimizationSetting).order_by(OptimizationSetting.setting_id.desc()).first()
                rule = getattr(setting, "compatibility_rule", None) if setting else None
                if rule:
                    a.compatibility_rule = rule
                    prov["compatibility_rule"] = "database"
        except Exception:  # database missing or older schema: fall back to config defaults
            pass
    for k, v in (overrides or {}).items():
        if k not in NUMERIC_KEYS + ["compatibility_rule"]:
            raise ValueError(f"unknown assumption {k!r}")
        setattr(a, k, v if k == "compatibility_rule" else float(v))
        prov[k] = "override (this session)"
    a.provenance = prov
    return a.validate()


def load_weights(preset: str | None = None, overrides: dict | None = None, use_database: bool = True) -> dict:
    """Objective weights. Explicit preset/overrides win; otherwise the latest optimization_settings row."""
    if preset is not None:
        if preset not in WEIGHT_PRESETS:
            raise ValueError(f"unknown weight preset {preset!r}")
        w = dict(WEIGHT_PRESETS[preset])
    else:
        w = dict(WEIGHT_PRESETS[DEFAULT_WEIGHT_PRESET])
        if use_database:
            try:
                from database.connection import get_session
                from database.models import OptimizationSetting
                with get_session() as s:
                    st = s.query(OptimizationSetting).order_by(OptimizationSetting.setting_id.desc()).first()
                    if st:
                        w = {"profit_weight": st.profit_weight, "speed_weight": st.speed_weight,
                             "risk_weight": st.risk_weight}
            except Exception:
                pass
    w.update(overrides or {})
    for k in ("profit_weight", "speed_weight", "risk_weight"):
        if k not in w or w[k] is None or w[k] < 0:
            raise ValueError(f"weight {k} must be a number >= 0")
    if sum(w.values()) == 0:
        raise ValueError("at least one weight must be > 0")
    return w
