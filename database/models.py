"""
SQLAlchemy ORM models — normalized schema per master prompt section 15.
SQLite, persistent (file-based, not recreated on every Streamlit run unless --rebuild is passed).
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()


class Factory(Base):
    __tablename__ = "factories"
    factory_id = Column(Integer, primary_key=True, autoincrement=True)
    factory_name = Column(String, unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    capacity = Column(Float, nullable=True)  # nullable: not supplied in source data
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Product(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String, unique=True, nullable=False)
    division = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"
    customer_id = Column(Integer, primary_key=True)
    country_region = Column(String)
    city = Column(String)
    state_province = Column(String)
    postal_code = Column(String)
    latitude = Column(Float, nullable=True)   # state-centroid approximation, see geographic_engine.py
    longitude = Column(Float, nullable=True)
    region = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"))
    order_date = Column(DateTime)
    ship_date = Column(DateTime)
    ship_mode = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class OrderItem(Base):
    __tablename__ = "order_items"
    order_item_id = Column(Integer, primary_key=True, autoincrement=True)
    source_row_id = Column(Integer, nullable=False)  # preserves original Row ID
    order_id = Column(String, ForeignKey("orders.order_id"))
    product_id = Column(Integer, ForeignKey("products.product_id"))
    sales = Column(Float)
    units = Column(Integer)
    gross_profit = Column(Float)
    cost = Column(Float)
    lead_time_days_raw = Column(Float)   # RAW, flagged unreliable — see data_quality_logs
    lead_time_index = Column(Float)      # de-trended relative index used by the model
    distance_miles = Column(Float)

    __table_args__ = (Index("ix_order_items_product", "product_id"),)


class ProductFactoryAssignment(Base):
    __tablename__ = "product_factory_assignments"
    assignment_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"))
    factory_id = Column(Integer, ForeignKey("factories.factory_id"))
    assignment_type = Column(String)      # 'baseline' | 'proposed'
    is_compatible = Column(Boolean, default=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ShippingPrediction(Base):
    __tablename__ = "shipping_predictions"
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"))
    factory_id = Column(Integer, ForeignKey("factories.factory_id"))
    destination_region = Column(String)
    ship_mode = Column(String)
    predicted_lead_time = Column(Float)   # predicted lead_time_index, NOT calendar days
    model_version = Column(String)
    confidence_information = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ScenarioSimulation(Base):
    __tablename__ = "scenario_simulations"
    scenario_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_name = Column(String)
    product_id = Column(Integer, ForeignKey("products.product_id"))
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"
    recommendation_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"))
    current_factory_id = Column(Integer, ForeignKey("factories.factory_id"))
    recommended_factory_id = Column(Integer, ForeignKey("factories.factory_id"), nullable=True)
    predicted_lead_time_improvement = Column(Float)
    estimated_profit_impact = Column(Float)
    risk_level = Column(String)
    confidence_score = Column(Float)
    recommendation_rank = Column(Integer)
    recommendation_reason = Column(String)
    recommendation_status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    model_id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String)
    model_version = Column(String)
    algorithm = Column(String)
    mae = Column(Float)
    rmse = Column(Float)
    r2_score = Column(Float)
    training_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    model_path = Column(String)
    is_active = Column(Boolean, default=False)


class OptimizationSetting(Base):
    __tablename__ = "optimization_settings"
    setting_id = Column(Integer, primary_key=True, autoincrement=True)
    speed_weight = Column(Float, default=0.4)
    profit_weight = Column(Float, default=0.4)
    risk_weight = Column(Float, default=0.2)
    minimum_profit_threshold = Column(Float, default=0.0)
    optimization_mode = Column(String, default="balanced")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class FinancialAssumption(Base):
    __tablename__ = "financial_assumptions"
    assumption_id = Column(Integer, primary_key=True, autoincrement=True)
    assumption_name = Column(String, unique=True)
    assumption_value = Column(Float)
    assumption_unit = Column(String)
    assumption_source = Column(String)
    is_configurable = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class DataQualityLog(Base):
    __tablename__ = "data_quality_logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String)
    issue_type = Column(String)
    issue_description = Column(String)
    affected_records = Column(Integer)
    severity = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
