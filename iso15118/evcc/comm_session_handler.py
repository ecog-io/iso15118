"""
This module contains the EVCC's CommunicationSessionHandler class as well as
its EVCCCommunicationSession class. The former is used to initiate the EVCC
and handle the SDP (SECC Discovery Protocol) exchange with the EVCC, which - if
successful - will result in spawning up an EVCCCommunicationSession object.
That EVCCCommunicationSession object is taking care of the TCP communication
with the SECC to properly exchange all messages in a V2G communication session.
"""

import asyncio
import logging
from asyncio.streams import StreamReader, StreamWriter
from ipaddress import IPv6Address
from typing import Coroutine, List, Optional, Tuple, Union

from pydantic.error_wrappers import ValidationError

from iso15118.evcc.controller.interface import EVControllerInterface
from iso15118.evcc.evcc_config import EVCCConfig
from iso15118.evcc.transport.tcp_client import TCPClient
from iso15118.evcc.transport.udp_client import UDPClient
from iso15118.shared.comm_session import V2GCommunicationSession
from iso15118.shared.exceptions import (
    InvalidSDPResponseError,
    InvalidSettingsValueError,
    InvalidV2GTPMessageError,
    MessageProcessingError,
    SDPFailedError,
)
from iso15118.shared.exi_codec import EXI
from iso15118.shared.iexi_codec import IEXICodec
from iso15118.shared.messages.app_protocol import AppProtocol, SupportedAppProtocolReq
from iso15118.shared.messages.enums import (
    AuthEnum,
    DINPayloadTypes,
    EnergyTransferModeEnum,
    ISOV2PayloadTypes,
    ISOV20PayloadTypes,
    Namespace,
    Protocol,
)
from iso15118.shared.messages.iso15118_2.datatypes import (
    ChargingSession as ChargingSessionV2,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationReq,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ChargingSession as ChargingSessionV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ScheduleExchangeReq,
    ScheduleExchangeRes,
)
from iso15118.shared.messages.iso15118_20.common_types import Processing
from iso15118.shared.messages.sdp import SDPRequest, SDPResponse, Security, Transport
from iso15118.shared.messages.timeouts import Timeouts
from iso15118.shared.messages.v2gtp import V2GTPMessage
from iso15118.shared.notifications import (
    ReceiveTimeoutNotification,
    StopNotification,
    UDPPacketNotification,
)
from iso15118.shared.utils import cancel_task, wait_for_tasks

logger = logging.getLogger(__name__)

SDP_MAX_REQUEST_COUNTER = 50


class EVCCCommunicationSession(V2GCommunicationSession):
    """
    The communication session object for the EVCC, which holds session-specific
    variables and also implements a pausing mechanism.
    """

    def __init__(
        self,
        transport: Tuple[StreamReader, StreamWriter],
        session_handler_queue: asyncio.Queue,
        evcc_config: EVCCConfig,
        iface: str,
        ev_controller: EVControllerInterface,
    ):
        # Need to import here to avoid a circular import error
        # pylint: disable=import-outside-toplevel
        from iso15118.evcc.states.sap_states import SupportedAppProtocol

        # TODO: There must be another way to do this than to pass the self
        # itself into the child. There are just a few attributes in these
        # class. If it is really necessary we can pass them into the child
        # From what I could see, we just use attributes of the V2GCommunication
        # Session, so we dont need to do this self injection, since self
        # is already injected by default on a child
        V2GCommunicationSession.__init__(
            self, transport, SupportedAppProtocol, session_handler_queue, self
        )

        self.config = evcc_config
        self.iface = iface
        # The EV controller that implements the interface EVControllerInterface
        self.ev_controller = ev_controller
        # The authorization option (called PaymentOption in ISO 15118-2) the
        # EVCC selected from the authorization options offered by the SECC
        self.selected_auth_option: Optional[AuthEnum] = None
        # The amount of ServiceDetailReq messages (with the particular service
        # id to request more details for) the EVCC needs to send after having
        # received the ServiceDiscoveryRes
        self.service_details_to_request: List[int] = []
        # Protocols supported by the EVCC as sent to the SECC via
        # the SupportedAppProtocolReq message
        self.supported_app_protocols: List[AppProtocol] = []
        # The Ongoing timer (given in seconds) starts running once the EVCC
        # receives a response with the field EVSEProcessing set to 'Ongoing'.
        # Once the timer is up, the EV will terminate the communication session.
        # A value >= 0 means the timer is running, a value < 0 means it stopped.
        self.ongoing_timer: float = -1
        # Temporarily save the ScheduleExchangeReq, which need to be resent to the SECC
        # if the response message's EVSEProcessing field is set to "Ongoing"
        self.ongoing_schedule_exchange_req: Optional[ScheduleExchangeReq] = None
        # Whether the EV is still processing to calculate the EVPowerProfile.
        # That value is needed across states (ScheduleExchange and PowerDelivery)
        # (ISO 15118-20)
        self.ev_processing: Processing = Processing.FINISHED
        # Temporarily save the ScheduleExchangeRes, in case the EVProcessing field of
        # PowerDeliveryReq is set to "Ongoing", so we can access that response in the
        # following PowerDelivery state (ISO 15118-20)
        self.schedule_exchange_res: Optional[ScheduleExchangeRes] = None
        # Whether to pause or terminate a charging session. Is set when sending
        # a PowerDeliveryReq (ISO 15118-2)
        self.charging_session_stop_v2: Optional[ChargingSessionV2] = None
        # Whether to pause, standby or terminate a charging session. Is set when sending
        # a PowerDeliveryReq (ISO 15118-20)
        self.charging_session_stop_v20: Optional[ChargingSessionV20] = None
        # Whether a renegotiation was requested by the SECC (with either
        # a MeteringReceiptRes, ChargingStatusRes, or CurrentDemandRes) or EVCC
        self.renegotiation_requested = False
        # The ID of the EVSE that controls the power flow to the EV
        self.evse_id: str = ""
        # "Caching" authorization_req. (Required in ISO15118-20)
        # Avoids recomputing the signature, eim, pnc params during authorization loop.
        self.authorization_req_message: Optional[AuthorizationReq] = None
        # The energy mode the EVCC selected (ISO 15118-2)
        self.selected_energy_mode: Optional[EnergyTransferModeEnum] = None
        self.is_tls = False

    def create_sap(self) -> Union[SupportedAppProtocolReq, None]:
        """
        Sends a Supported App Protocol Request (SAP Request) via TCP to the
        SECC to agree upon a mutually supported communication protocol
        (an application layer protocol handshake).
        After receiving the SAP Response, the EVCC will change state to
        SupportedAppProtocol and process the message accordingly.

        Returns:
            A SupportedAppProtocolReq (request) message
        """
        app_protocols = []
        schema_id = 0
        priority = 0
        supported_protocols = self.config.supported_protocols

        # [V2G-DC-618] For DC charging according to DIN SPEC 70121,
        # an SDP server shall send an SECC Discovery Response message with Transport
        # Protocol equal to “TCP” and Security equal to “No transport layer security”
        # according to Table 23. Remove it from the supported protocols list if
        # use_tls is enabled
        if self.is_tls:
            try:
                supported_protocols.remove(Protocol.DIN_SPEC_70121)
                logger.warning(
                    "Removed DIN_SPEC from the list of supported Protocols as "
                    "TLS is enabled"
                )
            except ValueError:
                pass

        for protocol in supported_protocols:
            # A SchemaID (schema_id) is simply a running counter, enabling the
            # SECC to refer to a specific entry. It can, in principle, be
            # randomly chosen by the EVCC as long as it's in the value range of
            # one byte (=255). Each app_protocol_entry must have a different
            # schema_id and max. 20 app_protocol_entry elements are allowed
            # according to ISO 15118 and DIN SPEC 70121.
            #
            # We start by assigning the number 1 to the first entry and simply
            # increase the counter by 1 for each following entry.
            #
            # To enforce a specific priority of protocols, make sure to list
            # them in descending order in evcc_settings.SUPPORTED_PROTOCOLS
            schema_id += 1
            priority += 1
            app_protocol_entry = AppProtocol(
                protocol_ns=protocol.ns.value,
                major_version=(
                    2
                    if protocol in [Protocol.ISO_15118_2, Protocol.DIN_SPEC_70121]
                    else 1
                ),
                minor_version=0,
                schema_id=schema_id,
                priority=priority,
            )
            app_protocols.append(app_protocol_entry)

        self.supported_app_protocols = app_protocols
        sap_req = SupportedAppProtocolReq(app_protocol=self.supported_app_protocols)

        return sap_req

    async def send_sap(self):
        """
        Sends the Supported App Protocol Request

        Raises:
            MessageProcessingError, in case the instantiation of a
            SupportedAppProtocolRequest fails
        """
        try:
            sap_req = self.create_sap()
        except ValidationError as exc:
            logger.exception(
                "Validation error occurred while creating "
                f"SupportedAppProtocolReq: {exc}"
            )
            raise MessageProcessingError("SupportedAppProtocolReq") from exc

        v2gtp_msg = V2GTPMessage(
            Protocol.UNKNOWN,
            ISOV2PayloadTypes.EXI_ENCODED,
            EXI().to_exi(sap_req, Namespace.SAP),
        )
        self.current_state.message = sap_req
        await self.send(v2gtp_msg)

    def save_session_info(self):
        """
        Saves the values that need to be persisted during a charging pause
        according to section 8.4.2 in ISO 15118-2
        TODO Check what needs to happen in a pause with ISO 15118-20
        """
        logger.debug(
            "Writing session variables to settings for use when "
            "resuming the communication session later"
        )

        # === PAUSING RELATED INFORMATION ===
        # If a charging session needs to be paused, the EVCC needs to persist certain
        # information that must be provided again once the communication session
        # resumes. This information includes:
        # - Session ID: int or None
        # - Selected authorization option: must be a member of AuthEnum enum or None
        # - Requested energy transfer mode: must be a member of EnergyTransferModeEnum
        #                                   or None
        # TODO Check what ISO 15118-20 demands for pausing

        # TODO: save the settings into redis
        # RESUME_SESSION_ID = self.session_id
        # RESUME_SELECTED_AUTH_OPTION = self.selected_auth_option
        # RESUME_REQUESTED_ENERGY_MODE = self.selected_energy_mode


class CommunicationSessionHandler:
    """
    The CommunicationSessionHandler is the control center that manages the
    communication session with the SECC.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        config: EVCCConfig,
        iface: str,
        codec: IEXICodec,
        ev_controller: EVControllerInterface,
    ):
        self.list_of_tasks: List[Coroutine] = []
        self.udp_client: UDPClient = None
        self.tcp_client: TCPClient = None
        self.tls_client: bool = None
        self.config: EVCCConfig = config
        self.iface: str = iface
        self.ev_controller: EVControllerInterface = ev_controller
        self.sdp_retries_number = SDP_MAX_REQUEST_COUNTER
        self._sdp_retry_cycles = self.config.sdp_retry_cycles

        # Set the selected EXI codec implementation
        EXI().set_exi_codec(codec)

        # Receiving queue for UDP client to notify about incoming datagrams
        self._rcv_queue: asyncio.Queue = asyncio.Queue(0)

        # The communication session is a tuple containing the session itself
        # and the associated task, so we can cancel the task when needed
        self.comm_session: Tuple[
            Optional[V2GCommunicationSession], Optional[asyncio.Task]
        ] = (None, None)

    async def start_session_handler(self):
        """
        This method is necessary, because python does not allow
        async def __init__. Therefore, we need to create a separate async
        method to be our constructor.
        """
        self.udp_client = UDPClient(self._rcv_queue, self.iface)
        self.list_of_tasks = [
            self.udp_client.start(),
            self.get_from_rcv_queue(self._rcv_queue),
            self.restart_sdp(True),
        ]

        logger.info("Communication session handler started")

        await wait_for_tasks(self.list_of_tasks)

    async def send_sdp(self):
        """
        Sends an SECC Discovery Protocol Request (SDP Request) via UDP to
        the SECC to retrieve the IP address and port of the SECC so that we
        can establish a TCP connection to the SECC's TCP server, given the
        IP address and port contained in the SDP Response
        """
        # the following loop is to allow the synchronization of the udp client
        # and the task to handle the SDP restart
        while not self.udp_client.started:
            await asyncio.sleep(0.1)
        security = Security.NO_TLS
        if self.config.use_tls:
            security = Security.TLS
        sdp_request = SDPRequest(security=security, transport_protocol=Transport.TCP)
        v2gtp_msg = V2GTPMessage(
            Protocol.UNKNOWN, sdp_request.payload_type, sdp_request.to_payload()
        )
        logger.info(f"Sending SDPRequest: {sdp_request}")
        await self.udp_client.send_and_receive(v2gtp_msg)

    async def restart_sdp(self, new_sdp_cycle: bool):
        """
        Initiates a new SECC Discovery Protocol (SDP) request message, which the
        EVCC sends to the SECC via UDP.

        The SDP messages are sent via UDP and the EVCC expects an SDP response
        from the SECC within 250 ms. If the EVCC runs into a timeout, it will
        send another SDP request. Up to 49 retries (50 SDP requests in total)
        are allowed before the SDP is deemed unsuccessful. As a result,
        the ISO 15118 communication cannot proceed and the EV would have to
        fall back to analog PWM (Pulse Width Modulation) based charging.

        The constant SDP_MAX_REQUEST_COUNTER is used to compare the current
        SDP request counter with the maximum allowed number of SDP requests in
        one go (50).

        However, once SDP was successful and the ISO 15118 communication
        proceeds, an error can occur later while processing one of the messages.
        It is up to the car manufacturer to decide how many times the EV should
        try to restart the communication, starting with the SDP. The rationale
        here is that this same error might not occur twice (maybe there was an
        unfortunate bit flip, for example).

        For restarting an SDP, we use the SDP_RETRY_CYCLES setting in the
        evcc_settings.py file. One SDP_RETRY_CYCLE can send up to 50 SDP
        consecutive requests before the cycle is over.

        Args:
            new_sdp_cycle:  True, if a new SDP cycle shall be initiated, which
                            would be the case if the previous SDP cycle resulted
                            in a V2GCommunicationSession and that session was
                            terminated. False, if a timeout occurred while
                            waiting for the SDP response, which triggers sending
                            another SDP request until SDP_MAX_REQUEST_COUNTER
                            is reached.

        Raises:
            SDPFailedError
        """
        shutdown_msg = (
            "Shutting down high-level communication. Unplug and "
            "plug in the cable again if you want to start anew."
        )

        if new_sdp_cycle:
            if self._sdp_retry_cycles == 0:
                raise SDPFailedError(
                    f"EVCC tried to initiate a V2GCommunicationSession, "
                    f"but maximum number of SDP retry cycles "
                    f"({self.config.sdp_retry_cycles}) is now reached. {shutdown_msg}"
                )

            self._sdp_retry_cycles -= 1
            self.sdp_retries_number = SDP_MAX_REQUEST_COUNTER
            logger.debug(
                "Initiating new SDP cycle, "
                f"{self._sdp_retry_cycles} more cycles(s) left"
            )

        if self.sdp_retries_number > 0:
            logger.info(f"Remaining SDP requests: {self.sdp_retries_number}")
            try:
                await self.send_sdp()
            except InvalidSettingsValueError as exc:
                logger.error(
                    f"Invalid value for {exc.entity} setting "
                    f"{exc.setting}: {exc.invalid_value}"
                )

            self.sdp_retries_number -= 1
        else:
            self.sdp_retries_number = SDP_MAX_REQUEST_COUNTER
            raise SDPFailedError(f"SDPRequest was not successful. " f"{shutdown_msg}")

    async def start_comm_session(self, host: IPv6Address, port: int, is_tls: bool):
        server_type = "TLS" if is_tls else "TCP"

        try:
            logger.info(
                f"Starting {server_type} client, trying to connect to "
                f"{host.compressed} at port {port} ..."
            )
            self.tcp_client = await TCPClient.create(
                host, port, self._rcv_queue, is_tls, self.iface
            )
            logger.info("TCP client connected")
        except Exception as exc:
            logger.exception(
                f"{exc.__class__.__name__} when trying to connect "
                f"to host {host} and port {port}"
            )
            return

        comm_session = EVCCCommunicationSession(
            (self.tcp_client.reader, self.tcp_client.writer),
            self._rcv_queue,
            self.config,
            self.iface,
            self.ev_controller,
        )
        # Overwriting is_tls field in EVCCCommunicationSession with the setting
        # returned from SDP response. Remember is_tls field in config still represents
        # the value initially provided in evcc_config.
        comm_session.is_tls = is_tls

        try:
            await comm_session.send_sap()
            self.comm_session = comm_session, asyncio.create_task(
                comm_session.start(Timeouts.SUPPORTED_APP_PROTOCOL_REQ)
            )
        except MessageProcessingError as exc:
            logger.exception(
                f"{exc.__class__.__name__} occurred while trying to "
                f"create create an SDPRequest"
            )
            return

    async def process_incoming_udp_packet(self, message: UDPPacketNotification):
        """
        We expect this to be an SDP response from the UDP server.
        Let's first check if it could be an SDP response with or without PPD
        (pairing and positioning device -> ACD-pantograph in ISO 15118-20)

        Args:
            message:    The UDPPacket containing an SDP response message
        """
        try:
            v2gtp_msg = V2GTPMessage.from_bytes(Protocol.UNKNOWN, message.data)
        except InvalidV2GTPMessageError as exc:
            logger.error(exc)
            return

        if v2gtp_msg.payload_type in [
            ISOV2PayloadTypes.SDP_RESPONSE,
            DINPayloadTypes.SDP_RESPONSE,
        ]:
            try:
                sdp_response = SDPResponse.from_payload(v2gtp_msg.payload)
            except InvalidSDPResponseError as exc:
                logger.error(exc)
                try:
                    await self.restart_sdp(True)
                    return
                except SDPFailedError as exc:
                    logger.exception(exc)
                    return  # TODO check if this is correct here

            logger.info(f"SDPResponse received: {sdp_response}")

            secc_signals_tls = False
            if sdp_response.security == Security.TLS:
                secc_signals_tls = True

            # The idea here is to use both the USE_TLS and ENFORCE_TLS setting of the
            # EVCC. USE_TLS can be used to set the Security byte field of the SDP
            # request to either 0x00 (TLS) or 0x10 (no NO_TLS). It's basically there
            # just to test both use cases.
            #
            # The ENFORCE_SECURITY setting can be used by the EV OEM to make sure the EV
            # only accepts TLS-secured communication sessions, if set to True. If set
            # to False, and USE_TLS is set to True, then the EVCC can also accept an
            # unsecure communication (triggered by the SECC sending an SDP response with
            # the Security byte field set to 0x10 (no NO_TLS)).
            #
            # The rationale behind this might be that the EV OEM trades convenience
            # (the EV driver can always charge) over security.
            if (not secc_signals_tls and self.config.enforce_tls) or (
                secc_signals_tls and not self.config.use_tls
            ):
                logger.error(
                    "Security mismatch, can't initiate communication session."
                    f"\nEVCC setting USE_TLS: {self.config.use_tls}"
                    f"\nEVCC setting ENFORCE_TLS: {self.config.enforce_tls}"
                    f"\nSDP response signals TLS: {secc_signals_tls}"
                )
                return

            ip_address_int = int.from_bytes(sdp_response.ip_address, "big")
            host = IPv6Address(ip_address_int)
            port = sdp_response.port
        elif v2gtp_msg.payload_type == ISOV20PayloadTypes.SDP_RESPONSE_WIRELESS:
            raise NotImplementedError(
                "The incoming datagram seems to be a SDPResponse "
                "for wireless communication (used for ACD-P). "
                "This feature is not yet implemented."
            )
        else:
            logger.error(
                f"Incoming datagram of {len(message)} bytes is no "
                f"valid SDPResponse message"
            )
            try:
                await self.restart_sdp(True)
            except SDPFailedError as exc:
                logger.exception(exc)
                return  # TODO check if this is correct here
            return

        await self.start_comm_session(host, port, secc_signals_tls)

    async def get_from_rcv_queue(self, queue: asyncio.Queue):
        """
        Waits for an incoming message from the UDP server or a notification
        from an ongoing EVCCCommunicationSession instance (e.g. ReceiveTimeout
        or a notification to pause or terminate the session).
        It will then be further processed accordingly.
        """
        while True:
            try:
                notification = queue.get_nowait()
            except asyncio.QueueEmpty:
                notification = await queue.get()

            try:
                if isinstance(notification, UDPPacketNotification):
                    await self.process_incoming_udp_packet(notification)
                elif isinstance(notification, ReceiveTimeoutNotification):
                    try:
                        await self.restart_sdp(False)
                    except SDPFailedError as exc:
                        logger.exception(exc)
                        # TODO not sure what else to do here
                elif isinstance(notification, StopNotification):
                    await cancel_task(self.comm_session[1])
                    del self.comm_session
                    if notification.successful:
                        break
                    else:
                        try:
                            await self.restart_sdp(True)
                        except SDPFailedError as exc:
                            logger.exception(exc)
                            # TODO not sure what else to do here
                else:
                    logger.warning(
                        "Communication session handler received "
                        "an unknown message or notification: "
                        f"{notification}"
                    )
            finally:
                queue.task_done()
