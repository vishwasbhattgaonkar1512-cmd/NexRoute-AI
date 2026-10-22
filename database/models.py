"""
SQLAlchemy ORM models (SQLite).

Schema changes are ADDITIVE ONLY: new tables and new nullable columns are added to an existing database
by database/migrations.py, without touching existing rows. Columns marked "v2" were added on 2026-10-22.
"""
import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    """Naive UTC timestamp (SQLite has no time zones)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Factory(Base):
    __tablename__ = "factories"
    factory_id = Column(Integer, primary_key=True, autoincrement=True)
    factory_name = Column(String, unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    capacity = Column(Float, nullable=True)  # nullable: not supplied in source data
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Product(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String, unique=True, nullable=False)
    division = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    source_product_id = Column(String, nullable=True)  # v2: Product ID from the raw file


class Customer(Base):
    """One row per Customer ID. NOTE: 28 customers ship to several states; use Order.ship_* for geography."""
    __tablename__ = "customers"
    customer_id = Column(Integer, primary_key=True)
    country_region = Column(String)
    city = Column(String)
    state_province = Column(String)  # first state seen for the customer
    postal_code = Column(String)
    latitude = Column(Float, nullable=True)   # state-centroid approximation
    longitude = Column(Float, nullable=True)
    region = Column(String)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Order(Base):
    """One row per distinct Order ID (which embeds customer and product, see data-quality report)."""
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), index=True)
    order_date = Column(DateTime)   # as in the source (year relabelled — see data-quality report)
    ship_date = Column(DateTime)    # as in the source (shifted — see data-quality report)
    ship_mode = Column(String)
    created_at = Column(DateTime, default=utc_now)
    # v2: ship-to geography of this order (correct even for customers with several destinations)
    ship_country = Column(String, nullable=True)
    ship_city = Column(String, nullable=True)
    ship_state = Column(String, nullable=True, index=True)
    ship_postal_code = Column(String, nullable=True)
    ship_region = Column(String, nullable=True)
    order_date_rebuilt = Column(DateTime, nullable=True)  # v2: Order Date with the Order ID year (derived)


class OrderItem(Base):
    __tablename__ = "order_items"
    order_item_id = Column(Integer, primary_key=True, autoincrement=True)
    source_row_id = Column(Integer, nullable=False)  # preserves original Row ID
    order_id = Column(String, ForeignKey("orders.order_id"), index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"))
    sales = Column(Float)
    units = Column(Integer)
    gross_profit = Column(Float)
    cost = Column(Float)
    lead_time_days_raw = Column(Float)   # RAW gap, NOT a lead time — see data_quality_logs
    lead_time_index = Column(Float)      # DEPRECATED previous target
    distance_miles = Column(Float)       # current factory -> destination centroid, straight line
    # v2
    lead_time_recovered_days = Column(Float, nullable=True)   # DERIVED lead time (ML target)
    lead_time_recovered_flag = Column(String, nullable=True)  # ok | out_of_range | unrebuildable
    is_possible_duplicate = Column(Boolean, nullable=True)

    __table_args__ = (
        Index("ix_order_items_product", "product_id"),
        Index("ux_order_items_source_row", "source_row_id", unique=True),
    )


class ProductFactoryAssignment(Base):
    __tablename__ = "product_factory_assignments"
    assignment_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), index=True)
    factory_id = Column(Integer, ForeignKey("factories.factory_id"), index=True)
    assignment_type = Column(String)      # 'baseline' | 'proposed'
    is_compatible = Column(Boolean, default=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)


class OptimizationRun(Base):
    """v2: one row per saved optimization or scenario run (the context every result row refers to)."""
    __tablename__ = "optimization_runs"
    run_id = Column(String, primary_key=True)
    run_type = Column(String, nullable=False)  # 'recommendation' | 'scenario'
    created_at = Column(DateTime, default=utc_now)
    objective = Column(Text)
    weights_json = Column(Text)
    assumptions_json = Column(Text)
    capacities_json = Column(Text)
    solver_status = Column(String)
    solver_message = Column(Text)
    objective_value = Column(Float)
    model_version = Column(String)
    n_products = Column(Integer)
    notes = Column(Text)


class ShippingPrediction(Base):
    __tablename__ = "shipping_predictions"
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), index=True)
    factory_id = Column(Integer, ForeignKey("factories.factory_id"), index=True)
    destination_region = Column(String)   # 'ALL' = product's full historical demand mix
    ship_mode = Column(String)            # 'MIX' = product's historical ship-mode mix
    predicted_lead_time = Column(Float)   # v2 meaning: estimated lead time in days (processing + assumed transit)
    model_version = Column(String)
    confidence_information = Column(String)
    created_at = Column(DateTime, default=utc_now)
    # v2
    run_id = Column(String, ForeignKey("optimization_runs.run_id"), nullable=True, index=True)
    prediction_unit = Column(String, nullable=True)
    processing_lead_days = Column(Float, nullable=True)
    transit_days_assumed = Column(Float, nullable=True)
    interval_low = Column(Float, nullable=True)
    interval_high = Column(Float, nullable=True)
    weighted_distance_miles = Column(Float, nullable=True)

    __table_args__ = (Index("ux_shipping_predictions_run_pf", "run_id", "product_id", "factory_id", unique=True),)


class ScenarioSimulation(Base):
    __tablename__ = "scenario_simulations"
    scenario_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_name = Column(String)
    product_id = Column(Integer, ForeignKey("products.product_id"), index=True)
    baseline_factory_id = Column(Integer, ForeignKey("factories.factory_id"))
    proposed_factory_id = Column(Integer, ForeignKey("factories.factory_id"))
    destination_region = Column(String)
    ship_mode = Column(String)
    baseline_predicted_lead_time = Column(Float)
    alternative_predicted_lead_time = Column(Float)
    lead_time_reduction_percentage = Column(Float)
    estimated_profit_impact = Column(Float)
    risk_level = Column(String)
    scenario_status = Column(String)
    created_at = Column(DateTime, default=utc_now)
    # v2
    run_id = Column(String, ForeignKey("optimization_runs.run_id"), nullable=True, index=True)
    scenario_key = Column(String, nullable=True)
    estimated_cost_impact = Column(Float, nullable=True)
    lead_time_impact_days = Column(Float, nullable=True)
    distance_impact_miles = Column(Float, nullable=True)
    overall_risk = Column(Float, nullable=True)
    confidence_label = Column(String, nullable=True)
    explanation = Column(Text, nullable=True)

    __table_args__ = (Index("ux_scenario_run_key_product", "run_id", "scenario_key", "product_id", unique=True),)


RECOMMENDATION_STATUSES = ["proposed", "under_review", "approved", "rejected", "implemented"]


class Recommendation(Base):
    __tablename__ = "recommendations"
    recommendation_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), index=True)
    current_factory_id = Column(Integer, ForeignKey("factories.factory_id"))
    recommended_factory_id = Column(Integer, ForeignKey("factories.factory_id"), nullable=True)
    predicted_lead_time_improvement = Column(Float)  # days, + = faster (estimate)
    estimated_profit_impact = Column(Float)
    risk_level = Column(String)
    confidence_score = Column(Float)  # v2 meaning: 1 - overall_risk (heuristic, NOT a probability)
    recommendation_rank = Column(Integer)
    recommendation_reason = Column(String)
    recommendation_status = Column(String)
    created_at = Column(DateTime, default=utc_now)
    # v2
    run_id = Column(String, ForeignKey("optimization_runs.run_id"), nullable=True, index=True)
    decision = Column(String, nullable=True)
    confidence_label = Column(String, nullable=True)
    estimated_cost_impact = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    status_updated_at = Column(DateTime, nullable=True)
    status_note = Column(Text, nullable=True)
    model_version = Column(String, nullable=True)

    __table_args__ = (Index("ux_recommendations_run_product", "run_id", "product_id", unique=True),)

    history = relationship("RecommendationStatusHistory", back_populates="recommendation",
                           order_by="RecommendationStatusHistory.changed_at")


class RecommendationStatusHistory(Base):
    """v2: audit trail of status changes."""
    __tablename__ = "recommendation_status_history"
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.recommendation_id"), nullable=False, index=True)
    old_status = Column(String)
    new_status = Column(String, nullable=False)
    note = Column(Text)
    changed_at = Column(DateTime, default=utc_now)
    recommendation = relationship("Recommendation", back_populates="history")


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    model_id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String)
    model_version = Column(String)
    algorithm = Column(String)
    mae = Column(Float)        # final test MAE (selected model refit on train+validation)
    rmse = Column(Float)
    r2_score = Column(Float)
    training_timestamp = Column(DateTime, default=utc_now)
    model_path = Column(String)
    is_active = Column(Boolean, default=False)
    # v2
    target = Column(String, nullable=True)
    val_mae = Column(Float, nullable=True)
    val_rmse = Column(Float, nullable=True)
    val_r2 = Column(Float, nullable=True)
    cv_mae_mean = Column(Float, nullable=True)
    cv_mae_std = Column(Float, nullable=True)
    train_rows = Column(Integer, nullable=True)
    validation_rows = Column(Integer, nullable=True)
    test_rows = Column(Integer, nullable=True)
    features_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    data_sha256 = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("ux_model_registry_version_name", "model_version", "model_name", unique=True),)


class OptimizationSetting(Base):
    __tablename__ = "optimization_settings"
    setting_id = Column(Integer, primary_key=True, autoincrement=True)
    speed_weight = Column(Float, default=0.4)
    profit_weight = Column(Float, default=0.4)
    risk_weight = Column(Float, default=0.2)
    minimum_profit_threshold = Column(Float, default=0.0)  # legacy copy; financial_assumptions is authoritative
    optimization_mode = Column(String, default="balanced")
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    compatibility_rule = Column(String, nullable=True)  # v2


class FinancialAssumption(Base):
    __tablename__ = "financial_assumptions"
    assumption_id = Column(Integer, primary_key=True, autoincrement=True)
    assumption_name = Column(String, unique=True)
    assumption_value = Column(Float)
    assumption_unit = Column(String)
    assumption_source = Column(String)
    is_configurable = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class DataQualityLog(Base):
    __tablename__ = "data_quality_logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String)
    issue_type = Column(String)
    issue_description = Column(String)
    affected_records = Column(Integer)
    severity = Column(String)
    created_at = Column(DateTime, default=utc_now)
    # v2: logs are versioned by report; older reports are kept (is_current = False), never deleted
    report_id = Column(String, nullable=True, index=True)
    is_current = Column(Boolean, nullable=True)
    evidence_json = Column(Text, nullable=True)
