from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

from iso15118.secc.controller.common import Limits, UnknownEnergyService
from iso15118.shared.messages.din_spec.body import (
    CurrentDemandReq as DIN_CurrentDemandReq,
)
from iso15118.shared.messages.din_spec.body import (
    DCEVChargeParameter as DIN_DCEVChargeParameter,
)
from iso15118.shared.messages.din_spec.body import PreChargeReq as DIN_PreChargeReq
from iso15118.shared.messages.enums import (
    AuthEnum,
    ControlMode,
    EnergyTransferModeEnum,
    ServiceV20,
)
from iso15118.shared.messages.iso15118_2.body import (
    ACEVChargeParameter,
    CurrentDemandReq,
    DCEVChargeParameter,
    PreChargeReq,
)
from iso15118.shared.messages.iso15118_2.datatypes import ChargeService
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeLoopReq,
    ACChargeParameterDiscoveryReq,
    ACChargeParameterDiscoveryReqParams,
    BPTACChargeParameterDiscoveryReqParams,
    BPTDynamicACChargeLoopReqParams,
    BPTScheduledACChargeLoopReqParams,
    DynamicACChargeLoopReqParams,
    ScheduledACChargeLoopReqParams,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    DynamicScheduleExchangeReqParams,
    ScheduledScheduleExchangeReqParams,
    ScheduleExchangeReq,
    SelectedEnergyService,
)
from iso15118.shared.messages.iso15118_20.common_types import DisplayParameters
from iso15118.shared.messages.iso15118_20.dc import (
    BPTDCChargeParameterDiscoveryReqParams,
    BPTDynamicDCChargeLoopReqParams,
    BPTScheduledDCChargeLoopReqParams,
    DCChargeLoopReq,
    DCChargeParameterDiscoveryReq,
    DCChargeParameterDiscoveryReqParams,
    DCPreChargeReq,
    DynamicDCChargeLoopReqParams,
    ScheduledDCChargeLoopReqParams,
)


@dataclass
class EVACCPDLimits(Limits):
    """Holds the AC limits shared by the EV during ChargeParameterDiscovery"""

    # used in -2
    max_charge_current: Optional[float] = None
    min_charge_current: Optional[float] = None
    max_voltage: Optional[float] = None

    max_charge_power: Optional[float] = 0.0
    max_charge_power_l2: Optional[float] = None
    max_charge_power_l3: Optional[float] = None

    min_charge_power: Optional[float] = 0.0
    min_charge_power_l2: Optional[float] = None
    min_charge_power_l3: Optional[float] = None

    max_discharge_power: Optional[float] = None
    max_discharge_power_l2: Optional[float] = None
    max_discharge_power_l3: Optional[float] = None
    min_discharge_power: Optional[float] = None
    min_discharge_power_l2: Optional[float] = None
    min_discharge_power_l3: Optional[float] = None


@dataclass
class EVDCCPDLimits(Limits):
    """Holds the DC limits shared by the EV during ChargeParameterDiscovery"""

    max_charge_power: Optional[float] = 0.0
    min_charge_power: Optional[float] = 0.0
    max_charge_current: Optional[float] = None
    min_charge_current: Optional[float] = None
    max_voltage: Optional[float] = None
    min_voltage: Optional[float] = None

    max_discharge_power: Optional[float] = None
    min_discharge_power: Optional[float] = None
    max_discharge_current: Optional[float] = None
    min_discharge_current: Optional[float] = None


@dataclass
class EVACCLLimits(Limits):
    """Holds the AC limits shared by the EV during ChargingLoop.
    Unlike the CPD values, these could potentially change during charing loop"""

    max_charge_power: Optional[float] = None
    max_charge_power_l2: Optional[float] = None
    max_charge_power_l3: Optional[float] = None

    min_charge_power: Optional[float] = None
    min_charge_power_l2: Optional[float] = None
    min_charge_power_l3: Optional[float] = None

    max_discharge_power: Optional[float] = None
    max_discharge_power_l2: Optional[float] = None
    max_discharge_power_l3: Optional[float] = None

    min_discharge_power: Optional[float] = None
    min_discharge_power_l2: Optional[float] = None
    min_discharge_power_l3: Optional[float] = None


@dataclass
class EVDCCLLimits(Limits):
    """Holds the DC Power, Current and Voltage limits
    shared by the EV during ChargingLoop.
    Unlike the CPD values, these could potentially
    change during charging loop"""

    max_charge_power: Optional[float] = None
    min_charge_power: Optional[float] = None
    max_charge_current: Optional[float] = None
    max_voltage: Optional[float] = None
    min_voltage: Optional[float] = None

    max_discharge_power: Optional[float] = None
    min_discharge_power: Optional[float] = None
    max_discharge_current: Optional[float] = None


@dataclass
class EVRatedLimits(Limits):
    def __init__(
        self,
        ac_limits: Optional[EVACCPDLimits] = EVACCPDLimits(),
        dc_limits: Optional[EVDCCPDLimits] = EVDCCPDLimits(),
    ):
        self.ac_limits = ac_limits
        self.dc_limits = dc_limits


@dataclass
class EVSessionLimits(Limits):
    def __init__(
        self,
        ac_limits: Optional[EVACCLLimits] = EVACCLLimits(),
        dc_limits: Optional[EVDCCLLimits] = EVDCCLLimits(),
    ):
        self.ac_limits = ac_limits
        self.dc_limits = dc_limits


class CurrentType(str, Enum):
    AC = "AC"
    DC = "DC"


@dataclass
class EVDataContext:
    def __init__(
        self,
        evcc_id: Optional[str] = None,
        rated_limits: Optional[EVRatedLimits] = EVRatedLimits(),
        session_limits: Optional[EVSessionLimits] = EVSessionLimits(),
        departure_time: Optional[int] = None,
        target_energy_request: Optional[float] = None,
        target_soc: Optional[int] = None,
        total_battery_capacity: Optional[float] = None,
        max_energy_request: Optional[float] = None,
        min_energy_request: Optional[float] = None,
        min_soc: Optional[int] = None,
        max_soc: Optional[int] = None,
        max_v2x_energy_request: Optional[float] = None,
        min_v2x_energy_request: Optional[float] = None,
        remaining_time_to_target_soc: Optional[float] = None,
        remaining_time_to_max_soc: Optional[float] = None,
        remaining_time_to_min_soc: Optional[float] = None,
        bulk_soc: Optional[float] = None,
        remaining_time_to_bulk_soc: Optional[float] = None,
        present_soc: Optional[int] = None,
        present_voltage: Optional[float] = None,
        present_active_power: Optional[float] = None,
        present_active_power_l2: Optional[float] = None,
        present_active_power_l3: Optional[float] = None,
        present_reactive_power: Optional[float] = None,
        present_reactive_power_l2: Optional[float] = None,
        present_reactive_power_l3: Optional[float] = None,
        target_current: float = 0.0,
        target_voltage: float = 0.0,
    ):
        self.evcc_id = evcc_id
        self.rated_limits = rated_limits
        self.session_limits = session_limits

        self.current_type: Optional[CurrentType] = None

        # Target request is only set in Schedule mode during
        # Schedule exchange in -20 and in -2 AC CPD (EAmount)
        # and optionaly in -2 DC CPD (EVEnergyRequest)

        # EV driver Emobility Needs
        self.departure_time: Optional[int] = departure_time
        self.target_energy_request: Optional[float] = target_energy_request
        self.target_soc: Optional[int] = target_soc  # 0-100

        # EV Battery Energy/SOC and V2X Limits
        self.total_battery_capacity: Optional[float] = total_battery_capacity
        self.max_energy_request: Optional[float] = max_energy_request
        self.min_energy_request: Optional[float] = min_energy_request
        self.min_soc: Optional[int] = min_soc  # 0-100
        self.max_soc: Optional[int] = max_soc  # 0-100
        self.max_v2x_energy_request: Optional[float] = max_v2x_energy_request
        self.min_v2x_energy_request: Optional[float] = min_v2x_energy_request
        self.remaining_time_to_target_soc: Optional[float] = (
            remaining_time_to_target_soc  # noqa: E501
        )
        # In -2 is FullSOC
        self.remaining_time_to_max_soc: Optional[float] = remaining_time_to_max_soc
        self.remaining_time_to_min_soc: Optional[float] = remaining_time_to_min_soc
        # -20 does not have equivalent for this.
        # This is the time to achieve 80% SoC
        self.bulk_soc: Optional[float] = bulk_soc
        self.remaining_time_to_bulk_soc: Optional[float] = remaining_time_to_bulk_soc

        # EV Meter data
        self.present_soc: Optional[int] = present_soc  # 0-100
        # Sent in -20 PreChargeReq and DC ChargeLoopReq
        self.present_voltage: Optional[float] = present_voltage
        # Only used in AC
        self.present_active_power: Optional[float] = present_active_power
        self.present_active_power_l2: Optional[float] = present_active_power_l2
        self.present_active_power_l3: Optional[float] = present_active_power_l3
        self.present_reactive_power: Optional[float] = present_reactive_power
        self.present_reactive_power_l2: Optional[float] = present_reactive_power_l2
        self.present_reactive_power_l3: Optional[float] = present_reactive_power_l3

        # Target EV request
        # DC Scheduled ChargeLoopReq and
        # -2 CurrentDemand
        self.target_current: float = target_current
        # Sent in -2,-20 PreChargeReq
        # and same as above
        self.target_voltage: float = target_voltage
        # The energy mode the EVCC selected.
        self.selected_energy_mode: Optional[EnergyTransferModeEnum] = None

    def update_ac_charge_parameters_v2(
        self, ac_ev_charge_parameter: ACEVChargeParameter
    ) -> None:
        """Update the EV data context with the ACEVChargeParameter parameters"""
        self.departure_time = ac_ev_charge_parameter.departure_time
        ac_rated_limits = self.rated_limits.ac_limits = EVACCPDLimits()
        self.session_limits.ac_limits = EVACCLLimits()
        self.target_energy_request = (
            ac_ev_charge_parameter.e_amount.get_decimal_value()
        )  # noqa: E501
        ac_rated_limits.max_voltage = (
            ac_ev_charge_parameter.ev_max_voltage.get_decimal_value()
        )  # noqa: E501
        ac_rated_limits.max_charge_current = (
            ac_ev_charge_parameter.ev_max_current.get_decimal_value()
        )  # noqa: E501
        ac_rated_limits.min_charge_current = (
            ac_ev_charge_parameter.ev_min_current.get_decimal_value()
        )  # noqa: E501

        # Create the session limits based on the rated limits
        self.session_limits.ac_limits.update(ac_rated_limits.as_dict())

    def update_dc_charge_parameters(
        self,
        dc_ev_charge_parameter: Union[DCEVChargeParameter, DIN_DCEVChargeParameter],
    ) -> None:
        """Update the EV data context with the DCEVChargeParameter parameters"""
        if type(dc_ev_charge_parameter) is DCEVChargeParameter:
            self.departure_time = dc_ev_charge_parameter.departure_time
        self.present_soc = dc_ev_charge_parameter.dc_ev_status.ev_ress_soc
        self.target_energy_request = (  # noqa: E501
            None
            if dc_ev_charge_parameter.ev_energy_request is None
            else dc_ev_charge_parameter.ev_energy_request.get_decimal_value()
        )

        dc_rated_limits = self.rated_limits.dc_limits = EVDCCPDLimits()
        self.session_limits.dc_limits = EVDCCLLimits()
        dc_rated_limits.max_voltage = (
            dc_ev_charge_parameter.ev_maximum_voltage_limit.get_decimal_value()
        )

        dc_rated_limits.max_charge_current = (
            dc_ev_charge_parameter.ev_maximum_current_limit.get_decimal_value()
        )

        dc_rated_limits.max_charge_power = (  # noqa: E501
            None
            if dc_ev_charge_parameter.ev_maximum_power_limit is None
            else dc_ev_charge_parameter.ev_maximum_power_limit.get_decimal_value()
        )

        self.total_battery_capacity = (  # noqa: E501
            None
            if dc_ev_charge_parameter.ev_energy_capacity is None
            else dc_ev_charge_parameter.ev_energy_capacity.get_decimal_value()
        )

        self.max_soc = (  # noqa: E501
            None
            if dc_ev_charge_parameter.full_soc is None
            else dc_ev_charge_parameter.full_soc
        )
        self.bulk_soc = (  # noqa: E501
            None
            if dc_ev_charge_parameter.bulk_soc is None
            else dc_ev_charge_parameter.bulk_soc
        )

        # Create the session limits based on the rated limits
        self.session_limits.dc_limits.update(dc_rated_limits.as_dict())

    def update_pre_charge_parameters(
        self, pre_charge_req: Union[PreChargeReq, DIN_PreChargeReq]
    ) -> None:
        """Update the EV data context with the PreChargeReq parameters"""
        self.present_soc = pre_charge_req.dc_ev_status.ev_ress_soc
        self.target_current = pre_charge_req.ev_target_current.get_decimal_value()
        self.target_voltage = pre_charge_req.ev_target_voltage.get_decimal_value()

    def update_charge_loop_parameters(
        self,
        current_demand_req: Union[CurrentDemandReq, DIN_CurrentDemandReq],
    ) -> None:
        """Update the EV data context with the CurrentDemandReq parameters"""
        self.present_soc = current_demand_req.dc_ev_status.ev_ress_soc
        self.target_current = current_demand_req.ev_target_current.get_decimal_value()
        self.target_voltage = current_demand_req.ev_target_voltage.get_decimal_value()
        if current_demand_req.remaining_time_to_full_soc is not None:
            self.remaining_time_to_max_soc = (
                current_demand_req.remaining_time_to_full_soc.get_decimal_value()
            )

        if current_demand_req.remaining_time_to_bulk_soc is not None:
            self.remaining_time_to_bulk_soc = (
                current_demand_req.remaining_time_to_bulk_soc.get_decimal_value()
            )

        if current_demand_req.ev_max_current_limit is not None:
            self.session_limits.dc_limits.max_charge_current = (
                current_demand_req.ev_max_current_limit.get_decimal_value()
            )

        if current_demand_req.ev_max_power_limit is not None:
            self.session_limits.dc_limits.max_charge_power = (
                current_demand_req.ev_max_power_limit.get_decimal_value()
            )

        if current_demand_req.ev_max_voltage_limit is not None:
            self.session_limits.dc_limits.max_voltage = (
                current_demand_req.ev_max_voltage_limit.get_decimal_value()
            )

    def update_schedule_exchange_parameters(
        self, control_mode: ControlMode, schedule_exchange_req: ScheduleExchangeReq
    ):
        """Update the EV data context with the ScheduleExchangeReq parameters"""
        if control_mode == ControlMode.SCHEDULED:
            self._update_common_se_params(schedule_exchange_req.scheduled_params)
        if control_mode == ControlMode.DYNAMIC:
            self._update_common_se_params(schedule_exchange_req.dynamic_params)
            if schedule_exchange_req.dynamic_params.target_soc:
                self.target_soc = schedule_exchange_req.dynamic_params.target_soc
            if schedule_exchange_req.dynamic_params.min_soc:
                self.min_soc = schedule_exchange_req.dynamic_params.min_soc
            if schedule_exchange_req.dynamic_params.ev_max_v2x_energy_request:
                self.max_v2x_energy_request = (
                    schedule_exchange_req.dynamic_params.ev_max_v2x_energy_request.get_decimal_value()  # noqa: E501
                )
            if schedule_exchange_req.dynamic_params.ev_min_v2x_energy_request:
                self.min_v2x_energy_request = (
                    schedule_exchange_req.dynamic_params.ev_min_v2x_energy_request.get_decimal_value()  # noqa: E501
                )

    def _update_common_se_params(
        self,
        params: Union[
            ScheduledScheduleExchangeReqParams, DynamicScheduleExchangeReqParams
        ],
    ):
        """Update the EV data context with the common ScheduleExchangeReq parameters"""
        if params.departure_time:
            self.departure_time = params.departure_time
        if params.ev_target_energy_request:
            self.target_energy_request = (
                params.ev_target_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_energy_request:
            self.max_energy_request = (
                params.ev_max_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_energy_request:
            self.min_energy_request = (
                params.ev_min_energy_request.get_decimal_value()
            )  # noqa: E501

    def update_ac_charge_parameters_v20(
        self,
        energy_service: ServiceV20,
        charge_parameter: ACChargeParameterDiscoveryReq,
    ) -> None:
        """Update the EV data context with the
        ACChargeParameterDiscoveryReq parameters"""
        ac_rated_limits = self.rated_limits.ac_limits = EVACCPDLimits()
        self.session_limits.ac_limits = EVACCLLimits()
        params: Union[
            ACChargeParameterDiscoveryReqParams, BPTACChargeParameterDiscoveryReqParams
        ] = None
        if energy_service == ServiceV20.AC:
            params = charge_parameter.ac_params
            self._update_common_ac_charge_parameters_v20(ac_rated_limits, params)
        elif energy_service == ServiceV20.AC_BPT:
            params = charge_parameter.bpt_ac_params
            self._update_acbpt_charge_parameters_v20(ac_rated_limits, params)
        else:
            raise UnknownEnergyService(f"Unknown Service {energy_service}")
        # Create the session limits based on the rated limits
        self.session_limits.ac_limits.update(ac_rated_limits.as_dict())

    def _update_common_ac_charge_parameters_v20(
        self,
        ac_rated_limits: EVACCPDLimits,
        params: Union[
            ACChargeParameterDiscoveryReqParams, BPTACChargeParameterDiscoveryReqParams
        ],
    ) -> None:
        """Update the EV data context with the common
        DCChargeParameterDiscoveryReq parameters"""
        ac_rated_limits.max_charge_power = (
            params.ev_max_charge_power.get_decimal_value()
        )  # noqa: E501
        if params.ev_max_charge_power_l2:
            ac_rated_limits.max_charge_power_l2 = (
                params.ev_max_charge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_charge_power_l3:
            ac_rated_limits.max_charge_power_l3 = (
                params.ev_max_charge_power_l3.get_decimal_value()
            )  # noqa: E501
        ac_rated_limits.min_charge_power = (
            params.ev_min_charge_power.get_decimal_value()
        )  # noqa: E501
        if params.ev_min_charge_power_l2:
            ac_rated_limits.min_charge_power_l2 = (
                params.ev_min_charge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_charge_power_l3:
            ac_rated_limits.min_charge_power_l3 = (
                params.ev_min_charge_power_l3.get_decimal_value()
            )  # noqa: E501

    def _update_acbpt_charge_parameters_v20(
        self,
        ac_rated_limits: EVACCPDLimits,
        params: BPTACChargeParameterDiscoveryReqParams,
    ) -> None:
        """Update the EV data context with the
        BPTDCChargeParameterDiscoveryReq parameters"""
        self._update_common_ac_charge_parameters_v20(ac_rated_limits, params)
        ac_rated_limits.max_discharge_power = (
            params.ev_max_discharge_power.get_decimal_value()
        )  # noqa: E501
        if params.ev_max_discharge_power_l2:
            ac_rated_limits.max_discharge_power_l2 = (
                params.ev_max_discharge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_discharge_power_l3:
            ac_rated_limits.max_discharge_power_l3 = (
                params.ev_max_discharge_power_l3.get_decimal_value()
            )  # noqa: E501
        ac_rated_limits.min_discharge_power = (
            params.ev_min_discharge_power.get_decimal_value()
        )  # noqa: E501
        if params.ev_min_discharge_power_l2:
            ac_rated_limits.min_discharge_power_l2 = (
                params.ev_min_discharge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_discharge_power_l3:
            ac_rated_limits.min_discharge_power_l3 = (
                params.ev_min_discharge_power_l3.get_decimal_value()
            )  # noqa: E501

    def update_ac_charge_loop_v20(
        self,
        ac_charge_loop_req: ACChargeLoopReq,
        energy_service: ServiceV20,
        control_mode: ControlMode,
    ) -> None:
        """Update the EV data context with the ACChargeLoopReq parameters"""
        ac_limits = self.session_limits.ac_limits
        if energy_service == ServiceV20.AC:
            if control_mode == ControlMode.SCHEDULED:
                self._update_common_ac_limits(
                    ac_limits, ac_charge_loop_req.scheduled_params
                )
            elif control_mode == ControlMode.DYNAMIC:
                params = ac_charge_loop_req.dynamic_params
                # Departure time only in Dynamic
                if params.departure_time:
                    self.departure_time = params.departure_time
                self._update_common_ac_limits(ac_limits, params)
        elif energy_service == ServiceV20.AC_BPT:
            if control_mode == ControlMode.SCHEDULED:
                self._update_common_acbpt_limits(
                    ac_limits, ac_charge_loop_req.bpt_scheduled_params
                )
            elif control_mode == ControlMode.DYNAMIC:
                params = ac_charge_loop_req.bpt_dynamic_params
                # Departure time only in Dynamic
                if params.departure_time:
                    self.departure_time = params.departure_time
                # V2X Limits only in Dynamic BPT
                if params.ev_max_v2x_energy_request:
                    self.max_v2x_energy_request = (
                        params.ev_max_v2x_energy_request.get_decimal_value()
                    )  # noqa: E501
                if params.ev_min_v2x_energy_request:
                    self.min_v2x_energy_request = (
                        params.ev_min_v2x_energy_request.get_decimal_value()
                    )  # noqa: E501

                self._update_common_acbpt_limits(ac_limits, params)
        else:
            raise UnknownEnergyService(f"Unknown Service {energy_service}")

    def _update_common_ac_limits(
        self,
        ac_limits: EVACCLLimits,
        params: Union[
            ScheduledACChargeLoopReqParams,
            DynamicACChargeLoopReqParams,
            BPTScheduledACChargeLoopReqParams,
            BPTDynamicACChargeLoopReqParams,
        ],
    ):
        """Update the EV data context with the common ACChargeLoopReq parameters"""
        if params.ev_target_energy_request:
            self.target_energy_request = (
                params.ev_target_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_energy_request:
            self.max_energy_request = (
                params.ev_max_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_energy_request:
            self.min_energy_request = (
                params.ev_min_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_charge_power:
            ac_limits.max_charge_power = (
                params.ev_max_charge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_charge_power_l2:
            ac_limits.max_charge_power_l2 = (
                params.ev_max_charge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_charge_power_l3:
            ac_limits.max_charge_power_l3 = (
                params.ev_max_charge_power_l3.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_charge_power:
            ac_limits.min_charge_power = (
                params.ev_min_charge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_charge_power_l2:
            ac_limits.min_charge_power_l2 = (
                params.ev_min_charge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_charge_power_l3:
            ac_limits.min_charge_power_l3 = (
                params.ev_min_charge_power_l3.get_decimal_value()
            )  # noqa: E501
        if params.ev_target_energy_request:
            self.target_energy_request = (
                params.ev_target_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_energy_request:
            self.max_energy_request = (
                params.ev_max_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_energy_request:
            self.min_energy_request = (
                params.ev_min_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_present_active_power:
            self.present_active_power = (
                params.ev_present_active_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_present_active_power_l2:
            self.present_active_power_l2 = (
                params.ev_present_active_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_present_active_power_l3:
            self.present_active_power_l3 = (
                params.ev_present_active_power_l3.get_decimal_value()
            )  # noqa: E501
        if params.ev_present_reactive_power:
            self.present_reactive_power = (
                params.ev_present_reactive_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_present_reactive_power_l2:
            self.present_reactive_power_l2 = (
                params.ev_present_reactive_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_present_reactive_power_l3:
            self.present_reactive_power_l3 = (
                params.ev_present_reactive_power_l3.get_decimal_value()
            )  # noqa: E501

    def _update_common_acbpt_limits(
        self,
        ac_limits: EVACCLLimits,
        params: Union[
            BPTScheduledACChargeLoopReqParams, BPTDynamicACChargeLoopReqParams
        ],
    ):
        """Update the EV data context with the common ACChargeLoopReq BPT parameters"""
        self._update_common_ac_limits(ac_limits, params)
        if params.ev_max_discharge_power:
            ac_limits.max_discharge_power = (
                params.ev_max_discharge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_discharge_power_l2:
            ac_limits.max_discharge_power_l2 = (
                params.ev_max_discharge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_discharge_power_l3:
            ac_limits.max_discharge_power_l3 = (
                params.ev_max_discharge_power_l3.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_discharge_power:
            ac_limits.min_discharge_power = (
                params.ev_min_discharge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_discharge_power_l2:
            ac_limits.min_discharge_power_l2 = (
                params.ev_min_discharge_power_l2.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_discharge_power_l3:
            ac_limits.min_discharge_power_l3 = (
                params.ev_min_discharge_power_l3.get_decimal_value()
            )  # noqa: E501

    def update_dc_charge_parameters_v20(
        self,
        energy_service: ServiceV20,
        charge_parameter: DCChargeParameterDiscoveryReq,
    ) -> None:
        """Update the EV data context with the
        DCChargeParameterDiscoveryReq parameters"""
        dc_rated_limits = self.rated_limits.dc_limits = EVDCCPDLimits()
        self.session_limits.dc_limits = EVDCCLLimits()
        params: Union[
            DCChargeParameterDiscoveryReqParams, BPTDCChargeParameterDiscoveryReqParams
        ] = None
        if energy_service == ServiceV20.DC:
            params = charge_parameter.dc_params
            self._update_common_dc_charge_parameters_v20(dc_rated_limits, params)
        elif energy_service == ServiceV20.DC_BPT:
            params = charge_parameter.bpt_dc_params
            self._update_dcbpt_charge_parameters_v20(dc_rated_limits, params)
        else:
            raise UnknownEnergyService(f"Unknown Service {energy_service}")
        # Create the session limits based on the rated limits
        self.session_limits.dc_limits.update(dc_rated_limits.as_dict())

    def _update_common_dc_charge_parameters_v20(
        self,
        dc_rated_limits: EVDCCPDLimits,
        params: Union[
            DCChargeParameterDiscoveryReqParams, BPTDCChargeParameterDiscoveryReqParams
        ],
    ) -> None:
        """Update the EV data context with the common
        DCChargeParameterDiscoveryReq parameters"""
        dc_rated_limits.max_charge_power = (
            params.ev_max_charge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_charge_power = (
            params.ev_min_charge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.max_charge_current = (
            params.ev_max_charge_current.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_charge_current = (
            params.ev_min_charge_current.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.max_voltage = (
            params.ev_max_voltage.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_voltage = (
            params.ev_min_voltage.get_decimal_value()
        )  # noqa: E501
        if params.target_soc:
            self.target_soc = params.target_soc

    def _update_dcbpt_charge_parameters_v20(
        self,
        dc_rated_limits: EVDCCPDLimits,
        params: BPTDCChargeParameterDiscoveryReqParams,
    ) -> None:
        """Update the EV data context with the
        BPTDCChargeParameterDiscoveryReq parameters"""
        self._update_common_dc_charge_parameters_v20(dc_rated_limits, params)
        dc_rated_limits.max_discharge_power = (
            params.ev_max_discharge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_discharge_power = (
            params.ev_min_discharge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.max_discharge_current = (
            params.ev_max_discharge_current.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_discharge_current = (
            params.ev_min_discharge_current.get_decimal_value()
        )  # noqa: E501

    def update_pre_charge_parameters_v20(self, pre_charge_req: DCPreChargeReq) -> None:
        """Update the EV data context with the DCPreChargeReq parameters"""
        self.present_voltage = pre_charge_req.ev_present_voltage.get_decimal_value()
        self.target_voltage = pre_charge_req.ev_target_voltage.get_decimal_value()

    def update_dc_charge_loop_parameters_v20(
        self,
        dc_charge_loop_req: DCChargeLoopReq,
        energy_service: SelectedEnergyService,
        control_mode: ControlMode,
    ) -> None:
        """Update the EV data context with the DCChargeLoopReq parameters"""
        params: Union[
            ScheduledDCChargeLoopReqParams,
            DynamicDCChargeLoopReqParams,
            BPTScheduledDCChargeLoopReqParams,
            BPTDynamicDCChargeLoopReqParams,
        ] = None
        self.present_voltage = (
            dc_charge_loop_req.ev_present_voltage.get_decimal_value()
        )  # noqa: E501

        if dc_charge_loop_req.display_parameters:
            self._update_display_parameters(dc_charge_loop_req.display_parameters)

        dc_limits = self.session_limits.dc_limits
        if energy_service.service == ServiceV20.DC:
            if control_mode == ControlMode.SCHEDULED:
                params = dc_charge_loop_req.scheduled_params
                # Target Current and Voltage only in Scheduled
                self.target_current = params.ev_target_current.get_decimal_value()
                self.target_voltage = params.ev_target_voltage.get_decimal_value()
                self._update_common_dc_limits(dc_limits, params)
            elif control_mode == ControlMode.DYNAMIC:
                params = dc_charge_loop_req.dynamic_params
                # Departure time only in Dynamic
                if params.departure_time:
                    self.departure_time = params.departure_time
                self._update_common_dc_limits(dc_limits, params)
        elif energy_service.service == ServiceV20.DC_BPT:
            if control_mode == ControlMode.SCHEDULED:
                params = dc_charge_loop_req.bpt_scheduled_params
                # Target Current and Voltage only in Scheduled
                self.target_current = params.ev_target_current.get_decimal_value()
                self.target_voltage = params.ev_target_voltage.get_decimal_value()
                self._update_common_dc_bpt_limits(dc_limits, params)
            elif control_mode == ControlMode.DYNAMIC:
                params = dc_charge_loop_req.bpt_dynamic_params
                # Departure time only in Dynamic
                if params.departure_time:
                    self.departure_time = params.departure_time
                # V2X Limits only in Dynamic BPT
                if params.ev_max_v2x_energy_request:
                    self.max_v2x_energy_request = (
                        params.ev_max_v2x_energy_request.get_decimal_value()
                    )  # noqa: E501
                if params.ev_min_v2x_energy_request:
                    self.min_v2x_energy_request = (
                        params.ev_min_v2x_energy_request.get_decimal_value()
                    )  # noqa: E501
                self._update_common_dc_bpt_limits(dc_limits, params)
        else:
            raise UnknownEnergyService("Unknown Service" f"{energy_service.service}")

    def _update_common_dc_limits(
        self,
        dc_limits: EVDCCLLimits,
        params: Union[
            ScheduledDCChargeLoopReqParams,
            DynamicDCChargeLoopReqParams,
            BPTScheduledDCChargeLoopReqParams,
            BPTDynamicDCChargeLoopReqParams,
        ],
    ):
        """Update the EV data context with the common DCChargeLoopReq parameters"""
        if params.ev_max_charge_power:
            dc_limits.max_charge_power = (
                params.ev_max_charge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_charge_power:
            dc_limits.min_charge_power = (
                params.ev_min_charge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_charge_current:
            dc_limits.max_charge_current = (
                params.ev_max_charge_current.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_voltage:
            dc_limits.max_voltage = (
                params.ev_max_voltage.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_voltage:
            dc_limits.min_voltage = (
                params.ev_min_voltage.get_decimal_value()
            )  # noqa: E501

        if params.ev_target_energy_request:
            self.target_energy_request = (
                params.ev_target_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_energy_request:
            self.max_energy_request = (
                params.ev_max_energy_request.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_energy_request:
            self.min_energy_request = (
                params.ev_min_energy_request.get_decimal_value()
            )  # noqa: E501

    def _update_common_dc_bpt_limits(
        self,
        dc_limits: EVDCCLLimits,
        params: Union[
            BPTScheduledDCChargeLoopReqParams, BPTDynamicDCChargeLoopReqParams
        ],
    ):
        """Update the EV data context with the common DCChargeLoopReq BPT parameters"""
        self._update_common_dc_limits(dc_limits, params)
        if params.ev_max_discharge_power:
            dc_limits.max_discharge_power = (
                params.ev_max_discharge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_min_discharge_power:
            dc_limits.min_discharge_power = (
                params.ev_min_discharge_power.get_decimal_value()
            )  # noqa: E501
        if params.ev_max_discharge_current:
            dc_limits.max_discharge_current = (
                params.ev_max_discharge_current.get_decimal_value()
            )  # noqa: E501

    def _update_display_parameters(self, params: DisplayParameters):
        """Update the EV data context with the DisplayParameters parameters"""
        if params.present_soc:
            self.present_soc = params.present_soc
        if params.target_soc:
            self.target_soc = params.target_soc
        if params.min_soc:
            self.min_soc = params.min_soc
        if params.max_soc:
            self.max_soc = params.max_soc
        if params.remaining_time_to_max_soc:
            self.remaining_time_to_max_soc = params.remaining_time_to_max_soc
        if params.remaining_time_to_min_soc:
            self.remaining_time_to_min_soc = params.remaining_time_to_min_soc
        if params.remaining_time_to_target_soc:
            self.remaining_time_to_target_soc = params.remaining_time_to_target_soc
        if params.battery_energy_capacity:
            self.total_battery_capacity = (
                params.battery_energy_capacity.get_decimal_value()
            )  # noqa: E501


@dataclass
class EVSessionContext15118:
    # EVSessionContext15118 holds information required to resume a paused session.
    # [V2G2-741] - In a resumed session, the following are reused:
    # 1. SessionID (SessionSetup)
    # 2. PaymentOption that was previously selected (ServiceDiscoveryRes)
    # 3. ChargeService (ServiceDiscoveryRes)
    # 4. SAScheduleTuple (ChargeParameterDiscoveryRes) -
    # Previously selected id must remain the same.
    # However, the entries could reflect the elapsed time
    session_id: Optional[str] = None
    auth_options: Optional[List[AuthEnum]] = None
    charge_service: Optional[ChargeService] = None
    sa_schedule_tuple_id: Optional[int] = None
