"""
The EVCC waits `ongoingRetryDelay` seconds before it re-sends a request the
SECC answered with EVSEProcessing = Ongoing.
"""

import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from iso15118.evcc import EVCCConfig
from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
from iso15118.evcc.controller.simulator import SimEVController
from iso15118.evcc.states import din_spec_states as din
from iso15118.evcc.states import iso15118_2_states as iso2
from iso15118.evcc.states import iso15118_20_states as iso20
from iso15118.shared.messages.datatypes import DCEVSEStatusCode
from iso15118.shared.messages.enums import (
    AuthEnum,
    ControlMode,
    EnergyTransferModeEnum,
    EVSEProcessing,
    IsolationLevel,
    Protocol,
    ServiceV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationReq,
    EIMAuthReqParams,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    MessageHeader,
    Processing,
)
from iso15118.shared.notifications import StopNotification
from tests.tools import MOCK_SESSION_ID

ONGOING_STATES = [
    # (state, check_msg method, path to evse_processing, ongoing value)
    (iso2.Authorization, "check_msg_v2", "body.authorization_res", EVSEProcessing),
    (
        iso2.ChargeParameterDiscovery,
        "check_msg_v2",
        "body.charge_parameter_discovery_res",
        EVSEProcessing,
    ),
    (iso2.CableCheck, "check_msg_v2", "body.cable_check_res", EVSEProcessing),
    (
        din.ContractAuthentication,
        "check_msg_din_spec",
        "body.contract_authentication_res",
        EVSEProcessing,
    ),
    (
        din.ChargeParameterDiscovery,
        "check_msg_din_spec",
        "body.charge_parameter_discovery_res",
        EVSEProcessing,
    ),
    (din.CableCheck, "check_msg_din_spec", "body.cable_check_res", EVSEProcessing),
    (iso20.Authorization, "check_msg_v20", "", Processing),
    (iso20.ScheduleExchange, "check_msg_v20", "", Processing),
    (iso20.DCCableCheck, "check_msg_v20", "", Processing),
]


def _comm_session(delay: float) -> Mock:
    comm_session = Mock(spec=EVCCCommunicationSession)
    comm_session.session_id = MOCK_SESSION_ID
    comm_session.stop_reason = StopNotification(False, "pytest")
    comm_session.ev_controller = SimEVController(
        EVCCConfig(energyTransferMode=EnergyTransferModeEnum.DC_EXTENDED)
    )
    comm_session.protocol = Protocol.UNKNOWN
    comm_session.ongoing_timer = -1
    comm_session.config = EVCCConfig(ongoingRetryDelay=delay)
    comm_session.authorization_req_message = AuthorizationReq(
        header=MessageHeader(session_id=MOCK_SESSION_ID, timestamp=time.time()),
        selected_auth_service=AuthEnum.EIM,
        eim_params=EIMAuthReqParams(),
    )
    comm_session.ongoing_schedule_exchange_req = Mock()
    comm_session.selected_charging_type_is_ac = False
    comm_session.control_mode = ControlMode.DYNAMIC
    comm_session.selected_energy_service = Mock(service=ServiceV20.DC)
    return comm_session


def _state(state_cls, check_msg, path, evse_processing, on_send):
    """The state under test, fed `evse_processing`, sends via `on_send`."""
    msg = MagicMock()
    res = msg
    for attr in filter(None, path.split(".")):
        res = getattr(res, attr)
    res.evse_processing = evse_processing
    # CableCheck only moves on to PreCharge with a ready, insulated EVSE
    res.dc_evse_status.evse_status_code = DCEVSEStatusCode.EVSE_READY
    res.dc_evse_status.evse_isolation_status = IsolationLevel.VALID
    state = state_cls(_comm_session(delay=0.2))
    setattr(state, check_msg, Mock(return_value=msg))
    setattr(state, "create_next_message", Mock(side_effect=on_send))
    return state


def test_ongoing_retry_delay_default_is_500_ms():
    assert EVCCConfig().ongoing_retry_delay == 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_cls, check_msg, path, processing",
    ONGOING_STATES,
    ids=[f"{s.__module__.rsplit('.', 1)[-1]}.{s.__name__}" for s, *_ in ONGOING_STATES],
)
async def test_ongoing_response_waits_before_resending(
    state_cls, check_msg, path, processing
):
    events: list = []
    fake_sleep = AsyncMock(side_effect=lambda delay: events.append(("sleep", delay)))
    state = _state(
        state_cls,
        check_msg,
        path,
        processing.ONGOING,
        lambda *a: events.append("send"),
    )

    with patch("asyncio.sleep", fake_sleep):
        await state.process_message(message=Mock())
        await state.process_message(message=Mock())

    assert events == [("sleep", 0.2), "send", ("sleep", 0.2), "send"]


@pytest.mark.asyncio
async def test_authorization_resends_are_spaced_in_real_time():
    sent_at: list = []
    state = _state(
        iso2.Authorization,
        "check_msg_v2",
        "body.authorization_res",
        EVSEProcessing.ONGOING,
        lambda *a: sent_at.append(time.monotonic()),
    )

    await state.process_message(message=Mock())
    await state.process_message(message=Mock())

    assert sent_at[1] - sent_at[0] >= 0.2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_cls, check_msg, path, processing",
    ONGOING_STATES,
    ids=[f"{s.__module__.rsplit('.', 1)[-1]}.{s.__name__}" for s, *_ in ONGOING_STATES],
)
async def test_finished_response_does_not_wait(state_cls, check_msg, path, processing):
    events: list = []
    fake_sleep = AsyncMock(side_effect=lambda delay: events.append(("sleep", delay)))
    state = _state(
        state_cls,
        check_msg,
        path,
        processing.FINISHED,
        lambda *a: events.append("send"),
    )

    with patch("asyncio.sleep", fake_sleep):
        await state.process_message(message=Mock())

    assert events == ["send"]
