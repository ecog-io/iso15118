# SPDX-License-Identifier: Apache-2.0
# Copyright 2020 - 2023 Pionix GmbH and Contributors to EVerest
from dataclasses import dataclass, field

DEFAULT_DC_MAX_CURRENT_LIMIT_A = 300
DEFAULT_DC_MAX_POWER_LIMIT_W = 150000
DEFAULT_DC_MAX_VOLTAGE_LIMIT_V = 900
DEFAULT_ENERGY_CAPACITY_WH = 60000
DEFAULT_TARGET_CURRENT_A = 5
DEFAULT_TARGET_VOLTAGE_V = 200

@dataclass
class EVState:
    # Common
    PaymentOption: str = ''
    EnergyTransferMode: str = ''
    StopCharging = False
    Pause = False

    # DC
    dc_max_current_limit: float = DEFAULT_DC_MAX_CURRENT_LIMIT_A
    dc_max_power_limit: float = DEFAULT_DC_MAX_POWER_LIMIT_W
    dc_max_voltage_limit: float = DEFAULT_DC_MAX_VOLTAGE_LIMIT_V
    dc_energy_capacity: float = DEFAULT_ENERGY_CAPACITY_WH
    dc_target_current: float = DEFAULT_TARGET_CURRENT_A
    dc_target_voltage: float = DEFAULT_TARGET_VOLTAGE_V

    # DC BPT
    dc_discharge_max_current_limit: float = 0
    dc_discharge_max_power_limit: float = 0
    dc_discharge_target_current: float = 0

    # Service HPC1
    ServiceHPC1_Active: bool = False

    # SAE J2847/2
    SAEJ2847_V2H_V2G_Active = False
    minimal_soc = 20

    def reset(self):
        self.StopCharging = False
        self.Pause = False