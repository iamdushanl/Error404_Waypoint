# Tech-Triathlon 2026: The Intelligent Enterprise

Challenge brief for designing and building a delivery planning system for **Waypoint Group**, followed by a data science solution for delivery and demand planning.

All dates and times use Sri Lanka time (`Asia/Colombo`, UTC+05:30). The competition data is synthetic.

## Competition Overview

Tech-Triathlon 2026 follows one business challenge across three phases over 15 days. The Designathon defines the experience, the Hackathon implements it, and the Datathon develops predictions that support planning.

| Milestone                   | Day | Deadline                              |
| --------------------------- | --: | ------------------------------------- |
| Brief and datasets released |   1 | Friday, September 25, 2026, 12:01 AM  |
| Designathon                 |   5 | Tuesday, September 29, 2026, 11:59 PM |
| Hackathon                   |  10 | Sunday, October 4, 2026, 11:59 PM     |
| Datathon                    |  15 | Friday, October 9, 2026, 11:59 PM     |

All three phases contribute equally to the overall score. The Hackathon build must follow the Designathon submission. Missing a phase results in zero for that phase, although the team may continue to the next phase.

## Waypoint Group

Waypoint Group (Pvt) Ltd is a fictional Sri Lankan retail group with three brands sharing one distribution network.

| Brand          | Outlets | Goods                               | Delivery schedule                 |
| -------------- | ------: | ----------------------------------- | --------------------------------- |
| Waypoint Fresh |      80 | Groceries, chilled and frozen goods | Daily; before stores open at 8 AM |
| Waypoint Style |      25 | Hanging garments and cartons        | Weekly, with seasonal peaks       |
| Waypoint Tech  |      15 | Appliances and consumer electronics | As needed; high-value and fragile |

The network serves 120 outlets through a distribution center in Peliyagoda and a regional hub in Kandy. Its 60 vehicles include 12 refrigerated trucks, 40 dry-box trucks, and eight small vans for outlets that larger vehicles cannot reach. Four vans are refrigerated, giving the fleet 16 vehicles that can carry chilled goods. Each vehicle operates from its assigned depot.

## Business Problem

The three brands compete for the same delivery capacity:

- Fresh deliveries must reach supermarkets before they open at 8 AM.
- Chilled orders require refrigerated vehicles.
- Some outlets can only be reached by van.
- Style orders are constrained by vehicle volume and mall delivery windows.
- Tech orders are heavy, fragile, valuable, and variable.
- Weekly fuel quotas, delivery windows, outlet access, and capacity all affect planning.
- When demand exceeds capacity, the dispatcher must decide which orders to defer and explain the consequences.

Current operations rely on spreadsheets, phone calls, conversations at the loading dock, and printed run sheets. The solution should improve planning, delivery visibility, deferral records, proof of delivery, demand forecasting, and offline field work.

## Operating Constraints

### Vehicles

- Every vehicle has both a weight limit and a volume limit.
- Only refrigerated vehicles may carry chilled or frozen goods. Refrigerated vehicles may also carry ambient goods.
- Each vehicle has a weekly fuel quota; route distance consumes that allowance.
- A vehicle can run up to two routes per day.
- Waypoint operates Monday through Saturday.
- Each vehicle has a driver. Driver availability is not a separate allocation constraint.

### Outlets

- Every outlet has a delivery window.
- Fresh deliveries must arrive before stores open at 8 AM, subject to each outlet's window.
- Mall outlets accept deliveries only within their fixed access window.
- Outlets marked `van_only` cannot be served by trucks.
- Unloading conditions vary: rear dock, curbside street access, or shared mall loading bay.

### Demand and Connectivity

- Paydays, festivals, weekends, and monsoon conditions affect demand or travel time.
- Use `calendar.csv` to identify operating dates.
- When demand exceeds capacity, deferred orders and the reason must be recorded.
- Mobile coverage can drop across hill country, the Kandy corridor, and rural districts.
- Work away from the depot must remain usable offline and reconcile when connectivity returns.

## User Roles and Workflow

| Role          | Working context                                                         | Needs                                                                                                    |
| ------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Dispatcher    | Large screen in the Peliyagoda planning office with stable connectivity | Build plans, track progress, understand problems, explain deferrals, identify repeatedly skipped outlets |
| Loader        | Shared tablet or terminal at the Peliyagoda or Kandy warehouse dock     | See stop sequence, load in unloading order, flag missing or damaged items before departure               |
| Driver        | Personal phone on the road                                              | Follow the route, record delivery outcomes and proof of delivery, work offline, synchronize later        |
| Store manager | Desktop or phone at the outlet counter                                  | Place orders, know expected arrival, receive deferral notices, confirm receipt, report issues            |

### Required End-to-End Flow

1. **Place order** - Store manager.
2. **Close orders** - Dispatcher captures and confirms orders before the cutoff.
3. **Plan and allocate** - Dispatcher brings orders into one queue, assigns served orders to vehicles and trips, and identifies deferred orders.
4. **Load** - Loader follows the planned stop sequence and flags shortfalls.
5. **Deliver** - Driver follows the route and records each stop, including while offline.
6. **Confirm receipt** - Store manager confirms what arrived and reports issues.
7. **Plan future capacity** - Dispatcher uses forecasts to plan vehicles, drivers, and refrigerated capacity.

## Shared Datasets

All phases use the same 120 outlets, 60 vehicles, two depots, and calendar.

| File           | Purpose                                                                                                           |
| -------------- | ----------------------------------------------------------------------------------------------------------------- |
| `outlets.csv`  | Outlet brand, district, depot, access restrictions, and delivery windows                                          |
| `vehicles.csv` | Vehicle type, temperature capability, weight and volume limits, fuel profile, and home depot                      |
| `calendar.csv` | Dates across the history and forecast horizon, including payday, festival, monsoon, and operating-day information |

Additional Datathon files are documented in the [Datathon Data Reference](#datathon-data-reference).

## Designathon

**Submission due:** Day 5, Tuesday, September 29, 2026, at 11:59 PM Sri Lanka time.

Design one system that helps all four roles complete the delivery workflow. Connect role-specific experiences so that dispatcher decisions reach loaders, driver records reach store managers, and each decision is explainable.

### Scope

Design the screens each role needs, including at least one fully developed failure scenario called a degradation screen. Explain the purpose and prioritization of each screen.

### Required Deliverables

- One user persona for each role.
- Screen flows for each role, with a paragraph of rationale for every screen.
- At least one fully designed degradation screen, with a name and rationale.
- A high-fidelity prototype in a design tool of choice.
- An unlisted YouTube demo video lasting three to five minutes, covering the design workflow and assumptions.
- AI tool disclosure describing AI-assisted and non-AI work and how tools were used.
- Optional: a core tradeoff explanation of up to one page or one diagram.
- Optional: a style guide.

### Judging Criteria

| Criterion                                                         | Weight |
| ----------------------------------------------------------------- | -----: |
| Problem framing                                                   |    25% |
| Understanding of user context                                     |    20% |
| Degradation screen quality                                        |    15% |
| Domain accuracy                                                   |    10% |
| Scope and prioritization                                          |    15% |
| Visual and interaction design, including consistency across roles |    15% |

### Submission

Organize personas, screen flows, rationales, degradation screens, diagrams, AI disclosure, and optional materials into one design file with distinct pages. Export it with base filename `TeamName_Designathon`, compress it as `TeamName_Designathon.zip`, and upload it through the submission form. Include shareable prototype and demo video links.

Submission form: https://forms.gle/H6dqUZP6pXdGC8Go8

The design may be refined during the Hackathon, but significant departures from the submitted design must be documented in the README.

## Hackathon

**Submission due:** Day 10, Sunday, October 4, 2026, at 11:59 PM Sri Lanka time.

Build the flows, screens, and capabilities in the Designathon submission. The submission must:

- Provide a responsive web application covering the delivery workflow across all four roles, from planning through loading and delivery to receipt.
- Work well on phone-sized screens for driver and loader experiences.
- Respect capacity, temperature, outlet access, delivery windows, and fuel quotas.
- Assign orders to vehicles and trips.
- Handle days when demand exceeds available capacity by identifying deferred orders.
- Use automatic allocation, assisted planning, or manual decisions with validation, provided the final allocation is feasible.

### Judge Walkthrough

Add a numbered walkthrough to the project README that a judge can follow across all four roles, from planning to completed delivery. Seed the system with the shared datasets and at least one realistic delivery day so the walkthrough works after a fresh installation.

### Required Deliverables

- Deployed system with a public URL and credentials for four seeded accounts, one per role.
- GitHub monorepo named `TeamName_SolutionName`.
- Root `README` with setup and configuration instructions, seeded account details, judge walkthrough, and significant departures from the Designathon.
- Root `docker-compose` file and `.env.example`. `docker compose up` must start the complete stack, including database and seed data.
- `docs` folder containing an architecture diagram and data model.
- AI tool disclosure in `docs`.
- Unlisted YouTube demo video lasting five to eight minutes. Show all four roles completing the walkthrough, then explain the code and architecture.

### Judging Criteria

| Criterion                                     | Weight |
| --------------------------------------------- | -----: |
| Functional completeness across all four roles |    20% |
| Planning and allocation engine                |    20% |
| Degradation, offline operation, and recovery  |    10% |
| Fidelity to the Day 5 design                  |    10% |
| Engineering quality and architecture          |    25% |
| Creativity                                    |     5% |
| Demo video                                    |    10% |

Submission form: https://forms.gle/WurHAKjbq2XEZQhbA

Submit the repository link, deployed URL, seeded account credentials, and demo video link. Keep the deployment live through the review period and, if applicable, the semifinal and Grand Finale periods.

## Datathon

**Submission due:** Day 15, Friday, October 9, 2026, at 11:59 PM Sri Lanka time.

The Datathon is judged separately from the Hackathon system. Teams do not need to integrate the Datathon solution into the Hackathon build.

Complete:

1. Task 1: predict service time and lateness.
2. Task 2A: forecast depot demand.
3. Task 2B: allocate the fleet on a peak day.

### Task 1: Predict Service Time and Lateness

For each planned order (`delivery_id`) in the test input, predict:

- `pred_service_min`: predicted handling time at the outlet, in minutes.
- `pred_late_prob`: probability that the order arrives after the outlet's delivery window closes.

Construct the training labels from the route and order data and document the reasoning. Early arrivals wait until the window opens. A late arrival is still delivered; lateness means arrival after the window closes. At prediction time, planned departure, travel duration, and arrival are available, while actual journey and handling times are available only in training route records.

**Inputs:** `task1_test_inputs.csv`, `route_legs_test.csv`, relevant files in Training Data and General Data.

**Output:** `submission_task1.csv`.

Requirements:

- Keep every `delivery_id` and the original row order unchanged.
- Fill only `pred_service_min` and `pred_late_prob`.
- `pred_late_prob` must be between 0 and 1.

### Task 2A: Forecast Depot Demand

Forecast demand for every depot, brand, and week combination across the 10 future weeks in the test inputs:

- `pred_total_volume_m3`: total ordered volume in cubic meters.
- `pred_chilled_volume_m3`: chilled portion of total volume in cubic meters.

Build training data from `deliveries_train.csv`, `task1_test_inputs.csv`, and `calendar.csv`.

Rules:

- Count every order once, including deferred and never-dispatched orders.
- Assign orders to the week requested by the store.
- Use `iso_year` and `iso_week` from `calendar.csv`.
- Only Fresh has chilled demand; use zero for Style and Tech.

**Input:** `task2a_test_inputs.csv`.

**Output:** `submission_task2a.csv`.

- Preserve every supplied `row_id`.
- Fill `pred_total_volume_m3` and `pred_chilled_volume_m3`.

### Task 2B: Allocate the Fleet on a Peak Day

Produce a complete allocation that:

- Marks every order `served` or `deferred`.
- Assigns every served order to one vehicle and one trip.
- Includes a written policy explaining allocation priorities and deferrals.

This does not require a trained model. Analyze demand and available capacity. There is no single correct allocation; feasibility and reasoning are assessed.

#### Scenario S1

Scenario S1 is a dispatch day at Peliyagoda. A festival is one week away, Fresh demand is rising, it is not a payday, there are no monsoon conditions, and several vehicles are in the workshop. Only vehicles marked `available` may be allocated.

**Inputs:**

- `task2b_peak_day_scenarios.csv`: every order, outlet, access restriction, delivery window, temperature requirement, and size.
- `task2b_peak_day_fleet.csv`: vehicle availability.
- `vehicles.csv`: vehicle capacity, temperature capability, and home depot.
- `district_travel.csv` and `service_allowance.csv`: trip-time inputs.

**Output:** `submission_task2b.csv`.

Keep `scenario`, `order_ref`, and `outlet_id` unchanged. Fill `decision`, `vehicle_id`, and `trip_id` for every row. For deferred orders, leave `vehicle_id` and `trip_id` blank.

| Column       | Required value                                        |
| ------------ | ----------------------------------------------------- |
| `scenario`   | Supplied identifier; always `S1`                      |
| `order_ref`  | Supplied unique order identifier and allocation key   |
| `outlet_id`  | Supplied outlet identifier                            |
| `decision`   | `served` or `deferred`                                |
| `vehicle_id` | Assigned vehicle for served orders; blank if deferred |
| `trip_id`    | `1` or `2` for served orders; blank if deferred       |

### Task 2B Feasibility Rules

1. **Brand and district:** all orders sharing a `vehicle_id` and `trip_id` must have the same brand and district.
2. **Refrigeration:** `chilled` orders require a vehicle with `temp = reefer`. Refrigerated vehicles may also carry ambient orders.
3. **Vehicle access:** outlets with `parking_constraint = van_only` require a vehicle with `type = van`.
4. **Home depot:** a vehicle may serve only outlets assigned to its own depot.
5. **Whole orders:** do not split an order across trips or vehicles.
6. **Capacity:** each trip must stay within both `volume_cap_m3` and `weight_cap_kg`.
7. **Trips and time:** each vehicle may run at most two trips, and trips must fit the daily budgets.

### Trip-Time Calculation

Each trip leaves the depot, travels to one district, and delivers its orders there. Do not add the return journey; the budgets already allow for it.

```text
trip_minutes = outbound travel + inter-stop travel + total handling time
```

1. **Outbound travel:** use `depot_to_district_freeflow_min` once per trip.
2. **Inter-stop travel:** use `inter_stop_freeflow_min * (number_of_orders - 1)`.
3. **Handling:** sum `service_allowance_min` for each order using its brand and dock type.

Example: a Fresh trip to Gampaha with three orders, two `rear_dock` stops, and one `street` stop takes:

| Component                         | Minutes |
| --------------------------------- | ------: |
| Depot to Gampaha                  |      37 |
| Two inter-stop journeys (`9 * 2`) |      18 |
| Fresh + rear dock                 |      15 |
| Fresh + rear dock                 |      15 |
| Fresh + street                    |      16 |
| **Total**                         | **101** |

Daily budgets per vehicle:

| Trip category           | Operating window   |                      Daily budget |
| ----------------------- | ------------------ | --------------------------------: |
| Fresh                   | 3:30 AM to 8:00 AM | 270 minutes total for Fresh trips |
| Style and Tech combined | Trading day        |                 480 minutes total |

The Fresh and Style/Tech budgets are separate, but the vehicle may still run only two trips in total. A vehicle may run one Fresh trip and one Style trip if both category budgets are respected.

### Written Prioritization Policy

Submit a policy of approximately one page or less. Show the allocation calculations and explain:

- Why orders were prioritized.
- Which resources limited service.
- Why specific orders were deferred.
- Which deferrals were unavoidable versus discretionary.
- The cost or consequence of the deferrals.

## Rules and Regulations

- The submission form closes after each deadline.
- Pre-trained models are prohibited except for synthetic data generation or preprocessing.
- Proprietary API-based modeling and preprocessing are prohibited.
- Cheating, plagiarism, or other rule violations result in disqualification.
- Low-code/no-code AI tools and fully automated end-to-end modeling tools are prohibited.

## Data Terms and Conditions

- Use the provided datasets only for this competition.
- Do not use the data for commercial purposes, academic research, or personal projects.
- Do not share, distribute, or transmit the datasets to any third party, publicly or privately.
- Do not publish or disclose the datasets or derivatives unless explicitly authorized by the organizers.
- Maintain the confidentiality of the datasets and any sensitive information they contain.
- Violations may result in disqualification.

## Datathon Deliverables

- Architecture diagrams showing models, preprocessing, and proposed deployment. High-level diagrams are sufficient.
- A data preprocessing document covering data preparation, label construction, cleaning, feature engineering, and rationale.
- Final model files saved alongside the notebook.
- `TeamName_FinalNotebook.ipynb`, retaining cells for label construction, preprocessing, training, and evaluation.
- A final notebook cell that loads saved models, demonstrates inference for Task 1 and Task 2A, and clearly prints inputs and predictions.
- `submission_task2b.csv` and the written prioritization policy.
- `submission_task1.csv` and `submission_task2a.csv` using the exact supplied columns and identifiers.
- An unlisted YouTube demo video lasting three to five minutes, covering architecture, preprocessing, label construction, and challenges.
- AI tool disclosure.

### Datathon Judging Criteria

| Criterion                                                | Weight |
| -------------------------------------------------------- | -----: |
| Data wrangling and label construction                    |    20% |
| Model and architecture implementation                    |    25% |
| Performance score for Task 1 and Task 2A                 |    20% |
| Task 2B allocation feasibility and prioritization policy |    15% |
| Creativity of the solution                               |    10% |
| Demo video                                               |    10% |

### Datathon Submission

Place all deliverables in one folder, compress it as `TeamName_Datathon.zip`, and upload it through the submission form.

Submission form: https://forms.gle/CcPPmttWdQgHvUdi6

## Datathon Data Reference

### Conventions

- Clock times use `HH:MM` in `Asia/Colombo`.
- Columns ending in `_time` contain clock times.
- Durations are measured in minutes.
- Columns ending in `_duration_min` contain durations.

### Training and Test Files

| File                            | Purpose                                                                                                                       |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `deliveries_train.csv`          | One row per order, identified by `delivery_id`. Dispatched orders map to one route leg through `route_id` and `seq_in_route`. |
| `route_legs_train.csv`          | One row per route leg, including planned and actual departure, travel, arrival, and completion times.                         |
| `task1_test_inputs.csv`         | Task 1 orders for a later period; all were dispatched.                                                                        |
| `route_legs_test.csv`           | Route legs for Task 1 with planned rather than actual times.                                                                  |
| `task2a_test_inputs.csv`        | One row per depot, brand, and forecast week.                                                                                  |
| `task2b_peak_day_scenarios.csv` | One row per order in the peak-day scenario.                                                                                   |
| `task2b_peak_day_fleet.csv`     | Vehicle availability for the peak-day scenario.                                                                               |

### Reference Tables

| File                    | Purpose                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| `outlets.csv`           | Outlet brand, district, depot, physical access, and delivery windows.    |
| `vehicles.csv`          | Vehicle type, temperature capability, capacity, fuel profile, and depot. |
| `calendar.csv`          | Calendar context.                                                        |
| `district_travel.csv`   | District travel distances and free-flow times.                           |
| `service_allowance.csv` | Standard handling-time allowance for each brand and dock type.           |
| `traffic_speed.csv`     | Typical congestion by district and hour.                                 |
| `road_conditions.csv`   | Date-specific district disruptions.                                      |

### Submission Templates

Use the exact filenames below. Keep all supplied identifiers and rows unchanged. Task 1 also requires the original row order.

| File                    | Task                                  |
| ----------------------- | ------------------------------------- |
| `submission_task1.csv`  | Service-time and lateness predictions |
| `submission_task2a.csv` | Weekly depot demand forecasts         |
| `submission_task2b.csv` | Peak-day allocation                   |

### Order Records

`deliveries_train.csv` and `task1_test_inputs.csv` contain one row per order.

| Column                                       | Meaning                                                                              |
| -------------------------------------------- | ------------------------------------------------------------------------------------ |
| `delivery_id`                                | Unique order identifier and Task 1 prediction key.                                   |
| `order_date`                                 | Date the store's order was for.                                                      |
| `dispatch_date`                              | Dispatch date; blank if the order never ran.                                         |
| `dispatch_status`                            | `attempted`, `deferred`, or `not_run`.                                               |
| `outlet_id`, `brand`, `district`, `depot`    | Outlet information.                                                                  |
| `temp_requirement`                           | `chilled` requires a refrigerated vehicle; `ambient` does not.                       |
| `order_units`                                | Number of items or cases.                                                            |
| `order_weight_kg`                            | Order weight in kilograms.                                                           |
| `order_volume_m3`                            | Order volume in cubic meters.                                                        |
| `route_id`                                   | Route carrying the order; blank if never run.                                        |
| `seq_in_route`                               | Route position starting at 0; together with `route_id`, identifies the matching leg. |
| `vehicle_id`, `vehicle_type`, `vehicle_temp` | Vehicle assigned to the order.                                                       |
| `planned_arrival_time`                       | Planned arrival time.                                                                |
| `window_open_time`, `window_close_time`      | Start and end of the requested delivery window.                                      |

### Route Legs

`route_legs_train.csv` and `route_legs_test.csv` contain one row per route leg.

| Column                                                                                  | Meaning                                                   |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `leg_id`                                                                                | Unique route-leg identifier.                              |
| `date`                                                                                  | Date the route ran.                                       |
| `route_id`, `seq`                                                                       | Route identifier and position starting at 0.              |
| `depot`, `vehicle_id`, `vehicle_type`, `vehicle_temp`, `brand`, `district`              | Route attributes.                                         |
| `from_point`                                                                            | `DEPOT` for the first leg; otherwise the previous outlet. |
| `to_outlet`                                                                             | Outlet served by the leg.                                 |
| `distance_km`                                                                           | Road distance in kilometers.                              |
| `planned_depart_time`, `planned_travel_duration_min`, `planned_arrival_time`            | Planned route timings.                                    |
| `actual_depart_time`, `actual_travel_duration_min`, `arrival_time`, `leave_outlet_time` | Training-only actual timings and completion time.         |
| `monsoon`                                                                               | `1` for a monsoon or inter-monsoon month; otherwise `0`.  |
| `dow`                                                                                   | Day of week, with `0` representing Monday.                |

### Outlet and Vehicle Tables

`outlets.csv` contains `outlet_id`, `brand`, `district`, `depot`, `dock_type`, `parking_constraint`, `mall_window`, `window_open_time`, and `window_close_time`. Outlet IDs run from `OUT001` through `OUT120`. Dock types are `rear_dock`, `street`, and `mall_bay`. Parking constraints are `normal` and `van_only`; `mall_dock` access is limited to the mall delivery window.

`vehicles.csv` contains `vehicle_id`, `type`, `temp`, `weight_cap_kg`, `volume_cap_m3`, `fuel_type`, `km_per_l`, `weekly_fuel_quota_l`, and `depot`. `type` distinguishes trucks and vans. `temp` is `reefer` or `ambient`; only reefer vehicles can carry chilled goods.

### Calendar and Travel Tables

`calendar.csv` contains `date`, `dow`, `dow_name`, `is_weekend`, `iso_year`, `iso_week`, `is_payday`, `festival`, `festival_ramp`, `is_holiday`, `monsoon`, and `is_operating`.

`district_travel.csv` contains `district`, `depot`, `road_class`, `free_flow_kmh`, `depot_to_district_km`, `depot_to_district_freeflow_min`, `inter_stop_km`, and `inter_stop_freeflow_min`.

`service_allowance.csv` contains one row per `brand` and `dock_type`, with `service_allowance_min` as the planning allowance per stop.

`traffic_speed.csv` documents `monsoon` and `speed_index`, where 100 means free-flowing traffic and lower values mean slower travel.

`road_conditions.csv` documents `disruption_index`, where 100 means clear conditions and lower values represent disruptions such as roadworks, flooding, or incidents.

### Peak-Day Tables

`task2b_peak_day_scenarios.csv` contains `scenario`, `order_ref`, outlet and network identifiers, access restrictions, delivery windows, temperature requirement, order size, `deferred_yesterday`, and `days_since_last_served`.

`task2b_peak_day_fleet.csv` contains `scenario`, `vehicle_id`, and `status`. Only vehicles with status `available` may be allocated; `in_workshop` vehicles cannot be used.

## Validation

`check_allocation.py` validates the Task 2B allocation against feasibility rules. Passing the checks confirms that the allocation is feasible, not that it is optimal. Judges assess prioritization and the explanation of deferrals.

## Contact

For questions: tech-triathlon@rootcode.io

Good luck!
