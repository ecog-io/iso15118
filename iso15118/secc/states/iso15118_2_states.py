"""
This module contains the SECC's States used to process the EVCC's incoming
V2GMessage objects of the ISO 15118-2 protocol, from SessionSetupReq to
SessionStopReq.
"""

import asyncio
import base64
import logging
import time
from typing import List, Optional, Tuple, Type, Union

from iso15118.secc.comm_session_handler import SECCCommunicationSession
from iso15118.secc.controller.ev_data import EVSessionContext15118
from iso15118.secc.controller.evse_data import CurrentType
from iso15118.secc.controller.interface import AuthorizationResponse
from iso15118.secc.states.secc_state import StateSECC
from iso15118.shared.exceptions import (
    CertAttributeError,
    CertChainLengthError,
    CertExpiredError,
    CertNotYetValidError,
    CertRevokedError,
    CertSignatureError,
    EncryptionError,
    PrivateKeyReadError,
)
from iso15118.shared.exi_codec import EXI
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.datatypes import (
    DCEVSEChargeParameter,
    DCEVSEStatus,
    PVEVSEPresentCurrent,
)
from iso15118.shared.messages.din_spec.datatypes import (
    ResponseCode as ResponseCodeDINSPEC,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.enums import (
    AuthEnum,
    AuthorizationStatus,
    AuthorizationTokenType,
    CpState,
    DCEVErrorCode,
    EVSEProcessing,
    IsolationLevel,
    Namespace,
    Protocol,
    SessionStopAction,
)
from iso15118.shared.messages.iso15118_2.body import (
    EMAID,
    AuthorizationReq,
    AuthorizationRes,
    BodyBase,
    CableCheckReq,
    CableCheckRes,
    CertificateInstallationReq,
    CertificateInstallationRes,
    ChargeParameterDiscoveryReq,
    ChargeParameterDiscoveryRes,
    ChargingStatusReq,
    ChargingStatusRes,
    CurrentDemandReq,
    CurrentDemandRes,
    MeteringReceiptReq,
    MeteringReceiptRes,
    PaymentDetailsReq,
    PaymentDetailsRes,
    PaymentServiceSelectionReq,
    PaymentServiceSelectionRes,
    PowerDeliveryReq,
    PowerDeliveryRes,
    PreChargeReq,
    PreChargeRes,
    ResponseCode,
    ServiceDetailReq,
    ServiceDetailRes,
    ServiceDiscoveryReq,
    ServiceDiscoveryRes,
    SessionSetupReq,
    SessionSetupRes,
    SessionStopReq,
    SessionStopRes,
    WeldingDetectionReq,
    WeldingDetectionRes,
)
from iso15118.shared.messages.iso15118_2.datatypes import (
    ACEVSEChargeParameter,
    ACEVSEStatus,
    AuthOptionList,
    CertificateChain,
    ChargeProgress,
    ChargeService,
    ChargingSession,
    DHPublicKey,
    EncryptedPrivateKey,
    EnergyTransferModeList,
    Parameter,
    ParameterSet,
)
from iso15118.shared.messages.iso15118_2.datatypes import ResponseCode as ResponseCodeV2
from iso15118.shared.messages.iso15118_2.datatypes import (
    SAScheduleList,
    SAScheduleTuple,
    ServiceCategory,
    ServiceDetails,
    ServiceID,
    ServiceList,
    ServiceName,
    ServiceParameterList,
    SubCertificates,
)
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.common_types import (
    ResponseCode as ResponseCodeV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.timeouts import Timeouts
from iso15118.shared.messages.xmldsig import Signature
from iso15118.shared.notifications import StopNotification
from iso15118.shared.security import (
    CertPath,
    KeyEncoding,
    KeyPasswordPath,
    KeyPath,
    build_pem_certificate_chain,
    create_signature,
    encrypt_priv_key,
    get_cert_cn,
    get_certificate_hash_data,
    get_random_bytes,
    load_cert,
    load_priv_key,
    log_certs_details,
    verify_certs,
    verify_signature,
)
from iso15118.shared.states import Base64, Pause, State, Terminate

logger = logging.getLogger(__name__)


# ============================================================================
# |     COMMON SECC STATES (FOR BOTH AC AND DC CHARGING) - ISO 15118-2       |
# ============================================================================


class SessionSetup(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a SessionSetupReq
    message from the EVCC.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        # TODO: less the time used for waiting for and processing the
        #       SDPRequest and SupportedAppProtocolReq
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
        msg = self.check_msg_v2(message, [SessionSetupReq])
        if not msg:
            return

        session_setup_req: SessionSetupReq = msg.body.session_setup_req

        # Check session ID. Most likely, we need to create a new one
        session_id: str = get_random_bytes(8).hex().upper()
        if msg.header.session_id == bytes(1).hex():
            # A new charging session is established
            self.response_code = ResponseCode.OK_NEW_SESSION_ESTABLISHED
            self.comm_session.ev_session_context = EVSessionContext15118()
            self.comm_session.ev_session_context.session_id = session_id
        elif (
            self.comm_session.ev_session_context.session_id
            and msg.header.session_id == self.comm_session.ev_session_context.session_id
        ):
            # The EV wants to resume the previously paused charging session
            session_id = self.comm_session.ev_session_context.session_id
            self.response_code = ResponseCode.OK_OLD_SESSION_JOINED
        else:
            # False session ID from EV, gracefully assigning new session ID
            logger.warning(
                f"EVCC's session ID {msg.header.session_id} "
                f"does not match {self.comm_session.session_id}. "
                f"New session ID {session_id} assigned"
            )
            self.response_code = ResponseCode.OK_NEW_SESSION_ESTABLISHED
            self.comm_session.ev_session_context = EVSessionContext15118()
            self.comm_session.ev_session_context.session_id = session_id

        session_setup_res = SessionSetupRes(
            response_code=self.response_code,
            evse_id=await self.comm_session.evse_controller.get_evse_id(
                Protocol.ISO_15118_2
            ),
            evse_timestamp=time.time(),
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
            Namespace.ISO_V2_MSG_DEF,
        )


class ServiceDiscovery(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a ServiceDiscoveryReq
    message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. ServiceDiscoveryReq
    2. ServiceDetailReq
    3. PaymentServiceSelectionReq

    Upon first initialisation of this state, we expect a ServiceDiscoveryReq
    but after that, the next possible request could be a ServiceDetailReq
    (for a value-added service that is offered in the service list if the
    ServiceDiscoveryRes) or a PaymentServiceSelectionReq. This means that we
    need to remain in this state until we receive the next message in the
    sequence.

    As a result, the create_next_message() method might be called with
    next_state = None.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_service_discovery_req: bool = True

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
        msg = self.check_msg_v2(
            message,
            [ServiceDiscoveryReq, ServiceDetailReq, PaymentServiceSelectionReq],
            self.expecting_service_discovery_req,
        )
        if not msg:
            return

        if msg.body.service_detail_req:
            await ServiceDetail(self.comm_session).process_message(message, message_exi)
            return

        if msg.body.payment_service_selection_req:
            await PaymentServiceSelection(self.comm_session).process_message(
                message, message_exi
            )
            return

        if msg.body.service_discovery_req and not self.expecting_service_discovery_req:
            self.stop_state_machine(
                f"{str(message)}' not accepted in state " f"{str(self)}",
                message,
                ResponseCode.FAILED_SEQUENCE_ERROR,
            )
            return
        service_discovery_req: ServiceDiscoveryReq = msg.body.service_discovery_req
        service_discovery_res = await self.get_services(
            service_discovery_req.service_category
        )

        self.create_next_message(
            None,
            service_discovery_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_service_discovery_req = False

    async def get_services(
        self, category_filter: ServiceCategory
    ) -> ServiceDiscoveryRes:
        """
        Provides the ServiceDiscoveryRes message with all its services,
        including the mandatory ChargeService and optional value-added services
        like the installation of contract certificates.

        Currently no filter based on service scope is applied since its string
        value is not standardized in any way
        """
        auth_options: List[AuthEnum] = []

        if self.comm_session.ev_session_context.auth_options:
            logger.info("AuthOptions available in context. This is a resumed session.")
            # This is a resumed session.
            # Return the auth option that was previously selected.
            auth_options = self.comm_session.ev_session_context.auth_options
        elif self.comm_session.selected_auth_option:
            # In case the EVCC resumes a paused charging session, the SECC
            # must only offer the auth option the EVCC selected previously
            if self.comm_session.selected_auth_option == AuthEnum.EIM_V2:
                auth_options.append(AuthEnum.EIM_V2)
            else:
                auth_options.append(AuthEnum.PNC_V2)
        else:
            if self.comm_session.evse_controller.is_eim_authorized():
                auth_options.append(AuthEnum.EIM_V2)
            else:
                supported_auth_options = self.comm_session.config.supported_auth_options
                if AuthEnum.EIM in supported_auth_options:
                    auth_options.append(AuthEnum.EIM_V2)
                if AuthEnum.PNC in supported_auth_options and self.comm_session.is_tls:
                    auth_options.append(AuthEnum.PNC_V2)

        self.comm_session.offered_auth_options = auth_options

        energy_modes = (
            await self.comm_session.evse_controller.get_supported_energy_transfer_modes(
                Protocol.ISO_15118_2
            )
        )

        if self.comm_session.ev_session_context.charge_service:
            logger.info(
                "ChargeService available in context. This is a resumed session."
            )
            charge_service = self.comm_session.ev_session_context.charge_service
        else:
            charge_service = ChargeService(
                service_id=ServiceID.CHARGING,
                service_name=ServiceName.CHARGING,
                service_category=ServiceCategory.CHARGING,
                free_service=self.comm_session.config.free_charging_service,
                supported_energy_transfer_mode=EnergyTransferModeList(
                    energy_modes=energy_modes
                ),
            )
            self.comm_session.ev_session_context.charge_service = charge_service

        service_list: List[ServiceDetails] = []
        # Value-added services (VAS), like installation of contract certificates
        # and the Internet service, are only allowed with TLS-secured comm.
        if self.comm_session.is_tls:
            if self.comm_session.config.allow_cert_install_service and (
                category_filter is None
                or category_filter == ServiceCategory.CERTIFICATE
            ):
                cert_install_service = ServiceDetails(
                    service_id=2,
                    service_name=ServiceName.CERTIFICATE,
                    service_category=ServiceCategory.CERTIFICATE,
                    free_service=self.comm_session.config.free_cert_install_service,
                )

                service_list.append(cert_install_service)

            # Add more value-added services (VAS) here if need be

        # The optional service_list element of ServiceDiscoveryRes must only be set if
        # the list of offered services is not empty, otherwise it must be None to avoid
        # an EXI decoding error. The XSD definition does not allow an empty list
        # (otherwise it would also say: minOccurs="0"):
        # <xs:element name="Service" type="ServiceType" maxOccurs="8"/>
        offered_services = None
        if len(service_list) > 0:
            offered_services = ServiceList(services=service_list)

        service_discovery_res = ServiceDiscoveryRes(
            response_code=ResponseCode.OK,
            auth_option_list=AuthOptionList(auth_options=auth_options),
            charge_service=charge_service,
            service_list=offered_services,
        )

        self.comm_session.offered_services = service_list

        return service_discovery_res


class ServiceDetail(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a ServiceDetailReq
    message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. ServiceDetailReq
    2. PaymentServiceSelectionReq

    The EVCC may send a ServiceDetailReq several times (for each value-added
    service that is offered in the service list if the ServiceDiscoveryRes).
    This means that we need to remain in this state until we know
    which is the following request from the EVCC and then transition to the
    appropriate state (or terminate if the incoming message doesn't fit any of
    the expected requests).

    As a result, the create_next_message() method might be called with
    next_state = None.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_service_detail_req: bool = True

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
        msg = self.check_msg_v2(
            message,
            [ServiceDetailReq, PaymentServiceSelectionReq],
            self.expecting_service_detail_req,
        )
        if not msg:
            return

        if msg.body.payment_service_selection_req:
            await PaymentServiceSelection(self.comm_session).process_message(
                message, message_exi
            )
            return

        service_detail_req: ServiceDetailReq = msg.body.service_detail_req

        is_found = False
        for service_details in self.comm_session.offered_services:
            if service_detail_req.service_id == service_details.service_id:
                is_found = True
                break

        if not is_found:
            # [V2G2-425] The SECC shall respond with a negative ResponseCode
            # 'FAILED_ServiceIDInvalid'
            # if the EVCC provided a not previously retrieved ServiceID in the
            # ServiceDetailsReq.
            error_service_detail_res = ServiceDetailRes(
                response_code=ResponseCode.FAILED_SERVICE_ID_INVALID,
                service_id=service_detail_req.service_id,
            )
            self.create_next_message(
                None,
                error_service_detail_res,
                Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
                Namespace.ISO_V2_MSG_DEF,
            )
            logger.error(f"Service ID is invalid for {message}")
            return

        parameter_set: List[ParameterSet] = []

        # Certificate installation service
        # We only offer installation of contract certificates, not updates
        if service_detail_req.service_id == ServiceID.CERTIFICATE:
            install_parameter = Parameter(name="Service", str_value="Installation")
            install_parameter_set = ParameterSet(
                parameter_set_id=1, parameters=[install_parameter]
            )
            parameter_set.append(install_parameter_set)

        # To offer an Internet service, add the service parameter set here
        if service_detail_req.service_id == ServiceID.INTERNET:
            # We don't offer the Internet service at the moment via
            # ServiceDiscoveryReq, so we don't need to bother about responding
            # to a ServiceDetailReq. We can add an Internet service at a later
            # point in time once we have an actual use case for that.
            pass

        service_detail_res = ServiceDetailRes(
            response_code=ResponseCode.OK,
            service_id=service_detail_req.service_id,
            service_parameter_list=ServiceParameterList(parameter_set=parameter_set),
        )

        self.create_next_message(
            None,
            service_detail_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_service_detail_req = False


class PaymentServiceSelection(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a
    PaymentServiceSelectionReq message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. a PaymentServiceSelectionReq
    2. a CertificateInstallationReq (not the update, as we don't offer this)
    3. a PaymentDetailsReq
    4. an AuthorizationReq

    Upon first initialisation of this state, we expect a
    PaymentServiceSelectionReq, but after that, the next possible request could
    be one of the other three options. So we remain in this state until we know
    which is the following request from the EVCC and then transition to the
    appropriate state (or terminate if the incoming message doesn't fit any of
    the expected requests).

    As a result, the create_next_message() method might be called with
    next_state = None.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_service_selection_req: bool = True

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
        msg = self.check_msg_v2(
            message,
            [
                PaymentServiceSelectionReq,
                CertificateInstallationReq,
                PaymentDetailsReq,
                AuthorizationReq,
            ],
            self.expecting_service_selection_req,
        )
        if not msg:
            return

        if msg.body.certificate_installation_req:
            await CertificateInstallation(self.comm_session).process_message(
                message, message_exi
            )
            return

        if msg.body.payment_details_req:
            await PaymentDetails(self.comm_session).process_message(
                message, message_exi
            )
            return

        if msg.body.authorization_req:
            await Authorization(self.comm_session).process_message(message, message_exi)
            return

        # passes_initial_check, ensures that one of the accepted messages
        # was received. Thus, if the above body messages do not check out,
        # means that we are in presence of a `PaymentServiceSelectionReq`
        # maessage
        service_selection_req: PaymentServiceSelectionReq = (
            msg.body.payment_service_selection_req
        )
        selected_service_list = service_selection_req.selected_service_list

        charge_service_selected: bool = False
        for service in selected_service_list.selected_service:
            if service.service_id == ServiceID.CHARGING:
                charge_service_selected = True
                continue
            if service.service_id not in [
                offered_service.service_id
                for offered_service in self.comm_session.offered_services
            ]:
                self.stop_state_machine(
                    f"Selected service with ID {service.service_id} "
                    f"was not offered",
                    message,
                    ResponseCode.FAILED_SERVICE_SELECTION_INVALID,
                )
                return

        if not charge_service_selected:
            self.stop_state_machine(
                "Charge service not selected",
                message,
                ResponseCode.FAILED_NO_CHARGE_SERVICE_SELECTED,
            )
            return

        if service_selection_req.selected_auth_option.value not in [
            auth_option.value for auth_option in self.comm_session.offered_auth_options
        ]:
            self.stop_state_machine(
                "Selected authorization method "
                f"{service_selection_req.selected_auth_option} "
                f"was not offered",
                message,
                ResponseCode.FAILED_PAYMENT_SELECTION_INVALID,
            )
            return

        logger.debug(
            "EVCC chose authorization option "
            f"{service_selection_req.selected_auth_option.value}"
        )
        self.comm_session.selected_auth_option = AuthEnum(
            service_selection_req.selected_auth_option.value
        )
        self.comm_session.ev_session_context.auth_options = [
            self.comm_session.selected_auth_option
        ]

        # For now, we don't really care much more about the selected
        # value-added services. If the EVCC wants to do contract certificate
        # installation, it can do so as the service is offered.

        service_selection_res = PaymentServiceSelectionRes(
            response_code=ResponseCode.OK
        )

        self.create_next_message(
            None,
            service_selection_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_service_selection_req = False


class CertificateInstallation(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a
    CertificateInstallationReq message from the EVCC.
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
        msg = self.check_msg_v2(message, [CertificateInstallationReq])
        if not msg:
            return

        if not self.validate_message_signature(msg):
            self.stop_state_machine(
                "Signature verification failed for " "CertificateInstallationReq",
                message,
                ResponseCode.FAILED_SIGNATURE_ERROR,
            )
            return

        # In a real world scenario we need to fetch the certificate from the backend.
        # We call get_15118_ev_certificate method, which would be a direct mapping
        # to the Get15118EVCertificateRequest
        # message from OCPP 2.0.1 for the installation case.
        # This accepts 2 arguments:
        # 1. The raw EXI CertificateInstallationReq message coming from the EV
        # in base64 encoded form.
        # 2. A string that specifies `15118SchemaVersion` which would be either of
        # "urn:iso:15118:2:2013:MsgDef" or "urn:iso:std:iso:15118:-20:CommonMessages"
        signature = None

        try:
            if self.comm_session.config.use_cpo_backend:
                logger.info("Using CPO backend to fetch CertificateInstallationRes")
                # CertificateInstallationReq must be base64 encoded before forwarding
                # to backend.
                # Call to b64encode returns byte[] - hence the .decode("utf-8")
                base64_certificate_install_req = base64.b64encode(message_exi).decode(
                    "utf-8"
                )

                # The response received below is EXI response in base64 encoded form.
                # Decoding to EXI happens later just before V2GTP packet is built.
                base64_certificate_installation_res = (
                    await self.comm_session.evse_controller.get_15118_ev_certificate(
                        base64_certificate_install_req, Namespace.ISO_V2_MSG_DEF
                    )
                )
                certificate_installation_res: Union[
                    CertificateInstallationRes, Base64
                ] = Base64(
                    message=base64_certificate_installation_res,
                    message_name=CertificateInstallationRes.__name__,
                    namespace=Namespace.ISO_V2_MSG_DEF,
                )
            else:
                (
                    certificate_installation_res,
                    signature,
                ) = self.generate_certificate_installation_res()

        except Exception as e:
            error = f"Error building CertificateInstallationRes: {e}"
            logger.error(error)
            self.stop_state_machine(
                error,
                message,
                ResponseCode.FAILED_NO_CERTIFICATE_AVAILABLE,
            )
            return

        self.create_next_message(
            PaymentDetails,
            certificate_installation_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
            signature=signature,
        )

    def validate_message_signature(self, message: V2GMessageV2) -> bool:
        # For the CertificateInstallation, the min. the SECC can do is
        # to verify the message signature, using the OEM provisioning
        # certificate (public key) - this is available in the cert installation req.
        # The chain of signatures, from the signature in the
        # CertificateInstallationReq's header all the way to the
        # self-signed OEM/V2G root certificate, can be verified if the
        # OEM Sub-CA and OEM/V2G root CA certificate are available.

        cert_install_req: CertificateInstallationReq = (
            message.body.certificate_installation_req
        )

        sub_ca_certificates_oem = None
        root_ca_certificate_oem = None

        try:
            sub_ca_certificates_oem = [
                load_cert(CertPath.OEM_SUB_CA2_DER),
                load_cert(CertPath.OEM_SUB_CA1_DER),
            ]
            root_ca_certificate_oem = load_cert(CertPath.OEM_ROOT_DER)
        except (FileNotFoundError, IOError):
            pass

        return verify_signature(
            signature=message.header.signature,
            elements_to_sign=[
                (
                    cert_install_req.id,
                    EXI().to_exi(cert_install_req, Namespace.ISO_V2_MSG_DEF),
                )
            ],
            leaf_cert=cert_install_req.oem_provisioning_cert,
            sub_ca_certs=sub_ca_certificates_oem,
            root_ca_cert=root_ca_certificate_oem,
        )

    def generate_certificate_installation_res(
        self,
    ) -> Tuple[CertificateInstallationRes, Signature]:
        # Here we create the CertificateInstallationRes message ourselves as we
        # have access to all certificates and private keys needed.
        # This is however not the real production case.
        # Note: the Raw EXI encoded message that includes the Header and the Body of the
        # CertificateInstallationReq must be used.
        try:
            dh_pub_key, encrypted_priv_key_bytes = encrypt_priv_key(
                oem_prov_cert=load_cert(CertPath.OEM_LEAF_DER),
                priv_key_to_encrypt=load_priv_key(
                    KeyPath.CONTRACT_LEAF_PEM,
                    KeyEncoding.PEM,
                    KeyPasswordPath.CONTRACT_LEAF_KEY_PASSWORD,
                ),
            )
        except EncryptionError:
            raise EncryptionError(
                "EncryptionError while trying to encrypt the "
                "private key for the contract certificate"
            )
        except PrivateKeyReadError as exc:
            raise PrivateKeyReadError(
                f"Can't read private key to encrypt for "
                f"CertificateInstallationRes: {exc}"
            )

        # The elements that need to be part of the signature
        contract_cert_chain = CertificateChain(
            id="id1",
            certificate=load_cert(CertPath.CONTRACT_LEAF_DER),
            sub_certificates=SubCertificates(
                certificates=[
                    load_cert(CertPath.MO_SUB_CA2_DER),
                    load_cert(CertPath.MO_SUB_CA1_DER),
                ]
            ),
        )
        encrypted_priv_key = EncryptedPrivateKey(
            id="id2", value=encrypted_priv_key_bytes
        )
        dh_public_key = DHPublicKey(id="id3", value=dh_pub_key)
        emaid = EMAID(
            id="id4", value=get_cert_cn(load_cert(CertPath.CONTRACT_LEAF_DER))
        )
        cps_certificate_chain = CertificateChain(
            certificate=load_cert(CertPath.CPS_LEAF_DER),
            sub_certificates=SubCertificates(
                certificates=[
                    load_cert(CertPath.CPS_SUB_CA2_DER),
                    load_cert(CertPath.CPS_SUB_CA1_DER),
                ]
            ),
        )

        cert_install_res = CertificateInstallationRes(
            response_code=ResponseCode.OK,
            cps_cert_chain=cps_certificate_chain,
            contract_cert_chain=contract_cert_chain,
            encrypted_private_key=encrypted_priv_key,
            dh_public_key=dh_public_key,
            emaid=emaid,
        )

        try:
            # Elements to sign, containing its id and the exi encoded stream
            contract_cert_tuple = (
                cert_install_res.contract_cert_chain.id,
                EXI().to_exi(
                    cert_install_res.contract_cert_chain, Namespace.ISO_V2_MSG_DEF
                ),
            )
            encrypted_priv_key_tuple = (
                cert_install_res.encrypted_private_key.id,
                EXI().to_exi(
                    cert_install_res.encrypted_private_key, Namespace.ISO_V2_MSG_DEF
                ),
            )
            dh_public_key_tuple = (
                cert_install_res.dh_public_key.id,
                EXI().to_exi(cert_install_res.dh_public_key, Namespace.ISO_V2_MSG_DEF),
            )
            emaid_tuple = (
                cert_install_res.emaid.id,
                EXI().to_exi(cert_install_res.emaid, Namespace.ISO_V2_MSG_DEF),
            )

            elements_to_sign = [
                contract_cert_tuple,
                encrypted_priv_key_tuple,
                dh_public_key_tuple,
                emaid_tuple,
            ]
            # The private key to be used for the signature
            signature_key = load_priv_key(
                KeyPath.CPS_LEAF_PEM,
                KeyEncoding.PEM,
                KeyPasswordPath.CPS_LEAF_KEY_PASSWORD,
            )

            signature = create_signature(elements_to_sign, signature_key)

        except PrivateKeyReadError as exc:
            raise PrivateKeyReadError(
                "Can't read private key needed to create signature "
                f"for CertificateInstallationRes: {exc}",
                ResponseCode.FAILED,
            )

        return cert_install_res, signature


class PaymentDetails(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a
    PaymentDetailsReq message from the EVCC.

    The PaymentDetailsReq contains the EV's contract certificate and sub-CA
    certificate(s) used to automatically authenticate and authorize for
    charging. The EMAID (E-Mobility Account Identifier) is stored in the
    Common Name (CN) field of the contract certificate's 'Subject' attribute
    and is used as a credential for authorization, digitally signed by the
    issuer of the contract certificate. The contract certificate is the leaf
    certificate in the PaymentDetailsReq's certificate chain.

    The SECC needs to verify the certificate chain (e.g. signature check and
    validity check of each certificate and store the certificate chain in the
    communication session, so it can later verify digitally signed messages
    (such as the AuthorizationReq) from the EVCC.

    In general, a CPO (charge point operator) can decide if they want the SECC
    to perform this verification and validity checks locally or if the SECC
    shall defer that task to the CPO backend.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)

    def _mobility_operator_root_cert_path(self) -> Optional[str]:
        """Return the path to the MO root.  Included to be patched in tests."""
        return CertPath.MO_ROOT_DER

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
        msg = self.check_msg_v2(message, [PaymentDetailsReq])
        if not msg:
            return

        payment_details_req: PaymentDetailsReq = msg.body.payment_details_req

        try:
            leaf_cert = payment_details_req.cert_chain.certificate
            sub_ca_certs = payment_details_req.cert_chain.sub_certificates.certificates

            # Logging MO certificate and chain details to help with debugging.
            log_certs_details([leaf_cert])
            log_certs_details(sub_ca_certs)
            # TODO There should be an OCPP setting that determines whether
            #      or not the charging station should verify (is in
            #      possession of MO or V2G Root certificates) or if it
            #      should rather forward the certificate chain to the CSMS
            # TODO Either an MO Root certificate or a V2G Root certificate
            #      could be used to verify, need to be flexible with regards
            #      to the PKI that is used.
            root_cert_path = self._mobility_operator_root_cert_path()
            try:
                if root_cert_path:
                    root_cert = load_cert(root_cert_path)
                    logger.info(f"Using MO root at {root_cert_path}")
                else:
                    root_cert = None
                    logger.info("No suitable MO root found.")
            except FileNotFoundError:
                logger.warning("MO Root Cert not available.")
                root_cert = None

            try:
                verify_certs(leaf_cert, sub_ca_certs, root_cert)
            except CertSignatureError:
                # This error means there was an error while validating the parent-child
                # relationship in the cert chain. This could also very well be
                # a limitation on the SECC that the root certificate present
                # doesn't match the chain passed through.
                # So set root_cert to None and pass the incoming chain to the backend
                # for further checks.
                logger.info(
                    "Local chain verification failed. "
                    "Passing verification to backend."
                )
                root_cert = None

            # Note that the eMAID format (14 or 15 characters) will be validated
            # by the definition of the eMAID type in
            # shared/messages/iso15118_2/datatypes.py
            self.comm_session.emaid = payment_details_req.emaid
            self.comm_session.contract_cert_chain = payment_details_req.cert_chain

            hash_data = get_certificate_hash_data(
                self.comm_session.contract_cert_chain, root_cert
            )
            pem_certificate_chain = build_pem_certificate_chain(
                self.comm_session.contract_cert_chain, root_cert
            )

            current_authorization_status = (
                await self.comm_session.evse_controller.is_authorized(
                    id_token=payment_details_req.emaid,
                    id_token_type=AuthorizationTokenType.EMAID,
                    certificate_chain=bytes(pem_certificate_chain, "utf-8"),
                    hash_data=hash_data,
                )
            )
            response_code: Optional[
                Union[ResponseCodeV2, ResponseCodeV20, ResponseCodeDINSPEC]
            ] = ResponseCode.OK
            if resp_status := current_authorization_status.certificate_response_status:
                # according to table 112 of ISO 15118-2, the Response code
                # for this message can only be one of the following:
                # OK, FAILED,
                # FAILED_SEQUENCE_ERROR, FAILED_SIGNATURE_ERROR,
                # FAILED_UNKNOWN_SESSION, FAILED_CHALLENGE_INVALID
                # FAILED_CERTIFICATE_EXPIRED, FAILED_CERTIFICATE_REVOKED,
                # FAILED_NO_CERTIFICATE_AVAILABLE
                response_code = (
                    resp_status
                    if resp_status
                    in [
                        ResponseCode.OK,
                        ResponseCode.FAILED,
                        ResponseCode.FAILED_SEQUENCE_ERROR,
                        ResponseCode.FAILED_SIGNATURE_ERROR,
                        ResponseCode.FAILED_UNKNOWN_SESSION,
                        ResponseCode.FAILED_CERTIFICATE_EXPIRED,
                        ResponseCode.FAILED_CERTIFICATE_REVOKED,
                        ResponseCode.FAILED_NO_CERTIFICATE_AVAILABLE,
                    ]
                    else ResponseCode.FAILED
                )

            if current_authorization_status.authorization_status in [
                AuthorizationStatus.ACCEPTED,
                AuthorizationStatus.ONGOING,
            ]:
                self.comm_session.gen_challenge = get_random_bytes(16)
                payment_details_res = PaymentDetailsRes(
                    response_code=response_code,
                    gen_challenge=self.comm_session.gen_challenge,
                    evse_timestamp=time.time(),
                )

                self.create_next_message(
                    Authorization,
                    payment_details_res,
                    Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
                    Namespace.ISO_V2_MSG_DEF,
                )
            else:
                self.stop_state_machine(
                    "Authorization was rejected",
                    message,
                    response_code,
                )

        except (
            CertSignatureError,
            CertNotYetValidError,
            CertExpiredError,
            CertRevokedError,
            CertAttributeError,
            CertChainLengthError,
        ) as exc:
            reason = ""
            if isinstance(exc, CertSignatureError):
                response_code = ResponseCode.FAILED_CERT_CHAIN_ERROR
                reason = (
                    f"CertSignatureError for {exc.subject}, "
                    f"tried to verify with issuer: "
                    f"{exc.issuer}. \n{exc.extra_info}"
                )
            elif isinstance(exc, CertChainLengthError):
                response_code = ResponseCode.FAILED_CERT_CHAIN_ERROR
                reason = (
                    f"CertChainLengthError, max "
                    f"{exc.allowed_num_sub_cas} sub-CAs allowed "
                    f"but {exc.num_sub_cas} sub-CAs provided"
                )
            elif isinstance(exc, CertExpiredError):
                response_code = ResponseCode.FAILED_CERTIFICATE_EXPIRED
                reason = f"CertExpiredError for {exc.subject}"
            elif isinstance(exc, CertNotYetValidError):
                response_code = ResponseCode.FAILED_CERTIFICATE_EXPIRED
                reason = f"[V2G2-824] (Certificate not yet valid.) CertExpiredError for {exc.subject}"  # noqa
            elif isinstance(exc, CertRevokedError):
                response_code = ResponseCode.FAILED_CERTIFICATE_REVOKED
                reason = f"CertRevokedError for {exc.subject}"
            else:
                # Unfortunately, for other certificate-related errors
                # ISO 15118-2 does not have specific enough failure codes
                response_code = ResponseCode.FAILED
                reason = f"{exc.__class__.__name__} for {exc.subject}"

            if reason:
                logger.error(reason)
            self.stop_state_machine(reason, message, response_code)
            return


class Authorization(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    AuthorizationReq message from the EVCC.

    At this state, the application will assert if the authorization has been
    concluded by running the method `is_authorized` from the evcc_controller.
    If the method returns `Authorized`, then the authorization step is finished
    and the state machine can move on to the `ChargeParameterDiscovery` state,
    otherwise will stay in this state and answer to the EV with
    `EVSEProcessing=Ongoing`.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        # According to requirement [V2G2-684], in case of PnC,
        # the first AuthorizationReq will contain the message
        # signature in the header, but if the EVSEProcessing result is Ongoing
        # then the upcoming requests won't contain the signature. Thus, we
        # only do the signature validation once
        self.signature_verified_once = False
        self.authorization_complete = False

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
        msg = self.check_msg_v2(message, [AuthorizationReq])

        if not msg:
            return

        authorization_req: AuthorizationReq = msg.body.authorization_req

        if self.comm_session.selected_auth_option == AuthEnum.PNC_V2:
            if not self.comm_session.contract_cert_chain:
                self.stop_state_machine(
                    "No contract certificate chain available to "
                    "verify AuthorizationReq",
                    message,
                    ResponseCode.FAILED_SIGNATURE_ERROR,
                )
                return

            if not self.signature_verified_once:
                self.signature_verified_once = True

                # [V2G2-475] The message 'AuthorizationRes' shall contain
                # the ResponseCode 'FAILED_ChallengeInvalid' if the challenge
                # response contained in the AuthorizationReq message in attribute
                # GenChallenge is not valid versus the provided GenChallenge
                # in PaymentDetailsRes.
                if authorization_req.gen_challenge != self.comm_session.gen_challenge:
                    self.stop_state_machine(
                        "[V2G2-475] GenChallenge is not the same in PaymentDetailsRes",
                        message,
                        ResponseCode.FAILED_CHALLENGE_INVALID,
                    )
                    return

                if not verify_signature(
                    signature=msg.header.signature,
                    elements_to_sign=[
                        (
                            authorization_req.id,
                            EXI().to_exi(authorization_req, Namespace.ISO_V2_MSG_DEF),
                        )
                    ],
                    leaf_cert=self.comm_session.contract_cert_chain.certificate,
                ):
                    self.stop_state_machine(
                        "Unable to verify signature of AuthorizationReq",
                        message,
                        ResponseCode.FAILED_SIGNATURE_ERROR,
                    )
                    return

        auth_status: EVSEProcessing = EVSEProcessing.ONGOING
        next_state: Optional[Type["State"]] = Authorization
        # TODO: how should we obtain/hold the token for EIM?  Other cases?
        id_token = (
            self.comm_session.emaid
            if self.comm_session.selected_auth_option == AuthEnum.PNC_V2
            else None
        )
        # note that the certificate_chain and hashed_data are empty here
        # as they were already send previously in the PaymentDetails state

        response_code: Optional[
            Union[ResponseCodeV2, ResponseCodeV20, ResponseCodeDINSPEC]
        ] = ResponseCode.OK
        current_authorization_status = AuthorizationResponse(
            authorization_status=AuthorizationStatus.ONGOING
        )
        if not self.authorization_complete:
            current_authorization_status = (
                await self.comm_session.evse_controller.is_authorized(
                    id_token=id_token,
                    id_token_type=(
                        AuthorizationTokenType.EMAID
                        if self.comm_session.selected_auth_option == AuthEnum.PNC_V2
                        else AuthorizationTokenType.EXTERNAL
                    ),
                )
            )

            if resp_status := current_authorization_status.certificate_response_status:
                # according to table 112 of ISO 15118-2, the Response code
                # for this message can only be one of the following:
                # OK, FAILED,
                # FAILED_SEQUENCE_ERROR, FAILED_SIGNATURE_ERROR,
                # FAILED_UNKNOWN_SESSION or FAILED_CHALLENGE_INVALID

                response_code = (
                    resp_status
                    if resp_status
                    in [
                        ResponseCode.OK,
                        ResponseCode.FAILED,
                        ResponseCode.FAILED_SEQUENCE_ERROR,
                        ResponseCode.FAILED_SIGNATURE_ERROR,
                        ResponseCode.FAILED_UNKNOWN_SESSION,
                        ResponseCode.FAILED_CHALLENGE_INVALID,
                    ]
                    else ResponseCode.FAILED
                )

            if (
                current_authorization_status.authorization_status
                == AuthorizationStatus.ACCEPTED
            ):
                self.authorization_complete = True

        if (
            self.authorization_complete
            and self.comm_session.evse_controller.ready_to_charge()
        ):
            auth_status = EVSEProcessing.FINISHED
            next_state = ChargeParameterDiscovery

        elif (
            current_authorization_status.authorization_status
            == AuthorizationStatus.REJECTED
        ):
            self.stop_state_machine(
                "Authorization was rejected",
                message,
                response_code,
            )
            return
        else:
            # this means we fall into the ongoing case
            auth_status = EVSEProcessing.ONGOING
            next_state = None
            # According to requirement [V2G2-854]
            # If identification mode EIM has been selected by the
            # parameter SelectedPaymentOption equal to "External Payment"
            # in message ServicePaymentSelectReq and no positive EIM information
            # is available an SECC shall set the parameter EVSEProcessing to
            # „Ongoing_WaitingForCustomerInteraction“ in AuthorizationRes.
            if self.comm_session.selected_auth_option == AuthEnum.EIM_V2:
                auth_status = EVSEProcessing.ONGOING_WAITING_FOR_CUSTOMER

        authorization_res = AuthorizationRes(
            response_code=response_code, evse_processing=auth_status
        )

        self.create_next_message(
            next_state,
            authorization_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )


class ChargeParameterDiscovery(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    ChargeParameterDiscoveryReq message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. a ChargeParameterDiscoveryReq
    2. a PowerDeliveryReq (AC)
    3. a CableCheckreq (DC)

    Upon first initialisation of this state, we expect a
    ChargeParameterDiscoveryReq, but after that, the next possible request could
    be either another ChargeParameterDiscoveryReq (if EVSEProcessing=Ongoing in
    the ChargeParameterDiscoveryRes) or a PowerDeliveryReq. So we remain in this
    state until we know which is the following request from the EVCC and then
    transition to the appropriate state (or terminate if the incoming message
    doesn't fit any of the expected requests).

    As a result, the create_next_message() method might be called with
    next_state = None.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_charge_parameter_discovery_req = True

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
        msg = self.check_msg_v2(
            message,
            [ChargeParameterDiscoveryReq, PowerDeliveryReq, CableCheckReq],
            self.expecting_charge_parameter_discovery_req,
        )
        if not msg:
            return

        if msg.body.power_delivery_req:
            await PowerDelivery(self.comm_session).process_message(message, message_exi)
            return

        if msg.body.cable_check_req:
            await CableCheck(self.comm_session).process_message(message, message_exi)
            return

        charge_params_req: ChargeParameterDiscoveryReq = (
            msg.body.charge_parameter_discovery_req
        )

        if charge_params_req.requested_energy_mode not in (
            await self.comm_session.evse_controller.get_supported_energy_transfer_modes(
                Protocol.ISO_15118_2
            )
        ):  # noqa: E501
            self.stop_state_machine(
                f"{charge_params_req.requested_energy_mode} not "
                f"offered as energy transfer mode",
                message,
                ResponseCode.FAILED_WRONG_ENERGY_TRANSFER_MODE,
            )
            return

        evse_data_context = self.comm_session.evse_controller.evse_data_context
        ev_data_context = self.comm_session.evse_controller.ev_data_context

        ev_data_context.selected_energy_mode = charge_params_req.requested_energy_mode
        self.comm_session.selected_charging_type_is_ac = (
            ev_data_context.selected_energy_mode.value.startswith("AC")
        )

        max_schedule_entries: Optional[int] = (
            charge_params_req.max_entries_sa_schedule_tuple
        )

        ac_evse_charge_params: Optional[ACEVSEChargeParameter] = None
        dc_evse_charge_params: Optional[DCEVSEChargeParameter] = None
        if charge_params_req.ac_ev_charge_parameter:
            ac_evse_charge_params = (
                await self.comm_session.evse_controller.get_ac_charge_params_v2()
            )
            evse_data_context.current_type = CurrentType.AC
            # Update EV data context with the DC charge parameters
            ev_data_context.update_ac_charge_parameters_v2(
                charge_params_req.ac_ev_charge_parameter
            )
        else:
            dc_evse_charge_params = (
                await self.comm_session.evse_controller.get_dc_charge_parameters_v2()
            )
            evse_data_context.current_type = CurrentType.DC
            # Update EV data context with the DC charge parameters
            ev_data_context.update_dc_charge_parameters(
                charge_params_req.dc_ev_charge_parameter
            )
        await self.comm_session.evse_controller.send_rated_limits()

        departure_time = (
            ev_data_context.departure_time if ev_data_context.departure_time else 0
        )
        sa_schedule_list = await self.comm_session.evse_controller.get_sa_schedule_list(
            ev_data_context,
            self.comm_session.config.free_charging_service,
            max_schedule_entries,
            departure_time,
        )

        sa_schedule_list_valid = self.validate_sa_schedule_list(
            sa_schedule_list, departure_time
        )

        if (
            sa_schedule_list_valid
            and self.comm_session.ev_session_context.sa_schedule_tuple_id
        ):
            filtered_list = list(
                filter(
                    lambda schedule_entry: schedule_entry.sa_schedule_tuple_id
                    == self.comm_session.ev_session_context.sa_schedule_tuple_id,
                    sa_schedule_list,
                )
            )
            if len(filtered_list) != 1:
                logger.warning(
                    f"Resumed session. Previously selected sa_schedule_list is"
                    f" not present {sa_schedule_list}"
                )
            else:
                logger.info(
                    f"Resumed session. SAScheduleTupleID "
                    f"{self.comm_session.ev_session_context.sa_schedule_tuple_id} "
                    f"present in context"
                )

        if not sa_schedule_list_valid:
            # V2G2-305 : It is still acceptable if the sum of the schedule entry
            # durations falls short of departure_time requested by the EVCC in
            # ChargeParameterDiscoveryReq - EVCC could still request a new schedule
            # when it is on the last entry of the selected schedule.
            logger.warning(
                f"validate_sa_schedule_list() failed. departure_time: {departure_time} "
                f" {sa_schedule_list}"
            )

        signature = None
        next_state: Type[State] = None
        if sa_schedule_list:
            self.comm_session.offered_schedules = sa_schedule_list
            if charge_params_req.ac_ev_charge_parameter:
                next_state = PowerDelivery
            else:
                next_state = CableCheck

            # If a SalesTariff is provided, then sign it
            # This signature should actually be provided by the mobility
            # operator (MO), but for testing purposes you can set it here
            # TODO We should probably have a test mode setting
            for schedule in sa_schedule_list:
                if schedule.sales_tariff:
                    try:
                        element_to_sign = (
                            schedule.sales_tariff.id,
                            EXI().to_exi(
                                schedule.sales_tariff, Namespace.ISO_V2_MSG_DEF
                            ),
                        )
                        signature_key = load_priv_key(
                            KeyPath.MO_SUB_CA2_PEM,
                            KeyEncoding.PEM,
                            KeyPasswordPath.MO_SUB_CA2_PASSWORD,
                        )
                        signature = create_signature([element_to_sign], signature_key)
                    except PrivateKeyReadError as exc:
                        logger.warning(
                            "Can't read private key to needed to create "
                            f"signature for SalesTariff: {exc}"
                        )
                        # If a SalesTariff isn't signed, that's not the end of the
                        # world, no reason to stop the charging process here
                break

            self.expecting_charge_parameter_discovery_req = False
        else:
            self.expecting_charge_parameter_discovery_req = True

        charge_params_res = ChargeParameterDiscoveryRes(
            response_code=ResponseCode.OK,
            evse_processing=(
                EVSEProcessing.FINISHED if sa_schedule_list else EVSEProcessing.ONGOING
            ),
            sa_schedule_list=SAScheduleList(schedule_tuples=sa_schedule_list),
            ac_charge_parameter=ac_evse_charge_params,
            dc_charge_parameter=dc_evse_charge_params,
        )

        self.create_next_message(
            next_state,
            charge_params_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
            signature=signature,
        )

    def validate_sa_schedule_list(
        self, sa_schedules: List[SAScheduleTuple], departure_time: int
    ) -> bool:
        # V2G2-303 - The total duration covered by schedule_entries under
        # p_max_schedule must be equal to the duration_time provided by the EVCC
        # V2G2-304 - If no duration was provided, then the total duration covered
        # must be greater than or equal to 24 hours
        # V2G2-305 - In case, the total duration covered falls short of the duration
        # requested, it is up to the EVCC to request a new schedule via
        # ChargeParameterDiscoveryReq when the last pmax_schedule/sales tariff entry
        # becomes active.
        # In this method - if V2G2-305 is violated the method would return false
        # (but would tolerate if the total duration goes beyond the departure_time)
        valid = True
        duration_24_hours_in_seconds = 86400
        for schedule_tuples in sa_schedules:
            schedule_duration = 0

            p_max_sched = schedule_tuples.p_max_schedule
            if p_max_sched.schedule_entries is not None:
                first_entry_start_time = p_max_sched.schedule_entries[
                    0
                ].time_interval.start
                last_entry_start_time = p_max_sched.schedule_entries[
                    -1
                ].time_interval.start
                last_entry_schedule_duration = p_max_sched.schedule_entries[
                    -1
                ].time_interval.duration
                schedule_duration = (
                    last_entry_start_time - first_entry_start_time
                ) + last_entry_schedule_duration

            # If departure time is not provided, schedule duration must be at least
            # 24 hours
            if departure_time == 0 and schedule_duration < duration_24_hours_in_seconds:
                logger.warning(
                    f"departure_time is not set. schedule duration {schedule_duration}"
                )
                logger.warning(f"Schedule tuples {schedule_tuples}")
                valid = False
                break

            # Not setting this check as equality check as it is possible that the time
            # could be off by few seconds. Also considering V2G2-305, it would suffice
            # if departure_time_total is at least the same as departure_time
            # It is still possible to have a sa_schedule list that doesn't cover
            # the entire duration (V2G2-305). In this case, it is up to the EVCC to
            # request a new schedule via renegotiation while on the last entry in the
            # schedule/sales tariff entry
            elif departure_time != 0 and departure_time < schedule_duration:
                valid = False
                break
        return valid


class PowerDelivery(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    PowerDeliveryReq message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. a PowerDeliveryReq
    2. a ChargeParameterDiscoveryReq
    3. a ChargingStatusReq (AC-Message)
    4. a SessionStopReq
    5. a CurrentDemandReq (DC-Message)
    6. a WeldingDetectionReq (DC-Message)

    Upon first initialisation of this state, we expect a
    PowerDeliveryReq, but after that, the next possible request could
    be either
    - a ChargeParameterDiscoveryReq (if the SECC requests a
    renegotiation of the charging profile),
    - a ChargingStatusReq in case of AC-Charging and if the PowerDeliveryReq's
    ChargeProgress field is set to 'Start',
    - a CurrentDemandReq in case of DC-Charging and if the PowerdeliveryReq's
    ChargeProgress field is set to 'Start',
    - or a SessionStopReq in case of AC-Charging and if the PowerDeliveryReq's
    ChargeProgress field is set to 'Stop'.
    - In case of DC-Charging after a PowerDeliverReq's ChargeProgress field
    is set to 'Stop', the EV can send a WeldingDetectionReq or a SesstionStopReq

    So when a PowerDeliveryReq is received, we know the next state.
    Except when stopping DC-Charging

    As a result, the create_next_message() method might be called with
    next_state = None.
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
        msg = self.check_msg_v2(
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

        if power_delivery_req.sa_schedule_tuple_id not in [
            schedule.sa_schedule_tuple_id
            for schedule in self.comm_session.offered_schedules
        ]:
            self.stop_state_machine(
                f"{power_delivery_req.sa_schedule_tuple_id} "
                "does not match any offered tariff IDs",
                message,
                ResponseCode.FAILED_TARIFF_SELECTION_INVALID,
            )
            return

        if power_delivery_req.dc_ev_power_delivery_parameter:
            self.comm_session.evse_controller.ev_data_context.present_soc = (
                power_delivery_req.dc_ev_power_delivery_parameter.dc_ev_status.ev_ress_soc  # noqa
            )

        # TODO: Investigate this and reassess
        # if (
        #     power_delivery_req.charge_progress == ChargeProgress.START
        #     and not power_delivery_req.charging_profile
        # ):
        #     # Note Lukas Lombriser: I am not sure if I am correct:
        #     # But there is hardly no EV that sends a profile (DC-Charging)
        #     # According Table 40 and Table 104, ChargingProfile is optional
        #
        #     # Although the requirements don't make this 100% clear, it is
        #     # the intention of ISO 15118-2 for the EVCC to always send a
        #     # charging profile if ChargeProgress is set to 'Start'
        #     self.stop_state_machine(
        #         "No charge profile provided although "
        #         "ChargeProgress was set to 'Start'",
        #         message,
        #         ResponseCode.FAILED_CHARGING_PROFILE_INVALID,
        #     )
        #     return

        # [V2G2-225] The SECC shall send the negative ResponseCode
        # FAILED_ChargingProfileInvalid in
        # the PowerDelivery response message if the EVCC sends a ChargingProfile which
        # is not adhering to the PMax values of all PMaxScheduleEntry elements according
        # to the chosen SAScheduleTuple element in the last ChargeParameterDiscoveryRes
        # message sent by the SECC.
        if power_delivery_req.charging_profile:
            if not self._is_charging_profile_valid(power_delivery_req):
                self.stop_state_machine(
                    "[V2G2-225] ChargingProfile is not adhering to the Pmax values in "
                    "ChargeParameterDiscoveryRes",
                    message,
                    ResponseCode.FAILED_CHARGING_PROFILE_INVALID,
                )
                return

        logger.debug(f"ChargeProgress set to {power_delivery_req.charge_progress}")

        next_state: Type[State] = None
        if power_delivery_req.charge_progress == ChargeProgress.START:
            # According to section 8.7.4 in ISO 15118-2, the EV enters into HLC-C
            # (High Level Controlled Charging) once PowerDeliveryRes(ResponseCode=OK)
            # is sent with a ChargeProgress=Start
            # Updates the upper layer with the info if the EV is under HLC-C
            await self.comm_session.evse_controller.set_hlc_charging(True)
            # [V2G2-847] - The EV shall signal CP State C or D no later than 250ms
            # after sending the first PowerDeliveryReq with ChargeProgress equals
            # "Start" within V2G Communication SessionPowerDeliveryReq.

            # [V2G2-860] - If no error is detected, the SECC shall close the Contactor
            # no later than 3s after measuring CP State C or D.
            # Before closing the contactor, we need to check to
            # ensure the CP is in state C or D

            if not await self.wait_for_state_c_or_d():
                logger.warning(
                    "C2/D2 CP state not detected after 250ms in PowerDelivery"
                )

            if not await self.comm_session.evse_controller.is_contactor_closed():
                self.stop_state_machine(
                    "[V2G2-860] Contactor didn't close within the allotted 3 seconds.",
                    message,
                    ResponseCode.FAILED_CONTACTOR_ERROR,
                )
                return

            if self.comm_session.selected_charging_type_is_ac:
                next_state = ChargingStatus
            else:
                next_state = CurrentDemand
            self.comm_session.selected_schedule = (
                power_delivery_req.sa_schedule_tuple_id
            )
            self.comm_session.charge_progress_started = True
        elif power_delivery_req.charge_progress == ChargeProgress.STOP:
            next_state = None
            if self.comm_session.selected_charging_type_is_ac:
                next_state = SessionStop

            # According to section 8.7.4 in ISO 15118-2, the EV is out of the HLC-C
            # (High Level Controlled Charging) once PowerDeliveryRes(ResponseCode=OK)
            # is sent with a ChargeProgress=Stop
            # This needs to be called before any attempt to stop the charger/open the
            # contactor as for every effect, the session will be stopped.
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
                    ResponseCode.FAILED_CONTACTOR_ERROR,
                )
                return

        else:
            # ChargeProgress only has three enum values: Start, Stop, and
            # Renegotiate. So this is the renegotiation case.
            if self.comm_session.charge_progress_started:
                next_state = ChargeParameterDiscovery
            else:
                # TODO Need to check if we really need to terminate the
                #      session here or not
                self.stop_state_machine(
                    "EVCC wants to renegotiate, but charge "
                    "progress has not yet started",
                    message,
                    ResponseCode.FAILED,
                )
                return

        ac_evse_status: Optional[ACEVSEStatus] = None
        dc_evse_status: Optional[DCEVSEStatus] = None
        evse_controller = self.comm_session.evse_controller
        if self.comm_session.selected_charging_type_is_ac:
            ac_evse_status = await evse_controller.get_ac_evse_status()

        else:
            dc_evse_status = await evse_controller.get_dc_evse_status()

        power_delivery_res = PowerDeliveryRes(
            response_code=ResponseCode.OK,
            ac_evse_status=ac_evse_status,
            dc_evse_status=dc_evse_status,
        )

        self.create_next_message(
            next_state,
            power_delivery_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_power_delivery_req = False

    async def wait_for_state_c_or_d(self) -> bool:
        # [V2G2 - 847] The EV shall signal CP State C or D no later than 250ms
        # after sending the first PowerDeliveryReq with ChargeProgress equals
        # "Start" within V2G Communication SessionPowerDeliveryReq.
        STATE_C_TIMEOUT = 0.25

        async def check_state():
            while await self.comm_session.evse_controller.get_cp_state() not in [
                CpState.C2,
                CpState.D2,
            ]:
                await asyncio.sleep(0.05)
            logger.debug(
                f"State is " f"{await self.comm_session.evse_controller.get_cp_state()}"
            )
            return True

        try:
            return await asyncio.wait_for(
                check_state(),
                timeout=STATE_C_TIMEOUT,
            )
        except asyncio.TimeoutError:
            # try one more time to get the latest state
            return await self.comm_session.evse_controller.get_cp_state() in [
                CpState.C2,
                CpState.D2,
            ]

    def _is_charging_profile_valid(self, power_delivery_req: PowerDeliveryReq) -> bool:
        for schedule in self.comm_session.offered_schedules:
            if schedule.sa_schedule_tuple_id == power_delivery_req.sa_schedule_tuple_id:
                schedule_entries = schedule.p_max_schedule.schedule_entries
                # schedule_entries shall look like [PMaxScheduleEntry_0,
                # PMaxScheduleEntry_1, ...]. The enumerate will pair an index with
                # each list entry: (0, PMaxScheduleEntry_0), (1,
                # PMaxScheduleEntry_1), ...
                ev_profile = power_delivery_req.charging_profile
                ev_profile_entries = ev_profile.profile_entries
                cached_start_idx_ev: int = 0
                last_ev_running_idx: int = 0

                for idx, sa_profile_entry in enumerate(schedule_entries):
                    sa_profile_entry_start = sa_profile_entry.time_interval.start

                    sa_entry_pmax = (
                        sa_profile_entry.p_max.value
                        * 10**sa_profile_entry.p_max.multiplier
                    )

                    try:
                        # By getting the next entry/slot, we can know when
                        # the current entry ends
                        next_sa_profile_entry = schedule_entries[idx + 1]
                        sa_profile_entry_end = next_sa_profile_entry.time_interval.start

                    except IndexError:
                        # As the index is out of rage, it signals this is
                        # the final entry of the sa profile. The last entry
                        # must have a duration field, so we can calculate
                        # the end of the period summing the relative start
                        # of the entry with the duration of it
                        sa_profile_entry_end = (
                            sa_profile_entry_start
                            + sa_profile_entry.time_interval.duration
                        )
                    # The cached index and last ev running index are helpers that
                    # allow the for loop to start in the ev profile entry belonging
                    # to the start range of the SA entry. This avoids looping all
                    # over the ev profiles again for each SA entry schedule.
                    # For example, if the SA time schedule is
                    # [0; 1000[ [1000; 2000[ [2000; 3000[
                    # And the EV profile time schedule is
                    # [0, 100[ [100, 400[ [400; 1000[ [1000, inf+[
                    # The first three entries of the ev profile belong
                    # to the time range [0; 1000[ of the SA schedule and
                    # if the EV power, for those three entries
                    # does not surpass the limit imposed by the SA schedule
                    # during that time, then for the next loop iteration,
                    # we dont need to go test those EV time entries again,
                    # as they dont belong to the [1000; 2000[ SA time schedule slot.
                    cached_start_idx_ev += last_ev_running_idx
                    last_ev_running_idx = 0
                    # fmt: off
                    for (ev_profile_idx, ev_profile_entry) in enumerate(
                        ev_profile_entries[cached_start_idx_ev:]
                    ):
                        _is_last_ev_profile = (
                            ev_profile_entry.start == ev_profile_entries[-1].start
                        )

                        if (ev_profile_entry.start < sa_profile_entry_end or _is_last_ev_profile ): # noqa
                            ev_entry_pmax = (ev_profile_entry.max_power.value * 10 ** ev_profile_entry.max_power.multiplier)  # noqa
                            if ev_entry_pmax > sa_entry_pmax:
                                logger.error(
                                    f"EV Profile start {ev_profile_entry.start}s"
                                    f"is out of power range: "
                                    f"EV Max {ev_entry_pmax} W > EVSE Max "
                                    f"{sa_entry_pmax} W \n"
                                )
                                return False

                            if not _is_last_ev_profile:
                                ev_profile_entry_end = ev_profile_entries[
                                    ev_profile_idx + 1
                                ].start
                                if ev_profile_entry_end <= sa_profile_entry_end:
                                    last_ev_running_idx = ev_profile_idx + 1
                            else:
                                logger.debug(
                                    f"EV last Profile start "
                                    f"{ev_profile_entry.start}s is "
                                    f"within time range [{sa_profile_entry_start}; "
                                    f"{sa_profile_entry_end}[ and power range: "
                                    f"EV Max {ev_entry_pmax} W <= EVSE Max "
                                    f"{sa_entry_pmax} W \n"
                                )
                        else:
                            break
                    # fmt: on
        return True


class MeteringReceipt(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes a
    MeteringReceiptReq message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. a MeteringReceiptReq
    2. a ChargingStatusReq
    3. a CurrentDemandReq
    4. a PowerDeliveryReq

    Upon first initialisation of this state, we expect a MeteringReceiptReq, but
    after that, the next possible request could be either a PowerDeliveryReq,
    ChargingStatusReq, or a CurrentDemandReq. So we remain in this
    state until we know which is the following request from the EVCC and then
    transition to the appropriate state (or terminate if the incoming message
    doesn't fit any of the expected requests).

    As a result, the create_next_message() method will be called with
    next_state = None.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_metering_receipt_req = True

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
        msg = self.check_msg_v2(
            message,
            [MeteringReceiptReq, ChargingStatusReq, CurrentDemandReq, PowerDeliveryReq],
            self.expecting_metering_receipt_req,
        )
        if not msg:
            return

        if msg.body.power_delivery_req:
            await PowerDelivery(self.comm_session).process_message(message, message_exi)
            return

        if msg.body.charging_status_req:
            await ChargingStatus(self.comm_session).process_message(
                message, message_exi
            )
            return

        if msg.body.current_demand_req:
            await CurrentDemand(self.comm_session).process_message(message, message_exi)
            return

        metering_receipt_req: MeteringReceiptReq = msg.body.metering_receipt_req

        if not self.comm_session.contract_cert_chain:
            stop_reason = (
                "No contract certificate chain available to verify "
                "signature of MeteringReceiptReq"
            )
        elif not verify_signature(
            msg.header.signature,
            [
                (
                    metering_receipt_req.id,
                    EXI().to_exi(metering_receipt_req, Namespace.ISO_V2_MSG_DEF),
                )
            ],
            self.comm_session.contract_cert_chain.certificate,
        ):
            stop_reason = "Unable to verify signature of MeteringReceiptReq"
        elif not metering_receipt_req.meter_info.meter_reading or (
            self.comm_session.sent_meter_info
            and self.comm_session.sent_meter_info.meter_reading
            and metering_receipt_req.meter_info.meter_reading
            != self.comm_session.sent_meter_info.meter_reading
        ):
            stop_reason = (
                "EVCC's meter info is not a copy of the SECC's meter info "
                "sent in CharginStatusRes/CurrentDemandRes"
            )
        else:
            stop_reason = None

        if stop_reason:
            self.stop_state_machine(
                stop_reason, message, ResponseCode.FAILED_METERING_SIGNATURE_NOT_VALID
            )
            return

        evse_controller = self.comm_session.evse_controller
        if (
            evse_controller.ev_data_context.selected_energy_mode
            and self.comm_session.selected_charging_type_is_ac
        ):
            metering_receipt_res = MeteringReceiptRes(
                response_code=ResponseCode.OK,
                ac_evse_status=await evse_controller.get_ac_evse_status(),
            )
        else:
            metering_receipt_res = MeteringReceiptRes(
                response_code=ResponseCode.OK,
                dc_evse_status=await evse_controller.get_dc_evse_status(),
            )

        self.create_next_message(
            None,
            metering_receipt_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_metering_receipt_req = False


class SessionStop(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    SessionStopReq message from the EVCC.
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
        msg = self.check_msg_v2(message, [SessionStopReq])
        if not msg:
            return
        next_state: Type[State] = None
        if msg.body.session_stop_req.charging_session == ChargingSession.PAUSE:
            next_state = Pause
            session_stop_state = SessionStopAction.PAUSE
        else:
            next_state = Terminate
            session_stop_state = SessionStopAction.TERMINATE
            # EVSessionContext stores information for resuming a paused session.
            # As Terminate is requested, clear context information.
            self.comm_session.ev_session_context = None

        self.comm_session.stop_reason = StopNotification(
            True,
            f"EV requested to {session_stop_state.value} the communication session",
            self.comm_session.writer.get_extra_info("peername"),
            session_stop_state,
        )
        self.create_next_message(
            next_state,
            SessionStopRes(response_code=ResponseCode.OK),
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )


# ============================================================================
# |                     AC SECC STATES - ISO 15118-2                         |
# ============================================================================


class ChargingStatus(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    ChargingStatusReq message from the EVCC.

    The EVCC may send one of the following requests in this state:
    1. a ChargingStatusReq
    2. a PowerDeliveryReq
    3. a MeteringReceiptReq

    Upon first initialisation of this state, we expect a
    ChargingStatusReq, but after that, the next possible request could
    be either another ChargingStatusReq (ongoing energy flow), or a
    PowerDeliveryReq (to either renegotiate the charging profile or to stop the
    power flow), or a MeteringReceiptReq (to exchange metering information).

    So we remain in this state until we know which is the following request from
    the EVCC and then transition to the appropriate state (or terminate if the
    incoming message doesn't fit any of the expected requests).

    As a result, the create_next_message() method might be called with
    next_state = None.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_charging_status_req = True

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
        msg = self.check_msg_v2(
            message,
            [ChargingStatusReq, PowerDeliveryReq, MeteringReceiptReq],
            self.expecting_charging_status_req,
        )
        if not msg:
            return

        if msg.body.power_delivery_req:
            await PowerDelivery(self.comm_session).process_message(message, message_exi)
            return

        if msg.body.metering_receipt_req:
            await MeteringReceipt(self.comm_session).process_message(
                message, message_exi
            )
            return

        # We don't care about signed meter values from the EVCC, but if you
        # do, then set receipt_required to True and set the field meter_info
        evse_controller = self.comm_session.evse_controller
        charging_status_res = ChargingStatusRes(
            response_code=ResponseCode.OK,
            evse_id=await evse_controller.get_evse_id(Protocol.ISO_15118_2),
            sa_schedule_tuple_id=self.comm_session.selected_schedule,
            ac_evse_status=await evse_controller.get_ac_evse_status(),
            evse_max_current=await evse_controller.get_evse_max_current_limit(),
            # TODO Could maybe request an OCPP setting that determines
            #      whether or not a receipt is required and when
            #      (probably only makes sense at the beginning and end of
            #      a charging session). If true, set MeterInfo.
            # meter_info=await self.comm_session.evse_controller.get_meter_info_v2(),
            receipt_required=False,
        )

        if charging_status_res.meter_info:
            self.comm_session.sent_meter_info = charging_status_res.meter_info

        # TODO Check in which case we would set EVSEMaxCurrent and how to
        #      request it via MQTT. Is optional, so let's leave it out for
        #      now.

        # TODO Check if a renegotiation is wanted (would be set in the field
        #      ac_evse_status). Let's leave that out for now.

        # Next request could be another ChargingStatusReq or a
        # PowerDeliveryReq, so we remain in this state for now
        next_state: Optional[Type[State]] = None
        if charging_status_res.receipt_required:
            # But if we set receipt_required to True, we expect a
            # MeteringReceiptReq
            next_state = MeteringReceipt

        self.create_next_message(
            next_state,
            charging_status_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_charging_status_req = False


# ============================================================================
# |                     DC SECC STATES - ISO 15118-2                         |
# ============================================================================


class CableCheck(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    CableCheckReq message from the EVCC.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.cable_check_started = False
        self.contactors_closed = False

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
        msg = self.check_msg_v2(message, [CableCheckReq])
        if not msg:
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

        next_state = None
        evse_processing = EVSEProcessing.ONGOING

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
                IsolationLevel.NO_IMD,
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
            contactors_closed_for_cable_check = (
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

        cable_check_res = CableCheckRes(
            response_code=ResponseCode.OK,
            dc_evse_status=await self.comm_session.evse_controller.get_dc_evse_status(),
            evse_processing=evse_processing,
        )

        self.create_next_message(
            next_state,
            cable_check_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )


class PreCharge(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    PreChargeReq message from the EVCC.
    In this state the EVSE adapts the DC output voltage to the
    requested voltage from the EV.
    The difference between these voltages must be smaller than 20V (according 61851-23).
    The EV sends a PowerDeliveryReq as soon as the precharge process has finished.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_precharge_req = True

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
        msg = self.check_msg_v2(
            message,
            [PreChargeReq, PowerDeliveryReq],
            self.expecting_precharge_req,
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
                Protocol.ISO_15118_2
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
                Protocol.ISO_15118_2
            )
        )

        precharge_res = PreChargeRes(
            response_code=ResponseCode.OK,
            dc_evse_status=dc_charger_state,
            evse_present_voltage=evse_present_voltage,
        )

        next_state = None
        self.create_next_message(
            next_state,
            precharge_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_precharge_req = False


class CurrentDemand(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    CurrentDemandReq message from the EVCC.
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
        msg = self.check_msg_v2(
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

        # Updates the power electronics targets based on EV requests
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

        await self.comm_session.evse_controller.send_display_params()

        # We don't care about signed meter values from the EVCC, but if you
        # do, then set receipt_required to True and set the field meter_info
        evse_controller = self.comm_session.evse_controller
        current_demand_res = CurrentDemandRes(
            response_code=ResponseCode.OK,
            dc_evse_status=await evse_controller.get_dc_evse_status(),
            evse_present_voltage=await evse_controller.get_evse_present_voltage(
                Protocol.ISO_15118_2
            ),
            evse_present_current=await evse_controller.get_evse_present_current(
                Protocol.ISO_15118_2
            ),
            evse_current_limit_achieved=(
                await evse_controller.is_evse_current_limit_achieved()
            ),
            evse_voltage_limit_achieved=(
                await evse_controller.is_evse_voltage_limit_achieved()
            ),
            evse_power_limit_achieved=await evse_controller.is_evse_power_limit_achieved(),  # noqa
            evse_max_voltage_limit=await evse_controller.get_evse_max_voltage_limit(),
            evse_max_current_limit=await evse_controller.get_evse_max_current_limit(),
            evse_max_power_limit=await evse_controller.get_evse_max_power_limit(),
            evse_id=await evse_controller.get_evse_id(Protocol.ISO_15118_2),
            sa_schedule_tuple_id=self.comm_session.selected_schedule,
            # TODO Could maybe request an OCPP setting that determines
            #      whether or not a receipt is required and when
            #      (probably only makes sense at the beginning and end of
            #      a charging session). If true, set MeterInfo.
            # meter_info=await self.comm_session.evse_controller.get_meter_info(
            #     self.comm_session.protocol),
            receipt_required=False,
        )

        if current_demand_res.meter_info:
            self.comm_session.sent_meter_info = current_demand_res.meter_info

        # TODO Check in which case we would set EVSEMaxCurrent and how to
        #      request it via MQTT. Is optional, so let's leave it out for
        #      now.

        # TODO Check if a renegotiation is wanted (would be set in the field
        #      dc_evse_status). Let's leave that out for now.

        # TODO Next request could be another CurrentDemandReq or a
        # PowerDeliveryReq, so we remain in this state for now
        next_state: Optional[Type[State]] = None
        if current_demand_res.receipt_required:
            # But if we set receipt_required to True, we expect a
            # MeteringReceiptReq
            next_state = MeteringReceipt

        self.create_next_message(
            next_state,
            current_demand_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_current_demand_req = False


class WeldingDetection(StateSECC):
    """
    The ISO 15118-2 state in which the SECC processes an
    WeldingDetectionReq message from the EVCC.
    """

    def __init__(self, comm_session: SECCCommunicationSession):
        super().__init__(comm_session, Timeouts.V2G_SECC_SEQUENCE_TIMEOUT)
        self.expecting_welding_detection_req = True

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
        msg = self.check_msg_v2(
            message,
            [
                WeldingDetectionReq,
                SessionStopReq,
            ],
            self.expecting_welding_detection_req,
        )
        if not msg:
            return

        if msg.body.session_stop_req:
            await SessionStop(self.comm_session).process_message(message, message_exi)
            return

        welding_detection_res = WeldingDetectionRes(
            response_code=ResponseCode.OK,
            dc_evse_status=await self.comm_session.evse_controller.get_dc_evse_status(),
            evse_present_voltage=(
                await self.comm_session.evse_controller.get_evse_present_voltage(
                    Protocol.ISO_15118_2
                )
            ),
        )

        next_state = None
        self.create_next_message(
            next_state,
            welding_detection_res,
            Timeouts.V2G_SECC_SEQUENCE_TIMEOUT,
            Namespace.ISO_V2_MSG_DEF,
        )

        self.expecting_welding_detection_req = False


def get_state_by_msg_type(message_type: Type[BodyBase]) -> Optional[Type[State]]:
    states_dict = {
        SessionSetupReq: SessionSetup,
        ServiceDiscoveryReq: ServiceDiscovery,
        ServiceDetailReq: ServiceDetail,
        PaymentServiceSelectionReq: PaymentServiceSelection,
        CertificateInstallationReq: CertificateInstallation,
        PaymentDetailsReq: PaymentDetails,
        AuthorizationReq: Authorization,
        CableCheckReq: CableCheck,
        PreChargeReq: PreCharge,
        ChargeParameterDiscoveryReq: ChargeParameterDiscovery,
        PowerDeliveryReq: PowerDelivery,
        ChargingStatusReq: ChargingStatus,
        CurrentDemandReq: CurrentDemand,
        MeteringReceiptReq: MeteringReceipt,
        WeldingDetectionReq: WeldingDetection,
        SessionStopReq: SessionStop,
    }

    return states_dict.get(message_type, None)
