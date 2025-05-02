import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from iso15118.secc.controller.common import Limits, UnknownEnergyService
from iso15118.shared.messages.enums import (
    ControlMode,
    ServiceV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import ScheduleExchangeRes
from iso15118.shared.messages.iso15118_20.dc import (
    BPTDCChargeParameterDiscoveryResParams,
    DCChargeParameterDiscoveryRes,
    DCChargeParameterDiscoveryResParams,
)

logger = logging.getLogger(__name__)


@dataclass
class EVSEACCPDLimits(Limits):
    """Holds the EVSE's rated AC limits to be returned during
    Charge Parameter Discovery state."""

    max_current: Optional[float] = None  # Required

    # 15118-20 AC CPD (Required)
    max_charge_power: Optional[float] = None
    min_charge_power: Optional[float] = None

    # 15118-20 AC CPD (Optional)
    max_charge_power_l2: Optional[float] = None
    max_charge_power_l3: Optional[float] = None
    min_charge_power_l2: Optional[float] = None
    min_charge_power_l3: Optional[float] = None

    max_discharge_power: Optional[float] = None  # Required
    max_discharge_power_l2: Optional[float] = None  # Optional
    max_discharge_power_l3: Optional[float] = None  # Optional

    min_discharge_power: Optional[float] = None  # Required
    min_discharge_power_l2: Optional[float] = None  # Optional
    min_discharge_power_l3: Optional[float] = None  # Optional

    def update_from_dict(self, values: dict) -> None:
        for key, value in values.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)


@dataclass
class EVSEDCCPDLimits(Limits):
    """Holds the EVSE's rated DC limits to be returned during
    Charge Parameter Discovery state."""

    # Required in 15118-20 DC CPD
    max_charge_power: Optional[float] = None  # Required for -2 DC, DIN CPD
    min_charge_power: Optional[float] = None  # Not Required for -2 DC, DIN CPD
    max_charge_current: Optional[float] = None  # Required for -2 DC, DIN CPD
    min_charge_current: Optional[float] = None  # Required for -2 DC, DIN CPD
    max_voltage: Optional[float] = None  # Required for -2 DC, DIN CPD
    min_voltage: Optional[float] = None  # Required for -2 DC, DIN CPD

    # Required in 15118-20 DC BPT CPD
    max_discharge_power: Optional[float] = None
    min_discharge_power: Optional[float] = None
    max_discharge_current: Optional[float] = None
    min_discharge_current: Optional[float] = None

    def update_from_dict(self, values: dict) -> None:
        for key, value in values.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)


@dataclass
class EVSEACCLLimits(Limits):
    # Optional in both Scheduled and Dynamic CL (both AC CL and BPT AC CL)
    # ISO 15118-20 defines Targets instead of maximums, but
    # in order to keep consistency with other data structures,
    # we will use maximums here. Besides, in -20 the targets can be positive
    # (charging) or negative (discharging), which is a different command
    # structure than the one used in DC where we have charge and discharge.

    max_charge_power: Optional[float] = None
    max_charge_power_l2: Optional[float] = None
    max_charge_power_l3: Optional[float] = None
    max_charge_reactive_power: Optional[float] = None
    max_charge_reactive_power_l2: Optional[float] = None
    max_charge_reactive_power_l3: Optional[float] = None

    # BPT attributes
    max_discharge_power: Optional[float] = None
    max_discharge_power_l2: Optional[float] = None
    max_discharge_power_l3: Optional[float] = None
    max_discharge_reactive_power: Optional[float] = None
    max_discharge_reactive_power_l2: Optional[float] = None
    max_discharge_reactive_power_l3: Optional[float] = None

    def update_from_dict(self, values: dict) -> None:
        for key, value in values.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)


@dataclass
class EVSEDCCLLimits(Limits):
    # Optional in 15118-20 DC Scheduled CL
    max_charge_power: Optional[float] = None  # Required in 15118-20 Dynamic CL
    min_charge_power: Optional[float] = None  # Required in 15118-20 Dynamic CL
    max_charge_current: Optional[float] = None  # Required in 15118-20 Dynamic CL
    max_voltage: Optional[float] = None  # Required in 15118-20 Dynamic CL
    min_voltage: Optional[float] = None  # Required in 15118-20 Dynamic BPT CL
    # Optional and present in 15118-20 DC BPT CL (Scheduled)
    max_discharge_power: Optional[float] = None  # Req in 15118-20 Dynamic BPT CL
    min_discharge_power: Optional[float] = None  # Req in 15118-20 Dynamic BPT CL
    max_discharge_current: Optional[float] = None  # Req in 15118-20 Dynamic BPT CL

    def update_from_dict(self, values: dict) -> None:
        for key, value in values.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)


@dataclass
class EVSERatedLimits(Limits):
    def __init__(
        self,
        ac_limits: Optional[EVSEACCPDLimits] = EVSEACCPDLimits(),
        dc_limits: Optional[EVSEDCCPDLimits] = EVSEDCCPDLimits(),
    ):
        self.ac_limits = ac_limits
        self.dc_limits = dc_limits


@dataclass
class EVSESessionLimits(Limits):
    def __init__(
        self,
        ac_limits: Optional[EVSEACCLLimits] = EVSEACCLLimits(),
        dc_limits: Optional[EVSEDCCLLimits] = EVSEDCCLLimits(),
    ):
        self.ac_limits = ac_limits
        self.dc_limits = dc_limits


class CurrentType(str, Enum):
    AC = "AC"
    DC = "DC"


@dataclass
class EVSEDataContext:
    def __init__(
        self,
        rated_limits: EVSERatedLimits = EVSERatedLimits(),
        session_limits: EVSESessionLimits = EVSESessionLimits(),
        departure_time: Optional[int] = None,
        target_soc: Optional[int] = None,
        min_soc: Optional[int] = None,
        ack_max_delay: Optional[int] = None,
        power_ramp_limit: Optional[float] = None,
        nominal_voltage: Optional[float] = None,
        nominal_frequency: Optional[float] = None,
        max_power_asymmetry: Optional[float] = None,
        current_regulation_tolerance: Optional[float] = None,
        peak_current_ripple: Optional[float] = None,
        energy_to_be_delivered: Optional[float] = None,
        present_active_power: Optional[float] = 0,
        present_active_power_l2: Optional[float] = 0,
        present_active_power_l3: Optional[float] = 0,
        present_current: Union[float, int] = 0,
        present_voltage: Union[float, int] = 0,
    ):
        self.rated_limits = rated_limits
        self.session_limits = session_limits

        self.current_type: Optional[CurrentType] = None

        # Emobility Needs
        self.departure_time: Optional[int] = departure_time
        self.target_soc: Optional[int] = target_soc  # 0-100
        self.min_soc: Optional[int] = min_soc  # 0-100
        self.ack_max_delay: Optional[int] = ack_max_delay

        #  Optional in 15118-20 DC and AC CPD
        self.power_ramp_limit: Optional[float] = power_ramp_limit
        # Only used in -20 and -2 AC CPD
        self.nominal_voltage: Optional[float] = nominal_voltage
        self.nominal_frequency: Optional[float] = nominal_frequency
        self.max_power_asymmetry: Optional[float] = max_power_asymmetry

        #  Optional in 15118-2 CPD
        self.current_regulation_tolerance: Optional[float] = (
            current_regulation_tolerance
        )
        self.peak_current_ripple: Optional[float] = peak_current_ripple
        self.energy_to_be_delivered: Optional[float] = energy_to_be_delivered
        # Metering
        self.present_active_power: Optional[float] = (
            present_active_power  # Optional in AC Scheduled CL
        )
        self.present_active_power_l2: Optional[float] = (
            present_active_power_l2  # Optional in AC Scheduled CL
        )
        self.present_active_power_l3: Optional[float] = (
            present_active_power_l3  # Optional in AC Scheduled CL
        )

        # Required for -2 DC CurrentDemand, -20 DC CL
        self.present_current: Union[float, int] = present_current
        self.present_voltage: Union[float, int] = present_voltage

    # Note that there are no methods to update the session limits as
    # those are updated by the interaction
    # with an external interface like a smart charging application, that
    # gets access to the session limits
    # and updates them accordingly. The limits are then naturally
    # passed to the EV/EVSE during the Charging Loop.
    def update_schedule_exchange_parameters(
        self, control_mode: ControlMode, schedule_exchange_res: ScheduleExchangeRes
    ):
        """Update the EVSE data context with the ScheduleExchangeReq parameters"""
        if control_mode == ControlMode.DYNAMIC:
            se_params = schedule_exchange_res.dynamic_params
            if se_params.departure_time:
                self.departure_time = se_params.departure_time
            if se_params.target_soc:
                self.target_soc = se_params.target_soc
            if se_params.min_soc:
                self.min_soc = se_params.min_soc

    def update_dc_charge_parameters_v20(
        self,
        energy_service: ServiceV20,
        charge_parameter: DCChargeParameterDiscoveryRes,
    ) -> None:
        """Update the EVSE data context with the
        DCChargeParameterDiscoveryRes parameters"""
        logger.debug(
            "Updating EVSE Data Context (Rated and Session Limits) with "
            "ChargeParameterDiscoveryResponse"
        )
        logger.debug(f"Active Rated Limits {self.rated_limits.dc_limits}")
        logger.debug(f"Active Session Limits {self.session_limits.dc_limits}")
        self.current_type = CurrentType.DC
        dc_rated_limits = self.rated_limits.dc_limits = EVSEDCCPDLimits()
        self.session_limits = EVSESessionLimits()
        self.session_limits.dc_limits = EVSEDCCLLimits()
        params: Union[
            DCChargeParameterDiscoveryResParams, BPTDCChargeParameterDiscoveryResParams
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
        logger.debug(
            "Rated and Session Limits updated after " "ChargeParametersDiscovery"
        )
        logger.debug(f"New Rated Limits {self.rated_limits.dc_limits}")
        logger.debug(f"New Session Limits {self.session_limits.dc_limits}")

    def _update_common_dc_charge_parameters_v20(
        self,
        dc_rated_limits: EVSEDCCPDLimits,
        params: Union[
            DCChargeParameterDiscoveryResParams, BPTDCChargeParameterDiscoveryResParams
        ],
    ) -> None:
        """Update the EVSE data context with the common
        DCChargeParameterDiscoveryRes parameters"""
        dc_rated_limits.max_charge_power = (
            params.evse_max_charge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_charge_power = (
            params.evse_min_charge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.max_charge_current = (
            params.evse_max_charge_current.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_charge_current = (
            params.evse_min_charge_current.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.max_voltage = (
            params.evse_max_voltage.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_voltage = (
            params.evse_min_voltage.get_decimal_value()
        )  # noqa: E501
        if params.evse_power_ramp_limit:
            self.power_ramp_limit = (
                params.evse_power_ramp_limit.get_decimal_value()
            )  # noqa: E501

    def _update_dcbpt_charge_parameters_v20(
        self,
        dc_rated_limits: EVSEDCCPDLimits,
        params: BPTDCChargeParameterDiscoveryResParams,
    ) -> None:
        """Update the EVSE data context with the
        BPTDCChargeParameterDiscoveryRes parameters"""
        self._update_common_dc_charge_parameters_v20(dc_rated_limits, params)
        dc_rated_limits.max_discharge_power = (
            params.evse_max_discharge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_discharge_power = (
            params.evse_min_discharge_power.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.max_discharge_current = (
            params.evse_max_discharge_current.get_decimal_value()
        )  # noqa: E501
        dc_rated_limits.min_discharge_current = (
            params.evse_min_discharge_current.get_decimal_value()
        )  # noqa: E501
