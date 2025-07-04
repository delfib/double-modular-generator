# Double Modular Generator Model

This repository contains the model of a **Double Modular Generator System**, inspired by a simplified version of the **Triple Modular Generator with xSAP** architecture described in the paper **Model-based Safety Assessment of a Triple Modular Generator with xSAP**.

## Overview

This model represents a power distribution system composed of:

- **2 Generators** (`G1`, `G2`)
- **3 Circuit Breakers** (`GB1`, `GB2`, `BB1`)
- **2 Buses** (`B1`, `B2`)
---

## Modules
### Generator
- States: `on`, `off`
- Controlled by a `cmd` input.
- Can be forced off by a fault variable `fev_off`.

### Switch (Circuit Breaker)
- States: `open`, `closed`
- Reacts to control commands and can experience **stuck-at faults**:
  - `mode_is_stuckAt_open`
  - `mode_is_stuckAt_closed`

### Bus
- States: `working`, `broken`
- A bus breaks if it receives power from more than one source simultaneously.

### SystemConfiguration
- Instantiates generators, circuit breakers, and buses.
- Initializes system components.

### Controller
- Issues commands to Generators (always `on`) and Circuit Breakers (may open/close nondeterministically).