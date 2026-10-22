# NexRoute AI: Factory Reallocation and Shipping Optimization Recommendation System for Nassau Candy Distributor

**Project Name:** NexRoute AI
**Dataset:** Nassau Candy Distributor Historical Dataset (`Nassau Candy Distributor.csv`, 10,194 records)
**Research Topic:** Exploratory Data Analysis, Predictive Modeling, and Optimization for Factory Allocation in Supply Chain Distribution

*Author/institutional details were not available in the project documentation and are therefore omitted, per research accuracy rules.*

---

## Abstract

Nassau Candy Distributor ships 15 candy products from five factories to customers across the
United States and Canada. The company currently assigns each product to one factory using a
fixed, static rule. This research examines whether historical order data can be used to test
whether a different factory assignment would improve shipping performance or profitability.

We performed exploratory data analysis (EDA) on 10,194 historical order lines, covering product
sales, customer geography, shipping modes, and factory assignments. During this analysis we
discovered a serious problem: the dataset's "Ship Date" field does not represent real-world
delivery time. The gap between Order Date and Ship Date is 904 to 1,642 days (about 2.5 to 4.5
years) for every single order, regardless of whether the shipping mode is "Same Day" or
"Standard Class." This finding is reported honestly throughout this paper, and no claim is made
that the resulting model predicts real calendar-day delivery times.

Given this constraint, we built a machine learning model (comparing Linear Regression, Random
Forest, and Gradient Boosting) to predict a **de-trended relative lead-time index** rather than
the raw day count. The best model (Gradient Boosting) achieved a test R² of only 0.038 — close
to zero. This is reported as an honest result: it shows that geography, product, and shipping
mode carry very little genuine signal for this corrupted field, not that the modeling approach
failed.

We then built a scenario simulator and a constrained optimization engine that evaluates, for
each of the 15 products, whether moving it to a different factory would help. The engine
considers predicted lead-time, distance, estimated profit impact, product-factory compatibility,
and model confidence, and it is allowed to recommend "keep the current factory" when no
alternative is clearly better. Running this engine across all 15 products with balanced
priorities produced **zero reallocation recommendations** — every product is currently best left
at its existing factory, mainly because alternative factories are geographically farther from
each product's real customer base and the weak model gives low confidence in any predicted
improvement.

The main conclusion is that, with the data currently available, there is no reliable evidence
that reallocating any product to a different factory would improve shipping performance or
profitability. The most valuable recommendation from this research is not a factory change, but
a call to fix the Ship Date field at its source before any shipping-time-based decision is made.

---

## 1. Introduction

Supply chain management is the process of planning, producing, and delivering products from
factories to customers. One important decision in supply chain management is **factory
allocation**: deciding which factory should produce and ship each product. A good factory
allocation reduces shipping distance, reduces delivery time, and protects profit margins. A poor
allocation can lead to longer shipping times, higher costs, and dissatisfied customers.

Nassau Candy Distributor is a company that manufactures candy products (such as chocolate bars
and sugar candies) at five factories and ships them to customers across many U.S. states and a
small number of Canadian provinces. Currently, each of the company's 15 products is assigned to
exactly one factory, based on a fixed historical rule, not on an ongoing data-driven process.

This project, **NexRoute AI**, was built to test whether historical order data could reveal
better factory assignments. It combines exploratory data analysis, machine learning, geographic
distance calculation, financial estimation, and a constrained optimization engine into a single
decision-support system, delivered as an interactive Streamlit dashboard.

## 2. Problem Statement

The specific problems this research addresses are:

1. **Inefficient factory-to-product allocation.** Products are assigned to factories by a fixed
   rule. It is unknown whether this rule is still the best choice.
2. **Shipping lead-time variations.** Some orders may take longer to ship than others, and it is
   unclear which factors (distance, shipping mode, product, region) explain this variation.
3. **Geographical distribution challenges.** Customers are spread across many states and a few
   Canadian provinces, at different distances from each of the five factories.
4. **Operational cost and profitability considerations.** Any proposed factory change must be
   checked against its effect on profit, not just shipping speed.
5. **Need for a repeatable, data-driven decision process**, instead of a one-time manual
   assignment that is never revisited.

## 3. Research Objectives

1. Describe the dataset completely and honestly, including its limitations.
2. Perform structured exploratory data analysis across products, customers, geography, shipping,
   factories, and data quality.
3. Build and fairly compare three regression models to estimate shipping lead-time behavior.
4. Build a scenario simulator that compares the current factory against all alternative
   factories for each product.
5. Build an optimization engine that produces a ranked recommendation (reallocate or keep
   current) for every product, under realistic constraints.
6. Report all findings — including negative or inconclusive ones — without exaggeration.

## 4. Dataset Description

The dataset (`Nassau Candy Distributor.csv`) contains **10,194 order-line records** across
**18 columns**, covering **8,549 unique orders** from **5,044 unique customers**, for **15
unique products** across **3 product divisions** (Chocolate, Sugar, Other), shipped using
**4 shipping modes**, to customers in **57 unique states/provinces** across **4 sales regions**
(Pacific, Atlantic, Interior, Gulf).

**Table 1. Dataset Summary**

| Property | Value |
|---|---|
| Total order lines | 10,194 |
| Unique orders | 8,549 |
| Unique customers | 5,044 |
| Unique products | 15 |
| Factories | 5 |
| Product divisions | 3 (Chocolate, Sugar, Other) |
| Shipping modes | 4 |
| States/Provinces represented | 57 |
| Sales regions | 4 |
| Missing values (raw columns) | 0 |
| Missing values (derived distance only) | 200 (all Canadian orders — see Section 7.8) |
| Exact duplicate order lines (raw CSV) | 313 pairs/groups (see Section 7.8) |
| Date range — Order Date | 2024-01-02 to 2025-12-31 |
| Date range — Ship Date | 2026-06-30 to 2030-06-28 |

**Important columns:** Order ID, Order Date, Ship Date, Ship Mode, Customer ID, Country/Region,
City, State/Province, Division, Region, Product ID, Product Name, Sales, Units, Gross Profit,
Cost.

**Dataset limitations identified:**
- Ship Date does not behave like a real shipping-time field (explained fully in Section 7.8).
- No customer-level latitude/longitude; only state/province names are available.
- No factory capacity, alternative-factory manufacturing cost, or freight-cost data.
- 200 Canadian order lines fall outside the United-States-only geographic reference table used
  for distance estimation.

## 5. Exploratory Data Analysis

### 5.1 Overall Dataset Analysis

**What was analyzed:** Dataset shape, column data types, missing values, and duplicate records,
directly from the cleaned dataset stored in the project's database.

**Why:** To confirm the dataset is usable and to catch structural problems before any modeling.

**Actual result:** 10,194 rows survive the full cleaning pipeline (0 rows dropped — no invalid
dates, no negative numeric values, no unparseable records once the correct date format,
`DD-MM-YYYY`, was identified; the alternative `MM-DD-YYYY` format produced 6,064–6,173 parse
failures and was rejected). 313 exact-duplicate order lines exist in the **raw source file**
itself (same order, same product, identical sales/units/cost on two separate Row IDs) — these
were **not removed**, because without business confirmation it cannot be assumed they are
errors rather than genuinely repeated line items (e.g., two separate cartons of the same
product in one order).

**Interpretation:** The dataset is structurally clean (correct types, no corrupt numeric values),
but it contains a small number of literal duplicate line items that a business analyst should
verify against the original order system.

**Business insight:** Before any financial total is reported to management, Nassau Candy should
confirm whether these 313 duplicate lines represent real repeat items or a data-entry/export
error, since they currently inflate total Sales and Units by a small amount.

### 5.2 Product Analysis

**What was analyzed:** Sales distribution across the 15 products and 3 divisions.

**Why:** To understand which products drive the business, since a factory-reallocation decision
for a high-volume product matters more than for a low-volume one.

**Actual result:** The **Chocolate** division accounts for 9,844 of 10,194 order lines (96.6%).
**Sugar** (34 lines) and **Other** (316 lines) are a small share of total volume. The top-selling
product is **Wonka Bar - Triple Dazzle Caramel** ($28,485 total sales); the lowest is **Fun Dip**
($12 total sales — only 3 historical orders). The top 5 products by sales account for **92.9%**
of total sales.

**Figures:** Figure 1 (sales by product), Figure 2 (division share).

**Interpretation:** Product volume is extremely concentrated in Chocolate-division products made
at two factories (Lot's O' Nuts and Wicked Choccy's). Sugar and Other-division products have so
few historical orders that any prediction made for them is inherently low-confidence — not
because the model is weak, but because there is almost no data to learn from.

**Business insight:** Any reallocation decision for low-volume products (Fun Dip, Everlasting
Gobstopper, Hair Toffee) should rely more on business judgment than on this model, since the
sample sizes (3–8 historical orders) are too small for a statistically reliable estimate.

### 5.3 Customer Analysis

**What was analyzed:** Number of orders per customer, and customer concentration.

**Why:** To check whether the business depends on a small number of large customers (which would
make reallocation riskier for those customers specifically).

**Actual result:** The average customer placed **1.69 orders**, the busiest customer placed **15
orders**, and the **top 10 customers** account for only **1.1%** of all orders. Figure 3 shows
most customers order only once or twice.

**Interpretation:** The customer base is broad and not concentrated — no single customer
dominates order volume.

**Business insight:** Reallocation decisions do not need to be tailored around protecting a
handful of key accounts; the customer impact of any change is spread across many small buyers.

### 5.4 Geographical Analysis

**What was analyzed:** Order-line counts by state/province and by sales region, and the
straight-line distance from each product's assigned factory to its customers' state centroids.

**Why:** Geographic distance is a primary driver of shipping performance in supply-chain theory,
so it must be measured before any factory-reallocation claim can be evaluated.

**Actual result:** Order lines are concentrated across 57 states/provinces; the **Pacific**
region has the most order lines (3,260), followed by Atlantic (2,988), Interior (2,326), and
Gulf (1,620) (Figure 5). Figure 4 shows the 15 states with the most order lines. Distances were
calculated using the Haversine (great-circle) formula between each factory's exact supplied
coordinates and a public state-centroid coordinate for the customer's state — **this is a
straight-line approximation, not a road distance**, and is explicitly labeled as such everywhere
it is used.

**Interpretation:** Because Nassau Candy's factories are spread across the country (Arizona,
Georgia, North Dakota, Iowa, Tennessee), and customers are spread nationally, some customer-
product combinations are inherently far from their assigned factory. This is a structural
feature of the business, not a data error.

**Business insight:** Any product whose main customer base is geographically distant from its
assigned factory is a natural candidate to examine for reallocation — but, as Section 10 shows,
distance alone does not guarantee a better outcome once compatibility and profit are considered.

### 5.5 Shipping Analysis

**What was analyzed:** The distribution of Ship Mode, and the raw lead time (Ship Date − Order
Date) by shipping mode.

**Why:** This is the central shipping-performance question the project was commissioned to
answer.

**Actual result:** **Standard Class** is used in 6,120 of 10,194 order lines (60%), followed by
Second Class (1,979), First Class (1,548), and Same Day (547). The raw lead time ranges from
**904 to 1,642 days**, with a mean of **1,320.8 days** and a standard deviation of 262.4 days
(Figure 8). Critically, **the mean lead time for "Same Day" orders (1,333.4 days) is actually
19.1 days longer than for "Standard Class" orders (1,314.3 days)** — the opposite of what a real
shipping-mode effect should look like (Figure 7).

**Interpretation:** A difference of 19 days in the *wrong direction*, against a background
standard deviation of 262 days, confirms that **Ship Mode has no detectable real effect on the
raw lead-time field**. Combined with the magnitude of the gap itself (2.5–4.5 years, not hours
or days), this is strong evidence that the Ship Date field was generated or shifted independently
of the rest of each record, rather than recorded from an actual shipment event.

**Business insight:** This field cannot currently be used, on its own, to measure or compare real
shipping performance. See Section 7.8 and Section 14 for the full discussion and required fix.

### 5.6 Factory Analysis

**What was analyzed:** How many historical order lines and how many distinct products are
currently handled by each factory.

**Why:** To check whether workload is balanced across factories, which affects how much
historical evidence exists to evaluate each factory's performance.

**Actual result (Figure 10):**

| Factory | Order Lines | Products Assigned |
|---|---:|---:|
| Lot's O' Nuts | 5,692 | 3 |
| Wicked Choccy's | 4,152 | 2 |
| Secret Factory | 217 | 3 |
| The Other Factory | 100 | 2 |
| Sugar Shack | 33 | 5 |

**Interpretation:** Workload is extremely imbalanced. Two factories (Lot's O' Nuts, Wicked
Choccy's) handle 96.9% of all order lines, because they make the 5 Chocolate-division products,
which dominate sales. Sugar Shack, despite being assigned **5 different products**, has only 33
historical order lines in total — fewer than 7 per product on average.

**Business insight:** Confidence in any shipping-performance conclusion about Secret Factory,
The Other Factory, or Sugar Shack is inherently low, simply due to small sample size — this is
independent of, and in addition to, the lead-time data-quality problem.

### 5.7 Correlation Analysis

**What was analyzed:** Pearson correlation between Sales, Units, Gross Profit, Cost, Distance,
raw Lead Time, and the de-trended Lead-Time Index (Figure 11).

**Why:** To check whether distance — the one geographic signal available — has any measurable
relationship with lead time, before building a predictive model on it.

**Actual result:** The correlation between straight-line distance and raw lead time is
**r = 0.015** — statistically negligible (Figure 12).

**Interpretation:** A real-world shipping system should show a positive correlation between
distance and delivery time. A correlation of 0.015 is consistent with no real relationship,
reinforcing the Section 5.5 finding that the lead-time field does not reflect real shipping
behavior. (As instructed, this is reported as a correlation finding only — no causal claim is
made.)

**Business insight:** Until the Ship Date field is fixed, distance-based shipping-time arguments
cannot be verified against the data; the recommendations in this paper rely on distance and
profit together, not on a validated distance→time relationship.

### 5.8 Data Quality Analysis

**What was analyzed:** All issues found during cleaning, logged programmatically to the
project's `data_quality_logs` table (not hand-picked after the fact).

**Findings:**

1. **(Critical) Systemic lead-time anomaly.** Confirmed and quantified in Sections 5.5 and 5.7.
   Affects **all 10,194 records**.
2. **313 exact-duplicate order lines** in the raw CSV (Section 5.1) — retained, flagged for
   business review, not deleted.
3. **200 order lines with no distance estimate** — all from **Canadian** provinces (Ontario,
   Quebec, Alberta, British Columbia, and 6 others), because the state-centroid reference table
   used in this project only covers the 50 U.S. states and Washington D.C. This is a **scope
   limitation of the geographic approximation**, not a data error in the source file.
4. **0 negative lead times, 0 unparseable dates, 0 invalid numeric values** — once the correct
   date format (`DD-MM-YYYY`) was identified. The alternative format would have silently
   corrupted the entire date column; this was caught by testing both formats and comparing parse
   failure counts before choosing.

**Business insight:** Items 1 and 2 require a conversation with the team that exports this data;
item 3 requires either an expanded geographic reference table (if Canadian shipping is a
priority) or acceptance that Canadian scenarios will show "insufficient financial data" in the
dashboard, which is exactly how the system currently handles it.

---

## 6. Data Preprocessing and Feature Engineering

The following steps were implemented in `src/preprocessing.py`:

1. **Date parsing.** Both `DD-MM-YYYY` and `MM-DD-YYYY` formats were tested against the actual
   data; `DD-MM-YYYY` produced zero parse failures and was adopted.
2. **Lead-time calculation.** `lead_time_days_raw = Ship Date − Order Date`, computed and stored
   for transparency, but explicitly flagged as unreliable (Section 5.5–5.7).
3. **De-trended target construction.** Because the raw field carries a structural, non-shipping
   artifact, the modeling target is `lead_time_index = lead_time_days_raw − (median lead time for
   that Ship Mode)`. This removes the dominant artifact and lets the model attempt to learn
   whatever smaller, relative variation remains across product/region/distance — it is **not**
   presented as a real day-count anywhere in the system.
4. **Numeric validation.** Sales, Units, Gross Profit, and Cost were coerced to numeric types;
   any row that failed was logged and dropped (0 rows were affected).
5. **Duplicate handling.** Rows with duplicate `Row ID` were logged and removed (0 found, distinct
   from the 313 duplicate order-lines discussed above, which have different Row IDs).
6. **Categorical features retained as categories:** Division, current factory, Region,
   State/Province, Ship Mode, and Order Year (added after the chronological drift described in
   Section 9) — encoded with one-hot encoding inside a scikit-learn `ColumnTransformer`.
7. **Numeric features standardized:** distance_miles, Units, Sales, order_month, order_dow —
   scaled with `StandardScaler` inside the same pipeline, to prevent any leakage from
   fitting the scaler on data outside the training fold.
8. **Geographic feature engineering.** Straight-line Haversine distance from each record's
   *current assigned factory* to the customer's state centroid.
9. **Target/feature leakage prevention.** Ship Date and any post-shipment information are
   excluded from the model's input features; only information available at order time is used.
10. **Train/validation/test split.** Rows were sorted by Order Date and split **chronologically**
    (70% / 15% / 15%), not randomly, so that the test set simulates predicting the future rather
    than interpolating within a shuffled sample.

---

## 7. Machine Learning Analysis

Three models were implemented and fairly compared, each inside an identical preprocessing
pipeline so the comparison isolates the effect of the algorithm, not the feature processing:

- **Linear Regression** — a simple baseline model that fits a straight-line relationship between
  features and target. Easy to interpret, but assumes strictly additive, linear effects.
- **Random Forest Regressor** (200 trees, max depth 10) — an ensemble of decision trees that can
  capture non-linear patterns and interactions between features.
- **Gradient Boosting Regressor** (200 estimators, max depth 3) — builds trees sequentially,
  each correcting the errors of the previous ones; often strong on tabular data.

**Target variable:** `lead_time_index` (de-trended, relative — see Section 6).
**Input features:** Division, current factory, destination Region, destination State, Ship Mode,
Order Year, straight-line distance, Units, Sales, order month, order day-of-week.

**Table 2. Model Comparison (held-out test set, chronological split)**

| Model | Test MAE | Test RMSE | Test R² |
|---|---:|---:|---:|
| Linear Regression | 179.77 | 182.90 | −0.014 |
| Random Forest | 167.29 | 180.41 | 0.013 |
| **Gradient Boosting (selected)** | **169.02** | **178.12** | **0.038** |

**Selected model:** Gradient Boosting Regressor, because it achieved the highest held-out test
R² among the three. However, **an R² of 0.038 is very low** — it means the model explains only
about 3.8% of the variation in the (already de-trended) lead-time index. This is reported
honestly: the model is not discarded, because it still outperforms the simpler baseline, but its
predictions are labeled "low confidence" everywhere they are used in the dashboard and
optimization engine, and no claim of strong predictive accuracy is made anywhere in this project.

Residual analysis (Figure 13) shows errors of similar scale across all three models; feature
importance analysis (generated alongside this paper, see `models/evaluation/feature_importance.csv`)
shows no single feature dominates, consistent with the weak-signal finding.

---

## 8. Factory Reallocation Analysis

Nassau Candy's **existing allocation** (preserved exactly as the business baseline) assigns:

**Table 3. Baseline Product–Factory Assignment**

| Division | Product | Current Factory |
|---|---|---|
| Chocolate | Wonka Bar - Nutty Crunch Surprise | Lot's O' Nuts |
| Chocolate | Wonka Bar - Fudge Mallows | Lot's O' Nuts |
| Chocolate | Wonka Bar -Scrumdiddlyumptious | Lot's O' Nuts |
| Chocolate | Wonka Bar - Milk Chocolate | Wicked Choccy's |
| Chocolate | Wonka Bar - Triple Dazzle Caramel | Wicked Choccy's |
| Sugar | Laffy Taffy | Sugar Shack |
| Sugar | SweeTARTS | Sugar Shack |
| Sugar | Nerds | Sugar Shack |
| Sugar | Fun Dip | Sugar Shack |
| Other | Fizzy Lifting Drinks | Sugar Shack |
| Sugar | Everlasting Gobstopper | Secret Factory |
| Sugar | Hair Toffee | The Other Factory |
| Other | Lickable Wallpaper | Secret Factory |
| Other | Wonka Gum | Secret Factory |
| Other | Kazookles | The Other Factory |

**Product-factory compatibility:** only these 15 pairs are *confirmed* compatible (supplied by
the business). Any alternative factory is treated as **"unverified — assumed compatible within
the same product division"** — an explicit, labeled assumption, never presented as confirmed
fact.

**Optimization formulation.** For each product, a weighted score is computed for the current
factory and every eligible alternative:

```
score = (speed_weight × tanh(lead-time reduction %)) 
      + (profit_weight × tanh(profit impact / baseline profit))
      − (risk_weight × risk_penalty)
      − (reassignment_penalty, applied only to non-current factories)
```

Hard constraints are applied before ranking: an alternative is excluded if it is flagged
*unsupported* (fewer than 30 historical training rows) or if its estimated profit impact falls
below a configurable minimum-profit threshold (default: $0, i.e. no reallocation that reduces
profit is recommended). The engine explicitly supports **"KEEP CURRENT FACTORY"** as a valid,
and in this run, the only, outcome.

**Estimated cost and profit impact** are computed in `src/profit_engine.py` using the real
historical Sales and Cost for the baseline, and two clearly labeled analyst assumptions for any
alternative factory (since the source data contains no alternative-factory cost information):
an alternative-factory manufacturing-cost multiplier (default 1.0 — assumes equal cost) and a
shipping-cost-per-mile-per-unit rate (default $0.015 — an illustrative placeholder, not a real
freight contract rate).

---

## 9. Scenario Analysis

Rather than three fixed, generic scenarios, NexRoute AI's simulator evaluates **every eligible
factory** for every product against its **actual historical representative destination, shipping
mode, and order profile** (pulled from the database, not invented). The dashboard's What-If
Analysis page additionally lets a user build **custom Current / Alternative / Balanced / Speed-
priority / Profit-priority** comparisons interactively. The table below summarizes the
**balanced-priority, full-catalog run** actually executed for this paper:

**Table 4. Scenario Comparison Summary (Balanced Priority, All 15 Products)**

| Metric | Value |
|---|---|
| Products evaluated | 15 |
| Products recommended for reallocation | 0 |
| Products recommended to keep current factory | 15 |
| Main reason alternatives were rejected | Lower score once distance-driven profit impact, low model confidence, and the reassignment penalty are applied |
| Main advantage of this approach | No reallocation is proposed unless the evidence clearly supports it — avoids disruptive, unjustified factory changes |
| Main limitation | The same weak model signal (R²≈0.04) that prevents false positives could also be hiding a real improvement too small for this model to detect |

Figure 15 shows the decision split (15 "keep current," 0 "reallocate") graphically.

**Interpretation:** This is an honest, non-fabricated result. It does **not** mean the current
allocation is proven optimal — it means that, given the available data and its quality
limitations, there is no statistically defensible case for moving any product right now.

---

## 10. Major EDA Findings and Business Insights

| # | Finding (what the data shows) | Why it matters | Effect on factory allocation / shipping |
|---|---|---|---|
| 1 | Ship Date − Order Date = 904–1,642 days for all 10,194 records, with no real Ship-Mode effect (**actual dataset finding**) | The core "shipping lead time" field cannot be trusted as-is | All shipping-time conclusions in this project use a de-trended, low-confidence index, not real days |
| 2 | Distance vs. raw lead time correlation = 0.015 (**actual dataset finding**) | Confirms Finding 1 independently | Distance-only reallocation arguments cannot be validated against this data |
| 3 | Chocolate-division products = 96.6% of order volume, concentrated at 2 of 5 factories (**actual dataset finding**) | Workload and data volume are highly imbalanced | Low-volume factories (Sugar Shack, Secret Factory, The Other Factory) have too little history for confident predictions |
| 4 | Best model (Gradient Boosting) test R² = 0.038 (**actual model result**) | Model has very weak real-world predictive power | Every prediction is labeled "low confidence"; no decision should rely on the model alone |
| 5 | Balanced-priority optimization recommends 0 reallocations across all 15 products (**actual optimization-engine result**) | Current allocation is not clearly beaten by any alternative | No immediate factory change is supported by this analysis |
| 6 | 200 Canadian order lines (2.0% of data) lack a distance estimate (**actual dataset finding + tool limitation**) | Geographic coverage gap | Canadian scenarios show "insufficient financial data" rather than a possibly-wrong estimate |

---

## 11. Recommendations

1. **Factory allocation:** Do not reallocate any product at this time; the data does not support
   it. Revisit this analysis once the Ship Date issue (Recommendation 5) is fixed.
2. **Shipping performance:** Investigate the shipping-mode field's business meaning directly with
   operations staff, since it currently shows no measurable effect on lead time at all.
3. **Product distribution:** Treat Sugar Shack, Secret Factory, and The Other Factory as
   low-evidence factories; collect more transaction history before trusting any model output
   about them specifically.
4. **Geographical analysis:** Extend the geographic reference table to cover Canadian provinces
   if Canadian shipping decisions are a priority (currently 2.0% of orders are excluded from
   distance-based analysis).
5. **Data quality (highest priority):** Correct the Ship Date generation/export process at its
   source. This is the single most valuable action identified in this research — every other
   finding in this paper is constrained by this one data-quality problem.
6. **Cost and profitability:** Before using this system for a real financial decision, replace
   the placeholder shipping-cost-per-mile and alternative-factory cost-multiplier assumptions
   with real freight and manufacturing cost figures.
7. **Operational risk:** Treat every "low confidence" or "unsupported" label in the dashboard as
   a hard stop for automated decision-making — these scenarios require human judgment.
8. **Future data collection:** Begin capturing actual shipment scan events (dispatch time,
   in-transit time, delivery confirmation) so a future version of this model can be trained on a
   genuine, validated lead-time signal.

No recommendation above claims a specific dollar saving or guaranteed delivery-time improvement,
because the analysis does not support such a claim.

---

## 12. Limitations

- **Reconstructed lead-time information.** The `lead_time_index` used throughout this project is
  a de-trended approximation designed to work around a corrupted raw field — it is **not** a
  validated measure of real shipping duration.
- **Missing actual factory costs.** No alternative-factory manufacturing cost data exists in the
  source; a default equal-cost assumption is used and clearly labeled.
- **Estimated freight charges.** The $0.015/mile/unit shipping-cost figure is an illustrative
  placeholder, not a negotiated freight rate.
- **Capacity assumptions.** No factory capacity data exists; the optimization engine does not
  enforce a capacity constraint because none can be verified.
- **Product-compatibility assumptions.** Compatibility with any factory other than each
  product's current one is an assumed default (same product division), not confirmed by the
  business.
- **Geographical approximation.** Distances use U.S. state centroids, not customer street
  addresses, and do not cover Canadian provinces.
- **Small product sample sizes.** Several products (e.g., Fun Dip, Everlasting Gobstopper, Hair
  Toffee) have fewer than 10 historical orders, which is too small for a statistically reliable
  individual conclusion.
- **Prediction uncertainty.** The selected model's test R² (0.038) means its predictions should
  be treated as weak/directional signals only, never as precise forecasts.

---

## 13. Conclusion

This research analyzed 10,194 historical order records from Nassau Candy Distributor to evaluate
whether the company's current factory-to-product allocation could be improved. The exploratory
data analysis uncovered a critical, previously undocumented problem: the dataset's shipping
lead-time field is not a valid measure of real-world delivery performance. This finding reshaped
every later stage of the project — instead of a straightforward "predict shipping days" model,
the research built a de-trended relative index, reported the resulting weak model performance
honestly (R² = 0.038), and built every downstream recommendation to reflect that honest
uncertainty rather than hide it.

The scenario simulation and constrained optimization engine, run across all 15 products,
concluded that the current factory allocation should be kept unchanged for every product. This
is not a disappointing result — it is the correct, defensible answer given the evidence
available, and it protects Nassau Candy from an unjustified operational disruption.

NexRoute AI supports decision-making not by forcing a recommendation, but by making the
uncertainty, the assumptions, and the data-quality problems visible and explicit at every step —
through its data-quality warnings, confidence labels, and labeled financial assumptions in the
Streamlit dashboard. The most important next step is fixing the underlying Ship Date data at its
source, after which this same pipeline can be re-run to produce a trustworthy, decision-grade
recommendation.

---

## 14. References

- Dataset: `Nassau Candy Distributor.csv`, supplied as the project's primary historical dataset.
- Van Rossum, G., & Drake, F. L. (2009). *Python 3 Reference Manual*. Python Software Foundation.
- McKinney, W. (2010). Data Structures for Statistical Computing in Python. *Proceedings of the
  9th Python in Science Conference*.
- Harris, C.R., Millman, K.J., van der Walt, S.J. et al. (2020). Array programming with NumPy.
  *Nature*, 585, 357–362.
- Hunter, J. D. (2007). Matplotlib: A 2D Graphics Environment. *Computing in Science &
  Engineering*, 9(3), 90-95.
- Waskom, M. L. (2021). seaborn: statistical data visualization. *Journal of Open Source
  Software*, 6(60), 3021.
- Pedregosa, F., Varoquaux, G., Gramfort, A. et al. (2011). Scikit-learn: Machine Learning in
  Python. *Journal of Machine Learning Research*, 12, 2825-2830.
- Streamlit Inc. Streamlit documentation. https://docs.streamlit.io/
- Virtanen, P., Gommers, R., Oliphant, T.E. et al. (2020). SciPy 1.0: Fundamental Algorithms for
  Scientific Computing in Python. *Nature Methods*, 17, 261-272.

---

*All figures referenced in this document (Figure 1–15) are provided as PNG files in
`eda_visualizations/`. All underlying numbers are reproducible from `EDA_Metrics_Summary.csv` and
the project's `reports/research_paper/*.csv` export files, generated directly from the project's
database and model artifacts — no number in this paper was invented or estimated without being
clearly labeled as such.*
