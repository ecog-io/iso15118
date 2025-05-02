"""
This module contains the abstract class for an EVCC to retrieve data from the EV.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from iso15118.shared.messages.datatypes import (
    DCEVChargeParams,
    PVEVSEPresentVoltage,
    PVRemainingTimeToBulkSOC,
    PVRemainingTimeToFullSOC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    DCEVPowerDeliveryParameter as DCEVPowerDeliveryParameterDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import DCEVStatus as DCEVStatusDINSPEC
from iso15118.shared.messages.din_spec.datatypes import (
    SAScheduleTupleEntry as SAScheduleTupleEntryDINSPEC,
)
from iso15118.shared.messages.enums import ControlMode, Protocol, ServiceV20
from iso15118.shared.messages.iso15118_2.datatypes import (
    ACEVChargeParameter,
    ChargeProgress,
    ChargingProfile,
    DCEVChargeParameter,
    DCEVPowerDeliveryParameter,
    DCEVStatus,
    EnergyTransferModeEnum,
    SAScheduleTuple,
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
    DynamicScheduleExchangeReqParams,
    DynamicScheduleExchangeResParams,
    EMAIDList,
    EVPowerProfile,
    MatchedService,
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


@dataclass
class ChargeParamsV2:
    energy_mode: EnergyTransferModeEnum
    ac_parameters: Optional[ACEVChargeParameter]
    dc_parameters: Optional[DCEVChargeParameter]


class EVControllerInterface(ABC):
    # ============================================================================
    # |             COMMON FUNCTIONS (FOR ALL ENERGY TRANSFER MODES)             |
    # ============================================================================
    @abstractmethod
    async def charge_loop_delay(self) -> int:
        """
        Delays the charging loop for a certain amount of time. This could be used
        for example to simulate a delay in the charging process, e.g. due to a
        temporary lack of power.

        Returns:
            The amount of time the charging loop was delayed in seconds

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_evcc_id(self, protocol: Protocol, iface: str) -> str:
        """
        Retrieves the EVCCID, which is a field of the SessionSetupReq. The structure of
        the EVCCID depends on the protocol version. In DIN SPEC 70121 and ISO 15118-2,
        the EVCCID is the MAC address (given as hexadecimal bytes), in ISO 15118-20 it's
        similar to a VIN (Vehicle Identification Number, given as str).

        Args:
            protocol: The communication protocol, a member of the Protocol enum
            iface (str): The network interface selected

        Raises:
            InvalidProtocolError

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_energy_transfer_mode(
        self, protocol: Protocol
    ) -> EnergyTransferModeEnum:
        """
        Gets the energy transfer mode requested for the current charging session.
        This depends on the charging cable being plugged in, which could be a
        Type 2 AC or Combo 2 plug, for example.

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        """
        raise NotImplementedError

    async def get_supported_energy_services(self) -> List[ServiceV20]:
        """
        Gets the energy transfer service requested for the current charging session.
        This must be one of the energy related services (services with ID 1 through 7)

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def select_energy_service_v20(
        self, services: List[MatchedService]
    ) -> SelectedEnergyService:
        """
        Selects the energy service and associated parameter set from a given set of
        parameters per energy service ID.

        Args:
            services: List of compatible energy services offered by EVSE

        Returns:
            An instance of SelectedEnergyService, containing the service, whether it's
            free or paid, and its chosen parameter set.

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def select_vas_services_v20(
        self, services: List[MatchedService]
    ) -> Optional[List[SelectedVAS]]:
        """
        Selects a value-added service (VAS) and associated parameter set from a given
        set of parameters for that value-added energy. If you don't want to select
        the offered VAS, return None.

        Args:
            services: List of matched services

        Returns:
            A list of SelectedVAS, containing the service, whether it's free or
            paid, and its chosen parameter set.

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_scheduled_se_params(
        self, selected_energy_service: SelectedEnergyService
    ) -> ScheduledScheduleExchangeReqParams:
        """
        Gets the parameters for a ScheduleExchangeRequest, which correspond to the
        Scheduled control mode.

        Args:
            selected_energy_service: The energy services, which the EVCC selected.
                                     The selected parameter set, that is associated
                                     with that energy service, influences the
                                     parameters for the ScheduleExchangeReq

        Returns:
            Parameters for the ScheduleExchangeReq in Scheduled control mode

        Relevant for:
        - ISO 15118-20
        """

    @abstractmethod
    async def get_dynamic_se_params(
        self, selected_energy_service: SelectedEnergyService
    ) -> DynamicScheduleExchangeReqParams:
        """
        Gets the parameters for a ScheduleExchangeRequest, which correspond to the
        Dynamic control mode.

        Args:
            selected_energy_service: The energy services, which the EVCC selected.
                                     The selected parameter set, that is associated
                                     with that energy service, influences the
                                     parameters for the ScheduleExchangeReq

        Returns:
            Parameters for the ScheduleExchangeReq in Dynamic control mode

        Relevant for:
        - ISO 15118-20
        """

    @abstractmethod
    async def process_scheduled_se_params(
        self, scheduled_params: ScheduledScheduleExchangeResParams, pause: bool
    ) -> Tuple[Optional[EVPowerProfile], ChargeProgressV20]:
        """
        Processes the ScheduleExchangeRes parameters for the Scheduled mode.

        Args:
            scheduled_params: The list of offered schedule tuples for Scheduled mode
            pause: When set to True, this indicates that the EVSE doesn’t have any power
                   available and the EV should set ChargeProgress to PAUSE

        Returns:
            A tuple consisting of
            1. the resulting charging profile of the EV (or None, if not yet ready)
            1. the ChargeProgress status
            needed to create the PowerDeliveryReq message

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def process_dynamic_se_params(
        self, dynamic_params: DynamicScheduleExchangeResParams, pause: bool
    ) -> Tuple[Optional[EVPowerProfile], ChargeProgressV20]:
        """
        Processes the ScheduleExchangeRes parameters for the Dynamic mode.

        Args:
            dynamic_params: The parameters relevant for the Dynamic mode
            pause: When set to True, this indicates that the EVSE doesn’t have any power
                   available and the EV should set ChargeProgress to PAUSE

        Returns:
            A tuple consisting of
            1. the resulting charging profile of the EV (or None, if not yet ready)
            1. the ChargeProgress status
            needed to create the PowerDeliveryReq message

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def is_cert_install_needed(self) -> bool:
        """
        Returns True if the installation of a contract certificate is needed, False
        otherwise. A certificate installation is needed if the authorization option
        'Contract' (Plug & Charge) is chosen but no valid contract certificate is
        currently installed. An EV manufacturer might also choose to use the
        certificate installation process instead of a certificate update process
        available in ISO 15118-2 as there's no benefit of using the
        CertificateUpdateReq instead of the CertificateInstallationReq message.
        For example, you might want to choose to do a contract certificate
        installation if a certificate is about to expire (e.g. in two weeks).

        Relevant for:
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def process_sa_schedules_dinspec(
        self, sa_schedules: List[SAScheduleTupleEntryDINSPEC]
    ) -> int:
        """
        Processes the SAScheduleList provided with the ChargeParameterDiscoveryRes
        to decide which of the offered schedules to choose and whether or not to
        start charging instantly (ChargeProgress=Start) or to delay the charging
        process (ChargeProgress=Stop), including information on how the EV's
        charging profile will look like.

        Args:
            sa_schedules: The list of offered charging profiles (SAScheduleTuple
                          elements), each of which contains a mandatory PMaxSchedule
                          and an optional SalesTariff

        Returns the ID of the chosen charging schedule

        Relevant for:
        - DIN SPEC 70121
        """
        raise NotImplementedError

    @abstractmethod
    async def process_sa_schedules_v2(
        self, sa_schedules: List[SAScheduleTuple]
    ) -> Tuple[ChargeProgress, int, ChargingProfile]:
        """
        Processes the SAScheduleList provided with the ChargeParameterDiscoveryRes
        to decide which of the offered schedules to choose and whether or not to
        start charging instantly (ChargeProgress=Start) or to delay the charging
        process (ChargeProgress=Stop), including information on how the EV's
        charging profile will look like.

        Args:
            sa_schedules: The list of offered charging profiles (SAScheduleTuple
                          elements), each of which contains a mandatory PMaxSchedule
                          and an optional SalesTariff

        Returns:
            A tuple consisting of
            1. the ChargeProgress status,
            2. the ID of the chosen charging schedule (SAScheduleTuple), and
            3. the resulting charging profile of the EV, which may follow the
               suggestion of the offered charging schedule exactly or deviate
               (consume less power, but never more than the max limit provided by
               the SECC).

        Relevant for:
        - ISO 15118-2
        """
        raise NotImplementedError

    @abstractmethod
    async def continue_charging(self) -> bool:
        """
        Whether or not to continue the energy flow during the charging loop. This
        depends on factors like SOC or user interaction with the vehicle (e.g. opened
        doors). If True, the charging loop continues.

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def store_contract_cert_and_priv_key(
        self, contract_cert: bytes, priv_key: bytes
    ):
        """
        Stores the contract certificate and associated private key, both needed
        for Plug & Charge and received via a CertificateInstallationRes.
        This is a mockup, but a real EV should interact with a hardware security
        module (HSM) on a productive environment.

        Relevant for:
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_prioritised_emaids(self) -> Optional[EMAIDList]:
        """
        Indicates the list of EMAIDs (E-Mobility Account IDs) referencing contract
        certificates that shall be installed into the EV. The EMAIDs are given in
        the order of priority from highest priority to lowest priority.
        The secondary actor (e.g. Contract Certificate Pool operator, see the spec
        VDE-AR-E 2802-100-1, implemented by e.g. Hubject) will use this parameter to
        filter the list of contract certificates to be installed in case
        MaximumContractCertificateChains (a parameter the EVCC sends in
        CertificateInstallationReq) is smaller than the number of contract
        certificates available and ensures that the EV gets the highest priority
        contract certificates it desires.

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_dc_ev_status_dinspec(self) -> DCEVStatusDINSPEC:
        """
        Gets the DC-specific EV Status information.

        Relevant for:
        - DIN SPEC 70121
        """
        raise NotImplementedError

    @abstractmethod
    async def get_dc_ev_status(self) -> DCEVStatus:
        """
        Gets the DC-specific EV Status information.

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def is_precharged(
        self, present_voltage_evse: Union[PVEVSEPresentVoltage, RationalNumber]
    ) -> bool:
        """
        Return True if the output voltage of the EVSE has reached
        the requested precharge voltage. Otherwise return False.
        According 61851-23

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_charge_params_v2(self, protocol: Protocol) -> ChargeParamsV2:
        """
        Gets the charge parameter needed for ChargeParameterDiscoveryReq (ISO 15118-2),
        including the energy transfer mode and the energy mode-specific parameters,
        which is an instance of either ACEVChargeParameter.

        Returns:
            A tuple of ChargeParamsV2, including EnergyTransferMode and
            ACEVChargeParameter

        Relevant for:
        - ISO 15118-2
        """
        raise NotImplementedError

    @abstractmethod
    async def get_charge_params_v20(
        self, selected_service: SelectedEnergyService
    ) -> Union[
        ACChargeParameterDiscoveryReqParams,
        BPTACChargeParameterDiscoveryReqParams,
        DCChargeParameterDiscoveryReqParams,
        BPTDCChargeParameterDiscoveryReqParams,
    ]:
        """
        Gets the charge parameter needed for
        ACChargeParameterDiscovery/DCChargeParameterDiscovery (ISO 15118-20).
        Returns:
            One of [ACChargeParameterDiscoveryReqParams,
            BPTACChargeParameterDiscoveryReqParams,
            DCChargeParameterDiscoveryReqParams,
            BPTDCChargeParameterDiscoveryReqParams]
            based on the currently selected service.

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def ready_to_charge(self) -> bool:
        """
        Used by PowerDeliveryReq message (DIN SPEC) to indicate if we are
        ready to start/stop charging.
        """
        raise NotImplementedError

    @abstractmethod
    async def is_charging_complete(self) -> bool:
        """
        If set to True, the EV indicates that full charge (100% SOC) is complete.

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20

        """
        raise NotImplementedError

    @abstractmethod
    async def is_bulk_charging_complete(self) -> bool:
        """
        Returns True if the soc for bulk charging is reached

        Relevant for:
        - DIN SPEC 70121 ??
        - ISO 15118-2
        - ISO 15118-20 ??
        """
        raise NotImplementedError

    @abstractmethod
    async def get_remaining_time_to_full_soc(self) -> PVRemainingTimeToFullSOC:
        """
        Gets the remaining time until full soc is reached.

        Relevant for:
        - DIN SPEC 70121 ??
        - ISO 15118-2
        - ISO 15118-20 ??
        """
        raise NotImplementedError

    @abstractmethod
    async def get_ac_charge_loop_params_v20(
        self, control_mode: ControlMode, selected_service: ServiceV20
    ) -> Union[
        ScheduledACChargeLoopReqParams,
        BPTScheduledACChargeLoopReqParams,
        DynamicACChargeLoopReqParams,
        BPTDynamicACChargeLoopReqParams,
    ]:
        """
        Gets the parameters for the ACChargeLoopReq for the currently set control mode
         and service.
        Args:
            control_mode: Control mode for this session - Scheduled/Dynamic
            selected_service: Enum for this Service - AC/AC_BPT
        Returns:
            ChargeLoop params depending on the selected mode. Return object could be
            one of the following types:
            [
                ScheduledACChargeLoopReqParams,
                BPTScheduledACChargeLoopReqParams,
                DynamicACChargeLoopReqParams,
                BPTDynamicACChargeLoopReqParams,
            ]
        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    # ============================================================================
    # |                          DC-SPECIFIC FUNCTIONS                           |
    # ============================================================================

    @abstractmethod
    async def get_scheduled_dc_charge_loop_params(
        self,
    ) -> ScheduledDCChargeLoopReqParams:
        """
        Gets the parameters for the DCChargeLoopReq in the Scheduled control mode

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_dynamic_dc_charge_loop_params(self) -> DynamicDCChargeLoopReqParams:
        """
        Gets the parameters for the DCChargeLoopReq in the Dynamic control mode

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_bpt_scheduled_dc_charge_loop_params(
        self,
    ) -> BPTScheduledDCChargeLoopReqParams:
        """
        Gets the parameters for the DCChargeLoopReq in the Scheduled control mode for
        bi-directional power transfer (BPT)

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_bpt_dynamic_dc_charge_loop_params(
        self,
    ) -> BPTDynamicDCChargeLoopReqParams:
        """
        Gets the parameters for the DCChargeLoopReq in the Dynamic control mode for
        bi-directional power transfer (BPT)

        Relevant for:
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_present_voltage(self) -> RationalNumber:
        """
        Gets current voltage required for DCChargeLoop for
        DC charging.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_target_voltage(self) -> RationalNumber:
        """
        Gets current voltage required for DCChargeLoop for
        DC charging.
        """
        raise NotImplementedError

    async def get_remaining_time_to_bulk_soc(self) -> PVRemainingTimeToBulkSOC:
        """
        Gets the remaining time until bulk soc is reached.

        Relevant for:
        - DIN SPEC 70121 ??
        - ISO 15118-2
        - ISO 15118-20 ??
        """
        raise NotImplementedError

    @abstractmethod
    async def welding_detection_has_finished(self):
        """
        Returns true as soon as the process of welding
        detection has finished successfully.

        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20 ??
        """
        raise NotImplementedError

    @abstractmethod
    async def stop_charging(self) -> None:
        """
        Used by CurrentDemand to indicate to EV to stop charging.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_dc_ev_power_delivery_parameter_dinspec(
        self,
    ) -> DCEVPowerDeliveryParameterDINSPEC:
        """
        gets the Power Delivery Parameter of the EV

        Relevant for:
        - DIN SPEC 70121
        """
        raise NotImplementedError

    @abstractmethod
    async def get_dc_ev_power_delivery_parameter(self) -> DCEVPowerDeliveryParameter:
        """
        gets the Power Delivery Parameter of the EV

        Relevant for:
        - ISO 15118-2
        - ISO 15118-20
        """
        raise NotImplementedError

    @abstractmethod
    async def get_dc_charge_params(self) -> DCEVChargeParams:
        """
        This would return an encapsulation of the following parameters:
        DC Max Current Limit
        DC Max Voltage Limit
        DC Target Current
        DC Target Voltage

        Relevant for
        - DIN SPEC 70121
        """
        raise NotImplementedError

    @abstractmethod
    async def enable_charging(self, enabled: bool) -> None:
        """
        Enables charging for the EVCC.
        Can be used as an indication to go to state C
        Relevant for:
        - DIN SPEC 70121
        - ISO 15118-2
        - ISO 15118-20
        """

    @abstractmethod
    async def get_display_params(self) -> DisplayParameters:
        """
        Enables charging for the EVCC.
        Can be used as an indication to go to state C
        Relevant for:
        - ISO 15118-20
        """
