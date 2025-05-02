"""
This module contains the abstract class for an EVCC-specific state,
which extends the state shared between the EVCC and SECC.
"""

import logging
import time
from abc import ABC
from typing import Optional, Type, TypeVar, Union

from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.din_spec.body import Response as ResponseDINSPEC
from iso15118.shared.messages.din_spec.body import (
    SessionSetupRes as SessionSetupResDINSPEC,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.enums import ISOV20PayloadTypes, Namespace
from iso15118.shared.messages.iso15118_2.body import Response as ResponseV2
from iso15118.shared.messages.iso15118_2.body import (
    SessionSetupRes as SessionSetupResV2,
)
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.common_messages import (
    ChargeProgress,
    ChargingSession,
    PowerDeliveryReq,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    SessionSetupRes as SessionSetupResV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    MessageHeader,
    Processing,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GResponse as V2GResponseV20,
)
from iso15118.shared.messages.iso15118_20.timeouts import Timeouts
from iso15118.shared.notifications import StopNotification
from iso15118.shared.states import State, Terminate

logger = logging.getLogger(__name__)


class StateEVCC(State, ABC):
    """
    Extends the State shared across EVCC and SECC.

    Every state subclassing StateEVCC must implement State's process_message()
    and, if it's not a SupportedAppProtocol state, follow these steps:

    1. Check if the incoming message is valid with State's check_v2g_message()
    2.a If step 1 returns True, process the message's content accordingly.
        If the processing is successful, prepare the transition to the next
        state with State's create_next_message().
        If the processing is not successful, terminate the session with
        stop_evcc()
    2.b If step 2 returns False, terminate the session with stop_evcc()
    """

    def __init__(
        self, comm_session: "EVCCCommunicationSession", timeout: Union[float, int] = 0
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
        self.comm_session: "EVCCCommunicationSession" = comm_session

    T = TypeVar("T")

    def check_msg_din_spec(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_msg_type: Union[
            Type[SupportedAppProtocolRes],
            Type[ResponseV2],
            Type[V2GResponseV20],
            Type[ResponseDINSPEC],
        ],
    ) -> Optional[V2GMessageDINSPEC]:
        return self.check_msg(message, V2GMessageDINSPEC, expected_msg_type)

    def check_msg_v2(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_msg_type: Union[
            Type[SupportedAppProtocolRes],
            Type[ResponseV2],
            Type[V2GResponseV20],
            Type[ResponseDINSPEC],
        ],
    ) -> Optional[V2GMessageV2]:
        return self.check_msg(message, V2GMessageV2, expected_msg_type)

    def check_msg_v20(
        self,
        message: Union[
            SupportedAppProtocolReq,
            SupportedAppProtocolRes,
            V2GMessageV2,
            V2GMessageV20,
            V2GMessageDINSPEC,
        ],
        expected_msg_type: Union[
            Type[SupportedAppProtocolRes],
            Type[ResponseV2],
            Type[V2GResponseV20],
            Type[ResponseDINSPEC],
        ],
    ) -> Optional[V2GMessageV20]:
        return self.check_msg(message, V2GMessageV20, expected_msg_type)

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
        expected_msg_type: Union[
            Type[SupportedAppProtocolRes],
            Type[ResponseV2],
            Type[V2GResponseV20],
            Type[ResponseDINSPEC],
        ],
    ) -> Optional[T]:
        """
        This function is used to reduce code redundancy in the process_message()
        method of each EVCC state. The following checks are covered:
        1. Whether or not the incoming message is expected at this state
        2. Whether or not a FAILED response code was received
        3. Whether or not the session ID is valid (for messages after SessionSetupRes)

        Args:
            message: A response message of type EXIMessage
            expected_return_type: A type indication as to which of the Union types of
                                  the first 'message' parameter we are expecting. This
                                  will either be of type SupportedAppProtocolRes,
                                  V2GMessageV2 (ISO 15118-2), or V2GMessageV20
                                  (ISO 15118-20). This helps to narrow down the return
                                  type and to avoid lots of mypy errors (e.g. saying
                                  "SupportedAppProtocolRes has not attribute 'body'")
            expected_msg_type: The expected response message type, in particular the
                               message body

        Returns:
            True, if all preliminary checks pass, False otherwise.

            In the False case, the state machine is stopped, setting the communication
            session's StopNotification and setting the next state to Terminate
        """
        if not isinstance(message, expected_return_type):
            self.stop_state_machine(
                f"{type(message)}' not a valid message type " f"in state {str(self)}"
            )
            return None

        if isinstance(message, V2GMessageV2) or isinstance(message, V2GMessageDINSPEC):
            # ISO 15118-2 or DIN SPEC 72101
            msg_body = message.body.get_message()  # type: ignore
        else:
            # SupportedAppProtocolReq, V2GRequest (ISO 15118-20)
            msg_body = message

        if not isinstance(msg_body, expected_msg_type):
            self.stop_state_machine(
                f"{str(message)}' not accepted in state " f"{str(self)}"
            )
            return None

        if "FAILED" in msg_body.response_code:
            self.stop_state_machine(
                f"Negative response code {msg_body.response_code} "
                f"received with message {str(message)}"
            )
            return None

        if (
            message is not None
            and not isinstance(
                msg_body,
                (
                    SupportedAppProtocolRes,
                    SessionSetupResV2,
                    SessionSetupResV20,
                    SessionSetupResDINSPEC,
                ),
            )
            and not message.header.session_id == self.comm_session.session_id
        ):
            self.stop_state_machine(
                f"{str(message)}'s session ID "
                f"{message.header.session_id} does not match "
                f"session ID {self.comm_session.session_id}"
            )
            return None

        return message

    def stop_state_machine(self, reason: str):
        """
        Prepares the stop of the state machine by setting the next_state to Terminate
        and providing a reason for logging purposes.

        Args:
            reason: Additional information as to why the communication session is about
                    to be terminated. Helpful for further debugging.
        """
        self.comm_session.stop_reason = StopNotification(
            False, reason, self.comm_session.writer.get_extra_info("peername")
        )

        self.next_state = Terminate

    def stop_v20_charging(
        self, next_state: Type["State"], renegotiate_requested: bool = False
    ):
        power_delivery_req = PowerDeliveryReq(
            header=MessageHeader(
                session_id=self.comm_session.session_id,
                timestamp=time.time(),
            ),
            ev_processing=Processing.FINISHED,
            charge_progress=ChargeProgress.STOP,
        )

        if next_state.__name__ != "PowerDelivery":
            raise ValueError(
                f"Attempt to stop charging by going to "
                f"state {next_state.__name__} when "
                f" 'PowerDelivery' was expected"
            )

        self.create_next_message(
            next_state,
            power_delivery_req,
            Timeouts.POWER_DELIVERY_REQ,
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        )

        if renegotiate_requested:
            self.comm_session.renegotiation_requested = True
            self.comm_session.charging_session_stop_v20 = (
                ChargingSession.SERVICE_RENEGOTIATION
            )
            logger.debug(
                f"ChargeProgress is set to {ChargeProgress.SCHEDULE_RENEGOTIATION}"
            )
        else:
            self.comm_session.charging_session_stop_v20 = ChargingSession.TERMINATE
            # TODO Implement also a mechanism for pausing
            logger.debug(f"ChargeProgress is set to {ChargeProgress.STOP}")
