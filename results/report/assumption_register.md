# Assumption register

**Vehicle:** Tesla Model 3 RWD (Highland) (2024)  
**Parameter file:** `/Users/tarikbilla/Projects/Electric-Vehicle-Technologies-and-Applications/data/vehicles/tesla_model_3_rwd_2024.yaml`  
**Generated:** 2026-09-15

Of the 49 parameters in the model, **32** are engineering assumptions rather than published or measured data. Every assumed value is shown <span style="color:#c0271c">in red</span> throughout this report, as required by the project brief.

Each assumption was chosen from the manufacturer's own documentation where it exists, from independent teardowns and measurements where it does not, and otherwise from the standard automotive literature. The sensitivity study quantifies how much each one actually matters to the final result.

## Assumed parameters

| # | Parameter | Value | Unit | Basis for the assumption |
|--:|---|---:|---|---|
| 1 | `aerodynamics.frontal_area` | <span style="color:#c0271c">2.22</span> | m^2 | Not published. Estimated as 0.83 * width * height = 0.83*1.933*1.441 |
| 2 | `auxiliaries.base_load` | <span style="color:#c0271c">300</span> | W | 12 V systems, pumps, computer, lights - measured idle draw ~250-350 W |
| 3 | `auxiliaries.hvac_load` | <span style="color:#c0271c">0</span> | W | WLTP certification is run with auxiliaries off; set >0 for a real-world scenario |
| 4 | `battery.gross_capacity` | <span style="color:#c0271c">62.5</span> | kWh | Not published. LFP pack, teardown/BMS logs report ~62.5 kWh gross |
| 5 | `battery.internal_resistance` | <span style="color:#c0271c">0.075</span> | ohm | Pack-level DC resistance at 25 degC; typical for a 60 kWh LFP pack |
| 6 | `battery.max_charge_power` | <span style="color:#c0271c">7e+04</span> | W | Regenerative braking limited to ~70 kW on single-motor Model 3 |
| 7 | `battery.max_discharge_power` | <span style="color:#c0271c">2.2e+05</span> | W | Must cover motor peak power plus losses |
| 8 | `battery.nominal_voltage` | <span style="color:#c0271c">345</span> | V | LFP prismatic cells, ~106s configuration at 3.25 V/cell nominal |
| 9 | `battery.usable_fraction` | <span style="color:#c0271c">0.96</span> | - | LFP allows a wide SOC window (charge to 100 % recommended); 4 % buffer |
| 10 | `mass.cg_height` | <span style="color:#c0271c">0.46</span> | m | Skateboard battery pack -> very low CG; literature range 0.45-0.50 m for Model 3 |
| 11 | `mass.rear_axle_static_load_fraction` | <span style="color:#c0271c">0.52</span> | - | Measured 48/52 front/rear distribution reported for single-motor Model 3 |
| 12 | `mass.rotational_mass_factor` | <span style="color:#c0271c">1.04</span> | - | Typical single-speed BEV value (Ehsani, Modern Electric Vehicles, Tab. 2.2); lambda = 1 + J_eq/(m*r^2) |
| 13 | `mass.test_payload` | <span style="color:#c0271c">100</span> | kg | WLTP test mass = kerb + 25 kg; 100 kg chosen as driver+luggage for a realistic single-occupant run |
| 14 | `motor.continuous_power_fraction` | <span style="color:#c0271c">0.55</span> | - | Thermal derating; continuous rating typically 50-60 % of peak for liquid-cooled PMSM |
| 15 | `motor.loss_k_copper` | <span style="color:#c0271c">0.09042</span> | W/(N*m)^2 | Least-squares fit to seven operating points typical of a liquid-cooled automotive PMSM drive unit: 97 % peak, 92.5 % at peak power, 88 % at light load / high speed (motorway cruise), 80 % at light load / low speed |
| 16 | `motor.loss_k_iron` | <span style="color:#c0271c">0.669</span> | W/(rad/s) | Fitted with loss_k_copper, see above |
| 17 | `motor.loss_k_windage` | <span style="color:#c0271c">1.79e-06</span> | W/(rad/s)^3 | Fitted with loss_k_copper. An earlier hand-tuned value of 5.0e-6 made windage 73 % of all loss at motorway cruise, which is unphysical for a sealed oil-cooled rotor; the fitted value puts it at 26 % |
| 18 | `motor.loss_p_constant` | <span style="color:#c0271c">185.9</span> | W | Fitted with loss_k_copper. Inverter switching and control electronics standby losses |
| 19 | `motor.max_speed` | <span style="color:#c0271c">1.79e+04</span> | rpm | Not published; Model 3 rear drive unit teardowns report ~17 900-18 000 rpm |
| 20 | `regeneration.blend_speed` | <span style="color:#c0271c">4.2</span> | m/s | Linear blend-in of regen between cutoff (5 km/h) and 15 km/h |
| 21 | `regeneration.cutoff_speed` | <span style="color:#c0271c">1.4</span> | m/s | Regen blends out below ~5 km/h, friction brakes take over |
| 22 | `regeneration.max_regen_power` | <span style="color:#c0271c">7e+04</span> | W | Observed regen ceiling on single-motor Model 3 (~70 kW) |
| 23 | `regeneration.max_regen_torque_fraction` | <span style="color:#c0271c">0.6</span> | - | Regen shaft torque limited to ~60 % of traction peak torque |
| 24 | `road_load.coastdown_f0` | <span style="color:#c0271c">115.7</span> | N | EPA coastdown target A = 26.0 lbf for Model 3 RWD, converted to SI. Certification values vary with model year and wheel size |
| 25 | `road_load.coastdown_f1` | <span style="color:#c0271c">1.891</span> | N/(m/s) | EPA coastdown target B = 0.1900 lbf/mph, converted to SI |
| 26 | `road_load.coastdown_f2` | <span style="color:#c0271c">0.3784</span> | N/(m/s)^2 | EPA coastdown target C = 0.01700 lbf/mph^2, converted to SI |
| 27 | `road_load.coastdown_test_mass` | <span style="color:#c0271c">1900</span> | kg | Mass the coastdown was run at (EPA test weight = kerb + ~136 kg). The F0 term is rolling resistance and is proportional to normal load, so it is scaled by m/m_test when the vehicle is loaded differently. Without this the model would say payload is almost free, because the inertia it adds is largely returned by regeneration |
| 28 | `transmission.efficiency` | <span style="color:#c0271c">0.98</span> | - | Load-dependent meshing loss ONLY, for a single-stage helical reduction plus differential. The no-load churning, bearing and seal drag is already inside the coastdown F0/F1 terms - an electric drive unit cannot be disconnected during a coastdown - so a flat 0.96-0.97, which lumps both together, would count that drag twice |
| 29 | `transmission.gear_ratio` | <span style="color:#c0271c">9</span> | - | Not published; independent teardown of Model 3 rear drive unit gives 9.0:1 |
| 30 | `tyres.peak_friction_coefficient` | <span style="color:#c0271c">0.85</span> | - | Dry asphalt, summer tyre, launch-control traction limit |
| 31 | `tyres.rolling_resistance_coefficient` | <span style="color:#c0271c">0.008</span> | - | EU tyre label class A-B low rolling resistance OE tyre; f_r = 0.008 at 20 degC |
| 32 | `tyres.rolling_resistance_speed_coefficient` | <span style="color:#c0271c">1.2e-06</span> | s^2/m^2 | f_r(v) = f_r0 + k*v^2, k typical for passenger car radials (Mitschke/Wallentowitz) |

## Published and measured parameters

| # | Parameter | Value | Unit | Source |
|--:|---|---:|---|---|
| 1 | `aerodynamics.air_density` | 1.204 | kg/m^3 | ISO 1204 standard air, 20 degC, 101.325 kPa |
| 2 | `aerodynamics.drag_coefficient` | 0.219 | - | Tesla published Cd for Model 3 Highland (2024) |
| 3 | `battery.soc_max` | 1 | - | Full battery per the project brief |
| 4 | `battery.soc_min` | 0 | - | Range is defined from 100 % to 0 % of the usable window |
| 5 | `environment.gravity` | 9.807 | m/s^2 | ISO 80000-3 standard gravity |
| 6 | `environment.headwind` | 0 | m/s | Still air per cycle definition |
| 7 | `environment.road_grade` | 0 | rad | WLTP and NEDC are flat-road cycles |
| 8 | `mass.curb_mass` | 1765 | kg | Tesla EU technical data sheet, Model 3 RWD 2024 (kerb mass incl. 75 kg driver) |
| 9 | `mass.wheelbase` | 2.875 | m | Tesla Model 3 dimensional data sheet |
| 10 | `motor.peak_power` | 2.08e+05 | W | Tesla / EU type approval, Model 3 RWD 2024 (208 kW) |
| 11 | `motor.peak_torque` | 420 | N*m | Tesla technical data, Model 3 RWD (420 N*m shaft torque) |
| 12 | `reference.acceleration_0_100_kph` | 6.1 | s | Tesla published figure, Model 3 RWD 2024 (incl. 1-ft rollout) |
| 13 | `reference.speed_limiter` | 201 | km/h | Tesla published electronic limiter |
| 14 | `reference.top_speed` | 201 | km/h | Tesla published figure (electronically limited) |
| 15 | `reference.wltp_consumption` | 13.2 | kWh/100km | EU type-approval combined WLTP consumption (incl. charging losses) |
| 16 | `reference.wltp_range` | 513 | km | Tesla EU data sheet, Model 3 RWD 2024, 18-inch wheels |
| 17 | `tyres.dynamic_radius` | 0.3323 | m | Rolling circumference 2088 mm (ETRTO for 235/45 R18) / (2*pi) |

## Modelling assumptions that are not single numbers

| Assumption | Why | Effect on the result |
|---|---|---|
| <span style="color:#c0271c">Quasi-static (backward-facing) simulation</span> | The speed trace is the input; no driver model or closed-loop control is needed for an energy study | None, provided the powertrain can follow the trace, which the simulation verifies at every step |
| <span style="color:#c0271c">Constant battery internal resistance</span> | No temperature or state-of-charge dependence published | Ohmic loss is a small share of the total; the two range methods bracket the error |
| <span style="color:#c0271c">No thermal model</span> | Out of scope per the brief | Continuous power derating is not captured; it does not bind on a legislative cycle |
| <span style="color:#c0271c">No battery ageing</span> | Out of scope per the brief | Results apply to a new vehicle |
| <span style="color:#c0271c">Synthesised WLTC trace</span> | The official 1800-point table is copyright and not redistributed here | Cycle statistics are reproduced to within 0.5 %; see the cycle validation table |
