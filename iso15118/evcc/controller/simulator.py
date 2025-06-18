"""
This module contains a dummy implementation of the abstract class for an EVCC to
retrieve data from the EV. The DummyEVController overrides all abstract methods from
EVControllerInterface.
"""
from iso15118.evcc.everest import context as EVEREST_CONTEXT, float2Value_Multiplier
import logging
import random
from typing import List, Optional, Tuple, Union
import os
from pathlib import Path

from cryptography.x509 import load_der_x509_certificate, ExtensionOID
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    PrivateFormat,
)

from iso15118.evcc import EVCCConfig
from iso15118.evcc.controller.interface import ChargeParamsV2, EVControllerInterface
from iso15118.shared.exceptions import (
    InvalidProtocolError,
    MACAddressNotFound,
    CertChainLengthError,
)
from iso15118.shared.messages.datatypes import (
    DCEVChargeParams,
    PVEAmount,
    PVEVEnergyCapacity,
    PVEVEnergyRequest,
    PVEVMaxCurrent,
    PVEVMaxCurrentLimit,
    PVEVMaxPowerLimit,
    PVEVMaxVoltage,
    PVEVMaxVoltageLimit,
    PVEVMinCurrent,
    PVEVSEPresentVoltage,
    PVEVTargetCurrent,
    PVEVTargetVoltage,
    PVPMax,
    PVRemainingTimeToBulkSOC,
    PVRemainingTimeToFullSOC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    DCEVPowerDeliveryParameter as DCEVPowerDeliveryParameterDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import DCEVStatus as DCEVStatusDINSPEC
from iso15118.shared.messages.din_spec.datatypes import (
    ProfileEntryDetails as ProfileEntryDetailsDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    SAScheduleTupleEntry as SAScheduleTupleEntryDINSPEC,
)
from iso15118.shared.messages.enums import (
    ControlMode,
    DCEVErrorCode,
    EnergyTransferModeEnum,
    Namespace,
    PriceAlgorithm,
    Protocol,
    ServiceV20,
    UnitSymbol,
)
from iso15118.shared.messages.iso15118_2.datatypes import ACEVChargeParameter
from iso15118.shared.messages.iso15118_2.datatypes import (
    ChargeProgress as ChargeProgressV2,
)
from iso15118.shared.messages.iso15118_2.datatypes import (
    ChargingProfile,
    DCEVChargeParameter,
    DCEVPowerDeliveryParameter,
    DCEVStatus,
    ProfileEntryDetails,
    SAScheduleTuple,
    CertificateChain,
)
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeParameterDiscoveryReqParams,
    BPTACChargeParameterDiscoveryReqParams,
    BPTDynamicACChargeLoopReqParams,
    BPTScheduledACChargeLoopReqParams,
    DynamicACChargeLoopReqParams,
    ScheduledACChargeLoopReqParams,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ChargeProgress as ChargeProgressV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    DynamicEVPowerProfile,
    DynamicScheduleExchangeReqParams,
    DynamicScheduleExchangeResParams,
    EMAIDList,
    EVAbsolutePriceSchedule,
    EVEnergyOffer,
    EVPowerProfile,
    EVPowerSchedule,
    EVPowerScheduleEntry,
    EVPowerScheduleEntryList,
    EVPriceRule,
    EVPriceRuleStack,
    EVPriceRuleStackList,
    MatchedService,
    PowerToleranceAcceptance,
    ScheduledEVPowerProfile,
    ScheduledScheduleExchangeReqParams,
    ScheduledScheduleExchangeResParams,
    SelectedEnergyService,
    SelectedVAS,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    DisplayParameters,
    RationalNumber,
)
from iso15118.shared.messages.iso15118_20.dc import (
    BPTDCChargeParameterDiscoveryReqParams,
    BPTDynamicDCChargeLoopReqParams,
    BPTScheduledDCChargeLoopReqParams,
    DCChargeParameterDiscoveryReqParams,
    DynamicDCChargeLoopReqParams,
    ScheduledDCChargeLoopReqParams,
)
from iso15118.shared.network import get_nic_mac_address

from iso15118.shared.security import (
    CertPath,
    KeyEncoding,
    KeyPasswordPath,
    KeyPath,
    to_ec_priv_key,
)

from iso15118.shared.settings import get_PKI_PATH

logger = logging.getLogger(__name__)

EVEREST_EV_STATE = EVEREST_CONTEXT.ev_state


class SimEVController(EVControllerInterface):
    """
    A simulated version of an EV controller
    """

    def __init__(self, evcc_config: EVCCConfig):
        self.config = evcc_config
        self.charging_loop_cycles: int = max(evcc_config.charge_loop_cycle, 1)
        self.increment = (1 / self.charging_loop_cycles) * 100
        self.precharge_loop_cycles: int = 0
        self.welding_detection_cycles: int = 0
        self._charging_is_completed = False
        self._soc = 10
        max_current_limit_value, max_current_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_current_limit)
        max_power_limit_value, max_power_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_power_limit)
        max_voltage_limit_value, max_voltage_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_voltage_limit)
        energy_capacity_value, energy_capacity_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_energy_capacity)
        target_current_value, target_current_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_target_current)
        target_voltage_value, target_voltage_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_target_voltage)

        self.dc_ev_charge_params: DCEVChargeParams = DCEVChargeParams(
            dc_max_current_limit=PVEVMaxCurrentLimit(
                multiplier=max_current_limit_multiplier, value=max_current_limit_value, unit=UnitSymbol.AMPERE
            ),
            dc_max_power_limit=PVEVMaxPowerLimit(
                multiplier=max_power_limit_multiplier, value=max_power_limit_value, unit=UnitSymbol.WATT
            ),
            dc_max_voltage_limit=PVEVMaxVoltageLimit(
                multiplier=max_voltage_limit_multiplier, value=max_voltage_limit_value, unit=UnitSymbol.VOLTAGE
            ),
            dc_energy_capacity=PVEVEnergyCapacity(
                multiplier=energy_capacity_multiplier, value=energy_capacity_value, unit=UnitSymbol.WATT_HOURS
            ),
            dc_target_current=PVEVTargetCurrent(
                multiplier=target_current_multiplier, value=target_current_value, unit=UnitSymbol.AMPERE
            ),
            dc_target_voltage=PVEVTargetVoltage(
                multiplier=target_voltage_multiplier, value=target_voltage_value, unit=UnitSymbol.VOLTAGE
            ),
        )

        max_discharge_current_limit_value, max_discharge_current_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_discharge_max_current_limit)
        max_discharge_power_limit_value, max_discharge_power_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_discharge_max_power_limit)
        discharge_target_current_value, discharge_target_current_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_discharge_target_current)

        self.dc_ev_discharge_params: DCEVChargeParams = DCEVChargeParams(
            dc_max_current_limit=PVEVMaxCurrentLimit(
                multiplier=max_discharge_current_limit_multiplier, value=-max_discharge_current_limit_value, unit=UnitSymbol.AMPERE
            ),
            dc_max_power_limit=PVEVMaxPowerLimit(
                multiplier=max_discharge_power_limit_multiplier, value=-max_discharge_power_limit_value, unit=UnitSymbol.WATT
            ),
            dc_max_voltage_limit=PVEVMaxVoltageLimit(
                multiplier=max_voltage_limit_multiplier, value=max_voltage_limit_value, unit=UnitSymbol.VOLTAGE
            ),
            dc_energy_capacity=PVEVEnergyCapacity(
                multiplier=energy_capacity_multiplier, value=energy_capacity_value, unit=UnitSymbol.WATT_HOURS
            ),
            dc_target_current=PVEVTargetCurrent(
                multiplier=discharge_target_current_multiplier, value=-discharge_target_current_value, unit=UnitSymbol.AMPERE
            ),
            dc_target_voltage=PVEVTargetVoltage(
                multiplier=target_voltage_multiplier, value=target_voltage_value, unit=UnitSymbol.VOLTAGE
            ),
        )

    # ============================================================================
    # |             COMMON FUNCTIONS (FOR ALL ENERGY TRANSFER MODES)             |
    # ============================================================================

    async def get_evcc_id(self, protocol: Protocol, iface: str) -> str:
        """Overrides EVControllerInterface.get_evcc_id()."""

        if protocol in (Protocol.ISO_15118_2, Protocol.DIN_SPEC_70121):
            try:
                hex_str = get_nic_mac_address(iface)
                return hex_str.replace(":", "").upper()
            except MACAddressNotFound as exc:
                logger.warning(
                    "Couldn't determine EVCCID (ISO 15118-2) - "
                    f"Reason: {exc}. Setting MAC address to "
                    "'000000000000'"
                )
                return "000000000000"
        elif protocol.ns.startswith(Namespace.ISO_V20_BASE):
            # The check digit (last character) is not a correctly computed one
            return "WMIV1234567890ABCDEX"
        else:
            logger.error(f"Invalid protocol '{protocol}', can't determine EVCCID")
            raise InvalidProtocolError

    async def get_energy_transfer_mode(
        self, protocol: Protocol
    ) -> EnergyTransferModeEnum:
        """Overrides EVControllerInterface.get_energy_transfer_mode()."""
        return EnergyTransferModeEnum(EVEREST_EV_STATE.EnergyTransferMode)

    async def get_supported_energy_services(self) -> List[ServiceV20]:
        """Overrides EVControllerInterface.get_energy_transfer_service()."""
        return self.config.supported_energy_services

    async def select_energy_service_v20(
        self, services: List[MatchedService]
    ) -> SelectedEnergyService:
        """Overrides EVControllerInterface.select_energy_service_v20()."""
        top_of_list: MatchedService = services[0]
        selected_service = SelectedEnergyService(
            service=top_of_list.service,
            is_free=top_of_list.is_free,
            parameter_set=top_of_list.parameter_sets[0],
        )
        return selected_service

    async def select_vas_services_v20(
        self, services: List[MatchedService]
    ) -> Optional[List[SelectedVAS]]:
        """Overrides EVControllerInterface.select_vas_services_v20()."""
        matched_vas_services = [
            service for service in services if not service.is_energy_service
        ]
        selected_vas_services: List[SelectedVAS] = []
        for vas_service in matched_vas_services:
            selected_vas_services.append(
                SelectedVAS(
                    service=vas_service.service,
                    is_free=vas_service.is_free,
                    parameter_set=vas_service.parameter_sets[0],
                )
            )
        return selected_vas_services

    async def get_charge_params_v2(self, protocol: Protocol) -> ChargeParamsV2:
        """Overrides EVControllerInterface.get_charge_params_v2()."""
        ac_charge_params = None
        dc_charge_params = None

        if (await self.get_energy_transfer_mode(protocol)).startswith("AC"):
            e_amount = PVEAmount(multiplier=0, value=60,
                                 unit=UnitSymbol.WATT_HOURS)
            ev_max_voltage = PVEVMaxVoltage(
                multiplier=0, value=400, unit=UnitSymbol.VOLTAGE
            )
            ev_max_current = PVEVMaxCurrent(
                multiplier=-3, value=32000, unit=UnitSymbol.AMPERE
            )
            ev_min_current = PVEVMinCurrent(
                multiplier=0, value=10, unit=UnitSymbol.AMPERE
            )
            ac_charge_params = ACEVChargeParameter(
                departure_time=0,
                e_amount=e_amount,
                ev_max_voltage=ev_max_voltage,
                ev_max_current=ev_max_current,
                ev_min_current=ev_min_current,
            )
        else:
            ev_energy_request = PVEVEnergyRequest(
                multiplier=1, value=6000, unit=UnitSymbol.WATT_HOURS
            )
            dc_charge_params = DCEVChargeParameter(
                departure_time=0,
                dc_ev_status=await self.get_dc_ev_status(),
                ev_maximum_current_limit=self.dc_ev_charge_params.dc_max_current_limit,
                ev_maximum_power_limit=self.dc_ev_charge_params.dc_max_power_limit,
                ev_maximum_voltage_limit=self.dc_ev_charge_params.dc_max_voltage_limit,
                ev_energy_capacity=self.dc_ev_charge_params.dc_energy_capacity,
                ev_energy_request=ev_energy_request,
                full_soc=100,
                bulk_soc=80,
            )
        return ChargeParamsV2(
            await self.get_energy_transfer_mode(protocol),
            ac_charge_params,
            dc_charge_params,
        )

    async def get_charge_params_v20(
        self, selected_service: SelectedEnergyService
    ) -> Union[
        ACChargeParameterDiscoveryReqParams,
        BPTACChargeParameterDiscoveryReqParams,
        DCChargeParameterDiscoveryReqParams,
        BPTDCChargeParameterDiscoveryReqParams,
    ]:
        """Overrides EVControllerInterface.get_charge_params_v20()."""

        max_current_limit_value, max_current_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_current_limit)
        max_power_limit_value, max_power_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_power_limit)
        max_voltage_limit_value, max_voltage_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_voltage_limit)

        ac_cpd_params = ACChargeParameterDiscoveryReqParams(
            ev_max_charge_power=RationalNumber(exponent=3, value=11),
            ev_min_charge_power=RationalNumber(exponent=0, value=100),
        )
        dc_cpd_params = DCChargeParameterDiscoveryReqParams(
            ev_max_charge_power=RationalNumber(
                exponent=max_power_limit_multiplier, value=max_power_limit_value),
            ev_min_charge_power=RationalNumber(exponent=0, value=100),
            ev_max_charge_current=RationalNumber(
                exponent=max_current_limit_multiplier, value=max_current_limit_value),
            ev_min_charge_current=RationalNumber(exponent=0, value=10),
            ev_max_voltage=RationalNumber(
                exponent=max_voltage_limit_multiplier, value=max_voltage_limit_value),
            ev_min_voltage=RationalNumber(exponent=0, value=10),
        )
        if selected_service.service == ServiceV20.AC:
            return ac_cpd_params
        elif selected_service.service == ServiceV20.AC_BPT:
            return BPTACChargeParameterDiscoveryReqParams(
                **(ac_cpd_params.dict()),
                ev_max_discharge_power=RationalNumber(exponent=3, value=11),
                ev_min_discharge_power=RationalNumber(exponent=0, value=100),
            )
        elif selected_service.service in [ServiceV20.DC, ServiceV20.MCS]:
            return dc_cpd_params
        elif selected_service.service in [ServiceV20.DC_BPT, ServiceV20.MCS_BPT]:
            return BPTDCChargeParameterDiscoveryReqParams(
                **(dc_cpd_params.dict()),
                # Todo(sl): Update later if bpt is also available
                ev_max_discharge_power=RationalNumber(exponent=3, value=11),
                ev_min_discharge_power=RationalNumber(exponent=3, value=1),
                ev_max_discharge_current=RationalNumber(exponent=0, value=25),
                ev_min_discharge_current=RationalNumber(exponent=0, value=0),
            )
        else:
            # TODO Implement the remaining energy transer services
            logger.error(
                f"Energy transfer service {selected_service.service} not supported"
            )
            raise NotImplementedError

    async def get_scheduled_se_params(
        self, selected_energy_service: SelectedEnergyService
    ) -> ScheduledScheduleExchangeReqParams:
        """Overrides EVControllerInterface.get_scheduled_se_params()."""
        ev_price_rule = EVPriceRule(
            energy_fee=RationalNumber(exponent=0, value=0),
            power_range_start=RationalNumber(exponent=0, value=0),
        )

        ev_price_rule_stack = EVPriceRuleStack(
            duration=0, ev_price_rules=[ev_price_rule]
        )

        ev_price_rule_stack_list = EVPriceRuleStackList(
            ev_price_rule_stacks=[ev_price_rule_stack]
        )

        ev_absolute_price_schedule = EVAbsolutePriceSchedule(
            time_anchor=0,
            currency="EUR",
            price_algorithm=PriceAlgorithm.POWER,
            ev_price_rule_stacks=ev_price_rule_stack_list,
        )

        ev_power_schedule_entry = EVPowerScheduleEntry(
            duration=3600, power=RationalNumber(exponent=3, value=10)
        )

        ev_power_schedule_entries = EVPowerScheduleEntryList(
            entries=[ev_power_schedule_entry]
        )

        ev_power_schedule = EVPowerSchedule(
            time_anchor=0, ev_power_schedule_entries=ev_power_schedule_entries
        )

        energy_offer = EVEnergyOffer(
            ev_power_schedule=ev_power_schedule,
            ev_absolute_price_schedule=ev_absolute_price_schedule,
        )

        scheduled_params = ScheduledScheduleExchangeReqParams(
            departure_time=7200,
            ev_target_energy_request=RationalNumber(exponent=3, value=10),
            ev_max_energy_request=RationalNumber(exponent=3, value=20),
            ev_min_energy_request=RationalNumber(exponent=-2, value=5),
            ev_energy_offer=energy_offer,
        )

        return scheduled_params

    async def get_dynamic_se_params(
        self, selected_energy_service: SelectedEnergyService
    ) -> DynamicScheduleExchangeReqParams:
        """Overrides EVControllerInterface.get_dynamic_se_params()."""
        dynamic_params = DynamicScheduleExchangeReqParams(
            departure_time=7200,
            min_soc=30,
            target_soc=80,
            ev_target_energy_request=RationalNumber(exponent=3, value=40),
            ev_max_energy_request=RationalNumber(exponent=3, value=60),
            ev_min_energy_request=RationalNumber(exponent=3, value=-20),
            ev_max_v2x_energy_request=RationalNumber(exponent=3, value=5),
            ev_min_v2x_energy_request=RationalNumber(exponent=0, value=0),
        )

        return dynamic_params

    async def process_scheduled_se_params(
        self, scheduled_params: ScheduledScheduleExchangeResParams, pause: bool
    ) -> Tuple[Optional[EVPowerProfile], ChargeProgressV20]:
        """Overrides EVControllerInterface.process_scheduled_se_params()."""
        is_ready = bool(random.getrandbits(1))
        if not is_ready:
            logger.debug(
                "Scheduled parameters for ScheduleExchangeReq not yet ready")
            # TODO The standard doesn't clearly define what the ChargeProgress should
            #      be if EVProcessing is set to ONGOING. Will assume
            #      ChargeProgress.START but check with standardisation community
            return None, ChargeProgressV20.START

        charge_progress = ChargeProgressV20.START

        if pause:
            charge_progress = ChargeProgressV20.STOP

        # Let's just select the first schedule offered
        selected_schedule = scheduled_params.schedule_tuples[0]
        charging_schedule = selected_schedule.charging_schedule.power_schedule
        charging_schedule_entries = charging_schedule.schedule_entry_list.entries

        # We just copy the values from the charging schedule into the EV power profile
        ev_power_schedule_entries: List[EVPowerScheduleEntry] = []
        for entry in charging_schedule_entries:
            ev_power_schedule_entry = EVPowerScheduleEntry(
                duration=entry.duration, power=entry.power
            )
            ev_power_schedule_entries.append(ev_power_schedule_entry)

        ev_power_profile_entry_list = EVPowerScheduleEntryList(
            entries=ev_power_schedule_entries
        )

        scheduled_profile = ScheduledEVPowerProfile(
            selected_schedule_tuple_id=selected_schedule.schedule_tuple_id,
            power_tolerance_acceptance=PowerToleranceAcceptance.CONFIRMED,
        )

        ev_power_profile = EVPowerProfile(
            time_anchor=0,
            entry_list=ev_power_profile_entry_list,
            scheduled_profile=scheduled_profile,
        )

        return ev_power_profile, charge_progress

    async def process_dynamic_se_params(
        self, dynamic_params: DynamicScheduleExchangeResParams, pause: bool
    ) -> Tuple[Optional[EVPowerProfile], ChargeProgressV20]:
        """Overrides EVControllerInterface.process_dynamic_se_params()."""
        is_ready = bool(random.getrandbits(1))
        if not is_ready:
            logger.debug(
                "Dynamic parameters for ScheduleExchangeReq not yet ready")
            # TODO The standard doesn't clearly define what the ChargeProgress should
            #      be if EVProcessing is set to ONGOING. Will assume
            #      ChargeProgress.START but check with standardisation community
            return None, ChargeProgressV20.START

        charge_progress = ChargeProgressV20.START

        if pause:
            charge_progress = ChargeProgressV20.STOP

        ev_power_schedule_entry = EVPowerScheduleEntry(
            duration=3600, power=RationalNumber(exponent=3, value=11)
        )

        ev_power_profile_entry_list = EVPowerScheduleEntryList(
            entries=[ev_power_schedule_entry]
        )

        ev_power_profile = EVPowerProfile(
            time_anchor=0,
            entry_list=ev_power_profile_entry_list,
            dynamic_profile=DynamicEVPowerProfile(),
        )

        return ev_power_profile, charge_progress

    async def is_cert_install_needed(self) -> bool:
        """Overrides EVControllerInterface.is_cert_install_needed()."""

        contract_leaf_path = os.path.join(
            get_PKI_PATH(), CertPath.CONTRACT_LEAF_DER)

        if self.config.is_cert_install_needed or os.path.exists(contract_leaf_path) is False:
            return True
        else:
            return False

    async def process_sa_schedules_dinspec(
        self, sa_schedules: List[SAScheduleTupleEntryDINSPEC]
    ) -> int:
        """Overrides EVControllerInterface.process_sa_schedules_dinspec()."""
        schedule = sa_schedules.pop()
        profile_entry_list: List[ProfileEntryDetailsDINSPEC] = []

        # The charging schedule coming from the SECC is called 'schedule', the
        # pendant coming from the EVCC (after having processed the offered
        # schedule(s)) is called 'profile'. Therefore, we use the prefix
        # 'schedule_' for data from the SECC, and 'profile_' for data from the EVCC.
        for schedule_entry_details in schedule.p_max_schedule.entry_details:
            profile_entry_details = ProfileEntryDetailsDINSPEC(
                start=schedule_entry_details.time_interval.start,
                max_power=schedule_entry_details.p_max,
            )
            profile_entry_list.append(profile_entry_details)

            # The last PMaxSchedule element has an optional 'duration' field. if
            # 'duration' is present, then there'll be no more PMaxSchedule element
            # with p_max set to 0 kW. Instead, the 'duration' informs how long the
            # current power level applies before the offered charging schedule ends.
            if schedule_entry_details.time_interval.duration:
                zero_power = 1
                last_profile_entry_details = ProfileEntryDetailsDINSPEC(
                    start=(
                        schedule_entry_details.time_interval.start
                        + schedule_entry_details.time_interval.duration
                    ),
                    max_power=zero_power,
                )
                profile_entry_list.append(last_profile_entry_details)

        return schedule.sa_schedule_tuple_id

    async def process_sa_schedules_v2(
        self, sa_schedules: List[SAScheduleTuple]
    ) -> Tuple[ChargeProgressV2, int, ChargingProfile]:
        """Overrides EVControllerInterface.process_sa_schedules()."""
        secc_schedule = sa_schedules.pop()
        evcc_profile_entry_list: List[ProfileEntryDetails] = []

        # The charging schedule coming from the SECC is called 'schedule', the
        # pendant coming from the EVCC (after having processed the offered
        # schedule(s)) is called 'profile'. Therefore, we use the prefix
        # 'schedule_' for data from the SECC, and 'profile_' for data from the EVCC.
        for schedule_entry_details in secc_schedule.p_max_schedule.schedule_entries:
            profile_entry_details = ProfileEntryDetails(
                start=schedule_entry_details.time_interval.start,
                max_power=schedule_entry_details.p_max,
            )
            evcc_profile_entry_list.append(profile_entry_details)

            # The last PMaxSchedule element has an optional 'duration' field. if
            # 'duration' is present, then there'll be no more PMaxSchedule element
            # (with p_max set to 0 kW). Instead, the 'duration' informs how long the
            # current power level applies before the offered charging schedule ends.
            if schedule_entry_details.time_interval.duration:
                zero_power = PVPMax(multiplier=0, value=0,
                                    unit=UnitSymbol.WATT)
                last_profile_entry_details = ProfileEntryDetails(
                    start=(
                        schedule_entry_details.time_interval.start
                        + schedule_entry_details.time_interval.duration
                    ),
                    max_power=zero_power,
                )
                evcc_profile_entry_list.append(last_profile_entry_details)

        # TODO If a SalesTariff is present and digitally signed (and TLS is used),
        #      verify each sales tariff with the mobility operator sub 2 certificate

        return (
            ChargeProgressV2.START,
            secc_schedule.sa_schedule_tuple_id,
            ChargingProfile(profile_entries=evcc_profile_entry_list),
        )

    async def continue_charging(self) -> bool:
        """Overrides EVControllerInterface.continue_charging()."""
        # if self.charging_loop_cycles == 0 or await self.is_charging_complete():
        #     # To simulate a bit of a charging loop, we'll let it run chargingLoopCycle
        #     # times specified in config file
        #     return False
        # else:
        #     self.charging_loop_cycles -= 1
        #     self._soc = min(int(self._soc + self.increment), 100)
        #     # The line below can just be called once process_message in all states
        #     # are converted to async calls
        #     # await asyncio.sleep(0.5)
        #     return True
        return not EVEREST_EV_STATE.StopCharging
    
    async def pause(self) -> bool:
        return EVEREST_EV_STATE.Pause

    async def reset_ev_values(self):
        EVEREST_EV_STATE.reset()

    async def store_contract_cert_and_priv_key(
        self, contract_cert_chain: CertificateChain, priv_key: bytes
    ):
        """Overrides EVControllerInterface.store_contract_cert_and_priv_key()."""

        priv_key_pwd = "123456"
        ec_priv_key = to_ec_priv_key(priv_key)
        serialized_priv_key = ec_priv_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=BestAvailableEncryption(
                priv_key_pwd.encode(encoding="utf-8"))
        )
        with open(os.path.join(get_PKI_PATH(), KeyPath.CONTRACT_LEAF_PEM), 'wb') as f:
            f.write(serialized_priv_key)
        with open(os.path.join(get_PKI_PATH(), KeyPasswordPath.CONTRACT_LEAF_KEY_PASSWORD), 'wb') as f:
            f.write(priv_key_pwd.encode(encoding="utf-8"))
        with open(os.path.join(get_PKI_PATH(), CertPath.CONTRACT_LEAF_DER), 'wb') as f:
            f.write(contract_cert_chain.certificate)

        for sub_ca_cert in contract_cert_chain.sub_certificates.certificates:
            cert = load_der_x509_certificate(sub_ca_cert)
            path_len = cert.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS
            ).value.path_length
            if path_len == 0:
                with open(os.path.join(get_PKI_PATH(), CertPath.MO_SUB_CA2_DER), 'wb') as f:
                    f.write(sub_ca_cert)
            elif path_len == 1:
                with open(os.path.join(get_PKI_PATH(), CertPath.MO_SUB_CA1_DER), 'wb') as f:
                    f.write(sub_ca_cert)
            else:
                raise CertChainLengthError(
                    allowed_num_sub_cas=2, num_sub_cas=path_len)

    async def get_prioritised_emaids(self) -> Optional[EMAIDList]:
        return None

    async def ready_to_charge(self) -> bool:
        return await self.continue_charging()

    async def is_precharged(
        self, present_voltage_evse: Union[PVEVSEPresentVoltage, RationalNumber]
    ) -> bool:
        return (
            present_voltage_evse.get_decimal_value() > EVEREST_EV_STATE.dc_target_voltage*0.9
            and present_voltage_evse.get_decimal_value() < EVEREST_EV_STATE.dc_target_voltage*1.1
        )

    async def get_dc_ev_power_delivery_parameter_dinspec(
        self,
    ) -> DCEVPowerDeliveryParameterDINSPEC:
        return DCEVPowerDeliveryParameterDINSPEC(
            dc_ev_status=await self.get_dc_ev_status_dinspec(),
            bulk_charging_complete=False,
            charging_complete=await self.continue_charging(),
        )

    async def get_dc_ev_power_delivery_parameter(self) -> DCEVPowerDeliveryParameter:
        return DCEVPowerDeliveryParameter(
            dc_ev_status=await self.get_dc_ev_status(),
            bulk_charging_complete=False,
            charging_complete=await self.continue_charging(),
        )

    async def is_bulk_charging_complete(self) -> bool:
        return False

    async def is_charging_complete(self) -> bool:
        if self._soc == 100 or self._charging_is_completed:
            return True
        else:
            return False

    async def get_remaining_time_to_full_soc(self) -> PVRemainingTimeToFullSOC:
        return PVRemainingTimeToFullSOC(multiplier=0, value=100, unit="s")

    async def get_remaining_time_to_bulk_soc(self) -> PVRemainingTimeToBulkSOC:
        return PVRemainingTimeToBulkSOC(multiplier=0, value=80, unit="s")

    async def welding_detection_has_finished(self):
        if self.welding_detection_cycles == 3:
            return True
        self.welding_detection_cycles += 1
        return False

    async def stop_charging(self) -> None:
        self._charging_is_completed = True

    async def get_ac_charge_loop_params_v20(
        self, control_mode: ControlMode, selected_service: ServiceV20
    ) -> Union[
        ScheduledACChargeLoopReqParams,
        BPTScheduledACChargeLoopReqParams,
        DynamicACChargeLoopReqParams,
        BPTDynamicACChargeLoopReqParams,
    ]:
        """Overrides EVSControllerInterface.get_ac_charge_loop_params_v20()."""
        if control_mode == ControlMode.SCHEDULED:
            scheduled_params = ScheduledACChargeLoopReqParams(
                ev_present_active_power=RationalNumber(exponent=3, value=20),
                # Add more optional fields if wanted
            )
            if selected_service == ServiceV20.AC_BPT:
                bpt_scheduled_params = BPTScheduledACChargeLoopReqParams(
                    **(scheduled_params.dict()),
                    # Add more optional fields if wanted
                )
                return bpt_scheduled_params
            return scheduled_params
        else:
            # Dynamic Mode
            dynamic_params = DynamicACChargeLoopReqParams(
                departure_time=2000,
                ev_target_energy_request=RationalNumber(exponent=3, value=40),
                ev_max_energy_request=RationalNumber(exponent=3, value=60),
                ev_min_energy_request=RationalNumber(exponent=3, value=-20),
                ev_max_charge_power=RationalNumber(exponent=3, value=15),
                ev_min_charge_power=RationalNumber(exponent=0, value=100),
                ev_present_active_power=RationalNumber(exponent=3, value=15),
                ev_present_reactive_power=RationalNumber(exponent=3, value=15),
                # Add more optional fields if wanted
            )
            if selected_service == ServiceV20.AC_BPT:
                bpt_dynamic_params = BPTDynamicACChargeLoopReqParams(
                    **(dynamic_params.dict()),
                    ev_max_discharge_power=RationalNumber(
                        exponent=3, value=11),
                    ev_min_discharge_power=RationalNumber(
                        exponent=-3, value=1),
                    # Add more optional fields if wanted
                )
                return bpt_dynamic_params
            return dynamic_params

    # ============================================================================
    # |                          DC-SPECIFIC FUNCTIONS                           |
    # ============================================================================

    async def get_dc_charge_params(self) -> DCEVChargeParams:
        """Applies to both DIN SPEC and 15118-2"""
        return self.dc_ev_charge_params

    async def get_dc_ev_status_dinspec(self) -> DCEVStatusDINSPEC:
        return DCEVStatusDINSPEC(
            ev_ready=True,
            ev_error_code=DCEVErrorCode.NO_ERROR,
            ev_ress_soc=self._soc,
        )

    async def get_dc_ev_status(self) -> DCEVStatus:
        return DCEVStatus(
            ev_ready=True,
            ev_error_code=DCEVErrorCode.NO_ERROR,
            ev_ress_soc=self._soc,
        )

    async def get_scheduled_dc_charge_loop_params(
        self,
    ) -> ScheduledDCChargeLoopReqParams:
        """Overrides EVControllerInterface.get_scheduled_dc_charge_loop_params()."""
        target_current_value, target_current_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_target_current)
        target_voltage_value, target_voltage_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_target_voltage)
        return ScheduledDCChargeLoopReqParams(
            ev_target_current=RationalNumber(
                exponent=target_current_multiplier, value=target_current_value),
            ev_target_voltage=RationalNumber(
                exponent=target_voltage_multiplier, value=target_voltage_value),
        )

    async def get_dynamic_dc_charge_loop_params(self) -> DynamicDCChargeLoopReqParams:
        """Overrides EVControllerInterface.get_dynamic_dc_charge_loop_params()."""
        max_current_limit_value, max_current_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_current_limit)
        max_power_limit_value, max_power_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_power_limit)
        max_voltage_limit_value, max_voltage_limit_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_max_voltage_limit)
        energy_capacity_value, energy_capacity_multiplier = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_energy_capacity)

        return DynamicDCChargeLoopReqParams(
            ev_target_energy_request=RationalNumber(
                exponent=energy_capacity_multiplier, value=energy_capacity_value),
            ev_max_energy_request=RationalNumber(exponent=3, value=60),
            ev_min_energy_request=RationalNumber(exponent=0, value=1),
            ev_max_charge_power=RationalNumber(
                exponent=max_power_limit_multiplier, value=max_power_limit_value),
            ev_min_charge_power=RationalNumber(exponent=0, value=0),
            ev_max_charge_current=RationalNumber(
                exponent=max_current_limit_multiplier, value=max_current_limit_value),
            ev_max_voltage=RationalNumber(
                exponent=max_voltage_limit_multiplier, value=max_voltage_limit_value),
            ev_min_voltage=RationalNumber(exponent=0, value=150),
        )

    async def get_bpt_scheduled_dc_charge_loop_params(
        self,
    ) -> BPTScheduledDCChargeLoopReqParams:
        """Overrides EVControllerInterface.get_bpt_scheduled_dc_charge_loop_params()."""
        dc_scheduled_dc_charge_loop_params_v20 = (
            await self.get_scheduled_dc_charge_loop_params()
        ).dict()
        return BPTScheduledDCChargeLoopReqParams(
            **dc_scheduled_dc_charge_loop_params_v20
        )

    async def get_bpt_dynamic_dc_charge_loop_params(
        self,
    ) -> BPTDynamicDCChargeLoopReqParams:
        """Overrides EVControllerInterface.get_bpt_dynamic_dc_charge_loop_params()."""
        dc_dynamic_dc_charge_loop_params_v20 = (
            await self.get_dynamic_dc_charge_loop_params()
        ).dict()
        return BPTDynamicDCChargeLoopReqParams(
            **dc_dynamic_dc_charge_loop_params_v20,
            ev_max_discharge_power=RationalNumber(exponent=3, value=11),
            ev_min_discharge_power=RationalNumber(exponent=0, value=300),
            ev_max_discharge_current=RationalNumber(exponent=0, value=25),
        )

    async def get_present_voltage(self) -> RationalNumber:
        """Overrides EVControllerInterface.get_present_voltage()."""
        value, exponent = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_target_voltage)
        return RationalNumber(exponent=exponent, value=value)

    async def get_target_voltage(self) -> RationalNumber:
        """Overrides EVControllerInterface.get_target_voltage()."""
        value, exponent = float2Value_Multiplier(
            EVEREST_EV_STATE.dc_target_voltage)
        return RationalNumber(exponent=exponent, value=value)

    async def enable_charging(self, enabled: bool) -> None:
        """Overrides EVControllerInterface.enable_charging()."""
        pass

    async def get_display_params(self) -> DisplayParameters:
        """Overrides EVControllerInterface.get_display_params()."""
        return DisplayParameters(
            present_soc=self._soc,
            charging_complete=await self.is_charging_complete(),
        )

    async def is_service_hpc1_active(self) -> bool:
        return EVEREST_EV_STATE.ServiceHPC1_Active

    # ============================================================================
    # |                          SAE J2847/2 FUNCTIONS                           |
    # ============================================================================

    async def is_sae_j2847_v2g_active(self) -> bool:
        return EVEREST_EV_STATE.SAEJ2847_V2H_V2G_Active

    async def get_dc_discharge_params(self) -> DCEVChargeParams:
        """Applies to both DIN SPEC and 15118-2"""
        return self.dc_ev_discharge_params

    async def get_charge_params_v2h(self, protocol: Protocol) -> ChargeParamsV2:
        """Overrides EVControllerInterface.get_charge_params_v2()."""
        ac_charge_params = None

        ev_energy_request = PVEVEnergyRequest(
            multiplier=1, value=6000, unit=UnitSymbol.WATT_HOURS
        )
        dc_charge_params = DCEVChargeParameter(
            departure_time=0,
            dc_ev_status=await self.get_dc_ev_status(),
            ev_maximum_current_limit=self.dc_ev_discharge_params.dc_max_current_limit,
            ev_maximum_power_limit=self.dc_ev_discharge_params.dc_max_power_limit,
            ev_maximum_voltage_limit=self.dc_ev_discharge_params.dc_max_voltage_limit,
            ev_energy_capacity=self.dc_ev_discharge_params.dc_energy_capacity,
            ev_energy_request=ev_energy_request,
            full_soc=100,
            bulk_soc=EVEREST_EV_STATE.minimal_soc,
        )
        return ChargeParamsV2(
            await self.get_energy_transfer_mode(protocol),
            ac_charge_params,
            dc_charge_params,
        )
