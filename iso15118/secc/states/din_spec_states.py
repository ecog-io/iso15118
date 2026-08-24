"""
This module contains the SECC's States used to process the EVCC's incoming
V2GMessage objects of the DIN SPEC 70121 protocol, from SessionSetupReq to
SessionStopReq.
"""

import asyncio
import logging
import time
from typing import Optional, Type, Union

from iso15118.secc.comm_session_handler import SECCCommunicationSession
from iso15118.secc.controller.evse_data import CurrentType
from iso15118.secc.states.secc_state import StateSECC
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.datatypes import PVEVSEPresentCurrent
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
    ResponseCode,
    ServiceDiscoveryReq,
    ServiceDiscoveryRes,
    ServicePaymentSelectionReq,
    ServicePaymentSelectionRes,
    SessionSetupReq,
    SessionSetupRes,
    SessionStopReq,
    SessionStopRes,
    WeldingDetectionReq,
    WeldingDetectionRes,
)
from iso15118.shared.messages.din_spec.datatypes import (
    AuthOptionList,
    ChargeService,
    SAScheduleList,
    ServiceCategory,
    ServiceDetails,
    ServiceID,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.din_spec.timeouts import Timeouts
from iso15118.shared.messages.enums import (
    AuthEnum,
    AuthorizationStatus,
    DCEVErrorCode,
    EVSEProcessing,
    IsolationLevel,
    Namespace,
    Protocol,
)
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.notifications import StopNotification
from iso15118.shared.security import get_random_bytes
from iso15118.shared.states import State, Terminate

logger = logging.getLogger(__name__)


# ============================================================================
# |            SECC STATES - DIN SPEC 70121                                  |
# ============================================================================


class SessionSetup(StateSECC):
    """
    The DIN SPEC state in which the SECC processes a SessionSetupReq
    message from the EVCC.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_EVCC_COMMUNICATIONSETUP_TIMEOUT)

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
        msg = self.check_msg_dinspec(message, [SessionSetupReq])
        if not msg:
            return

        session_setup_req: SessionSetupReq = msg.body.session_setup_req

        # Check session ID. Most likely, we need to create a new one
        session_id: str = get_random_bytes(8).hex().upper()
        if msg.header.session_id == bytes(1).hex():
            # A new charging session is established
            self.response_code = ResponseCode.OK_NEW_SESSION_ESTABLISHED
        elif msg.header.session_id == self.comm_session.session_id:
            # The EV wants to resume the previously paused charging session
            session_id = self.comm_session.session_id
            self.response_code = ResponseCode.OK_OLD_SESSION_JOINED
        else:
            # False session ID from EV, gracefully assigning new session ID
            logger.warning(
                f"EVCC's session ID {msg.header.session_id} "
                f"does not match {self.comm_session.session_id}. "
                f"New session ID {session_id} assigned"
            )
            self.response_code = ResponseCode.OK_NEW_SESSION_ESTABLISHED

        session_setup_res = SessionSetupRes(
            response_code=self.response_code,
            evse_id=await self.comm_session.evse_controller.get_evse_id(
                Protocol.DIN_SPEC_70121
            ),
            datetime_now=time.time(),
        )

        self.comm_session.evcc_id = session_setup_req.evcc_id
        self.comm_session.evse_controller.ev_data_context.evcc_id = (
            session_setup_req.evcc_id
        )
        self.comm_session.session_id = session_id

        self.create_next_message(
            ServiceDiscovery,
            session_setup_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )


class ServiceDiscovery(StateSECC):
    """
    The DIN SPEC state in which the SECC processes a ServiceDiscoveryReq
    message from the EVCC.

    By sending the ServiceDiscoveryReq message, the EVCC triggers the SECC
    to send information about all services offered by the SECC.
    Furthermore, the EVCC can limit for particular services by using the
    service scope and service type elements.
    However, in DIN SPEC, ServiceCategory, if used, must be set to "EVCharging"
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)

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
        msg = self.check_msg_dinspec(message, [ServiceDiscoveryReq])
        if not msg:
            return

        service_discovery_req: ServiceDiscoveryReq = msg.body.service_discovery_req
        service_discovery_res = await self.build_service_discovery_res(
            service_discovery_req.service_category
        )

        self.create_next_message(
            ServicePaymentSelection,
            service_discovery_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )

    async def build_service_discovery_res(
        self, category_filter: ServiceCategory
    ) -> ServiceDiscoveryRes:
        """
        Provides the ServiceDiscoveryRes message with all its services.

        Currently, no filter based on service scope is applied since its string
        value is not standardized in any way. The only filter permitted for DIN SPEC is
        'EVCharging'.

        For payment options in DIN SPEC, only ExternalPayment is allowed.
        """

        self.comm_session.offered_auth_options = [AuthEnum.EIM_V2]
        energy_modes = (
            await self.comm_session.evse_controller.get_supported_energy_transfer_modes(
                Protocol.DIN_SPEC_70121
            )
        )  # noqa: E501
        energy_mode = energy_modes[0]

        service_details = ServiceDetails(
            service_id=ServiceID.CHARGING, service_category=ServiceCategory.CHARGING
        )
        charge_service = ChargeService(
            service_tag=service_details,
            free_service=self.comm_session.config.free_charging_service,
            energy_transfer_type=energy_mode,
        )

        service_discovery_res = ServiceDiscoveryRes(
            response_code=ResponseCode.OK,
            auth_option_list=AuthOptionList(
                auth_options=self.comm_session.offered_auth_options
            ),
            charge_service=charge_service,
        )

        return service_discovery_res


class ServicePaymentSelection(StateSECC):
    """
    State in which ServicePaymentSelectionReq message is handled.
    The request contains information for selected services and how
    the services will be paid for.
    DIN SPEC only supports one payment option - ExternalPayment
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)

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
        msg = self.check_msg_dinspec(message, [ServicePaymentSelectionReq])
        if not msg:
            return

        service_payment_selection_req: ServicePaymentSelectionReq = (
            msg.body.service_payment_selection_req
        )

        if service_payment_selection_req.selected_payment_option != AuthEnum.EIM_V2:
            self.stop_state_machine(
                f"Offered payment option  "
                f"{service_payment_selection_req.selected_payment_option} "
                f"not accepted.",
                message,
                ResponseCode.FAILED_PAYMENT_SELECTION_INVALID,
            )
            return
        self.comm_session.selected_auth_option = AuthEnum.EIM_V2
        if (
            len(service_payment_selection_req.selected_service_list.selected_service)
            == 0
        ):
            self.stop_state_machine(
                "No service was selected",
                message,
                ResponseCode.FAILED_SERVICE_SELECTION_INVALID,
            )
            return

        service_payment_selection_res: ServicePaymentSelectionRes = (
            ServicePaymentSelectionRes(response_code=ResponseCode.OK)
        )
        self.create_next_message(
            ContractAuthentication,
            service_payment_selection_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )


class ContractAuthentication(StateSECC):
    """
    State in which ContractAuthenticationReq message from EV is handled.
    The intention of the message is for the EV to understand if the processing
     of the ContractAuthenticationReq has been completed. The EV shall continue
      to resend this this request until EVSE completes authorisation.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)

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
        msg = self.check_msg_dinspec(message, [ContractAuthenticationReq])
        if not msg:
            return

        current_authorization_status = (
            await self.comm_session.evse_controller.is_authorized()
        )
        evse_processing = EVSEProcessing.ONGOING
        next_state: Type["State"] = None
        if (
            current_authorization_status.authorization_status
            == AuthorizationStatus.ACCEPTED
        ):
            evse_processing = EVSEProcessing.FINISHED
            next_state = ChargeParameterDiscovery

        contract_authentication_res: ContractAuthenticationRes = (
            ContractAuthenticationRes(
                response_code=ResponseCode.OK, evse_processing=evse_processing
            )
        )

        self.create_next_message(
            next_state,
            contract_authentication_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )


class ChargeParameterDiscovery(StateSECC):
    """
    State in which ChargeParamterDiscoveryReq request from EV is handled.
    The incoming request contains the charging parameters for the EV.
    The response message contains EVSE's status information and current
     power output limits.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)

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
        msg = self.check_msg_dinspec(message, [ChargeParameterDiscoveryReq])
        if not msg:
            return

        charge_parameter_discovery_req: ChargeParameterDiscoveryReq = (
            msg.body.charge_parameter_discovery_req
        )

        if charge_parameter_discovery_req.requested_energy_mode not in (
            await self.comm_session.evse_controller.get_supported_energy_transfer_modes(
                Protocol.DIN_SPEC_70121
            )
        ):
            self.stop_state_machine(
                f"{charge_parameter_discovery_req.requested_energy_mode} not "
                f"offered as energy transfer mode",
                message,
                ResponseCode.FAILED_WRONG_ENERGY_TRANSFER_MODE,
            )
            return
        self.comm_session.evse_controller.ev_data_context.selected_energy_mode = (
            charge_parameter_discovery_req.requested_energy_mode
        )

        evse_data_context = self.comm_session.evse_controller.evse_data_context
        ev_data_context = self.comm_session.evse_controller.ev_data_context
        ev_data_context.update_dc_charge_parameters(
            charge_parameter_discovery_req.dc_ev_charge_parameter
        )
        await self.comm_session.evse_controller.send_rated_limits()
        dc_evse_charge_params = (
            await self.comm_session.evse_controller.get_dc_charge_parameters_dinspec()  # noqa
        )
        evse_data_context.current_type = CurrentType.DC

        sa_schedule_list = (
            await self.comm_session.evse_controller.get_sa_schedule_list_dinspec(
                None, 0
            )
        )

        evse_processing: EVSEProcessing = EVSEProcessing.ONGOING
        next_state: Type["State"] = None
        sa_schedules = None
        if sa_schedule_list:
            evse_processing = EVSEProcessing.FINISHED
            next_state = CableCheck
            sa_schedules = SAScheduleList(values=sa_schedule_list)

        charge_parameter_discovery_res: ChargeParameterDiscoveryRes = (
            ChargeParameterDiscoveryRes(
                response_code=ResponseCode.OK,
                evse_processing=evse_processing,
                sa_schedule_list=sa_schedules,
                dc_charge_parameter=dc_evse_charge_params,
            )
        )

        self.create_next_message(
            next_state,
            charge_parameter_discovery_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )


class CableCheck(StateSECC):
    """
    State is which CableCheckReq from EV is handled.
    In this state, an isolation test is performed - which is
    required before DC charging.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.contactors_closed: bool = False
        self.cable_check_started: bool = False

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
        # According to the standard SessionStop is not expected here.
        #  But Tesla sends SessionStop here if SOC is already reached.
        msg = self.check_msg_dinspec(message, [CableCheckReq, SessionStopReq])
        if not msg:
            return

        if msg.body.session_stop_req:
            await SessionStop(self.comm_session).process_message(message, message_exi)
            return

        cable_check_req: CableCheckReq = msg.body.cable_check_req

        if cable_check_req.dc_ev_status.ev_error_code != DCEVErrorCode.NO_ERROR:
            self.stop_state_machine(
                f"{cable_check_req.dc_ev_status} "
                "has Error"
                f"{cable_check_req.dc_ev_status}",
                message,
                ResponseCode.FAILED,
            )
            return

        evse_processing: EVSEProcessing = EVSEProcessing.ONGOING
        response_code: ResponseCode = ResponseCode.OK
        next_state = None

        if not self.cable_check_started:
            await self.comm_session.evse_controller.start_cable_check()
            self.cable_check_started = True

        if self.contactors_closed:
            isolation_level = (
                await self.comm_session.evse_controller.get_cable_check_status()
            )  # noqa

            evse_processing = EVSEProcessing.ONGOING
            next_state = None
            if isolation_level in [
                IsolationLevel.VALID,
                IsolationLevel.WARNING,
            ]:
                if isolation_level == IsolationLevel.WARNING:
                    logger.warning(
                        "Isolation resistance measured by EVSE is in Warning-Range"
                    )
                evse_processing = EVSEProcessing.FINISHED
                next_state = PreCharge
            elif isolation_level in [
                IsolationLevel.FAULT,
                IsolationLevel.INVALID,
            ]:
                self.stop_state_machine(
                    f"Isolation Failure: {isolation_level}",
                    message,
                    ResponseCode.FAILED,
                )
                return
        else:
            # Requirement in 6.4.3.106 of the IEC 61851-23
            # Any relays in the DC output circuit of the DC station shall
            # be closed during the insulation test
            # If None is returned, then contactor close operation is ongoing.
            contactors_closed_for_cable_check: Optional[bool] = (
                await self.comm_session.evse_controller.is_contactor_closed()
            )

            if contactors_closed_for_cable_check is not None:
                if contactors_closed_for_cable_check:
                    self.contactors_closed = True
                else:
                    self.stop_state_machine(
                        "Contactor didnt close for Cable Check",
                        message,
                        ResponseCode.FAILED,
                    )
                    return

        self.comm_session.evse_controller.ev_data_context.present_soc = (
            cable_check_req.dc_ev_status.ev_ress_soc
        )

        # [V2G-DC-418] Stay in CableCheck state until EVSEProcessing is complete.
        # Until EVSEProcessing is completed, EV will send identical
        # CableCheckReq message.
        cable_check_res: CableCheckRes = CableCheckRes(
            response_code=response_code,
            dc_evse_status=await self.comm_session.evse_controller.get_dc_evse_status(),
            evse_processing=evse_processing,
        )

        self.create_next_message(
            next_state,
            cable_check_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )


class PreCharge(StateSECC):
    """
    State in which PreChargeReq message from EV is handled.
    The message is to help EVSE ramp up EVSE output voltage to EV RESS voltage.
    This helps minimize the inrush current when the contactors of the EV are closed.
    We stay in this state after PreCharge; expecting a PowerDeliveryReq
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_pre_charge_req = True

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
        msg = self.check_msg_dinspec(
            message, [PreChargeReq, PowerDeliveryReq], self.expecting_pre_charge_req
        )
        if not msg:
            return

        if msg.body.power_delivery_req:
            await PowerDelivery(self.comm_session).process_message(message, message_exi)
            return

        precharge_req: PreChargeReq = msg.body.pre_charge_req

        if precharge_req.dc_ev_status.ev_error_code != DCEVErrorCode.NO_ERROR:
            self.stop_state_machine(
                f"{precharge_req.dc_ev_status} "
                "has Error"
                f"{precharge_req.dc_ev_status}",
                message,
                ResponseCode.FAILED,
            )
            return

        ev_data_context = self.comm_session.evse_controller.ev_data_context
        ev_data_context.update_pre_charge_parameters(precharge_req)

        # for the PreCharge phase, the requested current must be < 2 A
        # (maximum inrush current according to CC.5.2 in IEC61851 -23)
        present_current = (
            await self.comm_session.evse_controller.get_evse_present_current(
                Protocol.DIN_SPEC_70121
            )
        )

        if isinstance(present_current, PVEVSEPresentCurrent):
            present_current_in_a = present_current.get_decimal_value()
            target_current_in_a = ev_data_context.target_current
        else:
            self.stop_state_machine(
                "Error reading EVSE Present Current."
                f"Wrong type: {type(present_current)}",
                message,
                ResponseCode.FAILED,
            )
            return

        if present_current_in_a > 2 or target_current_in_a > 2:
            self.stop_state_machine(
                "Target current or present current too high in state Precharge",
                message,
                ResponseCode.FAILED,
            )
            return

        # Set precharge voltage in every loop.
        # Because there are EVs that send a wrong Precharge-Voltage
        # in the first message (example: BMW i3 Rex 2018)
        try:
            await self.comm_session.evse_controller.send_charging_command(
                ev_data_context.target_voltage,
                ev_data_context.target_current,
                is_precharge=True,
            )
        except asyncio.TimeoutError:
            self.stop_state_machine(
                "Error sending targets to charging station in charging loop.",
                message,
                ResponseCode.FAILED,
            )
            return

        dc_charger_state = await self.comm_session.evse_controller.get_dc_evse_status()
        evse_present_voltage = (
            await self.comm_session.evse_controller.get_evse_present_voltage(
                Protocol.DIN_SPEC_70121
            )
        )

        precharge_res = PreChargeRes(
            response_code=ResponseCode.OK,
            dc_evse_status=dc_charger_state,
            evse_present_voltage=evse_present_voltage,
        )

        self.create_next_message(
            None,
            precharge_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )

        self.expecting_pre_charge_req = False


class PowerDelivery(StateSECC):
    """
    PowerDelivery state where SECC processes a PowerDeliveryReq
    Three possible requests in this state:
    1. PowerDeliveryReq
    2. SessionStop
    3. WeldingDetection
    Ready_to_charge field in the PowerDeliveryReq indicates if the EVCC is
    ready to start charging. Once this field is set to false, the next expected state
     is either WeldingDetection/SessionStop.
    WeldingDetectionReq is an optional message from the EVCC.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_power_delivery_req = True

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
        msg = self.check_msg_dinspec(
            message,
            [
                PowerDeliveryReq,
                SessionStopReq,
                WeldingDetectionReq,
            ],
            self.expecting_power_delivery_req,
        )
        if not msg:
            return

        if msg.body.session_stop_req:
            await SessionStop(self.comm_session).process_message(message, message_exi)
            return

        if msg.body.welding_detection_req:
            await WeldingDetection(self.comm_session).process_message(
                message, message_exi
            )
            return

        power_delivery_req: PowerDeliveryReq = msg.body.power_delivery_req

        self.comm_session.evse_controller.ev_data_context.present_soc = (
            power_delivery_req.dc_ev_power_delivery_parameter.dc_ev_status.ev_ress_soc
        )

        logger.debug(
            f"ChargeProgress set to "
            f"{'Ready' if power_delivery_req.ready_to_charge else 'Stopping'}"
        )

        next_state: Optional[Type[State]] = None
        if power_delivery_req.ready_to_charge:
            # The High Level Controlled Charging concept (HLC-C), is
            # only introduced in section 8.7.4 of the ISO 15118-2, and says that the
            # EV enters into HLC-C once PowerDeliveryRes(ResponseCode=OK)
            # is sent with a ChargeProgress=Start.
            # This concept is also introduced in ISO 15118-20 in section 8.5.6
            # For reasons of consistency, we also applied this concept in the DIN
            await self.comm_session.evse_controller.set_hlc_charging(True)
            next_state = CurrentDemand
            self.comm_session.charge_progress_started = True
        else:
            logger.debug(
                "PowerDeliveryReq ready_to_charge field set to false. "
                "Stay in this state and expect "
                "WeldingDetectionReq/SessionStopReq"
            )
            next_state = None

            # According to section 8.7.4 in ISO 15118-2, the EV is out of the HLC-C
            # (High Level Controlled Charging) once PowerDeliveryRes(ResponseCode=OK)
            # is sent with a ChargeProgress=Stop
            # Updates the upper layer with the info if the EV is under HLC-C
            await self.comm_session.evse_controller.set_hlc_charging(False)

            # 1st a controlled stop is performed (specially important for DC charging)
            # later on we may also need here some feedback on stopping the charger
            await self.comm_session.evse_controller.stop_charger()
            # 2nd once the energy transfer is properly interrupted,
            # the contactor(s) may open
            if not await self.comm_session.evse_controller.is_contactor_opened():
                self.stop_state_machine(
                    "Contactor didnt open",
                    message,
                    ResponseCode.FAILED,
                )
                return

        dc_evse_status = await self.comm_session.evse_controller.get_dc_evse_status()
        power_delivery_res = PowerDeliveryRes(
            response_code=ResponseCode.OK,
            dc_evse_status=dc_evse_status,
        )

        self.create_next_message(
            next_state,
            power_delivery_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )

        self.expecting_power_delivery_req = False


class CurrentDemand(StateSECC):
    """
    DINSPEC state in which CurrentDemandReq message from EV is handled.
    The incoming request contains certain current from EVSE.
    Target current and voltage are also specified in the incoming request.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_current_demand_req = True

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
        msg = self.check_msg_dinspec(
            message,
            [CurrentDemandReq, PowerDeliveryReq],
            self.expecting_current_demand_req,
        )
        if not msg:
            return

        if msg.body.power_delivery_req:
            await PowerDelivery(self.comm_session).process_message(message, message_exi)
            return

        current_demand_req: CurrentDemandReq = msg.body.current_demand_req

        ev_data_context = self.comm_session.evse_controller.ev_data_context
        ev_data_context.update_charge_loop_parameters(current_demand_req)

        try:
            await self.comm_session.evse_controller.send_charging_command(
                ev_data_context.target_voltage,
                ev_data_context.target_current,
            )
        except asyncio.TimeoutError:
            self.stop_state_machine(
                "Error sending targets to charging station in charging loop.",
                message,
                ResponseCode.FAILED,
            )
            return

        current_demand_res: CurrentDemandRes = CurrentDemandRes(
            response_code=ResponseCode.OK,
            dc_evse_status=await self.comm_session.evse_controller.get_dc_evse_status(),
            evse_present_voltage=(
                await self.comm_session.evse_controller.get_evse_present_voltage(
                    Protocol.DIN_SPEC_70121
                )
            ),
            evse_present_current=(
                await self.comm_session.evse_controller.get_evse_present_current(
                    Protocol.DIN_SPEC_70121
                )
            ),
            evse_current_limit_achieved=current_demand_req.charging_complete,
            evse_voltage_limit_achieved=(
                await self.comm_session.evse_controller.is_evse_voltage_limit_achieved()
            ),
            evse_power_limit_achieved=(
                await self.comm_session.evse_controller.is_evse_power_limit_achieved()
            ),
            evse_max_current_limit=(
                await self.comm_session.evse_controller.get_evse_max_current_limit()
            ),
            evse_max_voltage_limit=(
                await self.comm_session.evse_controller.get_evse_max_voltage_limit()
            ),
            evse_max_power_limit=(
                await self.comm_session.evse_controller.get_evse_max_power_limit()
            ),
        )
        await self.comm_session.evse_controller.send_display_params()
        self.create_next_message(
            None,
            current_demand_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )

        self.expecting_current_demand_req = False


class WeldingDetection(StateSECC):
    """
    The DIN SPEC state in which the SECC processes an WeldingDetectionReq message
     from the EV. The EV sends the Welding Detection Request to obtain from the
      EVSE the voltage value measured by the EVSE at its output. This state is
      optional for EV side but mandatory for EVSE.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expect_welding_detection = True

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
        msg = self.check_msg_dinspec(
            message,
            [WeldingDetectionReq, SessionStopReq],
            self.expect_welding_detection,
        )
        if not msg:
            return

        if msg.body.session_stop_req:
            await SessionStop(self.comm_session).process_message(message, message_exi)
            return

        self.expect_welding_detection = False
        self.create_next_message(
            None,
            await self.build_welding_detection_response(),
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )

    async def build_welding_detection_response(self) -> WeldingDetectionRes:
        return WeldingDetectionRes(
            response_code=ResponseCode.OK,
            dc_evse_status=await self.comm_session.evse_controller.get_dc_evse_status(),
            evse_present_voltage=(
                await self.comm_session.evse_controller.get_evse_present_voltage(
                    Protocol.DIN_SPEC_70121
                )
            ),
        )


class SessionStop(StateSECC):
    """
    DIN SPEC state in which SessionStopReq message from EV is handled.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)

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
        msg = self.check_msg_dinspec(message, [SessionStopReq])
        if not msg:
            return

        self.comm_session.stop_reason = StopNotification(
            True,
            "Communication session stopped successfully",
            self.comm_session.writer.get_extra_info("peername"),
        )

        self.create_next_message(
            Terminate,
            SessionStopRes(response_code=ResponseCode.OK),
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.DIN_MSG_DEF,
        )
