# Round 2: Expanded three-arm run

120 questions, three arms. Same 1-5 LLM-judge scoring for correctness and faithfulness.

## Scores

| Arm | Mean correctness | Mean faithfulness |
|---|---|---|
| PolicyBridge (RAG + graph) | 4.39/5 | 4.19/5 |
| Vanilla vector RAG | 3.96/5 | 4.00/5 |
| ChatGPT (manual) | 2.72/5 | 3.01/5 |

## Questions and answers

### L1-FIRE-001. Per WAC 51-54A 806 (decorative vegetation), what maximum height of outdoor artificial combustible vegetation triggers the placement and clearance restrictions?

**Reference answer:** 6 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 2/5

> Outdoor artificial combustible vegetation that is more than 6 feet high and permanently installed within 5 feet of a building or on a building roof is subject to the placement and clearance restrictions (must comply with Section 807.4.1 and placement must comply with Sections 806.3 and 807.4.2). `[WAC 51-54A-0321]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The trigger is when artificial combustible vegetation exceeds 6 feet (1829 mm) in height and is permanently installed outdoors within 5 feet of a building or on a roof; at that point it must comply with Section 807.4.1 and related placement provisions. [Source 1] WAC — wac_chapters, § 51-54, p.11 | Parameter | Threshold / Requirement | Citation | |-------------------------------------|----------------------------------|----------| | Maximum height before rules apply | 6 feet (1829 mm) | [Source 1] | | Distance from building for trigger | Within 5 feet (1524 mm) or on roof | [Source 1] |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0806 (Decorative vegetation / artificial combustible vegetation), the placement and clearance restrictions are triggered when outdoor artificial combustible vegetation exceeds: * 6 feet (72 inches) in height At or below 6 feet, the item is treated under general decorative placement rules; above that height, the additional clearance and separation requirements apply (including distance from building exterior walls and other ignition sources). ### Final answer: → 6 feet maximum height threshold (above this triggers restrictions).

---

### L1-FIRE-002. Per WAC 51-54A 322.4.1 (limited indoor battery storage), what is the maximum aggregate volume of lithium-ion or lithium metal batteries permitted?

**Reference answer:** 15 cubic feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum aggregate volume of lithium-ion or lithium metal batteries permitted under limited indoor storage in containers is 15 cubic feet. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Under WAC 51-54A-0322.4.1, the maximum aggregate volume of lithium-ion or lithium metal batteries permitted for limited indoor storage in containers is 15 cubic feet (0.42 m³). [Source 2] WAC — wac_chapters, § 51-54, p.12

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322.4.1 (Limited indoor storage in containers), the maximum permitted aggregate volume for lithium-ion or lithium metal batteries is: * 15 cubic feet (0.42 m³) total aggregate storage This is the overall cap for all qualifying battery containers within a limited indoor storage area. ### Final answer: → 15 cubic feet maximum aggregate volume.

---

### L1-FIRE-003. Per WAC 51-54A 322.4.1, what is the maximum volume (cubic feet) of a single container in a limited indoor lithium-ion battery storage area?

**Reference answer:** 7.5 cubic feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum volume of a single container (or group of containers) in a limited indoor lithium-ion battery storage area is 7.5 cubic feet. `322.4.1` `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The maximum volume of a single container in a limited indoor lithium-ion battery storage area is 7.5 cubic feet (0.21 m³), as individual containers and groups of containers “shall not exceed a capacity of 7.5 cubic feet.” [Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322.4.1 (Limited indoor lithium-ion/lithium metal battery storage in containers), the maximum permitted size of a single container (or group of containers treated as one) is: * 7.5 cubic feet (0.21 m³) This limit applies to each individual container or grouped set within the limited indoor storage arrangement. ### Final answer: → 7.5 cubic feet maximum per container.

---

### L1-FIRE-004. Per WAC 51-54A 322.4.1, what is the minimum required open-space separation between battery containers in limited indoor storage?

**Reference answer:** 3 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required open-space separation between a second battery container (or group of containers) and the first is 3 feet of open space, or 10 feet where the intervening space contains combustible materials. `322.4.1(3)` `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 2/5

> The minimum required open-space separation between a second container (or group of containers) and the first is 3 feet (914 mm) of open space, or 10 feet (3048 mm) if the intervening space contains combustible materials.[Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322.4.1 (Limited indoor lithium-ion/lithium metal battery storage in containers), the required separation between containers or groups of containers is: * 3 feet (914 mm) of open space, or * 10 feet (3048 mm) if the intervening space contains combustible materials ### Final answer: → 3 feet minimum open-space separation (10 feet if combustible materials are present).

---

### L1-FIRE-005. Per WAC 51-54A 3307 (construction fire safety), what is the minimum fire flow required when a building has a fire separation of less than 30 feet from property lot lines?

**Reference answer:** 500 gallons per minute

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> Where a Type III, IV, or V building has a fire separation distance of less than 30 feet from property lot lines and the adjacent property has an existing or buildable structure, the water supply must provide at least 500 gallons per minute or the entire required fire flow for the completed building, whichever is greater. `WAC 51-54A-3307`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> For buildings of Type III, IV, or V construction with a fire separation distance of less than 30 feet from property lot lines, the minimum required fire flow is 500 gallons per minute (1893 L/min) or the entire fire flow required for the building when constructed, whichever is greater.[Source 2] | Condition | Minimum Fire Flow Requirement | Citation | |--------------------------------------------------------------------------|--------------------------------------------------------------------|------------| | Type III, IV, or V building; fire separation < 30 ft from property lines | 500 gpm (1893 L/min) or full required building fire flow, whichever is greater | [Source 2] |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-3307.2.2.1 (construction fire flow requirements), when a building under construction has a fire separation distance of less than 30 feet from property lines (and potentially exposed adjacent properties), the minimum required fire flow is: * 500 gallons per minute (gpm) * Or the full calculated fire flow required for the completed building, * whichever is greater ### Final answer: → 500 gpm minimum (or higher if the calculated finished-building fire flow exceeds it).

---

### L1-FIRE-006. Per WAC 51-54A 510.4.1.1, what is the minimum required inbound signal strength for emergency responder communication coverage inside a building?

**Reference answer:** -95 dBm

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 2/5

> The minimum required inbound signal strength is -95 dBm in 95 percent of the coverage area and 99 percent of critical areas, with performance sufficient to provide at least DAQ 3.0 or equivalent SINR. `[WAC 51-54A-0323]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The minimum required inbound signal strength is -95 dBm inside the building. The code specifies that the inbound signal level must be at least -95 dBm in 95% of the coverage area and 99% of critical areas, with delivered audio quality (DAQ) of at least 3.0 or equivalent SINR for the technology used. [Source 1] WAC — wac_chapters, § 51-54, p.19; [Source 5] WAC — wac_chapters, § 51-54, p.18

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-510.4.1.1 (Emergency responder communication coverage – minimum performance), the required inbound signal strength inside a building is: * −95 dBm minimum inbound signal strength This level must be achieved in the required percentage of coverage areas (with additional requirements for critical areas as specified in the section), ensuring reliable emergency responder radio communication throughout the structure. ### Final answer: → −95 dBm minimum inbound signal strength.

---

### L1-FIRE-007. Per WAC 51-54A 1015.3, what is the minimum height of a required guard?

**Reference answer:** 42 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum height of a required guard is 42 inches measured vertically from the adjacent walking surface, stair tread nosing line, or ramp surface, as applicable. `WAC 51-54A-1015`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1015.3, required guards must be not less than 42 inches (1067 mm) high, measured vertically from the adjacent walking surfaces, from a line connecting the leading edges of stair tread nosings, or from the ramp surface at the guard. [Source 5]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1015.3 (Guards), the minimum required height of a guard is: * 42 inches (1067 mm) above the adjacent walking surface, floor, or ramp A commonly allowed exception is: * 36 inches (914 mm) in certain Group R occupancies and within dwelling units, depending on conditions specified in the code. ### Final answer: → 42 inches minimum guard height (36 inches allowed in limited residential exceptions).

---

### L1-FIRE-008. Per WAC 51-54A 1014.2.1, what is the minimum handrail height above stair tread nosings?

**Reference answer:** 34 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum handrail height above stair tread nosings is 34 inches. `[WAC 51-54A-1014]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum handrail height above stair tread nosings is 34 inches (864 mm) per WAC 51-54A-1014.2.1. [Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1014.2.1 (Handrails), the top of handrails must be installed at a height of: * 34 inches minimum to 38 inches maximum above the stair tread nosings This range is measured vertically from the nosing line of the stair treads. ### Final answer: → 34 inches minimum (within a 34–38 inch range above tread nosings).

---

### L1-FIRE-009. Per WAC 51-54A 5707 (mobile fueling), what is the maximum permitted length of a fuel-dispensing hose?

**Reference answer:** 50 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The dispensing hose shall not exceed 50 feet in length. `WAC 51-54A-5707`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The maximum permitted length of a fuel-dispensing hose for mobile fueling operations is 50 feet (15,240 mm). | Item | Maximum Length | Citation | |-------------------------------|----------------|----------| | Mobile fueling dispensing hose| 50 feet | [Source 4] WAC — wac_chapters, § 51-54, p.80 |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-5707 (Mobile fueling operations), the maximum permitted length of a fuel-dispensing hose is: * 50 feet (15,240 mm) This limit applies to mobile fueling systems to reduce hazard exposure during fueling operations and maintain control of hose management and emergency shutoff effectiveness. ### Final answer: → 50 feet maximum hose length.

---

### L1-FIRE-010. Per WAC 51-54A 1008 (means of egress illumination), what is the minimum duration of emergency-power-supplied egress illumination?

**Reference answer:** 90 minutes

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum duration is 90 minutes of emergency-power-supplied means-of-egress illumination. `[WAC 51-54A-1008]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 3/5

> From the provided materials, WAC 51-54A-1008 only states that Section 1008.2.3 (Exit discharge) “is not adopted” and does not specify a minimum duration for emergency-power-supplied egress illumination. [Source 6] However, WAC 51-50-2702 (Emergency and standby power systems) requires that emergency power systems be designed to provide required power for a minimum of 8 hours without refueling or recharging, with an exception allowing reduction to 2 hours for all required power loads except fire pumps, which must remain at 8 hours. [Source 3] | Requirement | Minimum Duration | Citation | |--------------------------------------------------|------------------|-----------------| | General emergency/standby power loads | 8 hours | [Source 3] | | Reduced duration for required power loads (not including fire pumps) | 2 hours (if exception used) | [Source 3] | | Fire pumps (emergency power) | 8 hours | [Source 3] | The specific minimum duration for egress illumination under WAC 51-54A-1008 itself could not be determined from the available materials.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1008 (Means of egress illumination), emergency-powered illumination for means of egress must be capable of providing light for a minimum duration of: * 90 minutes This applies when normal power fails and illumination is supplied by emergency systems such as batteries or generators. ### Final answer: → 90 minutes minimum duration.

---

### L1-PARK-001. Under SMC 23.54.030, what is the minimum width of a 'medium vehicle' parking space?

**Reference answer:** 8 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Under `SMC 23.54.030.A.2`, a "medium vehicle" parking space must be at least 8 feet in width. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum width of a “medium vehicle” parking space under SMC 23.54.030 is 8 feet. | Vehicle size category | Minimum width | Citation | |-----------------------|---------------|----------| | Medium vehicle | 8 feet | [Source 1] SMC — smc_chapters, § 23.54.030, p.829 |

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030 (Parking space standards), the minimum width for a “medium vehicle” parking space is: * 8 feet 6 inches (8.5 feet) This is the code’s defined stall width for medium-vehicle parking spaces, distinct from compact and standard/large vehicle stalls. ### Final answer: → 8 feet 6 inches minimum width.

---

### L1-PARK-002. Under SMC 23.54.030, what is the minimum length of a 'medium vehicle' parking space?

**Reference answer:** 16 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Under `SMC 23.54.030.A.2`, a "medium vehicle" parking space must be at least 16 feet in length. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum length of a “medium vehicle” parking space under SMC 23.54.030 is 16 feet. A medium vehicle space must be at least 8 feet in width and 16 feet in length.[Source 1]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030 (Parking space standards), a “medium vehicle” parking space must have a minimum length of: * 17 feet 6 inches (17.5 feet) ### Final answer: → 17 feet 6 inches minimum length.

---

### L1-PARK-003. Under SMC 23.54.030.B.2, in a nonresidential parking lot of 20 or more spaces, what is the maximum percentage of spaces that may be striped for small vehicles?

**Reference answer:** 65 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> In a nonresidential parking lot with 20 or more spaces, a maximum of 65 percent of the parking spaces may be striped for small vehicles. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For nonresidential uses with 20 or more parking spaces, a maximum of 65 percent of the parking spaces may be striped for small vehicles under SMC 23.54.030.B.2.[Source 8]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.B.2, in a nonresidential parking lot with 20 or more spaces, the maximum share of stalls that may be striped for small vehicles is: * 40% of total parking spaces ### Final answer: → 40% maximum.

---

### L1-PARK-004. Under Table A for SMC 23.54.030, what is the required aisle width for 90-degree medium-vehicle parking?

**Reference answer:** 22 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The required aisle width for 90-degree medium-vehicle parking is 22 feet for one-way traffic. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts reference Table A for 23.54.030 and state that required aisle width is specified there, but the actual numeric aisle width for 90‑degree medium‑vehicle parking is not included in the retrieved text.[Source 1][Source 4]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Under SMC 23.54.030, Table A (Parking space and aisle standards), the required aisle width for 90-degree medium-vehicle parking is: * 22 feet minimum aisle width This is the standard two-way aisle dimension for perpendicular parking served by medium-vehicle stalls. ### Final answer: → 22 feet.

---

### L1-PARK-005. Per RCW 36.70A.635(6)(e), what is the maximum number of off-street parking spaces per unit a city may require for middle housing on lots no greater than 6,000 square feet?

**Reference answer:** 1

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 2/5

> A city may not require more than one off-street parking space per middle housing unit on lots no greater than 6,000 square feet. `[WAC 365-196-872]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For middle housing on lots no greater than 6,000 square feet, RCW 36.70A.635(6)(e) limits cities to requiring no more than one off-street parking space per unit. This is contrasted with subsection (6)(f), which allows up to two spaces per unit on lots greater than 6,000 square feet.[Source 11] RCW — rcw_chapters, § 36.70, p.129

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per RCW 36.70A.635(6)(e), for middle housing on lots no greater than 6,000 square feet, a city may not require more than: * 0.5 off-street parking spaces per dwelling unit ### Final answer: → 0.5 spaces per dwelling unit (maximum).

---

### L1-PARK-006. Per RCW 36.70A.635(6)(f), what is the maximum number of off-street parking spaces per unit a city may require for middle housing on lots greater than 6,000 square feet?

**Reference answer:** 2

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 2/5

> A city may not require more than two off-street parking spaces per unit for middle housing on lots greater than 6,000 square feet before any zero lot line subdivisions or lot splits. `[WAC 365-196-872]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The maximum number of off-street parking spaces a city may require is two spaces per unit for middle housing on lots greater than 6,000 square feet, as stated in RCW 36.70A.635(6)(f): “shall not require more than two off-street parking spaces per unit.” [Source 9] RCW — rcw_chapters, § 36.70, p.129

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per RCW 36.70A.635(6)(f), for middle housing on lots greater than 6,000 square feet, a city may not require more than: * 1.0 off-street parking space per dwelling unit ### Final answer: → 1 parking space per dwelling unit (maximum).

---

### L1-PARK-007. Per WAC 51-50-1101.2.7, what is the minimum required width (in inches) of a car or van accessible parking space?

**Reference answer:** 96

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of a car or van accessible parking space is 96 inches. `[WAC 51-50-1101]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of both car and van accessible parking spaces is 96 inches (2440 mm) per WAC 51-50-1101.2.7.[Source 3]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Per WAC 51-50-1101.2.7 (accessible parking space dimensions), the minimum required widths are: * Car accessible space: 96 inches (8 feet) minimum * Van accessible space: 132 inches (11 feet) minimum *(or 144 inches if the access aisle is configured differently to provide van access compliance)* ### Final answer: * Car: 96 inches * Van: 132 inches (minimum standard)

---

### L1-PARK-008. Per SMC 23.54.030.I, what is the required width (in feet) of an off-street bus parking space?

**Reference answer:** 13

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The required width of an off-street bus parking space is 13 feet. `SMC 23.54.030.I`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The required width of an off-street bus parking space is 13 feet. This is stated in SMC 23.54.030.I: “Bus parking spaces, when required, shall be 13 feet in width and 40 feet in length.” [Source 1]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.I (Off-street bus parking standards), the required width of an off-street bus parking space is: * 12 feet minimum width ### Final answer: → 12 feet.

---

### L1-PARK-009. Per SMC 23.54.035.C.1, what is the minimum required width (in feet) of an off-street loading berth?

**Reference answer:** 10

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of an off-street loading berth is 10 feet. `SMC 23.54.035.C.1`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of an off-street loading berth is 10 feet. This is stated in the loading berth standards: “Each loading berth shall be not less than ten (10) feet in width and shall provide not less than fourteen (14) feet vertical clearance.” [Source 3] SMC — smc_chapters, § 23.54.035, p.845; [Source 10] SMC — smc_chapters, § 23.54.035, p.845

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 0/5

> Per SMC 23.54.035.C.1 (Off-street loading berth standards), the minimum required width of an off-street loading berth is: * 12 feet ### Final answer: → 12 feet.

---

### L1-PARK-010. Per SMC 23.54.015.K.8, what is the minimum office floor area (in square feet) that triggers the bicycle-commuter shower facility requirement?

**Reference answer:** 100000

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The bicycle-commuter shower facility requirement is triggered at 100,000 square feet of office use floor area in a structure. `SMC 23.54.015.K.8`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The bicycle-commuter shower facility requirement applies to “structures containing 100,000 square feet or more of office use floor area.” [Source 6] SMC — smc_chapters, § Title 23 - Land Use Code, p.808 | Trigger | Threshold | Citation | |--------|-----------|----------| | Minimum office floor area that triggers bicycle-commuter shower facilities | 100,000 sq ft of office use floor area | [Source 6] |

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.015.K.8, the bicycle commuter shower facility requirement is triggered when an office use reaches: * 50,000 square feet of office floor area ### Final answer: → 50,000 square feet.

---

### L2-FIRE-001. Per WAC 51-54A 105.6 (operational permits), what aggregate cubic feet of lithium-ion and lithium metal batteries triggers the requirement for an operational permit?

**Reference answer:** 15 cubic feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> An operational permit is required when there is an accumulation of more than 15 cubic feet (0.42 m³) of lithium-ion and lithium metal batteries, excluding those covered by the exceptions in Section 322.1. `[WAC 51-54A-0105]` `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> An operational permit is required when there is an accumulation of more than 15 cubic feet (0.42 m³) of lithium-ion and lithium metal batteries, excluding those covered by the exceptions in Section 322.1. | Trigger | Threshold | Citation | |---------|-----------|----------| | Operational permit for lithium-ion and lithium metal batteries | > 15 cubic feet (0.42 m³) aggregate accumulation | [Source 1] WAC — wac_chapters, § 51-54, p.4; [Source 2] WAC — wac_chapters, § 51-54, p.11; [Source 3] WAC — wac_chapters, § 51-54, p.11 |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0105.6 (Operational permits – hazardous materials / lithium batteries), an operational permit is required when the aggregate quantity of lithium-ion and lithium metal batteries exceeds: * 15 cubic feet (0.42 m³) This is the code’s threshold for triggering permitting for storage/handling operations involving these batteries. ### Final answer: → More than 15 cubic feet aggregate volume.

---

### L2-FIRE-002. Per WAC 51-54A 322 exceptions, at what maximum watt-hour rating per lithium-ion battery (in original retail packaging) is the battery exempt from indoor storage limits?

**Reference answer:** 300 watt-hours

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Lithium-ion batteries in original retail packaging are exempt from the indoor storage limits in Section 322 when each battery is rated at 300 watt-hours or less. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Lithium-ion batteries in original retail packaging are exempt from the indoor storage limits of WAC 51-54A-0322 when they are rated at 300 watt-hours or less per battery.[Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322 (exceptions to battery storage requirements), lithium-ion batteries in original retail packaging are exempt from the indoor storage limits when each battery is rated at: * 300 watt-hours (Wh) or less per lithium-ion battery This is the maximum single-battery energy rating that qualifies for the exemption. ### Final answer: → 300 Wh per lithium-ion battery (maximum for exemption).

---

### L2-FIRE-003. Per WAC 51-54A 322 exceptions, what maximum grams of lithium metal per battery (in retail packaging) exempts the battery from the storage rule?

**Reference answer:** 25 grams

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Batteries in original retail packaging are exempt from the lithium battery storage rule when they contain 25 grams or less of lithium metal per battery. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> Batteries in original retail packaging are exempt from the lithium battery storage rule if they contain 25 grams or less of lithium metal per battery. [Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322 (exceptions for lithium battery storage in original retail packaging), lithium metal batteries are exempt from the indoor storage limits when each battery contains: * 25 grams or less of lithium metal per battery This threshold applies only when the batteries are in original retail packaging and otherwise meet the exception conditions. ### Final answer: → 25 grams of lithium metal per battery (maximum for exemption).

---

### L2-FIRE-004. Per WAC 51-54A 322 (battery storage), what maximum state-of-charge percentage qualifies as 'demonstrated state of charge' for storage approval?

**Reference answer:** 30 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> A maximum state of charge of 30 percent qualifies as the “demonstrated state of charge” threshold for reduced indoor storage requirements; indoor storage areas with a demonstrated state of charge not exceeding 30 percent are not required to comply with Sections 322.4.2.1, 322.4.2.2, or 322.4.2.5, provided approved procedures are in place to limit and verify that the state of charge will not exceed 30 percent. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The WAC provision on lithium battery storage specifies that indoor storage areas for lithium-ion and lithium metal batteries with a demonstrated state of charge not exceeding 30 percent are eligible for reduced requirements, provided approved procedures exist to limit and verify that the state of charge will not exceed that level. [Source 1] WAC — wac_chapters, § 51-54, p.13

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322 (Battery storage — electrochemical energy storage provisions), “demonstrated state of charge” used for storage approval is limited to: * No more than 30% state of charge (SOC) This reduced charge level is part of the mitigation approach for stored lithium-ion systems to reduce fire and thermal runaway risk. ### Final answer: → 30% maximum state of charge (SOC).

---

### L2-FIRE-005. Per WAC 51-54A 903 (sprinkler exceptions), what aggregate cluster area defines the sprinkler exemption for portable school classrooms?

**Reference answer:** 6,000 square feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The sprinkler exemption for portable school classrooms applies where the aggregate area of any cluster of portable school classrooms does not exceed 6,000 square feet. `[WAC 51-54A-0903]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The sprinkler exemption for clusters of portable school classrooms applies only if the aggregate area of any cluster does not exceed 6,000 square feet (557 m²).[Source 2] [Source 3] [Source 5] [Source 9] [Source 11]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-0903 (automatic sprinkler systems — exceptions for portable classrooms), the sprinkler exemption for portable school classrooms is based on the size of a clustered group of portables. The code specifies: * 12,000 square feet maximum aggregate cluster area Portable classrooms that are arranged in clusters not exceeding this total area may qualify for the sprinkler exemption, subject to the additional spacing and fire access conditions in the section. ### Final answer: → 12,000 square feet maximum aggregate cluster area.

---

### L2-FIRE-006. Per WAC 51-54A 903 (Group R sprinkler exception for recreational use), what fire area (in square feet) defines the exemption?

**Reference answer:** 500 square feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The Group R sprinkler exemption applies only where the Group R fire area is no more than 500 square feet and used for recreational use only. `[WAC 51-54A-0903]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The Group R-1 recreational-use sprinkler exception applies only where the Group R fire area is no more than 500 square feet (46 m²).[Source 1] WAC — wac_chapters, § 51-54, p.30; [Source 3] WAC — wac_chapters, § 51-54, p.17

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-0903 (Group R sprinkler exceptions — recreational use), the exemption applies where the fire area does not exceed: * 1,000 square feet So the defining threshold for the recreational Group R sprinkler exception is: → 1,000 square feet maximum fire area.

---

### L2-FIRE-007. Per WAC 51-54A 510 testing, what is the maximum size of a single signal-strength test area?

**Reference answer:** 6,400 square feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum size of a single signal-strength test area is 6,400 square feet. `[WAC 51-54A-0510]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 2/5

> The maximum size of a single signal-strength test area is 6,400 square feet (595 m²) per test grid on each floor.[Source 2]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-510.4.2 (emergency responder radio coverage testing grid requirements), each signal-strength test area (grid cell) is limited to a maximum size of: * 2,500 square feet per test area This grid sizing is used to evaluate compliance with the required percentage of areas meeting minimum signal strength levels. ### Final answer: → 2,500 square feet maximum per signal-strength test area.

---

### L2-FIRE-008. Per WAC 51-54A 510 testing, what floor area threshold triggers splitting the floor into multiple signal-strength test areas?

**Reference answer:** 128,000 square feet

**PolicyBridge (RAG + graph)**: Correctness 4/5, Faithfulness 3/5

> A floor must be split into multiple signal-strength test areas when its area exceeds 6,400 square feet, because each floor is divided into 20 approximately equal test areas with a maximum test area size of 6,400 sq ft, and any floor area over 128,000 sq ft must be divided into more areas so that no test area exceeds 6,400 sq ft. `[WAC 51-54A-0510]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 1/5

> Under WAC 51-54A Section 510 testing, a floor must be divided into multiple signal-strength test areas whenever the floor area exceeds 6,400 square feet (595 m²), because each test area is limited to a maximum of 6,400 square feet and the floor is divided into 20 approximately equal test areas. [Source 6] WAC — wac_chapters, § 51-54, p.21

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-510.4.2 (Emergency responder radio coverage system testing), the floor must be divided into multiple signal-strength test grids when: * Any floor area exceeds 2,500 square feet At or below that size, a single grid is sufficient; above it, the floor must be subdivided into additional 2,500-square-foot test areas for compliance evaluation. ### Final answer: → More than 2,500 square feet triggers splitting into multiple test areas.

---

### L2-FIRE-009. Per WAC 51-54A 3307 (construction fire safety), what construction-height threshold (above grade) triggers additional fire-protection requirements?

**Reference answer:** 40 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> - More than 40 feet above the lowest level of fire department vehicle access: triggers requirement for a temporary or permanent stairway extended to within one floor of the highest secured decking/flooring. `3307.1.2` `[WAC 51-54A-3307]` - Exceeding 40 feet in height above the lowest level of fire department vehicle access: triggers requirement that at least one standpipe be installed for use during construction, extended as work progresses. `3307.5` `[WAC 51-54A-3307]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The key construction-height thresholds above grade in WAC 51-54A Chapter 33 are: | Requirement | Height Threshold Above Grade / Access | Citation | |--------------------------------------------------|----------------------------------------|----------| | Temporary or permanent stairway during construction | Building construction exceeds 40 feet above the lowest level of fire department vehicle access | [Source 1] | | Fire watch during construction (IFC text) | New construction exceeds 40 feet above the lowest adjacent grade at any point along the building perimeter (also triggered by large multistory area) | [Source 10] | | Additional safeguards for Type IV-A, IV-B, IV-C buildings | Building designed to be greater than six stories above grade plane | [Source 11] | So, 40 feet above the lowest fire department access/adjacent grade is a primary trigger for added measures (stairway and fire watch), and “greater than six stories above grade plane” triggers enhanced safeguards for certain Type IV construction.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-3307 (Fire safety during construction and demolition operations), additional fire-protection requirements are triggered when a building under construction reaches: * 40 feet (12,192 mm) above the lowest level of fire department vehicle access At or beyond this height, the code requires enhanced construction-phase fire protection measures (such as standpipes and related provisions, depending on construction type and progress). ### Final answer: → 40 feet above grade (fire department vehicle access level).

---

### L2-FIRE-010. Per WAC 51-54A 3307, what aggregate-area threshold per story triggers expanded construction fire-protection requirements?

**Reference answer:** 50,000 square feet

**PolicyBridge (RAG + graph)**: Correctness 4/5, Faithfulness 2/5

> Per `WAC 51-54A-3303.5.1`, a new multistory construction with an aggregate area exceeding 50,000 square feet per story triggers the requirement to provide a fire watch during nonworking hours, which is an expanded construction fire‑protection measure. `[WAC 51-54A-3303]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> The available excerpts of WAC 51-54A-3307 show specific fire-flow and hydrant requirements (e.g., minimum 500 gpm fire flow and hydrant within 500 feet for combustible materials; additional fire flow for Types III, IV, and V with separation <30 feet), but they do not state any aggregate floor-area-per-story threshold that triggers “expanded” construction fire-protection requirements. [Source 5] [Source 8] IBC_WA — ibc_wa_docs, § IBC International Fire Code, p.190. This could not be determined from the available materials.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-3307 (construction fire safety provisions), expanded construction-phase fire protection requirements are triggered when a single story under construction exceeds: * 15,000 square feet (1,394 m²) per story (aggregate area) Once that threshold is exceeded, additional fire protection measures apply during construction (such as increased standpipe provisions, access, and water supply/fire-flow coordination depending on height and construction stage). ### Final answer: → 15,000 square feet per story.

---

### L2-PARK-001. Per RCW 36.70A.535(7), how many distinct exception conditions exempt a city from the co-living parking limits of subsection (3)(a)?

**Reference answer:** 2

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts provided for RCW 36.70A.535 only include subsections (1), (4)–(7) in part and do not contain the text of subsection (3)(a) or any language describing “co-living parking limits” or their exceptions, so I cannot see how many distinct exception conditions are listed in subsection (7) for that specific purpose.[Source 3] RCW — rcw_chapters, § 36.70, p.112; [Source 7] RCW — rcw_chapters, § 36.70, p.113

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 3/5

> Per RCW 36.70A.535(7), there are two distinct exception pathways that can exempt a city from the co-living parking limits in subsection (3)(a): 1. Airport proximity-based exception (within the specified airport influence area tied to qualifying commercial airports meeting enplanement thresholds) 2. Transit proximity/service exception (based on proximity to qualifying major transit service conditions defined in the statute) ### Final answer: → 2 exception conditions.

---

### L2-PARK-002. An applicant is designing a single off-street bus parking space for a school site. Per SMC 23.54.030.I, what is the minimum required length (in feet) of that space?

**Reference answer:** 40 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required length of an off-street bus parking space is 40 feet. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required length for a single off-street bus parking space is 40 feet. This comes from the off-street bus parking standard: “Bus parking spaces, when required, shall be 13 feet in width and 40 feet in length.” `[Source 1] SMC — smc_chapters, § 23.54.030, p.842`

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per SMC 23.54.030.I (Off-street bus parking standards), a single off-street bus parking space must have a minimum length of: * 40 feet ### Final answer: → 40 feet.

---

### L2-PARK-003. A warehouse project is sizing an off-street loading berth. Per SMC 23.54.035.C.1, what is the minimum required vertical clearance (in feet) above the berth?

**Reference answer:** 14 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required vertical clearance above an off-street loading berth is 14 feet. `SMC 23.54.035.C.1`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required vertical clearance for each off-street loading berth is 14 feet above the berth surface. This is stated in SMC 23.54.035.C.1: “Each loading berth shall be not less than ten (10) feet in width and shall provide not less than fourteen (14) feet vertical clearance.” [Source 4] SMC — smc_chapters, § 23.54.035, p.845; [Source 7] SMC — smc_chapters, § 23.54.035, p.845

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per SMC 23.54.035.C.1 (Off-street loading berth standards), the minimum required vertical clearance for an off-street loading berth is: * 14 feet ### Final answer: → 14 feet.

---

### L2-PARK-004. Per SMC 23.54.030.A.2, what is the minimum required length (in feet) of a medium-vehicle off-street parking space?

**Reference answer:** 16 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required length of a medium-vehicle off-street parking space is 16 feet. `SMC 23.54.030.A.2`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The minimum required length of a medium-vehicle off-street parking space is 16 feet. | Vehicle size | Minimum width | Minimum length | Citation | |-------------|---------------|----------------|----------| | Medium | 8 feet | 16 feet | [Source 1] SMC — smc_chapters, § 23.54.030, p.829 |

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.A.2 (Off-street parking space dimensions), a medium-vehicle parking space must have a minimum length of: * 17 feet 6 inches (17.5 feet) ### Final answer: → 17.5 feet (17 feet 6 inches).

---

### L2-PARK-005. Per WAC 51-50-1101.2.9, what is the minimum required width (in inches) of an access aisle serving a van-accessible parking space?

**Reference answer:** 96 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 3/5

> The minimum required width of an access aisle serving a van-accessible parking space is 96 inches. `WAC 51-50-1101`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The minimum required width of an access aisle serving a van-accessible parking space is 96 inches (2440 mm) per WAC 51-50-1101.2.8/502.4.2 as continued in §1101.2.8–.9. [Source 4] WAC — wac_chapters, § 51-50, p.52; [Source 5] WAC — wac_chapters, § 51-50, p.53

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-50-1101.2.9 (accessible parking—van access aisles), the minimum required width of an access aisle serving a van-accessible parking space is: * 96 inches (8 feet) ### Final answer: → 96 inches (8 feet).

---

### L2-PARK-006. Per WAC 51-50-1101.2.8, what is the minimum required width (in inches) of an access aisle serving a car (non-van) accessible parking space?

**Reference answer:** 60 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 3/5

> The minimum required width of an access aisle serving a car (non-van) accessible parking space is 60 inches. `WAC 51-50-1101`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The minimum required width of an access aisle serving a car (non-van) accessible parking space is 60 inches.[Source 5] WAC — wac_chapters, § 51-50, p.52

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-50-1101.2.8 (accessible parking access aisles), the minimum required width for an access aisle serving a car (non-van) accessible parking space is: * 60 inches (5 feet) ### Final answer: → 60 inches.

---

### L2-PARK-007. Per RCW 36.70A.535(7) and (8) combined, how many distinct fractional caps does the statute place on how a city may treat a co-living sleeping unit relative to a dwelling unit for density and sewer-fee calculations?

**Reference answer:** 2

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> RCW `36.70A.535(7)` and `36.70A.535(8)` together establish two distinct fractional caps on how a city or county may treat a co-living sleeping unit relative to a dwelling unit. - For dwelling unit density, a sleeping unit may not be treated as more than one-quarter of a dwelling unit. `[RCW 36.70A.535]` - For sewer connection fee calculations, a sleeping unit may not be treated as more than one-half of a dwelling unit, absent a fact-based finding justifying higher fees. `[RCW 36.70A.535]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts provided include RCW 36.70A.535’s subject heading (co‑living housing) and cross‑references, but do not contain the text of subsections (7) or (8), nor any language about fractional caps on density or sewer-fee calculations for co‑living sleeping units. [Source 2] RCW — rcw_chapters, § 36.70, p.112; [Source 5] RCW — rcw_chapters, § 36.70, p.157.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 3/5

> Per RCW 36.70A.535(7) and (8), the statute establishes two distinct fractional (unit-equivalency) caps governing how co-living sleeping units may be treated relative to dwelling units: 1. Density calculation cap — limits how many sleeping units may be counted per dwelling unit equivalency for land use/density purposes. 2. Sewer or utility fee calculation cap — limits how sleeping units may be converted into dwelling-unit equivalents for utility billing purposes. These are structurally separate constraints applied to different regulatory contexts (land use vs. utilities), but both function as fractional conversion limits. ### Final answer: → 2 distinct fractional caps.

---

### L2-PARK-008. Per RCW 36.70A.535(8), what is the maximum fraction at which a city may treat a co-living sleeping unit relative to a dwelling unit for the purpose of calculating fees for sewer connections?

**Reference answer:** 0.5

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> A city may not treat a co-living sleeping unit as more than one-half (1/2) of a dwelling unit for purposes of calculating fees for sewer connections, unless it makes a fact-based finding that higher fees are warranted. `RCW 36.70A.535(8)`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> A city may not treat a sleeping unit in co-living housing as more than one-half (1/2) of a dwelling unit for purposes of calculating fees for sewer connections, unless it makes a fact-based finding that higher fees are warranted. [Source 3] RCW — rcw_chapters, § 36.70, p.113

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per RCW 36.70A.535(8), for purposes of calculating sewer connection fees, a co-living sleeping unit may be treated at a maximum equivalency of: * 0.25 of a dwelling unit (one-quarter unit) ### Final answer: → 0.25 dwelling unit (1/4 unit).

---

### L2-PARK-009. Per SMC 23.54.015 Table B, how many distinct zone/area categories receive 'No minimum requirement' for residential parking (urban centers; Station Area Overlay District; urban-village frequent-transit; congregate near transit; middle housing near transit)?

**Reference answer:** 5

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> Five distinct residential zone/area categories in Table B for `23.54.015` have “No minimum requirement” for parking: 1. All residential uses within urban centers or within the Station Area Overlay District (`L`). `[SMC 23.54.015]` 2. All residential uses in commercial, RSL, and multifamily zones within urban villages (not in an urban center or Station Area Overlay District) within a frequent transit service area (`M`). `[SMC 23.54.015]` 3. Congregate residences located within one-half mile walking distance of a major transit stop or a frequent transit stop (`P`). `[SMC 23.54.015]` 4. Middle housing located within one-half mile walking distance of a major transit stop (`Q`). `[SMC 23.54.015]` 5. Each moderate-income unit and each low-income unit (footnote `1` to Table B). `[SMC 23.54.015]`

**Vanilla vector RAG**: Correctness 2/5, Faithfulness 3/5

> Five distinct zone/area categories in Table B for SMC 23.54.015 receive a “No minimum requirement” for residential parking, matching the list you provided. They are: 1. All residential uses within urban centers or within the Station Area Overlay District – “No minimum requirement” [Source 4] SMC — smc_chapters, § 23.54.015, p.798 2. All residential uses in commercial, RSL, and multifamily zones within urban villages (not in an urban center or Station Area Overlay District) that are within a frequent transit service area – “No minimum requirement” [Source 4] SMC — smc_chapters, § 23.54.015, p.798 3. Congregate residences located within one-half mile walking distance of a major transit stop or a frequent transit stop – “No minimum requirement” [Source 4] SMC — smc_chapters, § 23.54.015, p.798 4–5. The “middle housing near transit” category you reference is not expressly named in the retrieved text; based on the available materials, only the three categories above are clearly specified as “No minimum requirement,” and any additional “middle housing” category could not be determined from the available materials.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Per SMC 23.54.015, Table B (Residential parking requirements), the categories explicitly marked as having “No minimum requirement” include five distinct zone/area types: 1. Urban Centers 2. Station Area Overlay District 3. Urban Village – Frequent Transit Service Areas 4. Congregate Residence near Transit 5. Middle Housing near Transit ### Count: That is 5 distinct categories. ### Final answer: → 5 categories.

---

### L2-PARK-010. Per SMC 23.54.030.A.1, what is the minimum required length (in feet) of a large-vehicle off-street parking space?

**Reference answer:** 19 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required length of a large-vehicle off-street parking space is 19 feet. `SMC 23.54.030.A.1`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required length of a large-vehicle off-street parking space is 19 feet. This is defined in SMC 23.54.030.A.1: “Large vehicle means the minimum size of a large vehicle parking space shall be 8 feet in width and 19 feet in length.” [Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per SMC 23.54.030.A.1 (Off-street parking space dimensions), a large-vehicle parking space must have a minimum length of: * 19 feet ### Final answer: → 19 feet.

---

### L3-FIRE-001. A lithium-ion battery storage room holds groups of containers separated by an aisle that contains combustible packaging materials. Per WAC 51-54A 322.4.1, what is the minimum required separation (in feet) between container groups in this configuration — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 10 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The aisle contains combustible materials, so container groups must be separated by not less than 10 feet of space. `322.4.1(3)` requires 3 feet of open space or 10 feet of space that contains combustible materials between a second container or group of containers. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> Under WAC 51-54A-322.4.1, where the space between container groups “contains combustible materials,” the minimum required separation between groups of containers is 10 feet (3048 mm) of space containing combustibles.[Source 1] WAC — wac_chapters, § 51-54, p.12 | Separation condition between container groups | Minimum separation | Citation | |----------------------------------------------|--------------------|----------| | Aisle/space contains combustible materials | 10 feet | [Source 1] |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322.4.1 (limited indoor lithium-ion/lithium metal battery storage in containers)—which is adopted in Seattle through SMC 22.600.020—the separation between container groups depends on what’s in the intervening aisle: * 3 feet minimum separation if the space is open (no combustibles) * 10 feet minimum separation if the intervening space contains combustible materials Since the aisle in your scenario contains combustible packaging materials, the combustible-condition applies. ### Final answer: → 10 feet minimum separation between container groups.

---

### L3-FIRE-002. Per WAC 51-54A 322.4.1, what is the minimum required distance (in feet) between a lithium-ion battery container in a limited indoor storage area and the nearest exit or exit access door — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 5 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required distance is 5 feet between lithium-ion battery containers in a limited indoor storage area and the nearest exit or exit access door. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The minimum required distance is 5 feet between lithium-ion (or lithium metal) battery containers in a limited indoor storage area and any exit or exit access door. Section 322.4.1(4) states: “Containers shall be located not less than 5 feet (1524 mm) from exits or exit access doors.” [Source 3] WAC — wac_chapters, § 51-54, p.12

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0322.4.1, as adopted in Seattle through SMC 22.600.020, lithium-ion/lithium metal battery storage containers in a limited indoor storage arrangement must be located so they do not obstruct egress components. The specific clearance requirement states: * Minimum 5 feet (1.5 m) from any exit or exit access door This separation ensures that stored battery containers do not interfere with required means of egress or create hazards at exit pathways. ### Final answer: → 5 feet minimum distance from an exit or exit access door.

---

### L3-FIRE-003. An outdoor lithium-ion battery storage installation has no 2-hour fire-resistance-rated barrier and is not enclosed in an approved prefabricated portable structure. Per WAC 51-54A 322.4.3.1, what is the minimum required distance (in feet) from any building, lot line, public street, public alley, public way, or means of egress — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 20 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> The minimum required distance is 20 feet from any building, lot line, public street, public alley, public way, or means of egress when there is no 2-hour fire-resistance-rated assembly and no approved 2-hour-rated prefabricated portable structure enclosing the batteries. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required distance is 20 feet from any building, lot line, public street, public alley, public way, or means of egress when the outdoor lithium-ion battery storage is not separated by a 2‑hour fire-resistance-rated assembly and is not in an approved prefabricated 2‑hour-rated portable structure. This comes from option 1 of WAC 51‑54A‑322.4.3.1, which requires that “battery storage shall be located not less than 20 feet (6096 mm)” from those exposures in the absence of the 2‑hour-rated separation alternatives in items 2 and 3.[Source 4]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-0322.4.3.1, as adopted in Seattle via SMC 22.600.020, an outdoor lithium-ion battery storage installation that is not protected by a 2-hour fire-resistance-rated barrier and is not within an approved prefabricated portable structure must be separated from exposures by: * 10 feet minimum distance This separation applies to: * Buildings * Lot lines * Public streets * Public alleys * Public ways * Means of egress ### Final answer: → 10 feet minimum separation distance.

---

### L3-FIRE-004. Per WAC 51-54A 322.4.3.2, what is the maximum permitted floor area (in sq ft) for a single outdoor lithium-ion battery storage area (including storage beneath approved weather protection) — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 900 sq ft

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> The maximum permitted floor area for a single outdoor lithium-ion battery storage area (including storage beneath weather protection) is 900 sq ft. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The maximum permitted floor area for a single outdoor lithium-ion (or lithium metal) battery storage area, including storage beneath weather protection in accordance with IBC 414.6.1, is 900 square feet (83.6 m²) per WAC 51-54A-322.4.3.2.[Source 1] | Standard | Value | Citation | |----------------------------------------------------|----------------|-----------| | Max floor area per outdoor lithium battery storage area (including under weather protection) | 900 sq ft | [Source 1] |

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-0322.4.3.2 (Outdoor lithium-ion/lithium metal battery storage areas)—as adopted in Seattle via SMC 22.600.020—the maximum permitted size of a single outdoor storage area is: * 10,000 square feet (929 m²) This limit applies to each individual outdoor storage area, including areas located under approved weather protection, and is part of the fire safety controls intended to limit the scale of any single battery storage exposure. ### Final answer: → 10,000 square feet maximum per outdoor lithium-ion battery storage area.

---

### L3-FIRE-005. An electrochemical energy storage system (ESS) is proposed for a building floor located above the lowest level of fire department vehicle access. Per WAC 51-54A 1207.5.3, what is the maximum elevation (in feet) above that lowest fire department access level at which the ESS may be located — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 75 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Electrochemical ESS shall not be located where the floor is more than 75 feet above the lowest level of fire department vehicle access; therefore, the maximum permitted elevation is 75 feet above that lowest access level. `[WAC 51-54A-1207.5.3]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The WAC elevation limit is 75 feet above the lowest level of fire department vehicle access. Electrochemical ESS “shall not be located…[w]here the floor is located more than 75 feet (22,860 mm) above the lowest level of fire department vehicle access,” so the maximum permitted elevation is 75 feet above that level. [Source 1] WAC — wac_chapters, § 51-54, p.56

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-1207.5.3 (Energy storage systems located above fire department vehicle access)—as adopted in Seattle through SMC 22.600.020—an electrochemical energy storage system (ESS) located above the lowest level of fire department vehicle access is limited to: * 30 feet maximum above the lowest level of fire department vehicle access Above this elevation, the code requires additional protective measures (such as increased fire-resistance-rated construction or other approved mitigation strategies depending on system size and classification). ### Final answer: → 30 feet maximum elevation.

---

### L3-FIRE-006. Per WAC 51-54A 1207.1.1 (Table 1207.1.1), at what minimum nameplate energy capacity (in kWh) does a lithium-ion battery energy storage system trigger compliance with Section 1207 — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 20 kWh

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> A lithium-ion battery energy storage system triggers compliance with Section 1207 when its nameplate energy capacity exceeds 20 kWh. `ESS having capacities exceeding the values shown in Table 1207.1.1 shall comply with this section`, and Table 1207.1.1 lists 20 kWh for lithium-ion batteries. `[WAC 51-54A-1207]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 5/5

> This could not be determined from the available materials. The excerpts of WAC 51-54A-1207 provided here reference Table 1207.1.1 and state that “ESS having capacities exceeding the values shown in Table 1207.1.1 shall comply with this section,” but the actual threshold values in kWh for lithium-ion systems are not included in the retrieved text.[Source 1] Without the contents of Table 1207.1.1 itself, the minimum nameplate energy capacity (kWh) that triggers Section 1207 compliance for lithium-ion ESS cannot be stated.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1207.1.1 (Table 1207.1.1 – Energy storage system thresholds)—as adopted in Seattle via SMC 22.600.020—a lithium-ion battery energy storage system becomes subject to Section 1207 requirements when it reaches: * 20 kWh (nameplate energy capacity) Below this threshold, systems are generally treated as small-scale installations and are not subject to the full ESS regulatory provisions of Section 1207. ### Final answer: → 20 kWh minimum nameplate energy capacity.

---

### L3-FIRE-007. Per WAC 51-54A 1207.5.1, electrochemical ESS must be segregated into groups not exceeding what maximum energy capacity (in kWh) per group — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 50 kWh

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> Per `WAC 51-54A-1207.5.1`, electrochemical ESS must be segregated into groups not exceeding 50 kWh each. `[WAC 51-54A-0323]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1207.5.1, electrochemical energy storage systems must be segregated into groups not exceeding 50 kWh of stored energy per group. [Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1207.5.1 (Energy storage system group size limits)—as adopted in Seattle via SMC 22.600.020—electrochemical energy storage systems must be arranged so that individual groups do not exceed: * 50 kWh maximum energy capacity per group This grouping limit is part of the fire protection strategy to limit the size of any single energy release or thermal runaway event. ### Final answer: → 50 kWh maximum per ESS group.

---

### L3-FIRE-008. Per WAC 51-54A 1206.6.3, at what maximum concentration (as percentage of the lower flammable limit) of flammable gas must the gas detection system for a stationary fuel cell power system activate — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 25 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> The gas detection system for a stationary fuel cell power system must be designed to activate at a flammable gas concentration of not more than 25 percent of the lower flammable limit (LFL). `[WAC 51-54A-1206]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved text for WAC 51-54A-1206.6.3 only states that stationary fuel cell power systems “shall be provided with a gas detection system” and that detection must be provided in approved locations, but it does not specify an activation setpoint as a percentage of the lower flammable limit (LFL) or any other numerical threshold. [Source 4]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1206.6.3 (Stationary fuel cell power systems — gas detection and alarm)—as adopted in Seattle via SMC 22.600.020—the gas detection system must activate when flammable gas concentrations reach: * 25% of the lower flammable limit (LFL) This early-action threshold is intended to provide warning well before conditions approach a combustible or explosive atmosphere. ### Final answer: → 25% of the lower flammable limit (LFL).

---

### L3-FIRE-009. Per WAC 51-54A 3307.4, where a standpipe is required during construction and a water supply must be provided for it, the fire hydrant used for that water supply must be located within what maximum distance (in feet) of the fire department connection supplying the standpipe — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 100 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The fire hydrant used to supply the required 500 gpm for a standpipe during construction must be located within 100 feet of the fire department connection supplying the standpipe. `WAC 51-54A-3307`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Under WAC 51-54A-3307.4, the fire hydrant used to supply the required standpipe during construction must be located within a maximum of 100 feet of the fire department connection supplying the standpipe. [Source 1] WAC — wac_chapters, § 51-54, p.66

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-3307.4 (Standpipes during construction)—as adopted in Seattle via SMC 22.600.020—when a standpipe is required and supplied by a fire hydrant, the hydrant must be located within: * 300 feet maximum distance of the fire department connection (FDC) supplying the standpipe This ensures reliable hose reach and effective fire department pumping operations during construction. ### Final answer: → 300 feet maximum distance.

---

### L3-FIRE-010. Per WAC 51-54A 1205, what is the maximum dimension (in feet) of a single rooftop photovoltaic array, above which a 3-foot clear access pathway must separate it from the next array — (adopted in Seattle via SMC 22.600.020.)

**Reference answer:** 150 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum dimension of a single rooftop photovoltaic array is 150 feet by 150 feet; multiple arrays must then be separated by a 3-foot-wide clear access pathway. `[WAC 51-54A-1205]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The maximum dimension of a single rooftop photovoltaic array is 150 feet by 150 feet; arrays larger than this are not permitted as a single array, and multiple arrays must be separated by a 3-foot-wide clear access pathway. | Requirement | Value | Citation | |----------------------------------------|----------------|----------| | Maximum array dimension (length) | 150 feet | [Source 1] | | Maximum array dimension (width) | 150 feet | [Source 1] | | Required clear access pathway between arrays | 3 feet wide | [Source 1] | [Source 1] WAC — wac_chapters, § 51-54A-1205, p.51

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1205 (Solar photovoltaic systems)—as adopted in Seattle via SMC 22.600.020—rooftop PV arrays must be separated by a 3-foot clear access pathway when they exceed a specific maximum dimension. The triggering limit is: * 150 feet maximum dimension (in any direction) If a rooftop PV array exceeds this size, a 3-foot clear pathway is required between arrays to provide fire department access and ventilation spacing. ### Final answer: → 150 feet maximum array dimension.

---

### L3-PARK-001. Under the SPU Development Services Manual (Volume 18) referencing SMC Chapter 22.805, what is the minimum new-and-replaced impervious surface threshold that triggers stormwater requirements for a parcels-based or single-family residential project (e.g., a residential parking lot or driveway)?

**Reference answer:** 1,500 square feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The SPU Development Services Manual states that on-site stormwater management (OSM) is required for parcel-based projects (`SMC 22.805.050`) and single-family residential projects (`SMC 22.805.030`) when there is ≥ 1,500 sq ft of new and replaced impervious surface or ≥ 7,000 sq ft of total land-disturbing activity on existing lots, and ≥ 750 sq ft of new and replaced hard surface or ≥ 7,000 sq ft of land-disturbing activity on lots created/altered by a recorded plat on or after January 1, 2016. [SPU 18.5.4.1]

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For parcels-based or single-family residential projects, the SPU Development Services Manual (Vol. 18) sets a minimum threshold of 1,500 square feet of new and replaced impervious surface (or ≥7,000 sq ft total land disturbing activity) to trigger on-site stormwater management (OSM) requirements, referencing SMC 22.805.030 and 22.805.050.[Source 2] SPU — spu_design_standards, § 18DevelopmentServicesFinalRedacted, p.18 For lots created/adjusted by a recorded plat on or after January 1, 2016, the lower threshold of 750 square feet of new plus replaced hard surface (or ≥7,000 sq ft land disturbing activity) applies.[Source 2] SPU — spu_design_standards, § 18DevelopmentServicesFinalRedacted, p.18 | Project / Lot Type | Trigger Threshold (new + replaced impervious/hard surface) | Citation | |--------------------------------------------------------------|------------------------------------------------------------|----------| | Parcels-based or single-family residential project | ≥ 1,500 sq ft | [Source 2] | | Same, on lot platted/adjusted on or after Jan 1, 2016 | ≥ 750 sq ft | [Source 2] |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 3/5

> Under SPU Development Services Manual (Volume 18) implementing SMC Chapter 22.805 (Minimum Requirements for All Projects), the stormwater trigger for parcel-based and single-family residential projects (including residential driveways and parking lots) is based on new plus replaced impervious surface area. From the SPU/Seattle Stormwater Code thresholds: ### Parcel-based / SFR threshold (regulatory trigger) Stormwater requirements are triggered when a project includes: * ≥ 1,500 square feet of new + replaced impervious surface, or * ≥ 7,000 square feet of total land disturbing activity For certain newer lots (platted after 2016), a lower trigger applies: * ≥ 750 square feet of new + replaced hard surface --- ### Key answer (standard threshold most commonly referenced) → 1,500 square feet of new and replaced impervious surface --- ### Final answer: → 1,500 square feet (new + replaced impervious surface) triggers stormwater requirements for parcel-based / single-family residential projects under SPU Volume 18 / SMC 22.805.

---

### L3-PARK-002. Per RCW 36.70A.622(1)(e), what is the maximum length (in feet) that a city may require for a residential off-street parking space when imposing parking requirements?

**Reference answer:** 20 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum length a city may require for a residential off-street parking space is 20 feet, except for required parking for people with disabilities. `[RCW 36.70A.622]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts of RCW 36.70A.622 provided only address: - prohibition on requiring garages/carports to meet minimum parking, - allowing enclosed or unenclosed spaces, and - counting tandem spaces at one space per 20 linear feet, but do not include subsection (1)(e) or any maximum stall length requirement. [Source 1] RCW — rcw_chapters, § 36.70, p.126

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per RCW 36.70A.622(1)(e), when a city imposes off-street parking requirements for residential uses, it may not require a parking space longer than: * 20 feet maximum length ### Final answer: → 20 feet.

---

### L3-PARK-003. Per SMC 23.54.030.A.5, what is the minimum required length (in feet) of a tandem-bay parking arrangement that accommodates two medium-vehicle parking spaces in series?

**Reference answer:** 32 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Per `SMC 23.54.030.A.5`, a tandem parking space must be two times the length of the vehicle size standard for the space type; a medium-vehicle space is 16 feet long under `SMC 23.54.030.A.2`, so a tandem bay for two medium spaces in series must be 32 feet long. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> A tandem parking space must be “two times the length of the vehicle size standards” for the vehicle size accommodated. For a medium vehicle, the minimum length of a single space is 16 feet, so two medium-vehicle spaces in tandem require 2 × 16 = 32 feet of length. [Source 3] SMC — smc_chapters, § 23.54.030.A (medium vehicle length 16 ft), p.829; [Source 1] SMC — smc_chapters, § 23.54.030 (tandem parking definition as twice the length of the applicable vehicle size standard), p.830.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.A.5 (tandem parking standards), a tandem arrangement for two medium-vehicle parking spaces in series must provide a minimum total length of: * 35 feet This accommodates two medium-vehicle stalls end-to-end, including required maneuvering and stall depth assumptions under the code. ### Final answer: → 35 feet.

---

### L3-PARK-004. Per WAC 51-50-1101.2.7, what is the minimum required width (in inches) of an accessible vehicle parking space?

**Reference answer:** 96 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of an accessible vehicle parking space is 96 inches. `[WAC 51-50-1101]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of an accessible vehicle parking space (car or van) is 96 inches per WAC 51-50-1101.2.7 (ICC A117.1 Section 502.2) vehicle space size.[Source 2]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-50-1101.2.7 (accessible parking space dimensions), the minimum required width of an accessible vehicle parking space (non-van standard condition) is: * 96 inches (8 feet) This applies to the parking space itself; access aisle dimensions are governed separately. ### Final answer: → 96 inches.

---

### L3-PARK-005. Per SMC 23.54.030.L.1.b.2, what percentage of parking spaces must be EV-ready for a multifamily project that provides more than 25 surface parking spaces?

**Reference answer:** 45 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> For surface parking serving multiple dwelling units, when more than 25 parking spaces are provided, 45 percent of all parking spaces must be EV-ready under `SMC 23.54.030.L.1.b.2`.

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For a multifamily project with more than 25 surface parking spaces serving multiple dwelling units, at least 45 percent of all parking spaces must be EV-ready. This is stated in SMC 23.54.030.L.1.b.2: “When more than 25 parking spaces are provided, 45 percent of all parking spaces shall be EV-ready.” [Source 11] SMC — smc_chapters, § 23.54.030.L.1.b.2, p.842

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.L.1.b.2 (EV infrastructure requirements for multifamily parking), when a multifamily project provides more than 25 surface parking spaces, the requirement is: * 50% of parking spaces must be EV-ready This applies to the portion of parking that exceeds the small-project threshold and reflects Seattle’s stepped EV infrastructure standard for larger multifamily developments. ### Final answer: → 50% EV-ready.

---

### L3-PARK-006. Per SMC 23.54.030.L.2.a, what is the minimum percentage of nonresidential parking spaces that must be EV-ready (base requirement, before exceptions in .L.2.b and .L.2.c)?

**Reference answer:** 30 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The base requirement is that 30 percent of nonresidential parking spaces must be EV-ready, per `SMC 23.54.030.L.2.a`.

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The base EV-ready requirement for nonresidential parking (before the alternative provisions in subsections 23.54.030.L.2.b and .L.2.c) is: | Parking type | Minimum EV-ready percentage | Citation | |-------------------------|-----------------------------|----------| | Nonresidential parking | 30% of spaces | [Source 1] | [Source 1] states: “When parking is provided for nonresidential uses, a minimum of 30 percent of those spaces shall be EV-ready, except as provided in subsection 23.54.030.L.2.b and subsection 23.54.030.L.2.c.”

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.L.2.a, the base requirement for nonresidential parking is that: * 20% of parking spaces must be EV-ready This is the baseline requirement before any adjustments or reductions allowed under subsections .L.2.b and .L.2.c. ### Final answer: → 20% EV-ready (minimum base requirement).

---

### L3-PARK-007. Per RCW 36.70A.535(3)(a)(ii), what is the maximum off-street parking (in spaces per sleeping unit) that a city may require for co-living housing outside the half-mile transit exception?

**Reference answer:** 0.25

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum off-street parking a city may require for co-living housing is 0.25 spaces per sleeping unit, except where the statute’s specific exceptions (empirical safety study or within one mile of a qualifying commercial airport) apply. `RCW 36.70A.535(3)(a)(ii)`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpt of RCW 36.70A.535 provided only states that cities and counties must allow co‑living housing as a permitted use within urban growth areas and does not include subsection (3)(a)(ii) or any numerical parking limits per sleeping unit. [Source 12] RCW — rcw_chapters, § 36.70, p.112

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per RCW 36.70A.535(3)(a)(ii), for co-living housing located outside the qualifying transit exception (i.e., beyond 0.5 miles of major transit service), a city may not require more than: * 0.5 off-street parking spaces per sleeping unit ### Final answer: → 0.5 parking spaces per sleeping unit (maximum).

---

### L3-PARK-008. Per SMC 23.54.030.I, what is the minimum required length (in feet) of an off-street bus parking space?

**Reference answer:** 40 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required length of an off-street bus parking space is 40 feet. `SMC 23.54.030.I`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required length of an off-street bus parking space is 40 feet per SMC 23.54.030.I, which states: “Bus parking spaces, when required, shall be 13 feet in width and 40 feet in length.” [Source 1]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per SMC 23.54.030.I (Off-street bus parking standards), the minimum required length of an off-street bus parking space is: * 40 feet ### Final answer: → 40 feet.

---

### L3-PARK-009. Per SMC 23.54.030.L.2.b, how many EV-ready parking spaces are required for an institutional small-lot project that provides fewer than 10 off-street parking spaces?

**Reference answer:** 1 space

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> For the listed institutional uses in `SMC 23.54.030.L.2.c` (e.g., community club/center, child care center, library, museum, religious facility, elementary/secondary school, etc.), when fewer than 10 off-street parking spaces are provided, exactly 1 EV-ready parking space is required per `SMC 23.54.030.L.2.b.1`.

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For institutional uses listed in SMC 23.54.030.L.2.c that are subject to the alternative requirements in 23.54.030.L.2.b, if fewer than ten parking spaces are provided, exactly one EV-ready parking space is required. `[Source 1] SMC — smc_chapters, § 23.54.030.L.2, p.843`

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per SMC 23.54.030.L.2.b, institutional small-lot projects that provide fewer than 10 off-street parking spaces are subject to a reduced EV infrastructure requirement: * 1 EV-ready parking space minimum ### Final answer: → 1 EV-ready space.

---

### L3-PARK-010. Per SMC 23.54.030.L.1.c, what is the minimum percentage of parking spaces that must be EV-ready in a parking garage serving multiple dwelling units?

**Reference answer:** 45 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> A parking garage serving multiple dwelling units must have a minimum of 45 percent of its parking spaces EV-ready. `SMC 23.54.030.L.1.c`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> In a parking garage serving multiple dwelling units, a minimum of 45 percent of the parking spaces must be EV-ready per SMC 23.54.030.L.1.c.[Source 1] SMC — smc_chapters, § Title 23 - Land Use Code, p.842

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.L.1.c (EV infrastructure for multifamily parking structures), a parking garage serving multiple dwelling units must provide at least: * 20% of parking spaces EV-ready This applies to structured parking (garages) serving multifamily residential uses, unless a specific exemption or alternative compliance path applies elsewhere in the section. ### Final answer: → 20% EV-ready (minimum).

---

### L4-FIRE-001. WAC 51-54A 1015.3 (state fire code) and WAC 51-50 1015.3 (state building code) both set the minimum required guard height for open-sided walking surfaces. What is that height in inches?

**Reference answer:** 42 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required guard height for open-sided walking surfaces is 42 inches in both the state fire code (`WAC 51-54A-1015.3`) and the state building code (`WAC 51-50-1015.3`). [WAC 51-54A-1015] [WAC 51-50-1015]

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Both WAC 51-54A 1015.3 (state fire code) and WAC 51-50 1015.3 (state building code) require guards to be not less than 42 inches high for required guards, measured vertically from the adjacent walking surface (with specific stair and ramp measurement rules). [Source 11] [Source 14] | Topic | Agency / Section | Minimum Guard Height | Citation | |--------------------------|-------------------------|----------------------|------------| | Required guard height | WAC 51-54A 1015.3 | 42 inches minimum | [Source 11] | | Required guard height | WAC 51-50 1015.3 | 42 inches minimum | [Source 14] | Both sections include an exception allowing 36 inches minimum for certain Group R-3 and R-2 dwelling-unit conditions. [Source 11] [Source 14]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Both WAC 51-54A-1015.3 (State Fire Code) and WAC 51-50-1015.3 (State Building Code) adopt the same IBC requirement for guards at open-sided walking surfaces. The minimum required guard height is: * 42 inches (1067 mm) This is measured vertically above the adjacent walking surface, floor, or ramp. Both codes also allow the same limited lower-height exception (typically 36 inches in certain Group R/dwelling unit conditions), but the baseline requirement is identical. ### Final answer: → 42 inches

---

### L4-FIRE-002. WAC 51-54A 1014.2.1 (state fire code) and WAC 51-50 1014.2.1 (state building code) both set the minimum height for stairway handrails. What is that minimum height in inches?

**Reference answer:** 34 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum stairway handrail height is 34 inches. `[WAC 51-54A-1014]` `[WAC 51-50-1014]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum handrail height for stairways under both WAC 51-54A-1014.2.1 (Fire Code) and WAC 51-50-1014.2.1 (Building Code) is 34 inches above the stair tread nosings or ramp surface. [Source 1] [Source 2]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Both WAC 51-54A-1014.2.1 (State Fire Code) and WAC 51-50-1014.2.1 (State Building Code) adopt the same IBC handrail height requirement. The minimum (and maximum range) is: * 34 inches minimum to 38 inches maximum This is measured vertically from the stair tread nosing or ramp surface to the top of the handrail. ### Final answer: → 34 inches (minimum; within a 34–38 inch range).

---

### L4-FIRE-003. Per WAC 51-54A 1004 (and WAC 51-50 1004 occupant-load tables, adopted in Seattle via SMC 22.600.020), what floor area per occupant (in sq ft) applies to standing space in an assembly use without fixed seats (e.g., a concentrated dance floor with no chairs)?

**Reference answer:** 5 sq ft per occupant

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Standing space in an assembly use without fixed seats must be calculated at 5 square feet per occupant. `[WAC 51-54A-1004]` `[WAC 51-50-1004]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For assembly uses without fixed seats, “standing space” is assigned an occupant load factor of 5 square feet per occupant. This appears in the occupant-load tables for areas without fixed seating in both the building and fire code adoptions of IBC Table 1004.5, as implemented in WAC 51-50-1004 and WAC 51-54A-1004. [Source 1] WAC — wac_chapters, § 51-50, p.40; [Source 7] WAC — wac_chapters, § 51-54, p.38; [Source 10] WAC — wac_chapters, § 51-54, p.38.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Across WAC 51-54A-1004 (Fire Code) and WAC 51-50-1004 (Building Code / IBC Table 1004.5)—as adopted in Seattle via SMC 22.600.020—the occupant load factor for assembly standing space without fixed seats (e.g., a concentrated dance floor, nightclub standing area, or similar) is: * 7 net square feet per occupant This applies to concentrated assembly use where occupants are standing and closely packed, without fixed seating or tables. ### Final answer: → 7 net square feet per occupant.

---

### L4-FIRE-004. Per WAC 51-54A 3604, what is the maximum travel distance (in feet) from any point on a marina pier or float system to a fire-protection access point?

**Reference answer:** 150 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum distance is 150 feet from any point on the marina pier or float system to a standpipe hose connection (fire-protection access point). `[WAC 51-54A-3604]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The maximum distance is 150 feet from any point on the marina pier or float system to a standpipe outlet (the required fire‑protection access point). This is stated as: “no point on the marina pier or float system exceeds 150 feet from a standpipe outlet.” [Source 1] WAC — wac_chapters, § 51-54, p.71

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-3604 (Marinas and floating structures—fire access provisions), the maximum travel distance from any point on a pier or float system to an approved fire-protection access point is: * 250 feet (76 m) This distance is measured along the travel path on the pier or float system. ### Final answer: → 250 feet maximum travel distance.

---

### L4-FIRE-005. Per WAC 51-54A 1015.2, at what minimum drop height (in inches) above the floor or grade below does an open-sided walking surface require a guard?

**Reference answer:** 30 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> An open-sided walking surface requires a guard when it is located more than 30 inches above the floor or grade below. `[WAC 51-54A-1015]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> An open-sided walking surface requires a guard when it is more than 30 inches above the floor or grade below, measured vertically at any point within 36 inches horizontally of the open edge. `[Source 3] WAC — wac_chapters, § 51-54, p.45`

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-1015.2 (Guards—when required), a guard is required at open-sided walking surfaces, including mezzanines, balconies, ramps, and similar locations, where the drop to the level below exceeds: * 30 inches (762 mm) measured vertically within a specified horizontal distance from the edge. ### Final answer: → 30 inches minimum drop height triggers a required guard.

---

### L4-FIRE-006. Per WAC 51-54A 3307.2.2.1, what is the minimum required construction-site fire flow (in gpm)?

**Reference answer:** 500 gpm

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> The minimum required construction-site fire flow is 500 gallons per minute (gpm). `WAC 51-54A-3307`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required construction-site fire flow under WAC 51-54A-3307.2.2.1 is 500 gallons per minute (gpm), or the entire fire flow required for the building when constructed, whichever is greater. [Source 4]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-3307.2.2.1 (construction fire-flow requirements), the minimum required construction-site fire flow is: * 500 gallons per minute (gpm) This is the baseline fire-flow floor, with higher flows required if the calculated fire flow for the completed building or exposure conditions exceed this minimum. ### Final answer: → 500 gpm minimum construction-site fire flow.

---

### L4-FIRE-007. Per WAC 51-54A 903 (state fire code), what fire-area threshold (in sq ft) triggers automatic sprinkler requirements for Group A occupancies?

**Reference answer:** 12,000 sq ft

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> - Group A-3: 12,000 sq ft fire area triggers sprinklers (or occupant load ≥300, or A-3 fire area on a non–exit-discharge floor). `903.2.1.3` [WAC 51-54A-0903] - Assembly occupancies on roofs (A-2 and other A): no square-foot threshold is stated; sprinklers are required based on occupant load (A-2 roof assembly load >100; other Group A roof assembly load >300). `903.2.1.6` [WAC 51-54A-0903] No other Group A fire-area square-foot thresholds are specified in the provided sections.

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> Based on the available sections, the Washington amendments specify a 12,000 square foot fire-area threshold for Group A-3 occupancies; when a Group A-3 fire area exceeds 12,000 sq ft, an automatic sprinkler system is required throughout the story containing the Group A-3 occupancy and all stories down to the level of exit discharge serving that occupancy.[Source 8] IBC_WA — ibc_wa_docs, § 903.2.1.3, p.84; [Source 12] IBC_WA — ibc_wa_docs, § 903.2.1.3, p.92 | Group A subtype | Fire-area threshold triggering sprinklers | Citation | |-----------------|-------------------------------------------|----------| | Group A-3 | Fire area exceeds 12,000 sq ft | [Source 8], [Source 12] | The materials provided do not show a square-footage threshold for other Group A subgroups (A-1, A-2, etc.), so any such thresholds could not be determined from the available excerpts.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-0903 (Automatic sprinkler systems — Group A occupancies), the fire-area threshold that triggers sprinkler requirements for Group A occupancies is: * 12,000 square feet (net fire area) If a Group A fire area exceeds this size, automatic sprinkler protection is required (subject to the other occupant load, height, and use-specific provisions in the section). ### Final answer: → 12,000 square feet.

---

### L4-FIRE-008. Per WAC 51-54A 3307.2.2.3, what minimum fire flow (in gpm) is required for buildings under construction with a fire separation of 60 feet or greater?

**Reference answer:** 500 gpm

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Per `WAC 51-54A-3307.2.2.3`, a building of Type III, IV, or V construction with a fire separation of 60 feet or greater from a property lot line must be provided with a water supply of 500 gallons per minute. `[WAC 51-54A-3307]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For buildings of Type III, IV, or V construction under WAC 51-54A-3307.2.2.3 with a fire separation distance of 60 feet or greater from a property lot line, the required minimum water supply (fire flow) is 500 gallons per minute (gpm). This is stated as: “Where a building of Type III, IV, or V construction has a fire separation of 60 feet (18,288 mm) or greater from a property lot line, a water supply of 500 gallons per minute (1893 L/m) shall be provided.” [Source 10] WAC — wac_chapters, § 51-54, p.66

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-54A-3307.2.2.3 (construction fire flow — increased fire separation distance), where a building under construction has a fire separation distance of 60 feet or greater, the minimum required fire flow is: * 500 gallons per minute (gpm) This is the baseline floor value, subject to being increased if the calculated fire flow for the completed building is higher. ### Final answer: → 500 gpm minimum fire flow.

---

### L4-FIRE-009. Per WAC 51-54A 806, decorative artificial vegetation greater than 6 feet tall must be located at least how many feet from a building's exterior wall?

**Reference answer:** 30 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 3/5

> Per `WAC 51-54A-0321`, artificial decorative vegetation is exempt from the roof/near-building requirements when it is located more than 30 feet from the exterior wall of a building. `[WAC 51-54A-0321]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> Decorative artificial combustible vegetation exceeding 6 feet in height must be located more than 30 feet from the exterior wall of a building to be exempt from the roof/near-building requirements of WAC 51-54A-0321.[Source 1]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-0806 (Decorative vegetation / artificial combustible vegetation), decorative artificial combustible vegetation exceeding 6 feet in height must be located at least: * 5 feet from a building’s exterior wall This separation is required to reduce ignition risk from taller combustible decorative elements. ### Final answer: → 5 feet minimum separation from the exterior wall.

---

### L4-FIRE-010. Per WAC 51-54A 507.3 Exception 1, fire flow is not required for an isolated recreational B, U, or R-1 structure under what maximum floor area (in sq ft), provided it is at least 30 feet from any other structure?

**Reference answer:** 500 sq ft

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Fire flow is not required for an isolated recreational Group B, U, or R-1 structure with a maximum floor area of 500 square feet, provided it is at least 30 feet from any other structure. `[WAC 51-54A-0507]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> Fire flow is not required for qualifying isolated recreational B, U, or R‑1 structures with a maximum floor area of 500 square feet (46 m²), provided they are at least 30 feet from any other structure and meet the other conditions in the exception.[Source 1]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per WAC 51-54A-0507.3, Exception 1 (Fire protection water supply), fire flow is not required for certain isolated structures when specific conditions are met. For an isolated recreational Group B, U, or R-1 structure, the exception applies when: * The structure is 1,000 square feet or less in floor area, and * It is located at least 30 feet from any other structure ### Final answer: → 1,000 square feet maximum floor area.

---

### L4-PARK-001. A middle-housing project sits on an 8,000 sq ft lot with 4 units. Per RCW 36.70A.635(6)(f), what is the maximum total off-street parking the city may require (in spaces)?

**Reference answer:** 8

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> On an 8,000 sq ft lot with 4 middle‑housing units, the lot is greater than 6,000 sq ft, so the applicable cap is no more than two off‑street parking spaces per unit. Therefore, the maximum total off‑street parking the city may require is 8 spaces (4 units × 2 spaces/unit). `[RCW 36.70A.635]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Under RCW 36.70A.635(6)(f), a city may not require more than two off-street parking spaces per unit on lots greater than 6,000 square feet. For 4 units on an 8,000 sq ft lot, the maximum total off-street parking the city may require is: | Units | Max spaces per unit | Maximum total spaces | |-------|---------------------|----------------------| | 4 | 2 | 8 | [Source 4] RCW — rcw_chapters, § 36.70, p.129

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 2/5

> Per RCW 36.70A.635(6)(f), for middle housing on lots greater than 6,000 square feet, a city may not require more than: * 1 off-street parking space per dwelling unit Given: * 4 dwelling units * Lot size: 8,000 sq ft (greater than 6,000 sq ft, so the 1.0 cap applies) ### Calculation: 4 units × 1 space/unit = 4 spaces ### Final answer: → 4 total off-street parking spaces (maximum).

---

### L4-PARK-002. A co-living development has 40 sleeping units. Per RCW 36.70A.535(3)(a)(ii), what is the maximum total off-street parking the city may require (in spaces)?

**Reference answer:** 10

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> The city may not require more than 0.25 off-street parking spaces per sleeping unit for co-living housing. For 40 sleeping units, the maximum is: - 40 × 0.25 = 10 off-street parking spaces `[RCW 36.70A.535]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> RCW 36.70A.535(3)(a)(ii) limits required off-street parking for co-living housing to no more than 0.25 spaces per sleeping unit. [Source 4] RCW — rcw_chapters, § 36.70, p.113; [Source 12] RCW — rcw_chapters, § 36.70, p.113 For 40 sleeping units: 0.25 spaces/unit × 40 units = 10 off-street parking spaces (maximum).

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per RCW 36.70A.535(3)(a)(ii), for co-living housing located outside the qualifying transit exception, a city may not require more than: * 0.5 off-street parking spaces per sleeping unit Given: * 40 sleeping units * 0.5 spaces per unit cap ### Calculation: 40 × 0.5 = 20 spaces ### Final answer: → 20 total off-street parking spaces (maximum).

---

### L4-PARK-003. A nonresidential project provides exactly 50 off-street parking spaces. Per SMC 23.54.030.L.2.a (base nonresidential EV-Ready requirement, no exception applies), how many of those spaces must be EV-Ready?

**Reference answer:** 15 spaces

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 2/5

> For nonresidential uses, 30 percent of provided parking spaces must be EV-ready; for 50 spaces, this equals 15 EV-ready spaces. `SMC 23.54.030.L.2.a`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 1/5

> For nonresidential uses, when parking is provided, a minimum of 30 percent of those spaces must be EV-ready, unless an exception in 23.54.030.L.2.b or .2.c applies (which you’ve said does not). [Source 1] 30% of 50 spaces = 15 spaces. So, 15 of the 50 off-street parking spaces must be EV-ready. [Source 1]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.L.2.a, the base requirement for nonresidential parking is: * 20% of parking spaces must be EV-ready Given: * Total spaces = 50 * Requirement = 20% ### Calculation: 50 × 0.20 = 10 spaces ### Final answer: → 10 EV-ready parking spaces.

---

### L4-PARK-004. A multifamily parking garage provides 60 off-street parking spaces. Per SMC 23.54.030.L.1.c (parking garages for multiple dwelling units), how many of those spaces must be EV-Ready?

**Reference answer:** 27 spaces

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> For a parking garage serving multiple dwelling units, 45 percent of the parking spaces must be EV-ready. For 60 spaces, 0.45 × 60 = 27, so 27 spaces must be EV-ready. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> For parking garages serving multiple dwelling units, at least 45 percent of the parking spaces must be EV-ready. [Source 2]; [Source 10] | Total spaces in garage | Required EV-ready percentage | Required EV-ready spaces | Citation | |------------------------|------------------------------|--------------------------|---------------------| | 60 | 45% | 27 | [Source 2]; [Source 10] | So, 27 of the 60 spaces must be EV-ready.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per SMC 23.54.030.L.1.c, parking garages serving multiple dwelling units must provide: * 20% of parking spaces EV-ready Given: * Total spaces = 60 * Requirement = 20% ### Calculation: 60 × 0.20 = 12 spaces ### Final answer: → 12 EV-ready parking spaces.

---

### L4-PARK-005. A new Group B office building provides 80 off-street parking spaces. Per WAC 51-50-0429 Table 429.2, how many of those spaces must be designated 'EV Charging Stations'?

**Reference answer:** 8 spaces

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> For a Group B occupancy, 10% of total parking spaces must be EV Charging Stations. For 80 spaces, this is 8 EV Charging Stations (80 × 10% = 8). `[WAC 51-50-0429]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> For Group B occupancies, Table 429.2 requires EV Charging Stations equal to 10% of total parking spaces. [Source 2] | Item | Value | Citation | |-------------------------------|-------|-----------| | Total off-street parking | 80 | (given) | | Required EV Charging Stations | 8 | [Source 2] WAC — wac_chapters, § 51-50, p.20 | Thus, 8 of the 80 spaces must be designated as EV Charging Stations.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per WAC 51-50-0429 Table 429.2 (Electric Vehicle Charging Infrastructure requirements for Group B occupancies), the requirement for EV charging stations (installed chargers, not just EV-ready spaces) is: * 10% of total parking spaces Given: * Total parking spaces = 80 * Requirement = 10% ### Calculation: 80 × 0.10 = 8 spaces ### Final answer: → 8 EV charging stations.

---

### L4-PARK-006. A new Group B office building provides 80 off-street parking spaces. Per WAC 51-50-0429 Table 429.2, how many spaces in total must carry EV infrastructure (EV Charging Stations + EV-Ready + EV-Capable combined)?

**Reference answer:** 24 spaces

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> For a Group B occupancy, 10% of total parking spaces must be EV Charging Stations, 10% EV-Ready, and 10% EV-Capable, for a combined 30% of total spaces with EV infrastructure. For 80 spaces, this equals 24 spaces (0.30 × 80). `[WAC 51-50-0429]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For Group B occupancies, Table 429.2 requires 10% of total parking spaces to be EV Charging Stations, 10% EV-Ready, and 10% EV-Capable.[Source 2][Source 11] For 80 spaces: | Category | Percentage | Spaces Required | Citation | |-------------------|------------|-----------------|-----------------| | EV Charging | 10% | 8 | [Source 2] WAC 51-50-0429 Table 429.2, p.20 | | EV-Ready | 10% | 8 | [Source 2] WAC 51-50-0429 Table 429.2, p.20 | | EV-Capable | 10% | 8 | [Source 2] WAC 51-50-0429 Table 429.2, p.20 | Total spaces that must carry some form of EV infrastructure = 8 + 8 + 8 = 24.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> We use WAC 51-50-0429 Table 429.2 for Group B occupancies. From the table: * Group A, B, E, F, H, I, M, and S occupancies require: * 10% EV Charging Stations * 10% EV-Ready spaces * 10% EV-Capable spaces ([Washington State Legislature][1]) ### Step 1: Apply percentages to 80 spaces Each category is calculated separately and rounded up to the nearest whole number. * EV Charging Stations: 10% of 80 = 8 * EV-Ready: 10% of 80 = 8 * EV-Capable: 10% of 80 = 8 ### Step 2: Combine all EV infrastructure categories Total EV infrastructure spaces = 8 + 8 + 8 = 24 spaces --- ### Final Answer: 24 total parking spaces must have EV infrastructure (EV Charging Stations + EV-Ready + EV-Capable combined). [1]: https://app.leg.wa.gov/wac/default.aspx?cite=51-50-0429&utm_source=chatgpt.com "WAC 51-50-0429:"

---

### L4-PARK-007. An office structure has 200,000 square feet of office floor area. Per SMC 23.54.015.K.8, how many bicycle commuter showers must be provided?

**Reference answer:** 4 showers

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Structures containing 100,000 sq ft or more of office use floor area must provide two showers for every 100,000 sq ft of office use. For 200,000 sq ft, this equals 4 bicycle commuter showers required. `SMC 23.54.015.K.8`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For office structures, SMC 23.54.015.K.8 requires “two showers … for every 100,000 square feet of office use.”[Source 1] SMC — smc_chapters, § Title 23 - Land Use Code, p.808 For 200,000 square feet of office floor area: | Office floor area | Shower requirement per SMC 23.54.015.K.8 | Total showers required | |-------------------|-------------------------------------------|------------------------| | 200,000 sq ft | 2 showers / 100,000 sq ft | 4 showers | So, 4 bicycle commuter showers are required.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 2/5

> Under SMC 23.54.015.K.8, bicycle commuter shower requirements are based on non-residential floor area at a rate of 1 shower per 50,000 square feet (or fraction thereof). ### Step 1: Apply ratio [ 200{,}000 \div 50{,}000 = 4 ] ### Step 2: Apply rounding rule Because the requirement is per 50,000 square feet or fraction thereof, the result is already a whole number. ### Final Answer: 4 bicycle commuter showers are required.

---

### L4-PARK-008. An eating and drinking establishment occupies 5,000 square feet of gross floor area. Per SMC 23.54.015 Table A row B.2, what is the minimum required number of off-street parking spaces for this use?

**Reference answer:** 20 spaces

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> An eating and drinking establishment requires 1 space per 250 sq ft of gross floor area. For 5,000 sq ft, the minimum required off-street parking is: - 5,000 ÷ 250 = 20 spaces. `[SMC 23.54.015 Table A row B.2]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum required off-street parking for an eating and drinking establishment is 1 space per 250 square feet of gross floor area. For 5,000 square feet: 5,000 sq ft ÷ 250 sq ft/space = 20 spaces. | Use | Area (sq ft) | SMC Ratio | Minimum Spaces | Citation | |------------------------------|--------------|------------------------------|----------------|---------------------| | Eating and drinking establishment | 5,000 | 1 space per 250 sq ft GFA | 20 | [Source 2] SMC — smc_chapters, § 23.54.015 Table A row B.2, p.792 |

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.015 Table A, Row B.2 (Eating and Drinking Establishments), the minimum off-street parking requirement is: * 1 parking space per 200 square feet of gross floor area ### Step 1: Apply the ratio [ 5{,}000 \div 200 = 25 ] ### Step 2: Rounding The result is already a whole number, so no rounding adjustment is needed. ### Final Answer: 25 off-street parking spaces are required.

---

### L4-PARK-009. A multifamily parking garage provides 100 off-street parking spaces. Per SMC 23.54.030.L.1.c, how many of those spaces must be EV-Ready?

**Reference answer:** 45 spaces

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> For a parking garage serving multiple dwelling units, 45 percent of the parking spaces must be EV-ready. For 100 spaces, this equals 45 EV-ready spaces. `SMC 23.54.030.L.1.c`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> For a parking garage serving multiple dwelling units, SMC 23.54.030.L.1.c requires that a minimum of 45 percent of the parking spaces be EV-ready.[Source 3] SMC — smc_chapters, § Title 23 - Land Use Code, p.842; [Source 12] SMC — smc_chapters, § Title 23 - Land Use Code, p.842 | Total spaces in multifamily garage | % required EV-ready | Number of EV-ready spaces required | |-----------------------------------|----------------------|-------------------------------------| | 100 | 45% | 45 |

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.L.1.c (parking garages for multiple dwelling units), the requirement for EV-Ready spaces is 20% of total parking spaces. ### Step 1: Apply requirement [ 100 \times 0.20 = 20 ] ### Step 2: Rounding Already a whole number, so no rounding adjustment applies. ### Final Answer: 20 parking spaces must be EV-Ready.

---

### L4-PARK-010. A loading area is being designed at the ground floor of a Group M retail use. Per SMC 23.54.035.C.1, what is the minimum required width (in feet) of a single off-street loading berth?

**Reference answer:** 10 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required width of a single off-street loading berth is 10 feet. `[SMC 23.54.035]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The minimum required width of a single off-street loading berth is 10 feet: “Each loading berth shall be not less than ten (10) feet in width and shall provide not less than fourteen (14) feet vertical clearance.” [Source 1] SMC — smc_chapters, § 23.54.035, p.845

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.035.C.1, a standard off-street loading berth must meet the minimum dimensional requirements for width. For a Group M (retail) use at the ground floor, the code requires: * Minimum loading berth width: 12 feet ### Final Answer: 12 feet

---

### L5-FIRE-001. Per RCW 19.27.510, what minimum aggregate floor area (in square feet) of concentrated dancing or standing space classifies an A-2 occupancy as a 'nightclub' subject to RCW 19.27.500's sprinkler mandate (below WAC 51-54A 903's general 12,000-sq-ft Group A sprinkler threshold)?

**Reference answer:** 350 square feet

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The minimum aggregate floor area is more than 350 square feet of concentrated use of unfixed chairs and standing space designated and primarily used for dancing or viewing performers. RCW 19.27.510 defines a "nightclub" as an A-2 occupancy where this concentrated dancing/viewing area "exceeds three hundred fifty square feet," excluding adjacent lobby areas, and this definition is what triggers the nightclub sprinkler mandate in RCW 19.27.500. [Source 1] RCW — rcw_chapters, § 19.27.510, p.26; [Source 3] RCW — rcw_chapters, § 19.27.500, p.26.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Per RCW 19.27.510 (nightclub definition for sprinkler mandate purposes), an A-2 occupancy is classified as a “nightclub” when it includes a concentrated dance floor or standing space with a minimum aggregate area of: * 250 square feet Once that threshold is met, the occupancy is treated as a nightclub for purposes of RCW 19.27.500, triggering the sprinkler requirement regardless of the broader 12,000 sq ft Group A fire-area threshold in WAC 51-54A-903. ### Final answer: → 250 square feet minimum concentrated dancing/standing area.

---

### L5-FIRE-002. Per WAC 51-54A 1014.2.1 and WAC 51-50 1014.2.1, both setting stairway handrail height limits, what is the MAXIMUM permitted handrail height (in inches) above stair tread nosings?

**Reference answer:** 38 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The maximum permitted handrail height above stair tread nosings is 38 inches. `WAC 51-50-1014` `WAC 51-54A-1014`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> The maximum permitted handrail height above stair tread nosings is 38 inches. Both WAC 51-54A-1014.2.1 and WAC 51-50-1014.2.1 state that handrail height “shall be uniform, not less than 34 inches (864 mm) and not more than 38 inches (965 mm)” above stair tread nosings or ramp surfaces. [Source 1] [Source 2]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Both WAC 51-54A-1014.2.1 (State Fire Code) and WAC 51-50-1014.2.1 (State Building Code) adopt the same IBC requirement for stair handrails. The permitted range is: * 34 inches minimum * 38 inches maximum Measured vertically from the stair tread nosings to the top of the handrail. ### Final answer: → 38 inches maximum handrail height.

---

### L5-FIRE-003. Per DR 7-2014 §1.2 (Seattle Director's Rule), at what maximum distance (in inches) from the elevator motor and sprinkler heads must a fixed-temperature heat detector be located when the driving machine is at the top of the hoistway or in the pit area? (WAC 51-54A 903 is silent on this specific distance.)

**Reference answer:** 18 inches

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The fixed-temperature heat detector must be located within a maximum of 18 inches of the elevator motor and sprinkler head(s) when the driving machine is at the top of the hoistway or in the pit area. `[DR 7-2014]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The maximum distance is 18 inches from the elevator motor and sprinkler heads. | Item | Required Maximum Distance | Citation | |-------------------------------------------|---------------------------|----------| | 135°F fixed-temperature heat detector(s) location relative to motor and sprinkler head(s) when driving machine is at top of hoistway or in pit | 18 inches | [Source 2] DIR — seattle_dir_rules, § 7-2014, p.2 |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per Seattle Department of Construction & Inspections Director’s Rule DR 7-2014 §1.2 (Elevator fire protection coordination), when a fixed-temperature heat detector is used for elevator shutdown and the elevator machine is located at the top of the hoistway or in the pit area, the detector must be positioned within: * 18 inches (maximum) of the elevator machine and sprinkler heads This requirement ensures early activation while avoiding nuisance tripping from localized heat sources directly at equipment or sprinkler discharge points. ### Final answer: → 18 inches maximum distance.

---

### L5-FIRE-004. Per DR 7-2014 (Seattle), in buildings without a fire alarm system, what minimum letter height (in inches) is required for the 'ELEVATOR FIRE ALARM' alarm sign located at the recall floor near the entrance to the elevators?

**Reference answer:** 1 inch

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The sign must use letters at least 1 inch high. `[DR 7-2014]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The minimum letter height required is 1 inch for the “ELEVATOR FIRE ALARM” sign in buildings without a fire alarm system, located at the recall floor near the elevator entrance. `[Source 2] DIR — seattle_dir_rules, § 7-2014, p.2`

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per Seattle Department of Construction & Inspections Director’s Rule DR 7-2014 (Elevator fire alarm and recall signage provisions), in buildings without a fire alarm system, the required signage at the recall floor reading “ELEVATOR FIRE ALARM” must have lettering with a minimum height of: * 1 inch (25 mm) minimum letter height This ensures the notice is clearly visible at the elevator landing where manual or dedicated elevator fire alarm indicators are provided in lieu of a building-wide fire alarm system. ### Final answer: → 1 inch minimum letter height.

---

### L5-FIRE-005. Per DR 7-2014 §3.1 (Seattle), what is the maximum permitted height (in feet) above the floor at which the elevator sprinkler control valve / power-disconnect device may be located outside the machine room door?

**Reference answer:** 6 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The sprinkler control valve / power-disconnect device must be located not higher than 6 feet above the floor outside and next to the machine room door. `[DR 7-2014]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The valve for the elevator machine-room sprinkler supply line must be located “not higher than 6 feet above the floor” outside and next to the machine room door. `[Source 7] DIR — seattle_dir_rules, § 7-2014, p.3`

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per Seattle Department of Construction & Inspections Director’s Rule DR 7-2014 §3.1 (Elevator fire protection equipment location), when the elevator sprinkler control valve or power disconnect device is located outside the machine room door, it must be installed at a height not exceeding: * 6 feet above the finished floor This ensures the controls are readily accessible for emergency responders without requiring ladders or special equipment. ### Final answer: → 6 feet maximum height above the floor.

---

### L5-FIRE-006. Per SPU Design Standards 5.6.1.3 (Water Infrastructure), what is the minimum required water main pressure (in psi) delivered to the meter under maximum-day demand plus required fire flow conditions?

**Reference answer:** 20 psi

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required pressure at the customer’s meter under maximum-day demand (MDD) plus required fire flow conditions is 20 psi. `[SPU 5.6.1.3]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> Under maximum-day demand plus required fire flow conditions, SPU requires that pressure at the customer’s meter must not be less than 20 psi. This is stated as: “Minimum pressure criteria for new water mains are 30 psi under peak hour demand (PHD) conditions, and 20 psi when flows are a combination of average maximum day demand (MDD) and required fire flow. Pressure at the customer’s meter must not be less than 20 psi.”[Source 1] SPU — spu_design_standards, § 5WaterInfrastructureFinalRedacted, p.20

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 2/5

> Per Seattle Public Utilities Design Standards §5.6.1.3 (Water Infrastructure), the minimum required system pressure at the meter under maximum-day demand plus required fire flow conditions is: * 20 psi minimum residual pressure This is the performance floor SPU uses to ensure adequate domestic and fire protection service under peak combined demand conditions. ### Final answer: → 20 psi minimum residual pressure.

---

### L5-FIRE-007. Per SPU Design Standards 5.6.1.3 (Water Infrastructure), what is the minimum required water main pressure (in psi) at peak hour demand (without a fire-flow contingency)?

**Reference answer:** 30 psi

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The minimum required water main pressure at peak hour demand (without a fire-flow contingency) is 30 psi for new water mains. `[SPU 5.6.1.3]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The minimum required water main pressure at peak hour demand (without fire-flow) is 30 psi. This comes from SPU’s minimum pressure criteria for new water mains: “30 psi under peak hour demand (PHD) conditions”; the 20 psi minimum applies only when flows are a combination of maximum day demand and required fire flow, not to PHD without fire flow. [Source 1] SPU — spu_design_standards, § 5WaterInfrastructureFinalRedacted, p.20.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 0/5

> Per Seattle Public Utilities Design Standards §5.6.1.3 (Water Infrastructure), under peak hour demand conditions without fire-flow added, the minimum required water system pressure at the meter is: * 35 psi minimum residual pressure This is the baseline service-pressure requirement used for normal peak-hour domestic demand conditions (i.e., excluding fire-flow scenarios, which are governed by the lower 20 psi combined-demand threshold). ### Final answer: → 35 psi minimum residual pressure.

---

### L5-FIRE-008. Per RCW 19.27.530, by what calendar year must all newly constructed buildings classified as residential occupancies (under chapter 51-54 WAC) be equipped with carbon monoxide alarms?

**Reference answer:** 2011

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> All newly constructed buildings classified as residential occupancies must be equipped with carbon monoxide alarms by calendar year 2011 (i.e., by January 1, 2011). `[RCW 19.27.530]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> All newly constructed buildings classified as residential occupancies must be equipped with carbon monoxide alarms by calendar year 2011. RCW 19.27.530(2)(a) states that the building code council’s rules must require that “by January 1, 2011, all newly constructed buildings classified as residential occupancies will be equipped with carbon monoxide alarms.” [Source 1] RCW — rcw_chapters, § 19.27, p.27

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per RCW 19.27.530, Washington’s statewide carbon monoxide alarm requirement for newly constructed residential occupancies (as defined under chapter 51-54 WAC) applies to buildings constructed after: * January 1, 2011 So, all newly constructed residential occupancies after that date must be equipped with CO alarms. ### Final answer: → 2011.

---

### L5-FIRE-009. Per RCW 19.27.530, by what calendar year must all OTHER (existing) residential-occupancy buildings be equipped with carbon monoxide alarms?

**Reference answer:** 2013

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> All other buildings classified as residential occupancies (i.e., not newly constructed) must be equipped with carbon monoxide alarms by January 1, 2013. `[RCW 19.27.530]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> All other existing buildings classified as residential occupancies must be equipped with carbon monoxide alarms by calendar year 2013. RCW 19.27.530(2)(a) states that “all newly constructed buildings … will be equipped with carbon monoxide alarms” by January 1, 2011, and “all other buildings classified as residential occupancies will be equipped with carbon monoxide alarms by January 1, 2013.” [Source 1] RCW — rcw_chapters, § 19.27, p.27

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> Per RCW 19.27.530, the requirement for existing residential occupancies (other than new construction) to be equipped with carbon monoxide alarms applied by: * January 1, 2013 ### Final answer: → 2013.

---

### L5-FIRE-010. Per DR 7-2014 §1.2 (Seattle), what temperature rating (in degrees Fahrenheit) is required for the fixed-temperature heat detector that initiates Phase I recall in an elevator machine room or hoistway?

**Reference answer:** 135 degrees F

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The fixed-temperature heat detector must be rated at 135 degrees Fahrenheit. `[DR 7-2014]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> The fixed-temperature heat detector must have a 135-degree Fahrenheit rating. `[Source 1] DIR — seattle_dir_rules, § 7-2014, p.2`

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Per Seattle Department of Construction & Inspections Director’s Rule DR 7-2014 §1.2 (Elevator fire alarm/recall initiation requirements), the fixed-temperature heat detector used to initiate Phase I elevator recall in an elevator machine room or hoistway must have a temperature rating of: * 135°F (57°C) This is the standard fixed-temperature rating used for elevator recall activation consistent with coordinated sprinkler/heat detection design criteria. ### Final answer: → 135°F.

---

### L5-PARK-001. Per RCW 36.70A.535(3)(a)(i), what is the maximum number of off-street parking spaces a city may require for co-living housing located within one-half mile walking distance of a major transit stop?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> The city may not require any off-street parking spaces for co-living housing located within one-half mile walking distance of a major transit stop. `[RCW 36.70A.535(3)(a)(i)]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts provided for RCW 36.70A.535 only state that cities and counties must allow co‑living housing as a permitted use within an urban growth area, and do not include subsection (3)(a)(i) or any numerical parking limits for co‑living housing near transit stops. `[Source 7] RCW — rcw_chapters, § 36.70, p.112`

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under RCW 36.70A.535(3)(a)(i), cities are prohibited from requiring more than a specified maximum amount of off-street parking for co-living housing located within one-half mile walking distance of a major transit stop. For co-living housing in that location, the statute sets the maximum parking requirement at: * 0.25 off-street parking spaces per sleeping unit (or equivalent co-living unit) This effectively means a city cannot require more than 1 parking space per 4 sleeping units. ### Final Answer: 0.25 off-street parking spaces per sleeping unit (maximum).

---

### L5-PARK-002. Per RCW 36.70A.635(6)(d), what is the maximum number of off-street parking spaces a city may require as a condition of permitting middle housing within one-half mile walking distance of a major transit stop?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 3/5

> A city may not require any off-street parking spaces as a condition of permitting middle housing within one-half mile walking distance of a major transit stop. `[WAC 365-196-872]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts provided for RCW 36.70A.635 only include subsection (1) regarding minimum residential density and do not contain subsection (6)(d) or any language specifying a maximum number of off‑street parking spaces for middle housing near major transit stops. [Source 5] RCW — rcw_chapters, § 36.70, p.127

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under RCW 36.70A.635(6)(d), for middle housing located within one-half mile walking distance of a major transit stop, a city may not require more than: * 0.5 off-street parking spaces per dwelling unit This is the statutory maximum parking standard allowed in that transit-proximate context. ### Final Answer: 0.5 off-street parking spaces per dwelling unit (maximum).

---

### L5-PARK-003. Per WAC 51-50-0429 Section 429.2 Exception 1, how many EV-Ready spaces are required in a Group B office project providing 8 on-site parking spaces (fewer than 10)?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> 0 EV-Ready spaces are required. Exception 1 to `Section 429.2` states that, except for Group A, E, and M occupancies, on-site parking with less than 10 parking spaces is not required to comply with Section 429.2; Group B is not listed in the exception to the exception, so a Group B office with 8 spaces has no EV charging infrastructure requirement under `Section 429.2`. `[WAC 51-50-0429]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> None are required. Exception 1 to Section 429.2 states that, except for Groups A, E, and M, “on-site parking with less than 10 parking spaces shall not be required to comply with Section 429.2.” [Source 2] This exception applies to Group B occupancies, so a Group B office project with 8 on-site parking spaces is not required to provide any EV-Ready spaces under WAC 51-50-0429. [Source 2]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Under WAC 51-50-0429 Section 429.2, Exception 1, small parking facilities are exempt from the standard EV infrastructure thresholds. For Group B occupancies (office), Exception 1 applies when a project provides: * Fewer than 10 total parking spaces In that case, the code states that EV infrastructure requirements (including EV-Ready spaces) do not apply. ### Step-by-step application: * Total spaces provided: 8 * Threshold for applicability: 10 spaces * Since 8 < 10 → Exception 1 applies ### Final Answer: 0 EV-Ready spaces are required.

---

### L5-PARK-004. Per SMC 23.54.030.L.8, how many EV supply equipment (chargers) does Section 23.54.030 require to be installed?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Section `23.54.030.L` requires parking spaces to be EV‑ready (raceway/circuit capacity), but explicitly states that EV supply equipment is not required to be installed: “This Section 23.54.030 does not require EV supply equipment … to be installed.” `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> Section 23.54.030 does not require any EV supply equipment (chargers) to be installed. The code explicitly states: “This Section 23.54.030 does not require EV supply equipment, as defined by Article 100 of the Seattle Electrical Code, to be installed.” [Source 1] SMC — smc_chapters, § 23.54.030.L, p.844.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.L.8, the requirement for EV supply equipment (EV chargers) is tied specifically to the EV Charging Station percentage requirement in the table. The code requires: * At least 10% of total parking spaces must be provided as EV Charging Stations, and * Those EV Charging Station spaces must be equipped with EV supply equipment (chargers). ### Key interpretation of Section L.8 Section 23.54.030.L.8 does not set a separate standalone number of chargers; instead, it requires that: * All required EV Charging Station spaces must include installed EVSE (chargers) * And the minimum number of chargers equals the number of required EV Charging Stations So the installed EVSE count = EV Charging Station requirement. ### Final Answer: EV supply equipment (chargers) must be installed in all required EV Charging Station spaces (i.e., 10% of total parking spaces).

---

### L5-PARK-005. Per WAC 173-26-241(3)(k), how many parking facilities qualify as a 'preferred use' under the Shoreline Master Program guidelines?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> No parking facilities qualify as a “preferred use” under the Shoreline Master Program guidelines; parking facilities in shorelines are explicitly stated to be “not a preferred use” and are allowed only as necessary to support an authorized use. `[WAC 173-26-241]`

**Vanilla vector RAG**: Correctness 1/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved WAC sections address various parking rules (state parks, campuses, allocation of spaces, accessible parking, and minimum residential parking requirements), but do not include WAC 173-26-241(3)(k) or any Shoreline Master Program “preferred use” classifications for parking facilities. [Source 1–12]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Under WAC 173-26-241(3)(k) (Shoreline Master Program Guidelines), the rule does not assign a numeric threshold for how many parking facilities qualify as a “preferred use.” Instead, it defines the concept in categorical terms: * Parking facilities are not generally designated as a “preferred use” outright. * They are treated as supporting or accessory uses to shoreline water-dependent, water-related, or water-enjoyment uses. * Only in specific contexts—where parking is integrated into an authorized shoreline use—can it be considered part of a preferred development pattern, but it is not independently classified as a preferred use category. ### Key point: The regulation is qualitative, not quantitative—it does not say “X number of parking facilities qualify.” ### Final Answer: 0 parking facilities are independently designated as a “preferred use”; the rule does not assign a numeric qualifying amount.

---

### L5-PARK-006. Per WAC 173-26-211(5)(a), how many new parking areas are allowed in the 'natural' shoreline environment when those parking areas can be located outside the natural-designated shoreline?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> Zero new parking areas are allowed in the "natural" environment when those parking areas can be located outside the natural-designated shoreline, because roads, utility corridors, and parking areas that can be located outside the "natural" shoreline should be located outside it. `[WAC 173-26-211]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved WAC sections address general parking rules (e.g., “parking only in designated areas,” campus rules, and beach parking limits) but do not include WAC 173-26-211(5)(a) or any provisions about the number of new parking areas allowed in a “natural” shoreline environment or conditions when parking can be located outside that designation.[Source 1][Source 2][Source 3][Source 4][Source 5][Source 6][Source 7][Source 8][Source 9][Source 10][Source 11][Source 12]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Under WAC 173-26-211(5)(a) (Shoreline Master Program environmental designations), the “natural” shoreline environment is the most restrictive designation and is intended to preserve areas essentially free from development. The rule specifically provides that: * The natural environment should be managed to prevent significant ecological impacts, and * New development such as parking areas should not be located within the natural environment if it can be located outside it. ### Key implication of the provision you referenced When a parking area can be located outside the natural shoreline environment, the guideline supports: * Avoidance of new parking facilities within the natural environment ### Final Answer: 0 new parking areas are allowed when they can be located outside the natural shoreline environment.

---

### L5-PARK-007. Per RCW 36.70A.535(2)(b), how many bedroom-mix or unit-size requirements may a city impose on co-living housing?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> A city subject to `RCW 36.70A.535` may not impose any requirements that co-living housing provide a mix of unit sizes or a particular number of bedrooms. `[RCW 36.70A.535]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The excerpts provided for RCW 36.70A.535 only state that cities and counties must allow co‑living housing as a permitted use within urban growth areas, but do not include subsection (2)(b) or any language specifying limits on bedroom‑mix or unit‑size requirements for co‑living housing. [Source 8] RCW — rcw_chapters, § 36.70, p.112

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Under RCW 36.70A.535(2)(b), cities are restricted from imposing certain design or composition controls on co-living housing. Specifically, the statute states that a city may not require or restrict bedroom mix or unit size for co-living housing. So the allowable number of such requirements is: * Zero ### Final Answer: 0 bedroom-mix or unit-size requirements may be imposed.

---

### L5-PARK-008. Per RCW 36.70A.535(7)(b), how many off-street parking spaces' worth of the airport carve-out applies to portions of Seattle within a one-mile radius of Sea-Tac International Airport (which lies in SeaTac, not Seattle)?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 2/5, Faithfulness 3/5

> Not found in provided sources. None of the excerpts for `RCW 36.70A.620`/`RCW 36.70A.622` or `WAC 365-196-872` specify any number of off-street parking spaces associated with the airport carve‑out; they only state that the listed residential parking provisions do not apply within a one‑mile radius of a qualifying commercial airport. `[RCW 36.70A.620]` `[WAC 365-196-872]`

**Vanilla vector RAG**: Correctness 1/5, Faithfulness 4/5

> RCW 36.70A.535(7)(b) (as reflected in the excerpted language) applies to “portions of cities within a one-mile radius of a commercial airport in Washington with at least 9,000,000 annual enplanements.” [Source 7] RCW — rcw_chapters, § 36.70, p.168. The retrieved text does not specify any numerical cap or a number of “off‑street parking spaces’ worth” for this airport carve‑out; it only defines the geographic area (within one mile of such an airport). [Source 7] RCW — rcw_chapters, § 36.70, p.168. Accordingly, the number of spaces affected within portions of Seattle near Sea‑Tac cannot be determined from the available materials.

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Under RCW 36.70A.535(7)(b), the “airport carve-out” is a location-based exemption tied to airport proximity areas where aviation-related impacts justify different parking treatment. However, the key limitation in the statute is geographic applicability: * The carve-out applies only to jurisdictions that contain land within the defined airport impact area. * The rule is not triggered simply because a nearby airport exists outside the jurisdiction boundary. * Since Sea-Tac International Airport is located in the City of SeaTac, not Seattle, Seattle land does not fall within the statutory airport carve-out zone described for that airport-specific provision. ### Therefore: * No portion of Seattle qualifies for the airport carve-out under this subsection. ### Final Answer: 0 off-street parking spaces’ worth of airport carve-out applies to Seattle under RCW 36.70A.535(7)(b).

---

### L5-PARK-009. Per WAC 51-50-0429 Table 429.2, how many EV Charging Stations are required for a Group B office providing exactly zero on-site parking spaces?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> 0 EV Charging Stations are required. Section `429.2` requires EV charging infrastructure only for “Buildings and accessory structures…provided with” parking spaces, and Table 429.2 expresses requirements as percentages of total parking spaces; with zero on-site parking spaces, the 10% requirement for Group B occupancies yields zero required EV Charging Stations. `[WAC 51-50-0429]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> None are required, because the EV charging requirements in WAC 51-50-0429 apply only to buildings and accessory structures “provided with” parking spaces, and the percentages in Table 429.2 are applied to the number of parking spaces (with calculations rounded up), which in this case is zero.[Source 3] WAC — wac_chapters, § 51-50, p.20; [Source 2] WAC — wac_chapters, § 51-50, p.20

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> Under WAC 51-50-0429 Table 429.2, EV infrastructure requirements are calculated based on the number of provided off-street parking spaces. For Group B (office) occupancies: * Requirements (including EV Charging Stations) apply only to spaces that are actually provided ### Key point: If a project provides 0 parking spaces, then: * There are no parking spaces to apply the 10% EV Charging Station requirement to. ### Step-by-step: * Total parking provided = 0 * EV Charging Station requirement = 10% × 0 = 0 ### Final Answer: 0 EV Charging Stations are required.

---

### L5-PARK-010. Per SMC 23.54.030.A.4 ('barrier-free parking'), by how many feet may an accessible parking space be narrower than the required 8-foot minimum width?

**Reference answer:** 0

**PolicyBridge (RAG + graph)**: Correctness 1/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Under SMC 23.54.030.A.4, barrier-free (accessible) parking spaces “shall not be less than 8 feet in width,” so they may not be narrower at all. There is no allowance in this section for any reduction below 8 feet. [Source 3] SMC — smc_chapters, § 23.54.030.A.4, p.830

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.A.4 (Barrier-Free Parking), accessible parking spaces may be reduced in width when additional maneuvering space is provided adjacent to the stall. The standard requirement is: * 8 feet minimum stall width The exception allows: * A reduction of up to 2 feet in stall width when the required access aisle or maneuvering space is provided So the minimum reduced width becomes: * 8 ft − 2 ft = 6 ft (with compliant access provisions) ### Final Answer: 2 feet

---

### L6-FIRE-001. Since WAC 51-54A 1014.2.1 sets the minimum handrail height for stairways at 30 inches above tread nosings, what is the maximum permitted handrail height (in inches)?

**Reference answer:** 34 inches

**PolicyBridge (RAG + graph)**: Correctness 1/5, Faithfulness 2/5

> The maximum permitted handrail height for stairways is 38 inches above the stair tread nosings. `WAC 51-50-1014`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 2/5

> The Washington amendments to IBC/IFC 1014.2.1 set the standard handrail height range at 34 inches minimum and 38 inches maximum above stair tread nosings for typical stairways and ramps. [Source 1] [Source 2] For alternating tread devices and ships ladders, the permitted range is 30 inches minimum to 34 inches maximum above tread nosings. [Source 1] [Source 2] | Condition | Minimum (in) | Maximum (in) | Citation | |-----------------------------------------------|-------------:|-------------:|-----------------| | Standard stairways/ramps handrail height | 34 | 38 | [Source 1][Source 2] | | Alternating tread devices / ships ladders | 30 | 34 | [Source 1][Source 2] |

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> That premise is off. WAC 51-54A-1014.2.1 does not set a 30-inch minimum for stair handrails. Under WAC 51-54A-1014.2.1 (which tracks the IBC), stairway handrails must be: * 34 inches minimum, and * 38 inches maximum measured vertically from the stair tread nosings. So the code already defines both bounds, and the maximum is not derived from a 30-inch minimum—it is explicitly stated. ### Final answer: → 38 inches maximum permitted handrail height.

---

### L6-FIRE-002. Since WAC 51-54A 322.4.1 limits any single lithium-battery container to 25 cubic feet, what aggregate volume (in cubic feet) is permitted in a limited indoor storage area?

**Reference answer:** 7.5 cubic feet

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 1/5

> Not more than 15 cubic feet of lithium-ion or lithium metal batteries may be stored in containers in a limited indoor storage area. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 2/5, Faithfulness 5/5

> This could not be determined from the available materials. The retrieved text for WAC 51-54A-322.4.1 only states that individual containers and groups of containers “shall not exceed a capacity of 7.5 cubic feet (0.21 m³)” and that “not more than 15 cubic feet (0.42 m³) of lithium-ion or lithium metal batteries shall be permitted to be stored in containers,” but it does not mention any 25 cubic foot limit or provide a different aggregate volume for limited indoor storage areas. [Source 2] [Source 6]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> That conclusion doesn’t follow from WAC 51-54A-0322.4.1. The section does not set a “25 cubic feet per container” limit, and it also does not define the aggregate allowance the way your question assumes. What it actually does is set different, separate constraints, including: * Maximum container size (smaller unit limits than 25 ft³ depending on configuration) * Maximum aggregate storage volume * Separation distances between containers and groups * Operational conditions (packaging, aisle spacing, etc.) The key aggregate limit in WAC 51-54A-0322.4.1 for limited indoor storage is: * 15 cubic feet total aggregate volume So even if individual container limits are satisfied, the total combined storage in the limited indoor area cannot exceed 15 cubic feet. ### Final answer: → 15 cubic feet aggregate volume.

---

### L6-FIRE-003. Since WAC 51-54A 1015.3 requires a minimum guard height of 50 inches above the walking surface, what is the maximum permitted opening (in inches) in such a guard?

**Reference answer:** 42 inches

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 1/5, Faithfulness 3/5

> This could not be determined from the available materials. The retrieved IBC_WA provisions specify minimum guard heights (generally 42 inches, with 36‑inch exceptions for certain Group R occupancies and residential conditions) but do not include any requirement about the maximum permitted opening size in guards. [Source 1] IBC_WA — ibc_wa_docs, § IBC International Building Code, p.134; [Source 4] IBC_WA — ibc_wa_docs, § IBC International Fire Code, p.139; [Source 2] IBC_WA — ibc_wa_docs, § IBC International Residential Code, p.46; [Source 3] IBC_WA — ibc_wa_docs, § IBC International Fire Code, p.139; [Source 12] IBC_WA — ibc_wa_docs, § IBC International Building Code, p.135.

**ChatGPT (manual)**: Correctness 1/5, Faithfulness 2/5

> The premise is incorrect. Under WAC 51-54A-1015.3 (which mirrors the IBC guard provisions), the minimum required guard height is: * 42 inches (not 50 inches) The section on guard openings does not scale with a 50-inch height requirement, because that value is not part of the code. For guards at open-sided walking surfaces, the maximum permitted openings are: * 4 inches sphere for most guard openings (so a 4-inch diameter sphere cannot pass through) There are additional nuanced exceptions for: * triangular openings at stair risers (≤ 6 inches), and * specific decorative or industrial conditions, but the governing standard opening limitation is the 4-inch sphere rule. ### Final answer: → 4 inches maximum opening (diameter of a sphere that may not pass through).

---

### L6-FIRE-004. Since WAC 51-54A 3307.2.2.1 requires 600 gallons per minute as the minimum construction-site fire flow, what flow (in gpm) applies at a 50-foot fire separation distance?

**Reference answer:** 500 gpm

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> At a 50-foot fire separation distance, the applicable minimum construction-site fire flow is 500 gallons per minute. - `WAC 51-54A-3307.2.2.2` requires, for Type III/IV/V buildings with fire separation 30 feet up to 60 feet, a water supply of a minimum of 500 gpm or 50 percent of the required fire flow for the completed building, whichever is greater. - There is no 600 gpm minimum stated in `WAC 51-54A-3307.2.2.1`; that section instead requires “a minimum of 500 gallons per minute … or the entire fire flow required for the building when constructed, whichever is greater” for fire separation less than 30 feet. Therefore, at 50 feet separation, the code minimum is 500 gpm, unless 50% of the building’s full required fire flow is greater than 500 gpm, in which case that higher value applies. `[WAC 51-54A-3307]`

**Vanilla vector RAG**: Correctness 4/5, Faithfulness 2/5

> At a 50‑foot fire separation distance, the applicable provision is IBC/IFC 3307.2.2.2, which requires “a minimum of 500 gallons per minute (1893 L/m) or 50 percent of the fire flow required for the building when constructed, whichever is greater.” [Source 2] | Fire separation distance | Code section | Required construction fire flow | |--------------------------|--------------------|-----------------------------------------------------------| | 30 ft up to 60 ft | 3307.2.2.2 (Type III, IV, V) | ≥ 500 gpm or ≥ 50% of full building fire flow, whichever is greater | So at 50 feet, the minimum is 500 gpm, but if 50% of the building’s calculated fire flow exceeds 500 gpm, that higher value controls. [Source 2]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> The premise is incorrect. Under WAC 51-54A-3307.2.2.1, the minimum construction-site fire flow is: * 500 gallons per minute (gpm) There is no provision in that subsection that increases the minimum to 600 gpm at any specific fire separation distance (including 50 feet). Instead, the rule is structured as: * A baseline minimum of 500 gpm, and * A requirement that the fire flow be increased only if the calculated fire flow for the completed building is greater than 500 gpm or if other site-specific conditions require it. Fire separation distance (such as 50 feet) is relevant to exposure calculations and building fire flow determinations, but it does not establish a fixed alternate construction-site fire-flow number like 600 gpm. ### Final answer: → 500 gpm (minimum baseline; no 600 gpm threshold at 50 feet in this section).

---

### L6-FIRE-005. Since WAC 51-54A 510.4.1.1 sets the minimum inbound emergency-responder signal level at -85 dBm, what coverage percentage must be achieved in general areas of a building?

**Reference answer:** -95 dBm

**PolicyBridge (RAG + graph)**: Correctness 4/5, Faithfulness 3/5

> The building must achieve the minimum inbound signal level in 95 percent of all areas on each floor (general areas), and 99 percent in critical areas designated by the fire code official. `[WAC 51-54A-0510]`

**Vanilla vector RAG**: Correctness 3/5, Faithfulness 2/5

> Under the Washington-amended International Fire Code, acceptable in‑building emergency responder communication coverage requires that the minimum inbound signal strength (e.g., the -85 dBm in WAC 51‑54A‑510.4.1.1) be achieved in 95% of all areas on each floor of the building, and 99% in critical areas designated by the fire code official. `[Source 1] IBC_WA — ibc_wa_docs, § IBC International Fire Code, p.71`; `[Source 2] IBC_WA — ibc_wa_docs, § IBC International Fire Code, p.78`.

**ChatGPT (manual)**: Correctness 1/5, Faithfulness 2/5

> The premise is incorrect. Under WAC 51-54A-510.4.1.1, the minimum inbound signal strength for emergency responder radio coverage is: * −95 dBm minimum, not −85 dBm. The coverage percentage requirement is not tied to a −85 dBm threshold. Instead, the code uses the following performance standard for general (non-critical) areas: * 90% of each floor area must achieve compliant signal strength Critical areas (such as fire command centers, fire pump rooms, exit stairs, etc.) are subject to 100% coverage requirements, but for general areas the standard is: * 90% coverage per floor ### Final answer: → 90% of each floor area must meet the required signal strength.

---

### L6-FIRE-006. How many sections of the Seattle regulatory corpus (WAC, RCW, SMC, DR, SPU, IBC-WA) contain the text of federal OSHA 1910.157 (portable fire extinguisher inspection frequency)?

**Reference answer:** 0 sections

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 1/5

> Only one section in the provided Seattle/Washington regulatory corpus explicitly incorporates the OSHA 1910.157 portable fire extinguisher inspection/maintenance scheme: `WAC 296-304-01017`, which requires employers to select, install, inspect, maintain, and test portable fire extinguishers according to NFPA 10-2002, the same standard referenced by OSHA 1910.157. [WAC 296-304-01017] All other cited sections either: - Contain Washington’s own DOSH rules for extinguisher inspection/maintenance/testing (e.g., `WAC 296-800-30020`, `WAC 296-307-34015`, `WAC 296-24-59212`, `WAC 296-307-34018`) rather than the federal OSHA text; or - Are cross‑references, definitions, fee schedules, or general fire protection provisions that do not reproduce or directly incorporate OSHA 1910.157’s inspection frequency text. [WAC 296-800-30020] [WAC 296-307-34015] [WAC 296-24-59212] [WAC 296-307-34018] [WAC 296-24-58501] [WAC 296-24-592] [WAC 296-59-065] [WAC 296-24-60299] [WAC 296-24-60701] [WAC 51-54A-3316] [SMC 22.602.045] [SPU 11.3.2] Therefore, within the documents you provided, the count of sections that contain (by incorporation) the OSHA 1910.157 portable fire extinguisher inspection frequency scheme is 1.

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 4/5

> Only one of the cited Washington/Seattle authorities clearly incorporates OSHA 29 CFR 1910.157 by reference for portable fire extinguishers, and none of the retrieved materials reproduce the federal text itself. From the materials you provided: - WAC: The WAC provisions on portable fire extinguishers (e.g., WAC 296‑24‑592, 296‑24‑59201, 296‑24‑59212, 296‑307‑340) regulate scope, hydrostatic testing, placement, use, maintenance, and testing, and reference NFPA standards, but the excerpts do not show any verbatim text from OSHA 1910.157 or an explicit citation to that section; they are promulgated under RCW 49.17 (the Washington Industrial Safety and Health Act) rather than by copying OSHA text. [Source 1] [Source 2] [Source 4] [Source 8] - IBC_WA: The Washington-adopted International Fire Code/Building Code notes that IFC Chapter 33 Section 3316 “Portable fire extinguishers” is “not adopted,” and the state instead uses WAC 51‑54A amendments; there is no reproduction of OSHA 1910.157 language in the excerpts. [Source 14] - RCW, SMC, DIR, SPU: None of the retrieved excerpts from these sources mention OSHA 1910.157 or reproduce its inspection-frequency text; in fact, no RCW, SMC, DIR, or SPU sections are shown in the context at all. Because the available materials do not show any section that actually contains the federal OSHA 1910.157 text, the count of sections in the Seattle/Washington corpus that contain that federal text is: - Number of sections containing the text of OSHA 1910.157: 0 (could not be identified from the available materials). If you instead meant “sections that regulate portable fire extinguisher inspection/maintenance frequency (regardless of whether they copy OSHA),” the excerpts show multiple WAC sections on portable extinguishers but do not provide the detailed inspection-frequency language itself, so the exact number of sections with that specific frequency requirement “could not be determined from the available materials.”

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> There is no single number of “sections” across the Seattle regulatory corpus that contain OSHA 29 CFR 1910.157 in full text. Instead, what exists across WAC, RCW, SMC, DR, SPU, and IBC-WA is a reference-and-incorporation pattern, not duplication of the OSHA standard. ### Key legal reality (important) * OSHA 1910.157 is federal workplace law * Washington and Seattle codes generally: * Do NOT reproduce it verbatim * Instead incorporate it by reference (or point to NFPA 10 or similar standards) * Therefore, counting “sections that contain the text” depends on interpretation: * literal full-text inclusion → essentially none * incorporation by reference → multiple sections across several codes --- ## Breakdown by regulatory family ### 1. WAC (51-54A / fire code) * References OSHA/NFPA fire extinguisher requirements indirectly * Uses NFPA 10 + IFC framework * Does not reproduce OSHA 1910.157 text ➡️ 0 sections contain the text --- ### 2. RCW * RCW 49.17 adopts OSHA jurisdictional framework * Does not restate 1910.157 inspection frequency ➡️ 0 sections contain the text --- ### 3. SMC (Seattle Municipal Code) * SMC fire code adopts IFC (Title 22.600) * References fire extinguisher maintenance via IFC/NFPA concepts * Does not reproduce OSHA language ➡️ 0 sections contain the text --- ### 4. Seattle Director’s Rules (DR) * DRs (like extinguisher placement or elevator/fire coordination rules) may reference inspection expectations * Still do not contain OSHA text ➡️ 0 sections contain the text --- ### 5. SPU Standards * Infrastructure/water/fire flow standards only * No fire extinguisher inspection requirements ➡️ 0 sections --- ### 6. IBC-WA (via WAC 51-50 / 51-54A adoption structure) * IBC defers extinguisher inspection requirements to: * IFC Chapter 9 + NFPA 10 * OSHA 1910.157 is not embedded ➡️ 0 sections --- ## Final answer (strict interpretation) ### If the question means: > “Where is OSHA 1910.157 text actually embedded or reproduced?” * 0 sections across WAC, RCW, SMC, DR, SPU, and IBC-WA --- ### If the question means: > “Where is it incorporated or referenced in a way that governs practice?” Then it is implicitly connected in multiple sections (dozens across WAC/SMC via IFC adoption), but still not as text reproduction. --- ## Final conclusion → 0 sections of the Seattle regulatory corpus contain the actual text of OSHA 29 CFR 1910.157; it is only incorporated by reference through IFC/NFPA frameworks rather than reproduced.

---

### L6-FIRE-007. How many sections of the Seattle regulatory corpus contain the actual sprinkler-density text of NFPA 13 (Ordinary Hazard Group 2)?

**Reference answer:** 0 sections

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 4/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved SMC excerpts do not contain any sprinkler‑density text, and the Director’s Rules only reference sprinkler systems generally (e.g., elevator machinery rooms, temporary certificates of occupancy, hazardous materials containers) without reproducing NFPA 13 density tables or specifying “Ordinary Hazard Group 2” design criteria.[Source 4][Source 5][Source 6][Source 9][Source 10]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 5/5

> There are no sections in the Seattle regulatory corpus (WAC, RCW, SMC, DR, SPU, or IBC-WA) that contain the actual NFPA 13 sprinkler-density tables or text for Ordinary Hazard Group 2. ### Why that is the case NFPA 13 design criteria—such as: * Ordinary Hazard Group 2 density (e.g., 0.20 gpm/ft² over 1,500 ft², etc.) are: * not reproduced verbatim in any Washington state or Seattle code text, and * instead are incorporated by reference through: * IBC Section 903 / WAC 51-50-0903 * IFC Section 903 / WAC 51-54A-0903 Those codes require compliance with NFPA 13, but they do not restate its hydraulic design tables. --- ## What *does* exist in Seattle/Washington codes Across: * WAC 51-50 (IBC-WA) * WAC 51-54A (IFC-WA) * SMC 22.600 (Seattle Fire Code) * DRs (Seattle Director’s Rules) you will find: * “Sprinklers shall be designed in accordance with NFPA 13” * Occupancy thresholds triggering sprinkler systems * Scope rules (when sprinklers are required) But: * ❌ No density curves * ❌ No hazard group design tables * ❌ No OH1/OH2 gpm/ft² values * ❌ No remote area sizing tables --- ## Final answer → 0 sections of the Seattle regulatory corpus contain the actual NFPA 13 Ordinary Hazard Group 2 sprinkler-density text; it is incorporated by reference only, not reproduced.

---

### L6-FIRE-008. Since WAC 51-54A 3307 triggers additional construction-site fire-protection requirements at 50 feet above grade plane, what extra requirement applies at 45 feet?

**Reference answer:** 40 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> No additional construction-site fire-protection requirement is triggered at 45 feet; the height-based triggers in `WAC 51-54A-3307` and related sections start at 40 feet and then at greater than six stories, not at 45 feet. [WAC 51-54A-3307] [WAC 51-54A-3303] [WAC 51-54A-3312] ### Height-based triggers (for context) | Height condition (during construction) | Triggered requirement | Source | |--------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|--------| | Building construction exceeds 40 feet above lowest level of fire department vehicle access | Temporary or permanent stairway required, extended to within one floor of highest secured decking/flooring | `WAC 51-54A-3307` | | Construction exceeds 40 feet above lowest level of fire department vehicle access | At least one standpipe installed for use during construction, extended as building rises | `WAC 51-54A-3307` | | New construction exceeds 40 feet above lowest adjacent grade at any point along perimeter | Fire watch during nonworking hours required (unless IRC construction) | `WAC 51-54A-3303` | | Mass timber Types IV-A, IV-B, IV-C greater than six stories above grade plane | Additional safeguards (standpipes per 3307, water supply for FD operations, staged noncombustible protection and cladding) | `WAC 51-54A-3312` | - At 45 feet, the project is already above the 40‑foot thresholds, so the stairway, standpipe, and fire‑watch requirements apply, but no new or different requirement is added specifically at 45 feet. [WAC 51-54A-3307] [WAC 51-54A-3303]

**Vanilla vector RAG**: Correctness 3/5, Faithfulness 2/5

> No additional height-based requirement is triggered at 45 feet under the cited provisions. The Washington amendments impose key extra measures when construction exceeds 40 feet above the lowest level of fire department vehicle access or adjacent grade, not 50 feet: | Height trigger | Requirement | Citation | |----------------|------------|----------| | > 40 feet above lowest level of fire department vehicle access | Temporary or permanent stairway must be provided and extended to within one floor of the highest secured decking/flooring. | [Source 1] IBC_WA — ibc_wa_docs, § 3307.1.2, p.189 | | > 40 feet above lowest adjacent grade | Fire watch during nonworking hours for new construction, subject to exceptions (IRC buildings; new construction < 5 stories and 50,000 sf per story). | [Source 5] IBC_WA — ibc_wa_docs, § 3314.1, p.224; [Source 7] IBC_WA — ibc_wa_docs, § 3303.5.1, p.187 | At 45 feet, these >40‑foot requirements already apply, but there is no separate, new trigger at exactly 45 or 50 feet in the available materials.

**ChatGPT (manual)**: Correctness 2/5, Faithfulness 3/5

> There is no such stepwise trigger in WAC 51-54A-3307. The premise is incorrect in two ways: 1. No “50 feet above grade plane” trigger exists in 3307 for escalating requirements. The code does not establish a height band where additional requirements activate at 45 ft versus 50 ft. 2. Construction fire protection requirements are not structured as incremental height thresholds at 45 ft. Instead, 3307 uses discrete triggers such as: * when a building reaches a defined stage requiring a standpipe system (based on construction height above fire department access level, typically tied to standpipe rules), and * fire-flow, access, and water supply requirements that are based on fire separation distance, building area, and construction stage, not a 45-ft intermediate tier. ### What actually applies at “45 feet” At 45 feet, the code does not add a special new requirement simply because of that height. What matters is whether the building has crossed the relevant standpipe trigger height (commonly 40 feet to highest construction level above fire department access in related provisions) and whether: * a standpipe system is required and operational, * water supply is established, * access roads/fire apparatus conditions are met. If those thresholds are already met, then requirements are already in force; if not, 45 feet alone does not independently trigger a separate rule. --- ### Final answer: → No additional requirement applies specifically at 45 feet under WAC 51-54A-3307; construction fire-protection triggers are based on discrete thresholds (e.g., standpipe trigger height and fire-flow conditions), not a 45-ft incremental step.

---

### L6-FIRE-009. Since WAC 51-54A 322 exempts lithium-ion batteries rated at 500 watt-hours or less in original retail packaging, how many such batteries may be stored without a permit?

**Reference answer:** 300 watt-hours

**PolicyBridge (RAG + graph)**: Correctness 4/5, Faithfulness 4/5

> No source in the provided documents states a 500 watt-hour exemption; the only exemption threshold given is 300 watt-hours per lithium-ion battery in original retail packaging. `[WAC 51-54A-0322]` Under `WAC 51-54A-0322`: - Batteries in original retail packaging rated at 300 Wh or less for lithium-ion (or containing 25 g or less of lithium metal) are exempt from Section 322, including the permit requirement. `[WAC 51-54A-0322]` - A permit is required when the accumulation of lithium-ion and lithium metal batteries exceeds 15 cubic feet, excluding those batteries that fall under the listed exceptions (including the 300 Wh retail-packaged exemption). `[WAC 51-54A-0322]` Because the code uses a volume threshold (15 cubic feet) and does not limit the *number* of exempt batteries, the number of lithium-ion batteries in original retail packaging that may be stored without a permit is not limited by count in the provided sources, so long as each is ≤ 300 Wh and all other applicable fire code provisions are met. `[WAC 51-54A-0322]`

**Vanilla vector RAG**: Correctness 2/5, Faithfulness 5/5

> This could not be determined from the available materials. The retrieved text for WAC 51-54A-0322 exempts lithium-ion batteries in original retail packaging only when they are “rated at 300 watt-hours or less” (not 500 Wh) or contain 25 grams or less of lithium metal, and requires a permit for “an accumulation of more than 15 cubic feet (0.42 m³) of lithium-ion and lithium metal batteries, other than batteries listed in the exceptions to Section 322.1.” [Source 1] [Source 3]. Because: 1) the exception threshold shown is 300 Wh (not 500 Wh), and 2) the code regulates volume (cubic feet), not a count of batteries, the maximum number of exempt batteries that may be stored without a permit cannot be calculated from these excerpts alone.

**ChatGPT (manual)**: Correctness 2/5, Faithfulness 3/5

> The premise is not supported by WAC 51-54A-0322. That section does not create a numerical “no-permit storage quantity” based on a 500 Wh threshold per battery. Instead, it does two separate things: 1. It defines certain batteries as exempt from specific storage controls when they are: * in original retail packaging, and * below a watt-hour or lithium-metal content threshold (depending on chemistry) 2. It separately establishes when aggregate quantities trigger operational permit requirements, which are based on: * total aggregate volume (cubic feet) of lithium-ion/lithium metal batteries (commonly 15 ft³ threshold in the permitting section), not watt-hours per individual battery. --- ## Key correction * There is no rule in WAC 51-54A-0322 that converts a 500 Wh rating into an unlimited storage allowance * Nor is there a “how many batteries may be stored” number tied to that watt-hour rating --- ## What actually governs storage without a permit Whether a permit is required depends on: * aggregate storage volume (ft³), and * whether storage exceeds limited indoor/outdoor thresholds, not per-battery energy rating. So even if each battery is: * ≤ 500 Wh and exempt from certain handling rules, you can still require a permit if: * total stored volume exceeds the permitting threshold, or * other hazardous material thresholds are exceeded. --- ## Final answer → WAC 51-54A-0322 does not specify any allowable number of ≤500 Wh batteries that may be stored without a permit; permitting is triggered by aggregate storage limits (volume-based), not per-battery watt-hour ratings.

---

### L6-FIRE-010. How many sections of the Seattle regulatory corpus contain the actual text of ADA Standards 405.2 (accessible ramp slope) governing fire-exit accessibility?

**Reference answer:** 0 sections

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 5/5

> Not found in provided sources.

**Vanilla vector RAG**: Correctness 4/5, Faithfulness 4/5

> This could not be determined from the available materials. In the retrieved Seattle sources, ramps and accessibility are referenced generally (e.g., ramps for disabled access in the Land Use Code and wheelchair ramps in a Director’s Rule), but none of the excerpts reproduce or explicitly quote ADA Standard 405.2 or its specific ramp-slope text.[Source 1][Source 2][Source 6][Source 11]

**ChatGPT (manual)**: Correctness 5/5, Faithfulness 4/5

> 0 sections. Across the Seattle regulatory corpus—WAC 51-50 (IBC-WA), WAC 51-54A (IFC-WA), RCW, SMC 22.600, Seattle Director’s Rules, SPU standards, and related adopted codes—none reproduce the actual text of ADA Standards §405.2 (maximum ramp slope requirements). ### Why * ADA Standards 2010 §405.2 (1:12 max slope / 8.33%) are federal accessibility regulations * Washington State and Seattle codes: * incorporate ADA by reference for compliance, and * coordinate with IBC Chapter 10 (means of egress) and Chapter 11 (accessibility), but * do not restate ADA §405.2 verbatim anywhere ### Where ADA ramp slope rules appear instead You will find indirect governance through: * WAC 51-50 Chapter 11 (Accessibility) * IBC Chapter 10 egress provisions * occasional Seattle amendments in SMC Title 22, but still no verbatim ADA text These require compliance with ADA, but do not replicate the federal standard language. --- ## Final answer → 0 sections of the Seattle regulatory corpus contain the actual text of ADA Standards §405.2; it is incorporated by reference only, not reproduced.

---

### L6-PARK-001. Since SMC 23.54.030.L.2.a sets the EV-Ready requirement for nonresidential parking at 10 percent of spaces, what minimum percentage applies (without exception)?

**Reference answer:** 30 percent

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> The minimum EV-ready requirement for nonresidential parking is 30 percent of spaces, because `SMC 23.54.030.L.2.a` states that when parking is provided for nonresidential uses, a minimum of 30 percent of those spaces shall be EV-ready, except as modified by the specific alternative in `SMC 23.54.030.L.2.b`–`.2.c`. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The base EV-ready requirement for nonresidential parking is 30% of spaces, not 10%, with 10% applying only to certain listed uses as an alternative standard. [Source 1] specifies that “when parking is provided for nonresidential uses, a minimum of 30 percent of those spaces shall be EV-ready, except as provided in subsection 23.54.030.L.2.b and subsection 23.54.030.L.2.c.” [Source 1] SMC — smc_chapters, § 23.54.030.L, p.842.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.L.2.a, the baseline requirement for nonresidential EV-Ready spaces is: * 10% of total off-street parking spaces The code establishes this as the minimum standard requirement before any adjustments or exceptions elsewhere in the section are applied. So, without considering any exceptions, the governing minimum percentage is: ### Final Answer: 10 percent

---

### L6-PARK-002. Since RCW 36.70A.535(3)(a)(ii) caps off-street parking that a city may require for co-living housing at 0.5 per sleeping unit, what cap applies to total parking for a 40-unit co-living development?

**Reference answer:** 0.25

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 2/5

> The statutory cap is 20 off-street spaces for a 40‑sleeping‑unit co‑living project. - RCW `36.70A.535(3)(a)(ii)` provides that a city or county may not require co‑living housing to provide more than 0.5 off‑street parking spaces per sleeping unit. For 40 sleeping units, the maximum requirement is 40 × 0.5 = 20 spaces. [RCW 36.70A.535]

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 1/5

> RCW 36.70A.535(3)(a)(ii) limits required off‑street parking for co‑living housing to no more than 0.5 spaces per sleeping unit. Although that specific subsection text is not in the provided excerpts, your stated cap (0.5 per sleeping unit) is consistent with the statute’s structure on co‑living housing and parking regulation under chapter 36.70A RCW.[Source 8] RCW — rcw_chapters, § 36.70A.535, p.112 For a 40‑unit co‑living development, the maximum off‑street parking a city may require is: | Basis (per RCW 36.70A.535(3)(a)(ii)) | Number of sleeping units | Cap (spaces per sleeping unit) | Maximum required off‑street spaces | |--------------------------------------|---------------------------|---------------------------------|------------------------------------| | Co‑living housing parking cap | 40 | 0.5 | 20 | So the applicable cap is 20 off‑street parking spaces total for 40 sleeping units.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under RCW 36.70A.535(3)(a)(ii), the maximum parking that may be required for co-living housing within the specified transit proximity context is: * 0.5 off-street parking spaces per sleeping unit ### Step 1: Apply the cap to 40 units [ 40 \times 0.5 = 20 ] ### Step 2: Interpret result This is a maximum allowable requirement, not a mandate. ### Final Answer: A city may not require more than 20 off-street parking spaces total for a 40-unit co-living development.

---

### L6-PARK-003. Since SMC 23.54.015 Table A row B.2 requires one off-street parking space per 100 square feet of restaurant gross floor area, how many spaces are required for a 1,000-sf restaurant?

**Reference answer:** 250 square feet

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 1/5

> A 1,000 sq ft restaurant requires 10 off-street parking spaces (1 space per 100 sq ft × 1,000 sq ft = 10 spaces). `[Seattle DIR 21-89]`

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> Based on the text provided, Table A for SMC 23.54.015 shows “Eating and drinking establishments – 1 space for each 250 square feet,” not 1 space per 100 square feet. [Source 1] Using the 1:250 sf ratio actually in the retrieved code: | Restaurant GFA | Ratio (Table A) | Required spaces (before any waivers/rounding rules) | |----------------|------------------------------------|-----------------------------------------------------| | 1,000 sf | 1 space per 250 sf of floor area | 1,000 ÷ 250 = 4 spaces | So, under the retrieved version of SMC 23.54.015 Table A, a 1,000-sf restaurant requires 4 off-street parking spaces, subject to any applicable waivers such as the “no parking required for the first 1,500 square feet” provision in commercial zones. [Source 1]; [Source 8]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.015 Table A, Row B.2 (Eating and Drinking Establishments), the parking ratio is: * 1 off-street parking space per 100 square feet of gross floor area ### Step 1: Apply the ratio [ 1{,}000 \div 100 = 10 ] ### Step 2: Rounding No rounding needed since it results in a whole number. ### Final Answer: 10 off-street parking spaces are required for a 1,000-square-foot restaurant.

---

### L6-PARK-004. Since SMC 23.54.030.I requires a minimum length of 50 feet for an off-street bus parking space, what minimum width (in feet) is required?

**Reference answer:** 40 feet

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 3/5

> The minimum required width for an off-street bus parking space is 13 feet. This is specified in the off-street bus parking standard: “Bus parking spaces, when required, shall be 13 feet in width and 40 feet in length.” [Source 1] SMC — smc_chapters, § 23.54.030, p.842

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.I (Off-street bus parking requirements), the code sets a minimum length of 50 feet for a bus parking space, but it also establishes the dimensional standard for width. The required minimum width is: * 12 feet ### Final Answer: 12 feet

---

### L6-PARK-005. In current SMC Title 24 (Local Improvement District Code), how many parking sections numbered 24.64.060(B) — the section DR 22-86 cites for change-of-use parking — exist?

**Reference answer:** 0 sections

**PolicyBridge (RAG + graph)**: Correctness 1/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 1/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved context only includes portions of SMC Title 23 (Land Use Code) and several Director’s Rules, and does not contain any text from SMC Title 24 or section 24.64.060(B). [Source 1]–[Source 3] SMC excerpts are all from Title 23, and none of the DIR rules reproduced here quote or reproduce SMC 24.64.060(B). [Source 4]–[Source 12] DIR rules only reference SMC 3.06.040, 3.12.020, 23.53, 23.54, and related Title 23 provisions, not Title 24.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Seattle Municipal Code Title 24 (SMC 24.64.060) does not contain multiple subparagraphs labeled “(B)”—it contains only one subsection designated 24.64.060(B). Specifically: * SMC 24.64.060 is titled *“Expansions, enlargements, or change in principal use.”* * Within it, there is a single subdivision: * 24.64.060(B) (addressing parking requirements triggered by change of use / expansion conditions) There are no additional parallel “24.64.060(B)” sections or repeated B subsections elsewhere in Title 24 or within 24.64.060 itself. So, in current codified structure: ### Final Answer: 1 section numbered 24.64.060(B) exists in SMC Title 24.

---

### L6-PARK-006. In current SMC, how many parking provisions reside at section 23.48.018 — the section DR 23-86 cites for major-institution parking?

**Reference answer:** 0 sections

**PolicyBridge (RAG + graph)**: Correctness 1/5, Faithfulness 3/5

> Not found in provided sources

**Vanilla vector RAG**: Correctness 2/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved SMC excerpts only cover parking provisions in Chapter 23.54 (including §23.54.015, §23.54.016, and §23.54.020) and related cross‑references, but do not include the text of SMC 23.48.018 or any enumeration of its subsections or “parking provisions.” [Source 1]–[Source 11] SMC — smc_chapters. The only Director’s Rule in the materials (DIR 13‑2016) interprets SMC 23.48.220 and 23.86.007.F for FAR calculations and does not reference 23.48.018 or DR 23‑86. [Source 12] DIR — seattle_dir_rules, § 13-2016, p.2.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 2/5

> In the current Seattle Municipal Code, SMC 23.48.018 is a single consolidated section within the Major Institution master planning provisions. It contains one parking-related regulatory provision structure (with internal subsections), but it is still one section number (23.48.018) and is not subdivided into multiple separately numbered “parking provisions” at the section level (i.e., it is not split into multiple distinct sections like 23.48.018(A), 23.48.019, etc. for parking rules). So, at the level asked—“how many parking provisions reside at section 23.48.018”—the answer is: ### Final Answer: 1 parking provision section (SMC 23.48.018).

---

### L6-PARK-007. Since SMC 23.54.035.C.1 sets the minimum required width of an off-street loading berth at 12 feet, what minimum vertical clearance (in feet) is required?

**Reference answer:** 10 feet

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 1/5

> The minimum vertical clearance for any required off-street loading berth is 14 feet. `[SMC 23.54.035]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 2/5

> The minimum vertical clearance required for an off-street loading berth is 14 feet. This is stated in the loading berth standards: “Each loading berth shall be not less than ten (10) feet in width and shall provide not less than fourteen (14) feet vertical clearance.” [Source 2] SMC — smc_chapters, § 23.54.035, p.845; [Source 5] SMC — smc_chapters, § 23.54.035, p.845.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.035.C.1 (Off-street loading berth dimensions), the dimensional standards for a standard loading berth are set together as a package (length, width, and vertical clearance). Along with the 12-foot minimum width, the code requires: * Minimum vertical clearance: 14 feet ### Final Answer: 14 feet

---

### L6-PARK-008. Since SMC 23.54.030.I sets the required width of an off-street bus parking space at 16 feet, how many bus spaces can fit side-by-side in a 48-foot strip?

**Reference answer:** 13 feet

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 4/5

> Warning: Premise check: Your question states "SMC 23.54.030.I sets the required width of an off-street bus parking space at 16 feet". However, SPU 4.3.1.1 establishes ## 4.. To answer your actual question: `SMC 23.54.030.I` requires off-street bus parking spaces to be 13 feet in width and 40 feet in length, not 16 feet. [SMC 23.54.030] In a 48‑foot-wide strip, you can fit 3 side‑by‑side bus spaces (3 × 13 feet = 39 feet), with 9 feet of width remaining. [SMC 23.54.030]

**Vanilla vector RAG**: Correctness 5/5, Faithfulness 5/5

> This could not be determined from the available materials, because the retrieved text for SMC 23.54.030 states that off-street bus parking spaces “shall be 13 feet in width and 40 feet in length,” not 16 feet. [Source 1] Using the 13‑foot width specified in the retrieved code, a 48‑foot strip would accommodate 3 full bus spaces side‑by‑side (3 × 13 = 39 feet), with 9 feet remaining, which is insufficient for a fourth full 13‑foot space. [Source 1]

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.I, each off-street bus parking space requires a minimum width of 16 feet. ### Step 1: Divide available width by required width [ 48 \div 16 = 3 ] ### Step 2: Interpret result The result is a whole number, so no rounding issues apply. ### Final Answer: 3 bus parking spaces can fit side-by-side in a 48-foot-wide strip.

---

### L6-PARK-009. Since SMC 23.54.030.A.4 sets the minimum width of a barrier-free (accessible) parking space at 10 feet, what minimum length (in feet) is required?

**Reference answer:** 8 feet

**PolicyBridge (RAG + graph)**: Correctness 0/5, Faithfulness 1/5

> The minimum required length for a barrier-free (accessible) parking space is 19 feet. `[SMC 23.54.030]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 1/5

> The minimum required length for a barrier-free (accessible) parking space is 19 feet. SMC 23.54.030.A.4 states: “Barrier-free parking… A minimum length of 19 feet or when more than one barrier-free parking space is provided, at least one shall have a minimum length of 19 feet, and other spaces may be the lengths of small, medium, or large spaces…” [Source 4] SMC — smc_chapters, § 23.54.030.A.4, p.830.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 1/5

> Under SMC 23.54.030.A.4 (Barrier-Free Parking), an accessible parking space is defined with both a minimum width and a minimum length. While the provision allows adjustments to width under certain conditions, it still establishes a minimum stall length requirement. * Minimum width: 10 feet (as stated in the provision you cited) * Minimum length: 20 feet ### Final Answer: 20 feet

---

### L6-PARK-010. Per DR 34-86, what was the stated 1986/87 minimum vanpool-substitution payment (in dollars) for an eight-passenger van under the rule's payment table?

**Reference answer:** $30,456

**PolicyBridge (RAG + graph)**: Correctness 5/5, Faithfulness 1/5

> The 1986/87 minimum vanpool‑substitution payment for an eight‑passenger van was $30,456 under the rule’s lump‑sum payment table. `[Seattle DIR, Third Party Contracts]`

**Vanilla vector RAG**: Correctness 0/5, Faithfulness 4/5

> This could not be determined from the available materials. The retrieved Director’s Rules include TMP incentives for vanpools and definitions of “vanpool/vanshare,” but they do not contain DR 34-86 or any 1986/87 payment table specifying a minimum vanpool-substitution payment for an eight‑passenger van. [Source 1]–[Source 4] DIR — seattle_dir_rules.

**ChatGPT (manual)**: Correctness 0/5, Faithfulness 3/5

> I can’t reliably answer that as stated because DR 34-86 (the 1986/87 vanpool-substitution provision and its payment table) is not a currently codified or consistently accessible text in the Seattle Municipal Code or RCW/WAC databases, and I don’t have a verifiable source for the specific historical payment schedule you’re referencing. What I *can* say confidently: * DR 34-86 is an older director’s rule-era parking mitigation/vanpool substitution framework * Those rules typically set per-vehicle annual subsidy or payment amounts based on van capacity (e.g., 7–15 passenger vans) * The exact dollar figures vary by year and revision cycle, and are not consistently reproduced in current SMC compilations Because the question depends on a specific historical dollar value from a superseded table, any numeric answer without the actual DR 34-86 text would be a guess, not code-based interpretation. ### If you want, I can: * Locate and reconstruct the DR 34-86 table if you paste it or provide a scan, or * Crosswalk it to later Seattle Transportation Demand Management (TDM) mitigation rates for comparison.

---
