"""
This module contains the abstract class for an SECC-specific state,
which extends the state shared between the EVCC and SECC.
"""

import logging
from abc import ABC
from typing import List, Optional, Type, TypeVar, Union

from iso15118.secc.comm_session_handler import SECCCommunicationSession
from iso15118.shared.messages.app_protocol import (
    ResponseCodeSAP,
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.din_spec.body import BodyBase as BodyBaseDINSPEC
from iso15118.shared.messages.din_spec.body import (
    SessionSetupReq as SessionSetupReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import get_msg_type as get_msg_type_dinspec
from iso15118.shared.messages.din_spec.datatypes import (
    ResponseCode as ResponseCodeDINSPEC,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.enums import Namespace
from iso15118.shared.messages.iso15118_2.body import BodyBase as BodyBaseV2
from iso15118.shared.messages.iso15118_2.body import (
    SessionSetupReq as SessionSetupReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    get_msg_type,
)
from iso15118.shared.messages.iso15118_2.datatypes import ResponseCode as ResponseCodeV2
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.common_messages import (
    SessionSetupReq as SessionSetupReqV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    ResponseCode as ResponseCodeV20,
)
from iso15118.shared.messages.iso15118_20.common_types import V2GMessage
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GRequest as V2GRequestV20,
)
from iso15118.shared.notifications import StopNotification
from iso15118.shared.states import State, Terminate

logger = logging.getLogger(__name__)


class StateSECC(State, ABC):
    """
    Extends the State shared across EVCC and SECC.

    Every state subclassing StateSECC must implement State's process_message()
    and follow these steps while doing so:

    1.  Check if the incoming message is valid with State's is_message_valid()
    2.a If step 1 returns True, process the message's content accordingly.
        If the processing is successful, prepare the transition to the next
        state with State's create_next_message().
        If the processing is not successful, terminate the session with
        stop_secc()
    2.b If step 2 returns False, terminate the session with stop_secc()
    """

    # The response code can be set by various methods on which a State's
    # process_message() method might rely on, such as is_message_valid().
    # The default response code 'OK' can be overwritten as needed.
    response_code: Union[ResponseCodeDINSPEC, ResponseCodeV2, ResponseCodeV20] = (
        ResponseCodeV2.OK
    )

    def __init__(
        self, comm_session: "SECCCommunicationSession", timeout: Union[float, int] = 0
    ):
        """
        Initialises a state to process a new message. Every state that inherits
        from State needs to implement __init__ and call super().__init__() with
        the corresponding timeout parameter for that state.

        Args:
            comm_session:   The V2GCommunicationSession object of SECC.
                            Needed to access certain session variables, as certain
                            states need to read and store session relevant information,
                            depending on the message.

                            For example: the SupportedAppProtocolReq message
                            contains information about the EVCC's supported
                            protocol, which is relevant information needed
                            throughout the session.
        """
        super().__init__(comm_session, timeout)
        self.comm_session: "SECCCommunicationSession" = comm_session

    T = TypeVar("T")

    def check_msg_dinspec(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_msg_types: List[
            Union[
                Type[SupportedAppProtocolReq],
                Type[BodyBaseDINSPEC],
                Type[V2GRequestV20],
                Type[BodyBaseV2],
            ]
        ],
        expect_first: bool = True,
    ) -> V2GMessageDINSPEC:
        return self.check_msg(
            message, V2GMessageDINSPEC, expected_msg_types, expect_first
        )

    def check_msg_v2(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_msg_types: List[
            Union[
                Type[SupportedAppProtocolReq],
                Type[BodyBaseV2],
                Type[V2GRequestV20],
                Type[BodyBaseDINSPEC],
            ]
        ],
        expect_first: bool = True,
    ) -> V2GMessageV2:
        return self.check_msg(message, V2GMessageV2, expected_msg_types, expect_first)

    def check_msg_v20(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_msg_types: List[
            Union[
                Type[SupportedAppProtocolReq],
                Type[BodyBaseV2],
                Type[V2GRequestV20],
                Type[BodyBaseDINSPEC],
            ]
        ],
        expect_first: bool = True,
    ) -> V2GMessageV20:
        return self.check_msg(message, V2GMessageV20, expected_msg_types, expect_first)

    def check_msg(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_return_type: Type[T],
        expected_msg_types: List[
            Union[
                Type[SupportedAppProtocolReq],
                Type[BodyBaseV2],
                Type[V2GRequestV20],
                Type[BodyBaseDINSPEC],
            ]
        ],
        expect_first: bool = True,
    ) -> Optional[T]:
        """
        This function is used to reduce code redundancy in the process_message()
        method of each SECC state. The following checks are covered:
        1. Whether or not the incoming message is expected at this state
        2. Whether or not the session ID is valid (for messages after SessionSetupRes)

        Args:
            message: A request message of type EXIMessage
            expected_return_type: A type indication as to which of the Union types of
                                  the first 'message' parameter we are expecting. This
                                  will either be of type SupportedAppProtocolReq,
                                  V2GMessageV2 (ISO 15118-2), V2GMessageV20
                                  (ISO 15118-20) or V2GMessageDINSPEC. This helps to narrow
                                  down the return type and to avoid lots of mypy errors
                                  (e.g. saying "SupportedAppProtocolReq has
                                  no attribute 'body'")
            expected_msg_types: The expected request message type, in particular the
                                message body
            expect_first: Whether or not only the first message type provided
                          with the list expected_msg_types is allowed.

                          Example:
                          While in the state PaymentServiceSelection, we can expect a
                          PaymentServiceSelectionReq, or a CertificateInstallationReq,
                          or a PaymentDetailsReq, or an AuthorizationReq (according to
                          the state machine outlined in ISO 15118-2). But when first
                          entering the state, the EVCC must send a
                          PaymentServiceSelectionReq - that's what expect_first is about.  # noqa: E501

                          Set to True by default, as some states expect only one request
                          message type.

        Returns:
            The message of type expected_return_type, if all preliminary checks pass,
            None otherwise.

            In the latter case, the state machine is stopped (setting the communication
            session's StopNotification and setting the next state to Terminate) and the
            last response message is prepared.
        """
        # TODO: Check the need for this if clause also because the Response code is
        # specific for V2 and we now have DIN and V20....
        if not isinstance(message, expected_return_type):
            self.stop_state_machine(
                f"{type(message)}' not a valid message type " f"in state {str(self)}",
                message,
                ResponseCodeV2.FAILED_SEQUENCE_ERROR,
            )
            return None

        msg_body: Union[
            SupportedAppProtocolReq, BodyBaseV2, V2GRequestV20, BodyBaseDINSPEC
        ]
        if isinstance(message, V2GMessageV2) or isinstance(message, V2GMessageDINSPEC):
            # ISO 15118-2
            msg_body = message.body.get_message()  # type: ignore
        else:
            # SupportedAppProtocolReq, V2GRequestV20 (ISO 15118-20)
            msg_body = message

        match = False
        for idx, expected_msg_type in enumerate(expected_msg_types):
            if (
                idx == 0
                and expect_first
                and not isinstance(msg_body, expected_msg_type)
            ):
                self.stop_state_machine(
                    f"{str(message)}' not accepted in state " f"{str(self)}",
                    message,
                    ResponseCodeV2.FAILED_SEQUENCE_ERROR,
                )
                return None

            if isinstance(msg_body, expected_msg_type):
                match = True
                break

        if not match:
            self.stop_state_machine(
                f"{str(message)}' not accepted in state " f"{str(self)}",
                message,
                ResponseCodeV2.FAILED_SEQUENCE_ERROR,
            )
            return None

        if (
            not isinstance(
                msg_body,
                (SessionSetupReqV2, SessionSetupReqV20, SessionSetupReqDINSPEC),
            )
            and not isinstance(message, SupportedAppProtocolReq)
            and not message.header.session_id == self.comm_session.session_id
        ):
            self.stop_state_machine(
                f"{str(message)}'s session ID "
                f"{message.header.session_id} does not match "
                f"session ID {self.comm_session.session_id}",
                message,
                ResponseCodeV2.FAILED_UNKNOWN_SESSION,
            )
            return None

        return message

    def stop_state_machine(
        self,
        reason: str,
        faulty_request: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
            None,
        ],
        response_code: Union[
            ResponseCodeSAP, ResponseCodeV2, ResponseCodeV20, ResponseCodeDINSPEC
        ],
        message_body_type: Optional[type] = None,
        namespace: Optional[Namespace] = None,
    ):
        """
        In case the processing of a message from the EVCC fails, the SECC needs
        to send a response to the corresponding request with minimal payload
        that still conforms to the XSD schema (i.e. only mandatory fields with
        the minimum possible data). See requirements [V2G2-736] and [V2G2-538]
        in ISO 15118-2 (and the according ones in ISO 15118-20).

        This method gets the response message, including the negative response code,
        corresponding to the incoming request. The SECC always needs to respond to the
        incoming request, even if the request was coming in the wrong order, causing a
        FAILED_SequenceError.
        """
        self.comm_session.stop_reason = StopNotification(
            False, reason, self.comm_session.writer.get_extra_info("peername")
        )
        msg_type: Optional[
            Union[
                Type[Union[BodyBaseDINSPEC, BodyBaseV2, V2GMessage]],
                SupportedAppProtocolReq,
            ]
        ] = None
        if isinstance(faulty_request, V2GMessageV2):
            msg_type = get_msg_type(str(faulty_request))
            msg_namespace = Namespace.ISO_V2_MSG_DEF
        elif isinstance(faulty_request, V2GMessageDINSPEC):
            msg_type = get_msg_type_dinspec(str(faulty_request))
            msg_namespace = Namespace.DIN_MSG_DEF
        elif isinstance(faulty_request, V2GMessageV20):
            msg_type = type(faulty_request)
            msg_namespace = Namespace.ISO_V20_BASE
        elif isinstance(faulty_request, SupportedAppProtocolReq):
            msg_type = faulty_request
            msg_namespace = Namespace.SAP
        else:
            msg_type = message_body_type
            msg_namespace = namespace

        if msg_namespace == Namespace.ISO_V2_MSG_DEF:
            error_res = self.comm_session.failed_responses_isov2.get(msg_type)
            error_res.response_code = response_code
            self.create_next_message(Terminate, error_res, 0, Namespace.ISO_V2_MSG_DEF)
        elif msg_namespace == Namespace.DIN_MSG_DEF:
            error_res = self.comm_session.failed_responses_din_spec.get(msg_type)
            error_res.response_code = response_code
            self.create_next_message(Terminate, error_res, 0, Namespace.DIN_MSG_DEF)
        # Here we could have been more specific and check if it is a V2GRequestV20,
        # but to be consistent with the other if clauses and since there is no negative
        # consequences in the behavior of the code, we check if it is a V2GMessageV20
        elif msg_namespace.startswith(Namespace.ISO_V20_BASE):
            (
                error_res,
                namespace,
                payload_type,
            ) = self.comm_session.failed_responses_isov20.get(msg_type)
            # As the Header in the case of -20 is part of the -20 message payload,
            # we need to set the session id of the current session to it
            error_res.header.session_id = self.comm_session.session_id
            error_res.response_code = response_code
            self.create_next_message(Terminate, error_res, 0, namespace, payload_type)
        elif msg_namespace == Namespace.SAP:
            error_res = SupportedAppProtocolRes(response_code=response_code)
            self.create_next_message(Terminate, error_res, 0, Namespace.SAP)
        else:
            # Should actually never happen
            logger.error(
                "Something's off here: the faulty_request and response_code "
                "are not of the expected type"
            )
