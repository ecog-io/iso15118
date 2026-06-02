import base64
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Type, Union

from pydantic.v1 import ValidationError

from iso15118.shared.exceptions import (
    EXIEncodingError,
    InvalidPayloadTypeError,
    InvalidProtocolError,
)
from iso15118.shared.exi_codec import EXI
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.din_spec.body import Body as BodyDINSPEC
from iso15118.shared.messages.din_spec.body import BodyBase as BodyBaseDINSPEC
from iso15118.shared.messages.din_spec.datatypes import FaultCode as FaultCodeDINSPEC
from iso15118.shared.messages.din_spec.datatypes import (
    Notification as NotificationDINSPEC,
)
from iso15118.shared.messages.din_spec.header import (
    MessageHeader as MessageHeaderDINSPEC,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.enums import (
    DINPayloadTypes,
    ISOV2PayloadTypes,
    ISOV20PayloadTypes,
    Namespace,
)
from iso15118.shared.messages.iso15118_2.body import Body, BodyBase
from iso15118.shared.messages.iso15118_2.datatypes import FaultCode, Notification
from iso15118.shared.messages.iso15118_2.header import MessageHeader as MessageHeaderV2
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.v2gtp import V2GTPMessage
from iso15118.shared.messages.xmldsig import Signature

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # EVCCCommunicationSession and SECCCommunicationSession are used for
    # annotation purposes only, as a type hint for the comm_session class
    # attribute. But comm_session also imports State. To avoid a circular import
    # error, one can use the TYPE_CHECKING boolean from typing, which evaluates
    # to True during mypy or other 3rd party type checker but assumes the value
    # 'False' during runtime.
    # Please check:
    # https://stackoverflow.com/questions/61545580/how-does-mypy-use-typing-type-checking-to-resolve-the-circular-import-annotation
    # https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING
    from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
    from iso15118.secc.comm_session_handler import SECCCommunicationSession


class Base64:
    def __init__(self, message: str, message_name: str, namespace: Namespace):
        """
        This was added to help indicate the type of payload for base64 encoded types.
        Used for CertificateInstallationRes received from backend.
        self.message = base64 encoded payload type
        self.message_type = A string representing the type of the message.
        self.namespace = The namespace of the message
        """
        self.message = message
        self.message_name = message_name
        self.namespace = namespace

    def __str__(self):
        return self.message_name


class State(ABC):
    """
    State Base Class

    A state in which
    - the EVCC is processing an incoming response message from the SECC, or
    - the SECC is processing an incoming request message from the EVCC
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        comm_session: Union["EVCCCommunicationSession", "SECCCommunicationSession"],
        timeout: Union[float, int] = 0,
    ):
        """
        Initialises a state to process a new message. Every state that inherits
        from State needs to implement __init__ and call super().__init__() with
        the corresponding timeout parameter for that state.

        Args:
            timeout: The amount of seconds to wait for an incoming message to
                     process before raising a timeout
        """
        self.comm_session: Union[
            "EVCCCommunicationSession", "SECCCommunicationSession"
        ] = comm_session
        self.comm_session.current_state = self
        # The amount of seconds to wait for an incoming message
        self.timeout: Union[float, int] = 0
        # The next state to transition to after processing the incoming message,
        # which is either a normal State (if waiting for another message), or
        # Terminate (if the session shall be terminated) or Pause (if the session
        # shall be paused and certain session values shall be saved until the
        # session is resumed later on)
        self.next_state: Optional[Type["State"]] = None
        # The optional signature in a V2GMessage's header
        self.next_msg_signature: Optional[Signature] = None
        # The next message, which is either a
        # SupportedAppProtocolReq,
        # SupportedAppProtocolRes,
        # a BodyBase instance of an ISO 15118-20 V2GMessage,
        # a BodyBase of DINSPEC V2G Message
        # or an instance of an ISO 15118-20 V2GMessage
        self.message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
            Base64,
            None,
        ] = None
        # Each V2GMessage (and SupportedAppProtocolReq and -Res)
        # is first EXI encoded and then placed as a payload in a V2GTP
        # (V2G Transfer Protocol) message, which is then sent to the counterpart
        self.next_v2gtp_msg: Optional[V2GTPMessage] = None
        # The timeout corresponding to waiting for the subsequent message as a
        # result of sending this next message
        self.next_msg_timeout: Union[float, int] = 0

        logger.info(f"Entered state {str(self)}")

        if timeout > 0:
            self.timeout = timeout
            logger.debug(f"Waiting for up to {timeout} s")

    @abstractmethod
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
        """
        Every State must implement this method to process the incoming message,
        which is either a request message (SECC) or a response message (EVCC) of
        DIN SPEC 70121, ISO 15118-2, or ISO 15118-20.

        Args:
            message: Either a DIN SPEC 70121, ISO 15118-2 message, or
                     ISO 15118-20 message
            message_exi: EXI stream representation of the message

        At first, each state must check the incoming message with the method
        check_msg() before further processing the message's content.

        If the further processing of an incoming message yields an error, you must
        immediately call the method stop_state_machine() return from process_message().

        Raises:
            MessageProcessingError, FaultyStateImplementationError
        """
        raise NotImplementedError

    def create_next_message(
        self,
        next_state: Optional[Type["State"]],
        next_msg: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            BodyBase,
            V2GMessageV20,
            BodyBaseDINSPEC,
            Base64,
        ],
        next_msg_timeout: Union[float, int],
        namespace: Namespace,
        next_msg_payload_type: Union[
            DINPayloadTypes, ISOV2PayloadTypes, ISOV20PayloadTypes
        ] = ISOV2PayloadTypes.EXI_ENCODED,
        signature: Signature = None,
    ):
        """
        Is called in case the processing of an incoming message was successful.
        Provides all the necessary information to create the next V2GTP
        (V2G Transfer Protocol) message. The communication session object will
        then take care of sending it over to the counterpart (EVCC or SECC)
        and waiting for 'timeout' seconds to receive the subsequent message.

        Steps to be done in this method:
        1. Set the next state and timeout for receiving the subsequent message
           in order for the state machine to proceed properly
        2. Create the V2GMessage from the provided 'message' parameter in case
           it is an ISO 15118-2 V2GMessage (where the message is actually the
           body element of the V2GMessage).
        3. EXI-encode the new message
        4. Create the next V2GTP message given the EXI-encoded message and the
           payload type.

        Args:
            next_state: The next state to transition to, or None, if we want to
                        stay in the same state in case the EVCC can send one of
                        several possible requests. In the latter case, the state
                        must be able to expect more than one type of request.

                        For example:
                        When sending the ServiceDetailRes, the next request
                        from the EVCC could be either another ServiceDetailReq
                        (if the list of offered services in ServiceDetailRes
                        contained more than one value-added service) or a
                        PaymentServiceSelectionReq. If the request is of type
                        ServiceDetailReq, we'll just use the same state's logic
                        to process the message. If the request is of type
                        PaymentServiceSelectionReq, we transition to the state
                        PaymentServiceSelection and use that state's
                        process_message() method to process the request.
            next_msg: The next message content (to be EXI-encoded and wrapped
                      into a V2GTP - V2G Transfer Protocol - message)
            next_msg_timeout: The amount of seconds to wait for the subsequent
                              message from the counterpart (EVCC or SECC)
            namespace: The XSD namespace used for EXI encoding the message
            next_msg_payload_type: The payload type of the next message content
                                   (necessary for building the V2GTP message)
            signature: The Signature element for the Header of an ISO 15118-2
                       V2GMessage. Optional as it is only needed for those
                       messages that need a digital signature
                       (e.g. AuthorizationReq, CertificateInstallationReq,
                       CertificateInstallationRes).
                       In ISO 15118-20, the optional signature is already part
                       of the message object.

        Raises:
            EXIEncodingError
        """
        # Step 1
        self.next_state = next_state
        self.next_msg_timeout = next_msg_timeout
        exi_payload: bytes = bytes(0)

        # Step 2
        if not next_msg:
            logger.error("Parameter 'message' of create_next_message() is " "None")
            return
        to_be_exi_encoded: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ] = None
        if isinstance(next_msg, BodyBaseDINSPEC):
            note_dinspec: Union[NotificationDINSPEC, None] = None
            if (
                self.comm_session.stop_reason
                and not self.comm_session.stop_reason.successful
            ):
                # The fault message must not be bigger than 64 characters according to
                # the XSD data type description
                if len(self.comm_session.stop_reason.reason) > 64:
                    fault_msg = self.comm_session.stop_reason.reason[:62] + ".."
                else:
                    fault_msg = self.comm_session.stop_reason.reason
                note_dinspec = NotificationDINSPEC(
                    fault_code=FaultCodeDINSPEC.PARSING_ERROR, fault_msg=fault_msg
                )
            header_dinspec: MessageHeaderDINSPEC = MessageHeaderDINSPEC(
                session_id=self.comm_session.session_id,
                signature=signature,
                notification=note_dinspec,
            )
            body_dinspec: BodyDINSPEC = BodyDINSPEC.parse_obj(
                {str(next_msg): next_msg.dict()}
            )
            try:
                to_be_exi_encoded = V2GMessageDINSPEC(
                    header=header_dinspec, body=body_dinspec
                )
            except ValidationError as exc:
                logger.exception(exc)
                raise exc
            self.message = to_be_exi_encoded
        elif isinstance(next_msg, BodyBase):
            note: Union[Notification, None] = None
            if (
                self.comm_session.stop_reason
                and not self.comm_session.stop_reason.successful
            ):
                # The fault message must not be bigger than 64 characters according to
                # the XSD data type description
                if len(self.comm_session.stop_reason.reason) > 64:
                    fault_msg = self.comm_session.stop_reason.reason[:62] + ".."
                else:
                    fault_msg = self.comm_session.stop_reason.reason
                note = Notification(
                    fault_code=FaultCode.PARSING_ERROR, fault_msg=fault_msg
                )
            header: MessageHeaderV2 = MessageHeaderV2(
                session_id=self.comm_session.session_id,
                signature=signature,
                notification=note,
            )
            body: Body = Body.parse_obj({str(next_msg): next_msg.dict()})
            try:
                to_be_exi_encoded = V2GMessageV2(header=header, body=body)
            except ValidationError as exc:
                logger.exception(exc)
                raise exc
            self.message = to_be_exi_encoded
        elif isinstance(next_msg, Base64):
            # Incoming message is base64 encoded EXI message.
            # So a base64 decode should retrieve the EXI stream.
            self.message = next_msg
            exi_payload = base64.b64decode(next_msg.message)
            if exi_payload:
                logger.info(
                    f"Already EXI encoded. Content: "
                    f"{EXI().get_exi_codec().decode(exi_payload,next_msg.namespace)}"
                )
        else:
            to_be_exi_encoded = next_msg
            self.message = to_be_exi_encoded

        # If to_be_exi_encoded is None it is possible that exi_payload is already
        # set (for eg:CertificateInstallationRes from backend).
        # Otherwise, EXI encode the message.
        if to_be_exi_encoded and next_msg_payload_type:
            # Step 3
            try:
                exi_payload = EXI().to_exi(to_be_exi_encoded, namespace)

                if hasattr(self.comm_session, "evse_id"):
                    logger.trace(  # type: ignore[attr-defined]
                        f"{self.comm_session.evse_id}:::"
                        f"{exi_payload.hex()}:::"
                        f"{namespace.value}"
                    )
            except EXIEncodingError as exc:
                logger.error(f"{exc}")
                self.next_state = Terminate
                raise

        # Step 4
        try:
            # Each V2GMessage (and SupportedAppProtocolReq and -Res)
            # is first EXI encoded and then placed as a payload in a
            # V2GTPMessage (V2G Transfer Protocol message)
            self.next_v2gtp_msg = V2GTPMessage(
                self.comm_session.protocol, next_msg_payload_type, exi_payload
            )
        except (InvalidProtocolError, InvalidPayloadTypeError) as exc:
            logger.exception(
                f"{exc.__class__.__name__} occurred while "
                f"creating a V2GTPMessage. {exc}"
            )

    def __repr__(self):
        """
        Returns the object representation in string format
        """
        return self.__str__()

    def __str__(self):
        """
        Returns the name of the State
        """
        return self.__class__.__name__


class Terminate(State):
    def __init__(
        self,
        comm_session: Union["EVCCCommunicationSession", "SECCCommunicationSession"],
    ):
        super().__init__(comm_session)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
            Base64,
        ],
        message_exi: bytes = None,
    ):
        pass


class Pause(State):
    def __init__(
        self,
        comm_session: Union["EVCCCommunicationSession", "SECCCommunicationSession"],
    ):
        super().__init__(comm_session)

    async def process_message(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
            Base64,
        ],
        message_exi: bytes = None,
    ):
        pass
