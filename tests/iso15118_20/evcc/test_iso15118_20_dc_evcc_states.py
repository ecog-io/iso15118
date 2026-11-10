from unittest.mock import Mock, patch

import pytest

from iso15118.evcc import EVCCConfig
from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
from iso15118.evcc.controller.simulator import SimEVController
from iso15118.evcc.states.iso15118_20_states import (
    DCCableCheck,
    DCChargeLoop,
    DCChargeParameterDiscovery,
    DCPreCharge,
    DCWeldingDetection,
    PowerDelivery,
    ScheduleExchange,
    ServiceDetail,
    ServiceDiscovery,
    ServiceSelection,
    SessionStop,
)
from iso15118.shared.messages.enums import Protocol, ServiceV20
from iso15118.shared.messages.iso15118_20.common_messages import (
    PowerDeliveryRes,
    ScheduleExchangeRes,
    ServiceDetailRes,
    ServiceDiscoveryRes,
    ServiceSelectionRes,
    SessionStopRes,
)
from iso15118.shared.messages.iso15118_20.common_types import Processing as ProcV20
from iso15118.shared.messages.iso15118_20.dc import (
    DCCableCheckRes,
    DCChargeLoopRes,
    DCChargeParameterDiscoveryRes,
    DCPreChargeRes,
    DCWeldingDetectionRes,
)
from iso15118.shared.notifications import StopNotification
from tests.tools import MOCK_SESSION_ID

HEADER = {"SessionID": MOCK_SESSION_ID, "TimeStamp": 1794340569531}


def rational(value: int, exponent: int = 0) -> dict:
    return {"Exponent": exponent, "Value": value}


def res(model, **body):
    return model.parse_obj({"Header": HEADER, "ResponseCode": "OK", **body})


def service_discovery_res() -> ServiceDiscoveryRes:
    # DC_BPT (6) is offered too; the EV only supports DC (2). The VASList holds
    # a ServiceID (64) that Table 204 does not assign to a service.
    return res(
        ServiceDiscoveryRes,
        ServiceRenegotiationSupported=False,
        EnergyTransferServiceList={
            "Service": [
                {"ServiceID": 6, "FreeService": True},
                {"ServiceID": 2, "FreeService": True},
            ]
        },
        VASList={"Service": [{"ServiceID": 64, "FreeService": True}]},
    )


@pytest.fixture
def evcc_dc_session():
    config = EVCCConfig(
        supportedProtocols=["ISO_15118_20_DC"], supportedEnergyServices=["DC"]
    )
    config.load_raw_values()
    session = Mock(spec=EVCCCommunicationSession)
    session.session_id = MOCK_SESSION_ID
    session.protocol = Protocol.ISO_15118_20_DC
    session.config = config
    session.ev_controller = SimEVController(config)
    session.stop_reason = StopNotification(False, "pytest")
    session.matched_services_v20 = []
    session.service_details_to_request = []
    session.selected_vas_list_v20 = []
    session.ongoing_timer = -1
    session.ev_processing = ProcV20.FINISHED
    session.charging_session_stop_v20 = None
    session.renegotiation_requested = False
    session.service_renegotiation_supported = False
    return session


@patch("iso15118.shared.states.EXI.to_exi", new=Mock(return_value=b"01"))
@pytest.mark.asyncio
async def test_service_discovery_skips_unknown_vas_service_id(evcc_dc_session):
    service_discovery = ServiceDiscovery(evcc_dc_session)
    await service_discovery.process_message(message=service_discovery_res())

    assert service_discovery.next_state == ServiceDetail
    assert [m.service for m in evcc_dc_session.matched_services_v20] == [ServiceV20.DC]


@patch("iso15118.shared.states.EXI.to_exi", new=Mock(return_value=b"01"))
# The simulated EV randomly reports its power profile as not ready yet.
@patch(
    "iso15118.evcc.controller.simulator.random.getrandbits", new=Mock(return_value=1)
)
@pytest.mark.asyncio
async def test_dc_session_reaches_session_stop(evcc_dc_session):
    """
    Walks the EVCC through a complete ISO 15118-20 DC (dynamic mode) session,
    from ServiceDiscoveryRes to SessionStopRes, with responses as a
    DC_BPT- and DC-capable SECC sends them.
    """
    session = evcc_dc_session

    async def step(state_cls, message):
        state = state_cls(session)
        await state.process_message(message=message)
        return state.next_state

    assert await step(ServiceDiscovery, service_discovery_res()) == ServiceDetail
    assert session.service_details_to_request == []

    detail_res = res(
        ServiceDetailRes,
        ServiceID=2,
        ServiceParameterList={
            "ParameterSet": [
                {
                    "ParameterSetID": 1,
                    "Parameter": [
                        {"Name": "Connector", "intValue": 2},
                        {"Name": "ControlMode", "intValue": 2},
                        {"Name": "MobilityNeedsMode", "intValue": 1},
                        {"Name": "Pricing", "intValue": 0},
                    ],
                }
            ]
        },
    )
    assert await step(ServiceDetail, detail_res) == ServiceSelection

    assert await step(ServiceSelection, res(ServiceSelectionRes)) == (
        DCChargeParameterDiscovery
    )

    cpd_res = res(
        DCChargeParameterDiscoveryRes,
        DC_CPDResEnergyTransferMode={
            "EVSEMaximumChargePower": rational(4000),
            "EVSEMinimumChargePower": rational(0),
            "EVSEMaximumChargeCurrent": rational(40),
            "EVSEMinimumChargeCurrent": rational(0),
            "EVSEMaximumVoltage": rational(500),
            "EVSEMinimumVoltage": rational(150),
        },
    )
    assert await step(DCChargeParameterDiscovery, cpd_res) == ScheduleExchange

    schedule_res = res(
        ScheduleExchangeRes,
        EVSEProcessing="Finished",
        Dynamic_SEResControlMode={},
    )
    assert await step(ScheduleExchange, schedule_res) == DCCableCheck

    assert (
        await step(DCCableCheck, res(DCCableCheckRes, EVSEProcessing="Finished"))
        == DCPreCharge
    )

    # The first PreChargeRes is answered with another PreChargeReq, the second
    # one (EVSE voltage matches) leads to PowerDelivery.
    pre_charge = DCPreCharge(session)
    # 20 kV matches the voltage the simulated EV reports.
    pre_charge_res = res(DCPreChargeRes, EVSEPresentVoltage=rational(20, 3))
    await pre_charge.process_message(message=pre_charge_res)
    assert pre_charge.next_state is None
    await pre_charge.process_message(message=pre_charge_res)
    assert pre_charge.next_state == PowerDelivery

    assert await step(PowerDelivery, res(PowerDeliveryRes)) == DCChargeLoop

    session.ev_controller.charging_loop_cycles = 0
    charge_loop_res = res(
        DCChargeLoopRes,
        EVSEPresentCurrent=rational(0),
        EVSEPresentVoltage=rational(400),
        EVSEPowerLimitAchieved=False,
        EVSECurrentLimitAchieved=False,
        EVSEVoltageLimitAchieved=False,
        Dynamic_DC_CLResControlMode={
            "EVSEMaximumChargePower": rational(4000),
            "EVSEMinimumChargePower": rational(0),
            "EVSEMaximumChargeCurrent": rational(40),
            "EVSEMaximumVoltage": rational(500),
        },
    )
    assert await step(DCChargeLoop, charge_loop_res) == PowerDelivery

    assert await step(PowerDelivery, res(PowerDeliveryRes)) == DCWeldingDetection

    welding = DCWeldingDetection(session)
    welding_res = res(DCWeldingDetectionRes, EVSEPresentVoltage=rational(0))
    while welding.next_state is None:
        await welding.process_message(message=welding_res)
    assert welding.next_state == SessionStop

    stop = SessionStop(session)
    session.writer = Mock()
    await stop.process_message(message=res(SessionStopRes))
    assert stop.next_state.__name__ == "Terminate"
    assert session.stop_reason.successful
