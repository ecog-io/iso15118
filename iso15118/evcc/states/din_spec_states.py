"""
This module contains the EVCC's States used to process the SECC's incoming
V2GMessage objects of the DIN SPEC 70121 protocol, from SessionSetupRes to
SessionStopRes.
"""

import asyncio
import logging
from time import time
from typing import Any, List, Union

from iso15118.evcc import evcc_settings
from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
from iso15118.evcc.states.evcc_state import StateEVCC
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.datatypes import (
    DCEVChargeParams,
    DCEVSEStatus,
    DCEVSEStatusCode,
    SelectedService,
    SelectedServiceList,
)
from iso15118.shared.messages.din_spec.body import (
    CableCheckReq,
    CableCheckRes,
    ChargeParameterDiscoveryReq,
    ChargeParameterDiscoveryRes,
    ContractAuthenticationReq,
    ContractAuthenticationRes,
    CurrentDemandReq,
    CurrentDemandRes,
    PowerDeliveryReq,
    PowerDeliveryRes,
    PreChargeReq,
    PreChargeRes,
    ServiceDiscoveryReq,
    ServiceDiscoveryRes,
    ServicePaymentSelectionReq,
    ServicePaymentSelectionRes,
    SessionSetupRes,
    SessionStopReq,
    SessionStopRes,
    WeldingDetectionReq,
    WeldingDetectionRes,
)
from iso15118.shared.messages.din_spec.datatypes import (
    ChargeService,
    DCEVChargeParameter,
    DCEVStatus,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.din_spec.timeouts import Timeouts
from iso15118.shared.messages.enums import (
    AuthEnum,
    EnergyTransferModeEnum,
    EVSEProcessing,
    IsolationLevel,
    Namespace,
    Protocol,
)
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.timeouts import Timeouts as TimeoutsShared
from iso15118.shared.notifications import StopNotification
from iso15118.shared.states import Terminate

logger = logging.getLogger(__name__)


# ============================================================================
# |    EVCC STATES- DIN SPEC 70121                                           |
# ============================================================================


class SessionSetup(StateEVCC):
    """
    The DIN SPEC state in which the EVCC processes a SessionSetupRes from
    the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        # TODO: less the time used for waiting for and processing the
        #       SDPResponse and SupportedAppProtocolRes
        super().__init__(comm_session, Timeouts.SESSION_SETUP_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, SessionSetupRes)
        if not msg:
            return

        session_setup_res: SessionSetupRes = msg.body.session_setup_res

        self.comm_session.session_id = msg.header.session_id
        self.comm_session.evse_id = session_setup_res.evse_id

        # TODO Build ServiceDiscoveryReq() by including optional parameters.
        #  This would help test scope and category filtering at the SECC end

        self.create_next_message(
            ServiceDiscovery,
            ServiceDiscoveryReq(),
            Timeouts.SERVICE_DISCOVERY_REQ,
            Namespace.DIN_MSG_DEF,
        )


class ServiceDiscovery(StateEVCC):
    """
    The DIN SPEC state in which the EVCC processes a
    ServiceDiscoveryRes message from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.SERVICE_DISCOVERY_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, ServiceDiscoveryRes)
        if not msg:
            return

        service_discovery_res: ServiceDiscoveryRes = msg.body.service_discovery_res

        if not service_discovery_res.charge_service:
            self.stop_state_machine("ChargeService not offered")
            return

        self.select_auth_mode(service_discovery_res.auth_option_list.auth_options)
        self.select_services(service_discovery_res)
        await self.select_energy_transfer_mode()

        charge_service: ChargeService = service_discovery_res.charge_service
        offered_energy_modes: List[EnergyTransferModeEnum] = [
            charge_service.energy_transfer_type
        ]

        if self.comm_session.selected_auth_option is None:
            self.stop_state_machine(
                f"Offered payment option(s) "
                f"[{service_discovery_res.auth_option_list.auth_options}]"
                f" are not valid"
            )
            return

        if self.comm_session.selected_energy_mode not in offered_energy_modes:
            self.stop_state_machine(
                f"Offered energy transfer modes "
                f"{offered_energy_modes} not compatible with "
                f"{self.comm_session.selected_energy_mode}"
            )
            return

        selected_service_list = SelectedServiceList(
            selected_service=self.comm_session.selected_services
        )

        service_payment_selection = ServicePaymentSelectionReq(
            selected_payment_option=self.comm_session.selected_auth_option,
            selected_service_list=selected_service_list,
        )

        self.create_next_message(
            ServicePaymentSelection,
            service_payment_selection,
            Timeouts.SERVICE_PAYMENT_SELECTION_REQ,
            Namespace.DIN_MSG_DEF,
        )

    async def select_energy_transfer_mode(self):
        """
        Check if an energy transfer mode was saved from a previously paused
        communication session and reuse for resumed session, otherwise request
        from EV controller.
        """
        if evcc_settings.RESUME_REQUESTED_ENERGY_MODE:
            logger.debug(
                "Reusing energy transfer mode "
                f"{evcc_settings.RESUME_REQUESTED_ENERGY_MODE} "
                "from previously paused session"
            )
            self.comm_session.selected_energy_mode = (
                evcc_settings.RESUME_REQUESTED_ENERGY_MODE
            )
            evcc_settings.RESUME_REQUESTED_ENERGY_MODE = None
        else:
            self.comm_session.selected_energy_mode = (
                await self.comm_session.ev_controller.get_energy_transfer_mode(
                    Protocol.DIN_SPEC_70121
                )
            )

    def select_auth_mode(self, auth_option_list: List[AuthEnum]):
        self.comm_session.selected_auth_option = None
        if AuthEnum.EIM_V2 in auth_option_list:
            self.comm_session.selected_auth_option = AuthEnum.EIM_V2

    def select_services(self, service_discovery_res: ServiceDiscoveryRes):
        # Add the ChargeService as a selected service
        self.comm_session.selected_services.append(
            SelectedService(
                service_id=service_discovery_res.charge_service.service_tag.service_id
            )
        )


class ServicePaymentSelection(StateEVCC):
    """
    DIN SPEC state in which ServicePaymentSelectionRes message from EV is handled.
    The incoming message contains response code indicating if options set in
    ServicePaymentSelectionReq was accepted
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.SERVICE_PAYMENT_SELECTION_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, ServicePaymentSelectionRes)
        if not msg:
            return

        contract_authentication_req: ContractAuthenticationReq = (
            ContractAuthenticationReq()
        )
        self.create_next_message(
            ContractAuthentication,
            contract_authentication_req,
            Timeouts.CONTRACT_AUTHENTICATION_REQ,
            Namespace.DIN_MSG_DEF,
        )


class ContractAuthentication(StateEVCC):
    """
    DIN SPEC state in which ContractAuthenticationRes message is processed.
    Response indicates if authorization is complete.
    EV would resend the request until the timeout is reached/processing
    is completed - whichever is earlier
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.CONTRACT_AUTHENTICATION_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, ContractAuthenticationRes)
        if not msg:
            return

        contract_authentication_res: ContractAuthenticationRes = (
            msg.body.contract_authentication_res
        )

        if self.comm_session.ongoing_timer > 0:
            elapsed_time = time() - self.comm_session.ongoing_timer
            if elapsed_time > TimeoutsShared.V2G_SECC_SEQUENCE_TIMEOUT:
                self.stop_state_machine(
                    "Ongoing timer timed out for " "ContractAuthenticationRes"
                )
                return
        elif self.comm_session.ongoing_timer == -1:
            self.comm_session.ongoing_timer = time()

        # There are two transitions possible in ContractAuthentication state:
        # 1. We stay in the same state until EVSE processing is complete.
        # ie, EVSE returns EVSEProcessing.ONGOING response
        # 2. Move on to next state: ChargeParameterDiscoveryReq
        next_state = None
        next_message: Any = ContractAuthenticationReq()
        timeout = Timeouts.CONTRACT_AUTHENTICATION_REQ

        if contract_authentication_res.evse_processing == EVSEProcessing.FINISHED:
            next_state = ChargeParameterDiscovery
            next_message = await self.build_charge_parameter_discovery_req()
            timeout = Timeouts.CHARGE_PARAMETER_DISCOVERY_REQ

        self.create_next_message(
            next_state,
            next_message,
            timeout,
            Namespace.DIN_MSG_DEF,
        )

    async def build_charge_parameter_discovery_req(self) -> ChargeParameterDiscoveryReq:
        dc_ev_status: DCEVStatus = (
            await self.comm_session.ev_controller.get_dc_ev_status_dinspec()
        )
        dc_charge_params: DCEVChargeParams = (
            await self.comm_session.ev_controller.get_dc_charge_params()
        )
        max_current_limit = dc_charge_params.dc_max_current_limit
        max_voltage_limit = dc_charge_params.dc_max_voltage_limit
        dc_charge_parameter: DCEVChargeParameter = DCEVChargeParameter(
            dc_ev_status=dc_ev_status,
            ev_maximum_current_limit=max_current_limit,
            ev_maximum_voltage_limit=max_voltage_limit,
        )
        return ChargeParameterDiscoveryReq(
            requested_energy_mode=(
                await self.comm_session.ev_controller.get_energy_transfer_mode(
                    Protocol.DIN_SPEC_70121
                )
            ),
            dc_ev_charge_parameter=dc_charge_parameter,
        )


class ChargeParameterDiscovery(StateEVCC):
    """
    DIN SPEC state in which ChargeParameterDiscoveryRes message from EVSE is handled.
    The response received from EVSE would indicate the applicable power output levels
     from the EVSE.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.CHARGE_PARAMETER_DISCOVERY_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, ChargeParameterDiscoveryRes)
        if not msg:
            return

        charge_parameter_discovery_res: ChargeParameterDiscoveryRes = (
            msg.body.charge_parameter_discovery_res
        )
        ev_controller = self.comm_session.ev_controller
        if charge_parameter_discovery_res.evse_processing == EVSEProcessing.FINISHED:
            # Reset the Ongoing timer
            self.comm_session.ongoing_timer = -1
            schedule_id = await ev_controller.process_sa_schedules_dinspec(
                charge_parameter_discovery_res.sa_schedule_list.values
            )

            cable_check_req = CableCheckReq(
                dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
            )

            self.create_next_message(
                CableCheck,
                cable_check_req,
                Timeouts.CABLE_CHECK_REQ,
                Namespace.DIN_MSG_DEF,
            )

            self.comm_session.selected_schedule = schedule_id
            await self.comm_session.ev_controller.enable_charging(True)
        else:
            logger.debug(
                "SECC is still processing the proposed charging "
                "schedule and charge parameters"
            )
            elapsed_time: float = 0
            if self.comm_session.ongoing_timer > 0:
                elapsed_time = time() - self.comm_session.ongoing_timer
                if elapsed_time > TimeoutsShared.V2G_SECC_SEQUENCE_TIMEOUT:
                    self.stop_state_machine(
                        "Ongoing timer timed out for " "ChargeParameterDiscoveryRes"
                    )
                    return
            elif self.comm_session.ongoing_timer == -1:
                self.comm_session.ongoing_timer = time()

            charge_parameter_discovery_req: ChargeParameterDiscoveryReq = (
                await self.build_charge_parameter_discovery_req()
            )

            self.create_next_message(
                None,
                charge_parameter_discovery_req,
                TimeoutsShared.V2G_SECC_SEQUENCE_TIMEOUT,
                Namespace.DIN_MSG_DEF,
            )

    async def build_charge_parameter_discovery_req(self) -> ChargeParameterDiscoveryReq:
        ev_controller = self.comm_session.ev_controller
        dc_charge_params: DCEVChargeParams = await ev_controller.get_dc_charge_params()
        max_current_limit = dc_charge_params.dc_max_current_limit
        max_voltage_limit = dc_charge_params.dc_max_voltage_limit
        dc_charge_parameter: DCEVChargeParameter = DCEVChargeParameter(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
            ev_maximum_current_limit=max_current_limit,
            ev_maximum_voltage_limit=max_voltage_limit,
        )

        charge_parameter_discovery_req = ChargeParameterDiscoveryReq(
            requested_energy_mode=(
                await self.comm_session.ev_controller.get_energy_transfer_mode(
                    Protocol.DIN_SPEC_70121
                )
            ),
            ac_ev_charge_parameter=None,
            dc_ev_charge_parameter=dc_charge_parameter,
        )

        return charge_parameter_discovery_req


class CableCheck(StateEVCC):
    """
    DIN SPEC state in which CableCheckRes message from DIN SPEC is handled.
    An isolation test is performed before charging. The first CableCheckReq send
    would start the isolation test and consecutive tests would indicate if the
    test is ongoing or completed.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.CABLE_CHECK_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, CableCheckRes)
        if not msg:
            return

        cable_check_res: CableCheckRes = msg.body.cable_check_res
        dc_evse_status: DCEVSEStatus = cable_check_res.dc_evse_status
        evse_status_code: DCEVSEStatusCode = dc_evse_status.evse_status_code
        isolation_status: IsolationLevel = dc_evse_status.evse_isolation_status

        if cable_check_res.evse_processing == EVSEProcessing.FINISHED:
            # Reset the Ongoing timer
            self.comm_session.ongoing_timer = -1
            pre_charge_req: PreChargeReq = await self.build_pre_charge_req()
            if (
                evse_status_code == DCEVSEStatusCode.EVSE_READY
                and isolation_status == IsolationLevel.VALID
            ):
                self.create_next_message(
                    PreCharge,
                    pre_charge_req,
                    Timeouts.PRE_CHARGE_REQ,
                    Namespace.DIN_MSG_DEF,
                )
            else:
                self.stop_state_machine("Isolation-Level of EVSE is not Valid")
                return
        else:
            if self.comm_session.ongoing_timer >= 0:
                elapsed_time = time() - self.comm_session.ongoing_timer
                if elapsed_time > Timeouts.V2G_EVCC_CABLE_CHECK_TIMEOUT:
                    self.stop_state_machine("Ongoing timer timed out for CableCheck")
                    return
            elif self.comm_session.ongoing_timer == -1:
                self.comm_session.ongoing_timer = time()

            self.create_next_message(
                None,
                await self.build_cable_check_req(),
                Timeouts.CABLE_CHECK_REQ,
                Namespace.DIN_MSG_DEF,
            )

    async def build_pre_charge_req(self) -> PreChargeReq:
        ev_controller = self.comm_session.ev_controller
        dc_charge_params = await ev_controller.get_dc_charge_params()
        pre_charge_req = PreChargeReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
            ev_target_voltage=dc_charge_params.dc_target_voltage,
            ev_target_current=dc_charge_params.dc_target_current,
        )
        return pre_charge_req

    async def build_cable_check_req(self) -> CableCheckReq:
        ev_controller = self.comm_session.ev_controller
        cable_check_req = CableCheckReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
        )
        return cable_check_req


class PreCharge(StateEVCC):
    """
    DIN SPEC state in which PreChargeRes from EVSE is handled. The intention of this
     message is to help EVSE rampup it's output voltage so that when the contractors
      are closed, there would be minimal inrush of current. The response received
      contains the output voltage of the EVSE that could be used to measure
      satisfactory "prerecharged" voltage after which power delivery can commence.

    The PowerDeliveryReq message that is sent would indicate if the EV is now
     ready to start charging.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.PRE_CHARGE_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, PreChargeRes)
        if not msg:
            return

        pre_charge_res: PreChargeRes = msg.body.pre_charge_res

        if await self.comm_session.ev_controller.is_precharged(
            pre_charge_res.evse_present_voltage
        ):
            self.comm_session.ongoing_timer = -1
            power_delivery_req: PowerDeliveryReq = await self.build_power_delivery_req()
            self.create_next_message(
                PowerDelivery,
                power_delivery_req,
                Timeouts.POWER_DELIVERY_REQ,
                Namespace.DIN_MSG_DEF,
            )
        else:
            logger.debug("EVSE still precharging")
            if self.comm_session.ongoing_timer >= 0:
                elapsed_time = time() - self.comm_session.ongoing_timer
                if elapsed_time > Timeouts.V2G_EVCC_PRE_CHARGE_TIMEOUT:
                    self.stop_state_machine("Precharge timed out")
                    return
            else:
                self.comm_session.ongoing_timer = time()

            pre_charge_req: PreChargeReq = await self.build_pre_charge_req()
            self.create_next_message(
                None,
                pre_charge_req,
                Timeouts.PRE_CHARGE_REQ,
                Namespace.DIN_MSG_DEF,
            )

    async def build_pre_charge_req(self) -> PreChargeReq:
        ev_controller = self.comm_session.ev_controller
        dc_charge_params = await ev_controller.get_dc_charge_params()
        pre_charge_req = PreChargeReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
            ev_target_voltage=dc_charge_params.dc_target_voltage,
            ev_target_current=dc_charge_params.dc_target_current,
        )
        return pre_charge_req

    async def build_power_delivery_req(self) -> PowerDeliveryReq:
        ev_controller = self.comm_session.ev_controller
        power_delivery_req = PowerDeliveryReq(
            ready_to_charge=True,
            charging_profile=None,
            dc_ev_power_delivery_parameter=(
                await ev_controller.get_dc_ev_power_delivery_parameter()
            ),
        )
        return power_delivery_req


class PowerDelivery(StateEVCC):
    """
    DIN SPEC state in which PowerDeliveryRes message is handled.
    The response contains information including information if power will be available.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.POWER_DELIVERY_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, PowerDeliveryRes)
        if not msg:
            return

        if await self.comm_session.ev_controller.continue_charging():
            self.create_next_message(
                CurrentDemand,
                await self.build_current_demand_req(),
                Timeouts.CURRENT_DEMAND_REQ,
                Namespace.DIN_MSG_DEF,
            )
        else:
            await self.comm_session.ev_controller.enable_charging(False)
            self.create_next_message(
                WeldingDetection,
                await self.build_welding_detection_req(),
                Timeouts.WELDING_DETECTION_REQ,
                Namespace.DIN_MSG_DEF,
            )

    async def build_current_demand_req(self) -> CurrentDemandReq:
        ev_controller = self.comm_session.ev_controller
        dc_charge_params = await ev_controller.get_dc_charge_params()
        current_demand_req: CurrentDemandReq = CurrentDemandReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
            ev_target_current=dc_charge_params.dc_target_current,
            ev_max_voltage_limit=dc_charge_params.dc_max_voltage_limit,
            ev_max_current_limit=dc_charge_params.dc_max_current_limit,
            ev_max_power_limit=dc_charge_params.dc_max_power_limit,
            bulk_charging_complete=(await ev_controller.is_bulk_charging_complete()),
            charging_complete=await ev_controller.is_charging_complete(),
            remaining_time_to_full_soc=(
                await ev_controller.get_remaining_time_to_full_soc()
            ),
            remaining_time_to_bulk_soc=(
                await ev_controller.get_remaining_time_to_bulk_soc()
            ),
            ev_target_voltage=dc_charge_params.dc_target_voltage,
        )
        return current_demand_req

    async def build_welding_detection_req(self):
        ev_controller = self.comm_session.ev_controller
        welding_detection_req: WeldingDetectionReq = WeldingDetectionReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec()
        )
        return welding_detection_req


class CurrentDemand(StateEVCC):
    """
    DIN SPEC state in which CurrentDemandRes message is handled.
    EV uses this message to request certain current from the EVSE.
    The target voltage and current are also indicated.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.CURRENT_DEMAND_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, CurrentDemandRes)
        if not msg:
            return

        current_demand_res: CurrentDemandRes = msg.body.current_demand_res
        dc_evse_status: DCEVSEStatus = current_demand_res.dc_evse_status

        # EVSE status must always be EVSE ready
        if dc_evse_status.evse_status_code is not DCEVSEStatusCode.EVSE_READY:
            logger.debug("EVSE Notification received requesting to stop charging.")
            await self.stop_charging()
        elif await self.comm_session.ev_controller.continue_charging():
            try:
                delay: int = (
                    await self.comm_session.ev_controller.charge_loop_delay()
                )  # noqa
                logger.info(f"Next ChargeLoop Req in {delay} seconds")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.info(f"No delay for the next ChargeLoop Req. Reason {e}")
            self.create_next_message(
                None,
                await self.build_current_demand_req(),
                Timeouts.CURRENT_DEMAND_REQ,
                Namespace.DIN_MSG_DEF,
            )
        else:
            logger.debug("EV initiated stop charging.")
            await self.stop_charging()

    async def stop_charging(self):
        ev_controller = self.comm_session.ev_controller
        await ev_controller.stop_charging()
        power_delivery_req = PowerDeliveryReq(
            ready_to_charge=False,
            dc_ev_power_delivery_parameter=(
                await ev_controller.get_dc_ev_power_delivery_parameter()
            ),
        )
        self.create_next_message(
            PowerDelivery,
            power_delivery_req,
            Timeouts.POWER_DELIVERY_REQ,
            Namespace.DIN_MSG_DEF,
        )

        logger.debug("Stopping charging.")

    async def build_current_demand_req(self):
        ev_controller = self.comm_session.ev_controller
        dc_charge_params: DCEVChargeParams = await ev_controller.get_dc_charge_params()
        current_demand_req: CurrentDemandReq = CurrentDemandReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec(),
            ev_target_current=dc_charge_params.dc_target_current,
            ev_max_voltage_limit=dc_charge_params.dc_max_voltage_limit,
            ev_max_current_limit=dc_charge_params.dc_max_current_limit,
            ev_max_power_limit=dc_charge_params.dc_max_power_limit,
            bulk_charging_complete=(await ev_controller.is_bulk_charging_complete()),
            charging_complete=await ev_controller.is_charging_complete(),
            remaining_time_to_full_soc=(
                await ev_controller.get_remaining_time_to_full_soc()
            ),
            remaining_time_to_bulk_soc=(
                await ev_controller.get_remaining_time_to_bulk_soc()
            ),
            ev_target_voltage=dc_charge_params.dc_target_voltage,
        )
        return current_demand_req


class WeldingDetection(StateEVCC):
    """
    DIN SPEC state is which WeldingDetectionRes message from EVSE is handled.
    This is an optional state for EV. A welding detection test is performed
    prior to unlocking the connector. A sequence of independent opening and
    closing of conductors is performed while evaluating the voltage on the
     inlet side. Voltage measurement could be done either on the EV side
     or the EVSE side.

    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.WELDING_DETECTION_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, WeldingDetectionRes)
        if not msg:
            return

        if self.comm_session.ongoing_timer > 0:
            elapsed_time = time() - self.comm_session.ongoing_timer
            if elapsed_time > TimeoutsShared.V2G_SECC_SEQUENCE_TIMEOUT:
                self.stop_state_machine(
                    "Ongoing timer timed out for " "WeldingDetectionRes"
                )
                return
        elif self.comm_session.ongoing_timer == -1:
            self.comm_session.ongoing_timer = time()

        ev_controller = self.comm_session.ev_controller
        next_state = None
        next_request: Any = WeldingDetectionReq(
            dc_ev_status=await ev_controller.get_dc_ev_status_dinspec()
        )
        next_timeout = Timeouts.WELDING_DETECTION_REQ
        if await ev_controller.welding_detection_has_finished():
            next_state = SessionStop
            next_request = SessionStopReq()
            next_timeout = Timeouts.SESSION_STOP_REQ

        self.create_next_message(
            next_state,
            next_request,
            next_timeout,
            Namespace.DIN_MSG_DEF,
        )


class SessionStop(StateEVCC):
    """
    DIN SPEC state in which SessionStopRes message from EVSE is handled.
    SessionStopRes message from EVSE marks the end of the charging session.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.SESSION_STOP_REQ)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        message_exi: bytes = None,
    ):
        msg = self.check_msg_din_spec(message, SessionStopRes)
        if not msg:
            return

        self.comm_session.stop_reason = StopNotification(
            True,
            "Communication session stopped successfully",
            self.comm_session.writer.get_extra_info("peername"),
        )

        self.next_state = Terminate

        return
