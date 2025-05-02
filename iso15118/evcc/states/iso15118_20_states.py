"""
This module contains the EVCC's States used to process the SECC's incoming
V2GMessage objects of the ISO 15118-20 protocol, from SessionSetupRes to
SessionStopRes.
"""

import asyncio
import logging
import time
from typing import Any, List, Union, cast

from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
from iso15118.evcc.states.evcc_state import StateEVCC
from iso15118.shared.exceptions import PrivateKeyReadError
from iso15118.shared.exi_codec import EXI
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.enums import (
    AuthEnum,
    ControlMode,
    ISOV20PayloadTypes,
    Namespace,
    ParameterName,
    ServiceV20,
    SessionStopAction,
)
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeLoopReq,
    ACChargeLoopRes,
    ACChargeParameterDiscoveryReq,
    ACChargeParameterDiscoveryRes,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationReq,
    AuthorizationRes,
    AuthorizationSetupReq,
    AuthorizationSetupRes,
    CertificateInstallationReq,
    ChannelSelection,
    ChargingSession,
    EIMAuthReqParams,
    MatchedService,
    PnCAuthReqParams,
    PowerDeliveryReq,
    PowerDeliveryRes,
    ScheduleExchangeReq,
    ScheduleExchangeRes,
    SelectedService,
    ServiceDetailReq,
    ServiceDetailRes,
    ServiceDiscoveryReq,
    ServiceDiscoveryRes,
    ServiceSelectionReq,
    ServiceSelectionRes,
    SessionSetupRes,
    SessionStopReq,
    SessionStopRes,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    EVSENotification,
    MessageHeader,
    Processing,
    RationalNumber,
    RootCertificateIDList,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GRequest,
)
from iso15118.shared.messages.iso15118_20.dc import (
    BPTDynamicDCChargeLoopReqParams,
    BPTScheduledDCChargeLoopReqParams,
    DCCableCheckReq,
    DCCableCheckRes,
    DCChargeLoopReq,
    DCChargeLoopRes,
    DCChargeParameterDiscoveryReq,
    DCChargeParameterDiscoveryRes,
    DCPreChargeReq,
    DCPreChargeRes,
    DCWeldingDetectionReq,
    DynamicDCChargeLoopReqParams,
    ScheduledDCChargeLoopReqParams,
)
from iso15118.shared.messages.iso15118_20.timeouts import Timeouts
from iso15118.shared.messages.timeouts import Timeouts as TimeoutsShared
from iso15118.shared.messages.xmldsig import X509IssuerSerial
from iso15118.shared.notifications import StopNotification
from iso15118.shared.security import (
    CertPath,
    KeyEncoding,
    KeyPasswordPath,
    KeyPath,
    create_signature,
    get_cert_issuer_serial,
    load_cert_chain,
    load_priv_key,
)
from iso15118.shared.states import Terminate

logger = logging.getLogger(__name__)


# ============================================================================
# |    COMMON EVCC STATES (FOR ALL ENERGY TRANSFER MODES) - ISO 15118-20     |
# ============================================================================


class SessionSetup(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a SessionSetupRes from
    the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        # TODO: less the time used for waiting for and processing the
        #       SDPResponse and SupportedAppProtocolRes
        super().__init__(comm_session, Timeouts.V2G_EVCC_COMMUNICATION_SETUP_TIMEOUT)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, SessionSetupRes)
        if not msg:
            return

        session_setup_res: SessionSetupRes = cast(SessionSetupRes, msg)

        self.comm_session.session_id = msg.header.session_id
        self.comm_session.evse_id = session_setup_res.evse_id

        auth_setup_req = AuthorizationSetupReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id, timestamp=time.time()
            )
        )

        self.create_next_message(
            AuthorizationSetup,
            auth_setup_req,
            Timeouts.AUTHORIZATION_SETUP_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )


class AuthorizationSetup(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes an AuthorizationSetupRes
    from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.AUTHORIZATION_SETUP_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, AuthorizationSetupRes)
        if not msg:
            return

        auth_setup_res: AuthorizationSetupRes = cast(AuthorizationSetupRes, msg)
        signature = None

        if (
            auth_setup_res.cert_install_service
            and await self.comm_session.ev_controller.is_cert_install_needed()
        ):
            # TODO: Find a more generic way to search for all available
            #       V2GRootCA certificates
            issuer, serial = get_cert_issuer_serial(CertPath.V2G_ROOT_DER)

            oem_prov_cert_chain = load_cert_chain(
                protocol=self.comm_session.protocol,
                leaf_path=CertPath.OEM_LEAF_DER,
                sub_ca2_path=CertPath.OEM_SUB_CA2_DER,
                sub_ca1_path=CertPath.OEM_SUB_CA1_DER,
                id="id1",
            )

            # TODO: Check how a signature in ISO 15118-20 differs from an
            #       ISO 15118-2 signature
            try:
                signature = create_signature(
                    [
                        (
                            "id1",
                            EXI().to_exi(
                                oem_prov_cert_chain, Namespace.ISO_V20_COMMON_MSG
                            ),
                        )
                    ],
                    load_priv_key(
                        KeyPath.OEM_LEAF_PEM,
                        KeyEncoding.PEM,
                        KeyPasswordPath.OEM_LEAF_KEY_PASSWORD,
                    ),
                )

                cert_install_req = CertificateInstallationReq(
                    header=MessageHeader(
                        session_id=self.comm_session.session_id,
                        timestamp=time.time(),
                        signature=signature,
                    ),
                    oem_prov_cert_chain=oem_prov_cert_chain,
                    root_cert_id_list=RootCertificateIDList(
                        root_cert_ids=[
                            X509IssuerSerial(
                                x509_issuer_name=issuer, x509_serial_number=serial
                            )
                        ]
                    ),
                    max_contract_cert_chains=self.comm_session.config.max_contract_certs,  # noqa: E501
                    prioritized_emaids=await self.comm_session.ev_controller.get_prioritised_emaids(),  # noqa: E501
                )

                self.create_next_message(
                    CertificateInstallation,
                    cert_install_req,
                    Timeouts.CERTIFICATE_INSTALLATION_REQ,
                    Namespace.ISO_V20_COMMON_MSG,
                )
                return
            except PrivateKeyReadError as exc:
                logger.warning(
                    "PrivateKeyReadError occurred while trying to create "
                    "signature for CertificateInstallationReq. Falling back to sending "
                    f"AuthorizationReq instead.\n{exc}"
                )

        eim_params, pnc_params = None, None
        if AuthEnum.PNC in auth_setup_res.auth_services:
            # TODO: Check if several contract certificates are in place and
            #      if the SECC sent a list of supported providers to pre-
            #      select the contract certificate(s) that work at this SECC
            pnc_params = PnCAuthReqParams(
                gen_challenge=auth_setup_res.pnc_as_res.gen_challenge,
                contract_cert_chain=load_cert_chain(
                    protocol=self.comm_session.protocol,
                    leaf_path=CertPath.CONTRACT_LEAF_DER,
                    sub_ca2_path=CertPath.MO_SUB_CA2_DER,
                    sub_ca1_path=CertPath.MO_SUB_CA1_DER,
                ),
                id="id1",
            )

            # TODO: Need a signature for ISO 15118-20, not ISO 15118-2
            pnc_params_tuple = (
                pnc_params.id,
                EXI().to_exi(pnc_params, Namespace.ISO_V20_COMMON_MSG),
            )
            elements_to_sign = [pnc_params_tuple]
            try:
                # The private key to be used for the signature
                signature_key = load_priv_key(
                    KeyPath.CONTRACT_LEAF_PEM,
                    KeyEncoding.PEM,
                    KeyPasswordPath.CONTRACT_LEAF_KEY_PASSWORD,
                )
                signature = create_signature(elements_to_sign, signature_key)
            except PrivateKeyReadError as exc:
                logger.warning(
                    "PrivateKeyReadError occurred while trying to create "
                    "signature for PnC_AReqAuthorizationMode. Falling back to EIM "
                    f"identification mode.\n{exc}"
                )
                pnc_params = None
                eim_params = EIMAuthReqParams()
        else:
            eim_params = EIMAuthReqParams()

        auth_req = AuthorizationReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
                signature=signature,
            ),
            selected_auth_service=AuthEnum.PNC if pnc_params else AuthEnum.EIM,
            pnc_params=pnc_params,
            eim_params=eim_params,
        )

        # Caching this in case, we need to loop AuthorizationReq/Res
        # [V2G20-1582] If EVSEProcessing is set to Ongoing, EVCC shall send another
        # unaltered AuthorizationReq (with the exception of timestamp)
        self.comm_session.authorization_req_message = auth_req
        self.create_next_message(
            Authorization,
            auth_req,
            Timeouts.AUTHORIZATION_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )


class CertificateInstallation(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a
    CertificateInstallationRes from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.CERTIFICATE_INSTALLATION_REQ)

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
        raise NotImplementedError("CertificateInstallation not yet implemented")


class Authorization(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes an AuthorizationRes
    from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.AUTHORIZATION_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, AuthorizationRes)
        if not msg:
            return

        auth_res: AuthorizationRes = cast(AuthorizationRes, msg)
        # TODO Act upon the response codes and evse_processing value of auth_res
        #      (and delete the # noqa: F841)
        # TODO: V2G20-2221 demands to send CertificateInstallationReq if necessary

        if auth_res.evse_processing == Processing.FINISHED:
            # Reset the Ongoing timer
            self.comm_session.ongoing_timer = -1

            service_discovery_req = ServiceDiscoveryReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                )
                # To limit the list of requested VAS services, set supported_service_ids
            )

            self.create_next_message(
                ServiceDiscovery,
                service_discovery_req,
                Timeouts.SERVICE_DISCOVERY_REQ,
                Namespace.ISO_V20_COMMON_MSG,
                ISOV20PayloadTypes.MAINSTREAM,
            )
        else:
            logger.debug("SECC is still processing the Authorization")
            elapsed_time: float = 0
            if self.comm_session.ongoing_timer >= 0:
                elapsed_time = time.time() - self.comm_session.ongoing_timer
                if elapsed_time > TimeoutsShared.V2G_EVCC_ONGOING_TIMEOUT:
                    debug_message = "Ongoing timer timed out for 'AuthorizationRes'"
                    self.comm_session.charging_session_stop_v20 = (
                        ChargingSession.TERMINATE
                    )
                    session_stop_req = SessionStopReq(
                        header=MessageHeader(
                            session_id=self.comm_session.session_id,
                            timestamp=time.time(),
                        ),
                        charging_session=self.comm_session.charging_session_stop_v20,
                        ev_termination_explanation=debug_message,
                    )
                    self.create_next_message(
                        SessionStop,
                        session_stop_req,
                        Timeouts.SESSION_STOP_REQ,
                        Namespace.ISO_V20_COMMON_MSG,
                        ISOV20PayloadTypes.MAINSTREAM,
                    )
                    return
            else:
                self.comm_session.ongoing_timer = time.time()

            auth_req = AuthorizationReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                    signature=(
                        self.comm_session.authorization_req_message.header.signature
                    ),
                ),
                selected_auth_service=(
                    self.comm_session.authorization_req_message.selected_auth_service
                ),
                pnc_params=self.comm_session.authorization_req_message.pnc_params,
                eim_params=self.comm_session.authorization_req_message.eim_params,
            )

            self.create_next_message(
                Authorization,
                auth_req,
                min(
                    Timeouts.AUTHORIZATION_REQ,
                    TimeoutsShared.V2G_EVCC_ONGOING_TIMEOUT - elapsed_time,
                ),
                Namespace.ISO_V20_COMMON_MSG,
                ISOV20PayloadTypes.MAINSTREAM,
            )


class ServiceDiscovery(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a ServiceDiscoveryRes
    from the SECC.
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
        msg: V2GMessageV20 = self.check_msg_v20(message, ServiceDiscoveryRes)
        if not msg:
            return

        service_discovery_res: ServiceDiscoveryRes = cast(ServiceDiscoveryRes, msg)

        self.comm_session.service_renegotiation_supported = (
            service_discovery_res.service_renegotiation_supported
        )

        req_energy_services: List[ServiceV20] = (
            await self.comm_session.ev_controller.get_supported_energy_services()
        )

        for energy_service in service_discovery_res.energy_service_list.services:
            for requested_energy_service in req_energy_services:
                if requested_energy_service.id == energy_service.service_id:
                    self.comm_session.matched_services_v20.append(
                        MatchedService(
                            service=ServiceV20.get_by_id(energy_service.service_id),
                            is_energy_service=True,
                            is_free=energy_service.free_service,
                            # Parameter sets are available with ServiceDetailRes
                            parameter_sets=[],
                        )
                    )
                    self.comm_session.service_details_to_request.append(
                        energy_service.service_id
                    )

        if not self.comm_session.matched_services_v20:
            self.comm_session.charging_session_stop_v20 = ChargingSession.TERMINATE
            termination_reason: str = "WrongServiceID"
            logger.info(f"Requesting SessionStop. Reason: {termination_reason} ")
            session_stop_req = SessionStopReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                charging_session=ChargingSession.TERMINATE,
                # See "3.5.2. Error handling" in CharIN Implementation Guide for DC BPT
                ev_termination_code=1,
                ev_termination_explanation=termination_reason,
            )

            self.create_next_message(
                SessionStop,
                session_stop_req,
                Timeouts.SESSION_STOP_REQ,
                Namespace.ISO_V20_COMMON_MSG,
                ISOV20PayloadTypes.MAINSTREAM,
            )
            return

        if service_discovery_res.vas_list:
            for vas_service in service_discovery_res.vas_list.services:
                self.comm_session.matched_services_v20.append(
                    MatchedService(
                        service=ServiceV20.get_by_id(vas_service.service_id),
                        is_energy_service=False,
                        is_free=vas_service.free_service,
                        # Parameter sets are available with ServiceDetailRes
                        parameter_sets=[],
                    )
                )

                # If you want to request service details for a specific value-added
                # service, then use these lines of code:
                # self.comm_session.service_details_to_request.append(
                #     vas_service.service_id
                # )

        service_detail_req = ServiceDetailReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            service_id=self.comm_session.service_details_to_request.pop(),
        )

        self.create_next_message(
            ServiceDetail,
            service_detail_req,
            Timeouts.SERVICE_DETAIL_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )


class ServiceDetail(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a ServiceDetailRes
    from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.SERVICE_DETAIL_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, ServiceDetailRes)
        if not msg:
            return

        service_detail_res: ServiceDetailRes = cast(ServiceDetailRes, msg)

        self.store_parameter_sets(service_detail_res)

        # Each ServiceDetailReq returns ParameterSet for a specified service.
        # Send ServiceDetailReq to EVSE if there are more parameter sets
        # to be requested
        if self.comm_session.service_details_to_request:
            service_detail_req = ServiceDetailReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                service_id=self.comm_session.service_details_to_request.pop(),
            )

            self.create_next_message(
                ServiceDetail,
                service_detail_req,
                Timeouts.SERVICE_DETAIL_REQ,
                Namespace.ISO_V20_COMMON_MSG,
                ISOV20PayloadTypes.MAINSTREAM,
            )
            return

        self.comm_session.selected_energy_service = (
            await self.comm_session.ev_controller.select_energy_service_v20(
                self.comm_session.matched_services_v20
            )
        )

        if not self.is_control_mode_set():
            session_stop_req = SessionStopReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                charging_session=ChargingSession.TERMINATE,
                ev_termination_explanation="Control mode parameter missing",
            )

            self.create_next_message(
                SessionStop,
                session_stop_req,
                Timeouts.SESSION_STOP_REQ,
                Namespace.ISO_V20_COMMON_MSG,
                ISOV20PayloadTypes.MAINSTREAM,
            )
            return

        service_selection_req: ServiceSelectionReq = (
            await self.build_service_selection_req()
        )

        self.create_next_message(
            ServiceSelection,
            service_selection_req,
            Timeouts.SERVICE_SELECTION_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )

    async def build_service_selection_req(self) -> ServiceSelectionReq:
        selected_energy_service = SelectedService(
            service_id=self.comm_session.selected_energy_service.service_id,
            parameter_set_id=self.comm_session.selected_energy_service.parameter_set_id,
        )

        self.comm_session.selected_vas_list_v20 = (
            await self.comm_session.ev_controller.select_vas_services_v20(
                self.comm_session.matched_services_v20
            )
        )

        selected_vas_list: List[SelectedService] = []
        for vas in self.comm_session.selected_vas_list_v20:
            selected_vas_list.append(
                SelectedService(
                    service_id=vas.service.id, parameter_set_id=vas.parameter_set.id
                )
            )

        service_selection_req = ServiceSelectionReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            selected_energy_service=selected_energy_service,
            selected_vas_list=selected_vas_list if selected_vas_list else None,
        )

        return service_selection_req

    def is_control_mode_set(self) -> bool:
        control_mode_set = False
        if self.comm_session.selected_energy_service:
            parameter_set = self.comm_session.selected_energy_service.parameter_set
            for param in parameter_set.parameters:
                if param.name == ParameterName.CONTROL_MODE:
                    self.comm_session.control_mode = ControlMode(param.int_value)
                    logger.info(
                        f"Selected Control Mode: {self.comm_session.control_mode}"
                    )
                    control_mode_set = True
        return control_mode_set

    def store_parameter_sets(self, service_detail_res: ServiceDetailRes):
        """
        Saves the parameter sets associated with the service id requested
        Args:
            service_detail_res: Service Detail Response for the service requested

        Returns:

        """
        for service in self.comm_session.matched_services_v20:
            # Save the parameter sets for a particular service
            if service.service.id == service_detail_res.service_id:
                service.parameter_sets = (
                    service_detail_res.service_parameter_list.parameter_sets
                )


class ServiceSelection(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a ServiceSelectionRes
    from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.SERVICE_SELECTION_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, ServiceSelectionRes)
        if not msg:
            return

        # TODO Act upon the possible negative response codes in service_selection_res

        next_req: Any = None
        if self.comm_session.selected_energy_service.service in (
            ServiceV20.AC,
            ServiceV20.AC_BPT,
        ):
            ac_params, bpt_ac_params = None, None
            self.comm_session.selected_charging_type_is_ac = True
            if self.comm_session.selected_energy_service.service == ServiceV20.AC:
                ac_params = await self.comm_session.ev_controller.get_charge_params_v20(
                    self.comm_session.selected_energy_service
                )
            else:
                bpt_ac_params = (
                    await self.comm_session.ev_controller.get_charge_params_v20(
                        self.comm_session.selected_energy_service
                    )
                )

            next_req = ACChargeParameterDiscoveryReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                ac_params=ac_params,
                bpt_ac_params=bpt_ac_params,
            )

            self.create_next_message(
                ACChargeParameterDiscovery,
                next_req,
                Timeouts.CHARGE_PARAMETER_DISCOVERY_REQ,
                Namespace.ISO_V20_AC,
                ISOV20PayloadTypes.AC_MAINSTREAM,
            )
        elif self.comm_session.selected_energy_service.service in (
            ServiceV20.DC,
            ServiceV20.DC_BPT,
        ):
            dc_params, bpt_dc_params = None, None
            self.comm_session.selected_charging_type_is_ac = False
            if self.comm_session.selected_energy_service.service == ServiceV20.DC:
                dc_params = await self.comm_session.ev_controller.get_charge_params_v20(
                    self.comm_session.selected_energy_service
                )
            else:
                bpt_dc_params = (
                    await self.comm_session.ev_controller.get_charge_params_v20(
                        self.comm_session.selected_energy_service
                    )
                )

            next_req = DCChargeParameterDiscoveryReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                dc_params=dc_params,
                bpt_dc_params=bpt_dc_params,
            )

            self.create_next_message(
                DCChargeParameterDiscovery,
                next_req,
                Timeouts.CHARGE_PARAMETER_DISCOVERY_REQ,
                Namespace.ISO_V20_DC,
                ISOV20PayloadTypes.DC_MAINSTREAM,
            )
        else:
            # TODO Implement support for other energy transfer services
            logger.error(
                "Energy transfer mode for service "
                f"{self.comm_session.selected_energy_service.service} "
                "not supported in ServiceSelection"
            )


class ScheduleExchange(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a ScheduleExchangeRes
    from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.SCHEDULE_EXCHANGE_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, ScheduleExchangeRes)
        if not msg:
            return

        schedule_exchange_res: ScheduleExchangeRes = cast(ScheduleExchangeRes, msg)

        if schedule_exchange_res.evse_processing == Processing.ONGOING:
            self.create_next_message(
                ScheduleExchange,
                self.comm_session.ongoing_schedule_exchange_req,
                Timeouts.SCHEDULE_EXCHANGE_REQ,
                Namespace.ISO_V20_COMMON_MSG,
                ISOV20PayloadTypes.MAINSTREAM,
            )
        else:
            if self.comm_session.control_mode == ControlMode.SCHEDULED:
                (
                    ev_power_profile,
                    charge_progress,
                ) = await self.comm_session.ev_controller.process_scheduled_se_params(
                    schedule_exchange_res.scheduled_params,
                    schedule_exchange_res.go_to_pause,
                )
            else:
                (
                    ev_power_profile,
                    charge_progress,
                ) = await self.comm_session.ev_controller.process_dynamic_se_params(
                    schedule_exchange_res.dynamic_params,
                    schedule_exchange_res.go_to_pause,
                )

            ev_processing = Processing.FINISHED
            bpt_channel_selection = None
            self.comm_session.schedule_exchange_res = schedule_exchange_res

            if not ev_power_profile:
                ev_processing = Processing.ONGOING
                self.comm_session.ev_processing = Processing.ONGOING
            else:
                # Information from EV to show if charging or discharging is planned
                if self.comm_session.selected_energy_service.service in (
                    ServiceV20.AC_BPT,
                    ServiceV20.DC_BPT,
                ):
                    power_value = ev_power_profile.entry_list.entries[-1].power.value
                    if power_value < 0:
                        bpt_channel_selection = ChannelSelection.DISCHARGE
                    else:
                        bpt_channel_selection = ChannelSelection.CHARGE

            await self.comm_session.ev_controller.enable_charging(True)
            if self.comm_session.selected_charging_type_is_ac:
                power_delivery_req = PowerDeliveryReq(
                    header=MessageHeader(
                        session_id=self.comm_session.session_id,
                        timestamp=time.time(),
                    ),
                    ev_processing=ev_processing,
                    charge_progress=charge_progress,
                    ev_power_profile=ev_power_profile,
                    bpt_channel_selection=bpt_channel_selection,
                )

                self.create_next_message(
                    PowerDelivery,
                    power_delivery_req,
                    Timeouts.POWER_DELIVERY_REQ,
                    Namespace.ISO_V20_COMMON_MSG,
                    ISOV20PayloadTypes.MAINSTREAM,
                )
            else:
                cable_check_req = DCCableCheckReq(
                    header=MessageHeader(
                        session_id=self.comm_session.session_id,
                        timestamp=time.time(),
                    )
                )
                self.create_next_message(
                    DCCableCheck,
                    cable_check_req,
                    Timeouts.DC_CABLE_CHECK_REQ,
                    Namespace.ISO_V20_DC,
                    ISOV20PayloadTypes.DC_MAINSTREAM,
                )


class PowerDelivery(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a PowerDeliveryRes
    from the SECC.
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
        msg: V2GMessageV20 = self.check_msg_v20(message, PowerDeliveryRes)
        if not msg:
            return

        if self.comm_session.ev_processing == Processing.ONGOING:
            await self.create_new_power_delivery_req(
                self.comm_session.schedule_exchange_res
            )
            return

        if self.comm_session.charging_session_stop_v20 in (
            ChargingSession.SERVICE_RENEGOTIATION,
            ChargingSession.TERMINATE,
        ):
            await self.comm_session.ev_controller.enable_charging(False)
            if self.comm_session.selected_energy_service.service in [
                ServiceV20.DC,
                ServiceV20.DC_BPT,
            ]:
                welding_detection_req = DCWeldingDetectionReq(
                    header=MessageHeader(
                        session_id=self.comm_session.session_id,
                        timestamp=time.time(),
                    ),
                    ev_processing=Processing.ONGOING,
                )
                self.create_next_message(
                    DCWeldingDetection,
                    welding_detection_req,
                    Timeouts.DC_WELDING_DETECTION_REQ,
                    Namespace.ISO_V20_DC,
                    ISOV20PayloadTypes.DC_MAINSTREAM,
                )
            else:
                session_stop_req = SessionStopReq(
                    header=MessageHeader(
                        session_id=self.comm_session.session_id,
                        timestamp=time.time(),
                    ),
                    charging_session=self.comm_session.charging_session_stop_v20,
                )
                self.create_next_message(
                    SessionStop,
                    session_stop_req,
                    Timeouts.SESSION_STOP_REQ,
                    Namespace.ISO_V20_COMMON_MSG,
                    ISOV20PayloadTypes.MAINSTREAM,
                )

            return

        scheduled_params: ScheduledDCChargeLoopReqParams = None
        dynamic_params: DynamicDCChargeLoopReqParams = None
        bpt_scheduled_params: BPTScheduledDCChargeLoopReqParams = None
        bpt_dynamic_params: BPTDynamicDCChargeLoopReqParams = None
        selected_energy_service = self.comm_session.selected_energy_service
        control_mode = self.comm_session.control_mode
        ev_controller = self.comm_session.ev_controller

        if selected_energy_service.service in [ServiceV20.AC, ServiceV20.AC_BPT]:
            charging_loop_params = await ev_controller.get_ac_charge_loop_params_v20(
                control_mode, selected_energy_service.service
            )
            if selected_energy_service.service == ServiceV20.AC:
                if control_mode == ControlMode.SCHEDULED:
                    scheduled_params = cast(
                        ScheduledDCChargeLoopReqParams, charging_loop_params
                    )
                else:
                    # Dynamic
                    dynamic_params = cast(
                        DynamicDCChargeLoopReqParams, charging_loop_params
                    )
            else:
                # AC_BPT
                if control_mode == ControlMode.SCHEDULED:
                    bpt_scheduled_params = cast(
                        BPTScheduledDCChargeLoopReqParams, charging_loop_params
                    )
                else:
                    # Dynamic
                    bpt_dynamic_params = cast(
                        BPTDynamicDCChargeLoopReqParams, charging_loop_params
                    )

            ac_charge_loop_req = ACChargeLoopReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                display_parameters=await self.comm_session.ev_controller.get_display_params(),  # noqa
                scheduled_params=scheduled_params,
                dynamic_params=dynamic_params,
                bpt_scheduled_params=bpt_scheduled_params,
                bpt_dynamic_params=bpt_dynamic_params,
                meter_info_requested=False,
            )

            self.create_next_message(
                ACChargeLoop,
                ac_charge_loop_req,
                Timeouts.AC_CHARGE_LOOP_REQ,
                Namespace.ISO_V20_AC,
                ISOV20PayloadTypes.AC_MAINSTREAM,
            )

        elif selected_energy_service.service in [ServiceV20.DC, ServiceV20.DC_BPT]:
            if selected_energy_service.service == ServiceV20.DC:
                if control_mode == ControlMode.SCHEDULED:
                    scheduled_params = (
                        await ev_controller.get_scheduled_dc_charge_loop_params()
                    )
                else:
                    dynamic_params = (
                        await ev_controller.get_dynamic_dc_charge_loop_params()
                    )
            elif selected_energy_service.service == ServiceV20.DC_BPT:
                if control_mode == ControlMode.SCHEDULED:
                    bpt_scheduled_params = (
                        await ev_controller.get_bpt_scheduled_dc_charge_loop_params()
                    )
                else:
                    bpt_dynamic_params = (
                        await ev_controller.get_bpt_dynamic_dc_charge_loop_params()
                    )

            dc_charge_loop_req = DCChargeLoopReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                display_parameters=await ev_controller.get_display_params(),
                ev_present_voltage=await ev_controller.get_present_voltage(),
                scheduled_params=scheduled_params,
                dynamic_params=dynamic_params,
                bpt_scheduled_params=bpt_scheduled_params,
                bpt_dynamic_params=bpt_dynamic_params,
                meter_info_requested=False,
            )

            self.create_next_message(
                DCChargeLoop,
                dc_charge_loop_req,
                Timeouts.DC_CHARGE_LOOP_REQ,
                Namespace.ISO_V20_DC,
                ISOV20PayloadTypes.DC_MAINSTREAM,
            )
        else:
            logger.error(f"Energy service unknown: {selected_energy_service.service}")
            return

    async def create_new_power_delivery_req(
        self, schedule_exchange_res: ScheduleExchangeRes
    ):
        if self.comm_session.control_mode == ControlMode.SCHEDULED:
            (
                ev_power_profile,
                charge_progress,
            ) = await self.comm_session.ev_controller.process_scheduled_se_params(
                schedule_exchange_res.scheduled_params,
                schedule_exchange_res.go_to_pause,
            )
        else:
            (
                ev_power_profile,
                charge_progress,
            ) = await self.comm_session.ev_controller.process_dynamic_se_params(
                schedule_exchange_res.dynamic_params, schedule_exchange_res.go_to_pause
            )

        ev_processing = Processing.FINISHED
        self.comm_session.ev_processing = Processing.FINISHED
        if not ev_power_profile:
            ev_processing = Processing.ONGOING
            self.comm_session.ev_processing = Processing.ONGOING

        # Information from EV to show if charging or discharging is planned
        bpt_channel_selection = None
        if self.comm_session.selected_energy_service.service in (
            ServiceV20.AC_BPT,
            ServiceV20.DC_BPT,
        ):
            bpt_channel_selection = ChannelSelection.CHARGE
            if ev_power_profile is not None:
                power_value = ev_power_profile.entry_list.entries[-1].power.value
                if power_value < 0:
                    bpt_channel_selection = ChannelSelection.DISCHARGE

        power_delivery_req = PowerDeliveryReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            ev_processing=ev_processing,
            charge_progress=charge_progress,
            ev_power_profile=ev_power_profile,
            bpt_channel_selection=bpt_channel_selection,
        )

        self.create_next_message(
            PowerDelivery,
            power_delivery_req,
            Timeouts.POWER_DELIVERY_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )


class SessionStop(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a SessionStopRes
    from the SECC.
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
        msg: V2GMessageV20 = self.check_msg_v20(message, SessionStopRes)
        if not msg:
            return

        session_stop_reason = self.comm_session.charging_session_stop_v20.lower()
        if session_stop_reason == "pause":
            session_stop_action = SessionStopAction.PAUSE
        else:
            session_stop_action = SessionStopAction.TERMINATE
        self.comm_session.stop_reason = StopNotification(
            True,
            f"Communication session " f"{session_stop_reason}d",
            self.comm_session.writer.get_extra_info("peername"),
            session_stop_action,
        )

        if (
            self.comm_session.service_renegotiation_supported
            and self.comm_session.renegotiation_requested
        ):
            self.comm_session.renegotiation_requested = False
            self.next_state = ServiceDiscovery
        else:
            self.next_state = Terminate

        return


# ============================================================================
# |                AC-SPECIFIC EVCC STATES - ISO 15118-20                    |
# ============================================================================


class ACChargeParameterDiscovery(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes an
    ACChargeParameterDiscoveryRes from the SECC.
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
        msg: V2GMessageV20 = self.check_msg_v20(message, ACChargeParameterDiscoveryRes)
        if not msg:
            return

        # TODO Act upon the possible negative response codes in ac_cpd_res

        self.comm_session.ongoing_schedule_exchange_req = (
            await self.build_schedule_exchange_request()
        )

        self.create_next_message(
            ScheduleExchange,
            self.comm_session.ongoing_schedule_exchange_req,
            Timeouts.SCHEDULE_EXCHANGE_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )

    async def build_schedule_exchange_request(self) -> ScheduleExchangeReq:
        scheduled_params, dynamic_params = None, None
        if self.comm_session.control_mode == ControlMode.SCHEDULED:
            scheduled_params = (
                await self.comm_session.ev_controller.get_scheduled_se_params(
                    self.comm_session.selected_energy_service
                )
            )

        if self.comm_session.control_mode == ControlMode.DYNAMIC:
            dynamic_params = (
                await self.comm_session.ev_controller.get_dynamic_se_params(
                    self.comm_session.selected_energy_service
                )
            )

        return ScheduleExchangeReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            max_supporting_points=self.comm_session.config.max_supporting_points,
            scheduled_params=scheduled_params,
            dynamic_params=dynamic_params,
        )


class ACChargeLoop(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes an
    ACChargeLoopRes from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.AC_CHARGE_LOOP_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, ACChargeLoopRes)
        if not msg:
            return

        ac_charge_loop_res: ACChargeLoopRes = cast(ACChargeLoopRes, msg)

        # Before checking if we should continue charging,
        # check if SECC requested a renegotiation.
        # evse_status field in ACChargeLoopRes is optional
        if ac_charge_loop_res.evse_status:
            renegotiation = False
            evse_notification = ac_charge_loop_res.evse_status.evse_notification
            if evse_notification not in [
                EVSENotification.SERVICE_RENEGOTIATION,
                EVSENotification.TERMINATE,
            ]:
                raise NotImplementedError(
                    f"Processing for EVSE Notification "
                    f"{evse_notification} is not "
                    f"supported at the moment"
                )
            if evse_notification == EVSENotification.SERVICE_RENEGOTIATION:
                renegotiation = True
            self.stop_v20_charging(
                next_state=PowerDelivery, renegotiate_requested=renegotiation
            )

        elif await self.comm_session.ev_controller.continue_charging():
            try:
                delay: int = (
                    await self.comm_session.ev_controller.charge_loop_delay()
                )  # noqa
                logger.info(f"Next ChargeLoop Req in {delay} seconds")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.info(f"No delay for the next ChargeLoop Req. Reason {e}")
            scheduled_params, dynamic_params = None, None
            bpt_scheduled_params, bpt_dynamic_params = None, None
            selected_energy_service = self.comm_session.selected_energy_service
            control_mode = self.comm_session.control_mode
            ev_controller = self.comm_session.ev_controller

            # TODO You might want to change certain request params based on the values
            #      in the response

            if selected_energy_service.service in [ServiceV20.AC, ServiceV20.AC_BPT]:
                charging_loop_params = (
                    await ev_controller.get_ac_charge_loop_params_v20(  # noqa
                        control_mode, selected_energy_service.service
                    )
                )
                if selected_energy_service.service == ServiceV20.AC:
                    if control_mode == ControlMode.SCHEDULED:
                        scheduled_params = charging_loop_params
                    else:
                        # Dynamic
                        dynamic_params = charging_loop_params
                else:
                    # AC_BPT
                    if control_mode == ControlMode.SCHEDULED:
                        bpt_scheduled_params = charging_loop_params
                    else:
                        # Dynamic
                        bpt_dynamic_params = charging_loop_params
            else:
                logger.error(
                    f"This shouldn't happen. {selected_energy_service.service} "
                    f"not expected here."
                )
                return

            ac_charge_loop_req = ACChargeLoopReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                display_parameters=await self.comm_session.ev_controller.get_display_params(),  # noqa
                scheduled_params=scheduled_params,
                dynamic_params=dynamic_params,
                bpt_scheduled_params=bpt_scheduled_params,
                bpt_dynamic_params=bpt_dynamic_params,
                meter_info_requested=False,
            )

            self.create_next_message(
                ACChargeLoop,
                ac_charge_loop_req,
                Timeouts.AC_CHARGE_LOOP_REQ,
                Namespace.ISO_V20_AC,
                ISOV20PayloadTypes.AC_MAINSTREAM,
            )
        else:
            self.stop_v20_charging(next_state=PowerDelivery)


# ============================================================================
# |                DC-SPECIFIC EVCC STATES - ISO 15118-20                    |
# ============================================================================


class DCChargeParameterDiscovery(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a
    DCChargeParameterDiscoveryRes from the SECC.
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
        msg: V2GMessageV20 = self.check_msg_v20(message, DCChargeParameterDiscoveryRes)
        if not msg:
            return

        # TODO Act upon the possible negative response codes in dc_cpd_res

        self.comm_session.ongoing_schedule_exchange_req = (
            await self.build_schedule_exchange_request()
        )

        self.create_next_message(
            ScheduleExchange,
            self.comm_session.ongoing_schedule_exchange_req,
            Timeouts.SCHEDULE_EXCHANGE_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )

    async def build_schedule_exchange_request(self) -> ScheduleExchangeReq:
        scheduled_params, dynamic_params = None, None
        if self.comm_session.control_mode == ControlMode.SCHEDULED:
            scheduled_params = (
                await self.comm_session.ev_controller.get_scheduled_se_params(
                    self.comm_session.selected_energy_service
                )
            )

        if self.comm_session.control_mode == ControlMode.DYNAMIC:
            dynamic_params = (
                await self.comm_session.ev_controller.get_dynamic_se_params(
                    self.comm_session.selected_energy_service
                )
            )

        return ScheduleExchangeReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            max_supporting_points=self.comm_session.config.max_supporting_points,
            scheduled_params=scheduled_params,
            dynamic_params=dynamic_params,
        )


class DCCableCheck(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a
    DCCableCheckRes from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.DC_CABLE_CHECK_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, DCCableCheckRes)
        if not msg:
            return

        cable_check_res: DCCableCheckRes = cast(DCCableCheckRes, msg)

        if cable_check_res.evse_processing == Processing.FINISHED:
            # Reset the Ongoing timer
            self.comm_session.ongoing_timer = -1
            precharge_req = await self.build_pre_charge_message()
            self.create_next_message(
                DCPreCharge,
                precharge_req,
                Timeouts.DC_PRE_CHARGE_REQ,
                Namespace.ISO_V20_DC,
                ISOV20PayloadTypes.DC_MAINSTREAM,
            )
        else:
            elapsed_time: float = 0
            if self.comm_session.ongoing_timer >= 0:
                elapsed_time = time.time() - self.comm_session.ongoing_timer
                if elapsed_time > Timeouts.V2G_EVCC_CABLE_CHECK_TIMEOUT:
                    self.stop_state_machine("Ongoing timer timed out for CableCheck")
                    return
            else:
                self.comm_session.ongoing_timer = time.time()

            cable_check_req = DCCableCheckReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                )
            )
            self.create_next_message(
                None,
                cable_check_req,
                Timeouts.DC_CABLE_CHECK_REQ,
                Namespace.ISO_V20_DC,
                ISOV20PayloadTypes.DC_MAINSTREAM,
            )

    async def build_pre_charge_message(self):
        present_voltage = await self.comm_session.ev_controller.get_present_voltage()
        processing = Processing.ONGOING
        dc_pre_charge_req = DCPreChargeReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            ev_processing=processing,
            ev_present_voltage=present_voltage,
            ev_target_voltage=await self.comm_session.ev_controller.get_target_voltage(),  # noqa
        )
        return dc_pre_charge_req


class DCPreCharge(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a
    DCPreChargeRes from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.DC_PRE_CHARGE_REQ)
        self.pre_charge_finished_message_built_once = False

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
        msg: V2GMessageV20 = self.check_msg_v20(message, DCPreChargeRes)
        if not msg:
            return

        precharge_res: DCPreChargeRes = cast(DCPreChargeRes, msg)
        next_state = None
        if (
            await self.comm_session.ev_controller.is_precharged(
                precharge_res.evse_present_voltage
            )
            and self.pre_charge_finished_message_built_once
        ):
            next_state = PowerDelivery
            next_request = await self.build_power_delivery_req()
            payload_type = ISOV20PayloadTypes.MAINSTREAM
            namespace = Namespace.ISO_V20_COMMON_MSG
            timeout = Timeouts.POWER_DELIVERY_REQ
        else:
            next_request = await self.build_pre_charge_message(
                precharge_res.evse_present_voltage
            )
            payload_type = ISOV20PayloadTypes.DC_MAINSTREAM
            timeout = Timeouts.DC_PRE_CHARGE_REQ
            namespace = Namespace.ISO_V20_DC
            self.pre_charge_finished_message_built_once = True

        self.create_next_message(
            next_state,
            next_request,
            timeout,
            namespace,
            payload_type,
        )

    async def build_power_delivery_req(self):
        if self.comm_session.control_mode == ControlMode.SCHEDULED:
            (
                ev_power_profile,
                charge_progress,
            ) = await self.comm_session.ev_controller.process_scheduled_se_params(
                self.comm_session.schedule_exchange_res.scheduled_params,
                self.comm_session.schedule_exchange_res.go_to_pause,
            )
        else:
            (
                ev_power_profile,
                charge_progress,
            ) = await self.comm_session.ev_controller.process_dynamic_se_params(
                self.comm_session.schedule_exchange_res.dynamic_params,
                self.comm_session.schedule_exchange_res.go_to_pause,
            )

        ev_processing = Processing.FINISHED
        self.comm_session.ev_processing = Processing.FINISHED
        if not ev_power_profile:
            ev_processing = Processing.ONGOING
            self.comm_session.ev_processing = Processing.ONGOING

        # Information from EV to show if charging or discharging is planned
        bpt_channel_selection = None
        if self.comm_session.selected_energy_service.service in (
            ServiceV20.AC_BPT,
            ServiceV20.DC_BPT,
        ):
            bpt_channel_selection = ChannelSelection.CHARGE
            if ev_power_profile is not None:
                power_value = ev_power_profile.entry_list.entries[-1].power.value
                if power_value < 0:
                    bpt_channel_selection = ChannelSelection.DISCHARGE
        power_delivery_req = PowerDeliveryReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            ev_processing=ev_processing,
            charge_progress=charge_progress,
            ev_power_profile=ev_power_profile,
            bpt_channel_selection=bpt_channel_selection,
        )
        return power_delivery_req

    async def build_pre_charge_message(self, evse_voltage: RationalNumber):
        present_voltage = await self.comm_session.ev_controller.get_present_voltage()
        is_precharged = await self.comm_session.ev_controller.is_precharged(
            evse_voltage
        )
        processing = Processing.ONGOING
        if is_precharged:
            processing = Processing.FINISHED
        dc_pre_charge_req = DCPreChargeReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            ev_processing=processing,
            ev_present_voltage=present_voltage,
            ev_target_voltage=await self.comm_session.ev_controller.get_target_voltage(),  # noqa
        )
        return dc_pre_charge_req


class DCChargeLoop(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a
    DCChargeLoopRes from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.DC_CHARGE_LOOP_REQ)

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
        msg: V2GMessageV20 = self.check_msg_v20(message, DCChargeLoopRes)
        if not msg:
            return

        charge_loop_res: DCChargeLoopRes = cast(DCChargeLoopRes, msg)

        # if charge_loop_res.evse_power_limit_achieved:
        #     self.stop_v20_charging(False)

        if charge_loop_res.evse_status:
            renegotiation = False
            evse_notification = charge_loop_res.evse_status.evse_notification
            if evse_notification not in [
                EVSENotification.SERVICE_RENEGOTIATION,
                EVSENotification.TERMINATE,
            ]:
                raise NotImplementedError(
                    f"Processing for EVSE Notification "
                    f"{evse_notification} is not "
                    f"supported at the moment"
                )
            if evse_notification == EVSENotification.SERVICE_RENEGOTIATION:
                renegotiation = True
            self.stop_v20_charging(
                next_state=PowerDelivery, renegotiate_requested=renegotiation
            )

        elif await self.comm_session.ev_controller.continue_charging():
            try:
                delay: int = (
                    await self.comm_session.ev_controller.charge_loop_delay()
                )  # noqa
                logger.info(f"Next ChargeLoop Req in {delay} seconds")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.info(f"No delay for the next ChargeLoop Req. Reason {e}")
            current_demand_req = await self.build_current_demand_data()

            self.create_next_message(
                None,
                current_demand_req,
                Timeouts.DC_CHARGE_LOOP_REQ,
                Namespace.ISO_V20_DC,
                ISOV20PayloadTypes.DC_MAINSTREAM,
            )
        else:
            self.stop_v20_charging(next_state=PowerDelivery)

    async def build_current_demand_data(self):
        scheduled_params, dynamic_params = None, None
        bpt_scheduled_params, bpt_dynamic_params = None, None
        if self.comm_session.selected_energy_service.service == ServiceV20.DC:
            if self.comm_session.control_mode == ControlMode.SCHEDULED:
                scheduled_params = (
                    await self.comm_session.ev_controller.get_scheduled_dc_charge_loop_params()  # noqa
                )
            else:
                dynamic_params = (
                    await self.comm_session.ev_controller.get_dynamic_dc_charge_loop_params()  # noqa
                )
        elif self.comm_session.selected_energy_service.service == ServiceV20.DC_BPT:
            if self.comm_session.control_mode == ControlMode.SCHEDULED:
                bpt_scheduled_params = (
                    await self.comm_session.ev_controller.get_bpt_scheduled_dc_charge_loop_params()  # noqa
                )
            else:
                bpt_dynamic_params = (
                    await self.comm_session.ev_controller.get_bpt_dynamic_dc_charge_loop_params()  # noqa
                )

        dc_charge_loop_req = DCChargeLoopReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            display_parameters=await self.comm_session.ev_controller.get_display_params(),  # noqa
            ev_present_voltage=await self.comm_session.ev_controller.get_present_voltage(),  # noqa
            scheduled_params=scheduled_params,
            dynamic_params=dynamic_params,
            bpt_scheduled_params=bpt_scheduled_params,
            bpt_dynamic_params=bpt_dynamic_params,
            meter_info_requested=False,
        )
        return dc_charge_loop_req


class DCWeldingDetection(StateEVCC):
    """
    The ISO 15118-20 state in which the EVCC processes a
    DCWeldingDetectionRes from the SECC.
    """

    def __init__(self, comm_session: EVCCCommunicationSession):
        super().__init__(comm_session, Timeouts.DC_WELDING_DETECTION_REQ)
        self.welding_detection_complete = False

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
        if self.comm_session.ongoing_timer > 0:
            elapsed_time = time.time() - self.comm_session.ongoing_timer
            logger.debug(f"EVCC timeout : {Timeouts.V2G_EVCC_ONGOING_TIMEOUT}")
            if elapsed_time > Timeouts.V2G_EVCC_ONGOING_TIMEOUT:
                self.stop_state_machine(
                    "Ongoing timer timed out for " "WeldingDetectionRes"
                )
                return
        elif self.comm_session.ongoing_timer == -1:
            self.comm_session.ongoing_timer = time.time()

        if self.welding_detection_complete:
            session_stop_req = SessionStopReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                charging_session=ChargingSession.TERMINATE,
            )
            next_state = SessionStop
            next_request: V2GRequest = session_stop_req
            next_timeout = Timeouts.SESSION_STOP_REQ
            namespace = Namespace.ISO_V20_COMMON_MSG
            next_payload_type = ISOV20PayloadTypes.MAINSTREAM
        else:
            processing = Processing.ONGOING
            if await self.comm_session.ev_controller.welding_detection_has_finished():
                processing = Processing.FINISHED
                self.welding_detection_complete = True
            next_request = DCWeldingDetectionReq(
                header=MessageHeader(
                    session_id=self.comm_session.session_id,
                    timestamp=time.time(),
                ),
                ev_processing=processing,
            )
            next_state = None
            next_timeout = Timeouts.DC_WELDING_DETECTION_REQ
            namespace = Namespace.ISO_V20_DC
            next_payload_type = ISOV20PayloadTypes.DC_MAINSTREAM

        self.create_next_message(
            next_state, next_request, next_timeout, namespace, next_payload_type
        )
