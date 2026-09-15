# Simulation results - Tesla Model 3 RWD (Highland)

**Generated:** 2026-09-15  
**Parameter file:** `/Users/tarikbilla/Projects/Electric-Vehicle-Technologies-and-Applications/data/vehicles/tesla_model_3_rwd_2024.yaml`  
**Driving cycle:** WLTC Class 3b (synthetic)  
**Assumed parameters:** 32 of 49, all shown <span style="color:#c0271c">in red</span>

---

## 1. Headline results

| Quantity | Simulated | Published | Deviation |
|---|---:|---:|---:|
| 0-100 km/h [s] | 6.1 | 6.1 | +0.7 % |
| Top speed [km/h] | 201.0 | 201.0 | +0.0 % |
| WLTP range (full battery) [km] | 508.3 | 513.0 | -0.9 % |
| Cycle consumption (battery side) [kWh/100km] | 11.5 | 11.7 | -2.1 % |

Cycle consumption is **11.45 kWh/100 km** at the battery terminals, and the predicted range on a full battery is **508 km**.

## 2. Vehicle and parameters

- Drivetrain: Single rear motor, single-speed reduction gear
- Battery chemistry: LFP (lithium iron phosphate)
- Kerb mass 1765 kg plus an assumed payload of <span style="color:#c0271c">100</span> kg, giving a test mass of 1865 kg
- Battery: <span style="color:#c0271c">62.5</span> kWh gross, <span style="color:#c0271c">60</span> kWh usable at <span style="color:#c0271c">345</span> V nominal
- Motor: 208 kW peak, 420 N m peak torque, single-speed <span style="color:#c0271c">9</span>:1 reduction
- Aerodynamics: C_d 0.219, frontal area <span style="color:#c0271c">2.22</span> m^2

The full parameter set, with the provenance of every value, is in [`assumption_register.md`](assumption_register.md).

## 3. Speed and acceleration characteristics

| quantity | value | unit |
|---|---:|---|
| Top speed | 201.00 | km/h |
| Maximum acceleration (from rest) | 4.79 | m/s^2 |
| Maximum wheel power | 203.84 | kW |
| Maximum tractive force | 9.30 | kN |
| 0-50 km/h | 2.95 | s |
| 0-100 km/h | 6.14 | s |
| 0-130 km/h | 8.93 | s |
| 0-160 km/h | 12.74 | s |


![Traction diagram: available force against running resistance](../figures/01_traction_diagram.png)

*Traction diagram: available force against running resistance*


![Speed and acceleration characteristic curves](../figures/02_acceleration_characteristic.png)

*Speed and acceleration characteristic curves*


![Power envelope and gradeability](../figures/03_power_and_gradeability.png)

*Power envelope and gradeability*


![Drive-unit efficiency map](../figures/04_efficiency_map.png)

*Drive-unit efficiency map*

## 4. Driving profile

Synthesised from the published WLTC Class 3b phase statistics (duration, distance, maximum speed and stop time reproduced to within 1 %).

| quantity | generated | published | deviation pct |
|---|---:|---:|---:|
| duration s | 1800.000 | 1800.000 | 0.000 |
| distance km | 23.268 | 23.266 | 0.007 |
| max speed kph | 131.300 | 131.300 | 0.000 |
| mean speed kph | 46.535 | 46.500 | 0.076 |
| stop time s | 243.000 | 242.000 | 0.413 |


![WLTC Class 3b (synthetic) speed and acceleration trace](../figures/05_driving_cycle.png)

*WLTC Class 3b (synthetic) speed and acceleration trace*

## 5. Cycle simulation

| quantity | value |
|---|---:|
| distance_km | 23.2677 |
| energy_traction_kwh | 3.3370 |
| energy_regen_kwh | 0.8224 |
| energy_auxiliary_kwh | 0.1500 |
| energy_friction_brake_kwh | 0.0088 |
| energy_drivetrain_loss_kwh | 0.4450 |
| energy_road_load_kwh | 2.0608 |
| energy_net_kwh | 2.6646 |
| consumption_wh_per_km | 114.5212 |
| consumption_internal_wh_per_km | 117.2845 |
| consumption_kwh_per_100km | 11.4521 |
| regen_fraction | 0.2464 |
| soc_start | 1.0000 |
| soc_end | 0.9576 |
| unmet_steps | 0.0000 |
| limited_steps | 0.0000 |
| max_tracking_error_kph | 0.0000 |
| depleted | 0.0000 |


![Speed, battery power and state of charge over the cycle](../figures/06_cycle_simulation.png)

*Speed, battery power and state of charge over the cycle*


![Energy balance over one cycle](../figures/07_energy_balance.png)

*Energy balance over one cycle*

## 6. Range on a full battery

| quantity | value |
|---|---:|
| range_integrated_km | 508.303 |
| range_analytic_km | 511.577 |
| method_disagreement_pct | -0.640 |
| consumption_kwh_per_100km | 11.452 |
| consumption_wh_per_km | 114.521 |
| consumption_internal_wh_per_km | 117.284 |
| usable_energy_kwh | 60.000 |
| energy_delivered_kwh | 58.378 |
| cycles_completed | 21.846 |

The *integrated* method repeats the cycle carrying the state of charge forward until the usable window is exhausted, so it sees the ohmic loss grow as the open-circuit voltage falls. The *analytic* method divides the usable energy by the cycle consumption and so assumes consumption is independent of the state of charge. Both divisions are made at the open-circuit level, which is where the usable energy is defined; the two agree to 0.64 %, which is the cross-check on the energy book-keeping.


![Discharge over repeated cycles and validation against the published range](../figures/08_range.png)

*Discharge over repeated cycles and validation against the published range*


![Range and consumption at steady cruising speed](../figures/09_constant_speed_range.png)

*Range and consumption at steady cruising speed*

## 7. Sensitivity to the assumptions

Ranked by how much each assumed parameter moves the range prediction across its plausible interval.

| Parameter | Interval | Range at low | Range at high | Span | Span of baseline |
|---|---|---:|---:|---:|---:|
| HVAC load | 0 - 3000 W | 508 km | 328 km | 181 km | 35.6 % |
| Regen power limit | 0 - 90000 W | 393 km | 508 km | 115 km | 22.6 % |
| Battery capacity | 57.5 - 66 kWh | 470 km | 539 km | 70 km | 13.7 % |
| Coastdown F2 (aero) | 0.34 - 0.44 N/(m/s)^2 | 531 km | 480 km | 52 km | 10.1 % |
| Coastdown F0 (rolling) | 95 - 140 N | 534 km | 483 km | 51 km | 10.1 % |
| Payload | 0 - 400 kg | 522 km | 481 km | 40 km | 7.9 % |
| Coastdown F1 (driveline) | 1.3 - 2.45 N/(m/s) | 527 km | 498 km | 28 km | 5.6 % |
| Gearbox efficiency | 0.96 - 0.992 - | 497 km | 521 km | 25 km | 4.8 % |
| Motor windage loss | 1e-06 - 3e-06 W/(rad/s)^3 | 520 km | 499 km | 22 km | 4.3 % |


![Sensitivity of the range prediction to the assumed parameters](../figures/10_sensitivity_tornado.png)

*Sensitivity of the range prediction to the assumed parameters*

## 8. Real-world scenarios

| Scenario | Conditions | Range | Consumption | Against certification |
|---|---|---:|---:|---:|
| WLTP certification | Auxiliaries off, driver only, standard air | 508 km | 11.45 kWh/100 km | +0 % |
| Mild weather, 2 occupants | Ventilation only, 20 degC | 455 km | 12.84 kWh/100 km | -10 % |
| Summer, air conditioning | A/C at 30 degC ambient, thinner air | 378 km | 15.46 kWh/100 km | -26 % |
| Winter, cabin + battery heating | Heating at 0 degC, cold and stiff tyres, dense air | 293 km | 20.03 kWh/100 km | -42 % |
| Fully loaded, roof box | Five occupants plus luggage on the roof | 394 km | 14.70 kWh/100 km | -22 % |


![Range under real-world conditions](../figures/11_scenarios.png)

*Range under real-world conditions*


![Parameter provenance](../figures/12_parameter_provenance.png)

*Parameter provenance*

## 9. Limitations

- No thermal model, so continuous-power derating and cold-battery resistance are not represented.
- No battery ageing; the results describe a new vehicle.
- The drive-unit efficiency comes from a four-term loss model fitted to plausible peak efficiencies, not from a measured map.
- The WLTC trace is synthesised from published phase statistics rather than the official second-by-second table.
