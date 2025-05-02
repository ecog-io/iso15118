from typing import Type
from unittest.mock import AsyncMock, Mock, patch

import pytest

from iso15118.secc.comm_session_handler import SECCCommunicationSession
from iso15118.secc.controller.ev_data import (
    EVDataContext,
    EVDCCLLimits,
    EVDCCPDLimits,
    EVRatedLimits,
    EVSessionLimits,
)
from iso15118.secc.controller.evse_data import (
    EVSEDataContext,
    EVSEDCCLLimits,
    EVSEDCCPDLimits,
    EVSERatedLimits,
    EVSESessionLimits,
)
from iso15118.secc.controller.simulator import SimEVSEController
from iso15118.secc.failed_responses import init_failed_responses_iso_v20
from iso15118.secc.states.iso15118_20_states import (
    DCCableCheck,
    DCChargeLoop,
    DCChargeParameterDiscovery,
    DCPreCharge,
    PowerDelivery,
    ScheduleExchange,
)
from iso15118.shared.messages.datatypes import PhysicalValue
from iso15118.shared.messages.enums import (
    ControlMode,
    CpState,
    EnergyTransferModeEnum,
    IsolationLevel,
    Protocol,
    ServiceV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ChargeProgress,
    SelectedEnergyService,
)
from iso15118.shared.messages.iso15118_20.common_types import Processing, RationalNumber
from iso15118.shared.messages.iso15118_20.dc import (
    BPTDCChargeParameterDiscoveryReqParams,
    BPTDCChargeParameterDiscoveryResParams,
    BPTDynamicDCChargeLoopReqParams,
    BPTDynamicDCChargeLoopRes,
    BPTScheduledDCChargeLoopReqParams,
    BPTScheduledDCChargeLoopResParams,
    DCChargeLoopRes,
    DCChargeParameterDiscoveryReqParams,
    DCChargeParameterDiscoveryRes,
    DCChargeParameterDiscoveryResParams,
    DynamicDCChargeLoopReqParams,
    DynamicDCChargeLoopRes,
    ScheduledDCChargeLoopReqParams,
    ScheduledDCChargeLoopResParams,
)
from iso15118.shared.notifications import StopNotification
from iso15118.shared.settings import load_shared_settings
from iso15118.shared.states import State, Terminate
from tests.dinspec.secc.test_dinspec_secc_states import MockWriter
from tests.iso15118_20.secc.test_messages import (
    get_cable_check_req,
    get_dc_charge_loop_req,
    get_dc_service_discovery_req,
    get_power_delivery_req,
    get_precharge_req,
    get_schedule_exchange_req_message,
    get_v2g_message_dc_charge_parameter_discovery_req,
)


@patch("iso15118.shared.states.EXI.to_exi", new=Mock(return_value=b"01"))
@pytest.mark.asyncio
class TestEvScenarios:
    @pytest.fixture(autouse=True)
    def _comm_session(self):
        self.comm_session = Mock(spec=SECCCommunicationSession)
        self.comm_session.session_id = "F9F9EE8505F55838"
        self.comm_session.selected_charging_type_is_ac = False
        self.comm_session.stop_reason = StopNotification(False, "pytest")
        self.comm_session.protocol = Protocol.ISO_15118_20_DC
        self.comm_session.writer = MockWriter()
        self.comm_session.failed_responses_isov20 = init_failed_responses_iso_v20()
        self.comm_session.evse_controller = SimEVSEController()
        self.comm_session.evse_controller.evse_data_context = self.get_evse_data()
        self.comm_session.evse_controller.ev_data_context = EVDataContext(
            rated_limits=EVRatedLimits(dc_limits=EVDCCPDLimits())
        )
        self.comm_session.evse_controller.ev_data_context.selected_energy_mode = (
            EnergyTransferModeEnum.DC_EXTENDED
        )
        load_shared_settings()

    def get_evse_data(self) -> EVSEDataContext:
        dc_limits = EVSEDCCPDLimits(
            max_charge_power=10,
            min_charge_power=10,
            max_charge_current=10,
            min_charge_current=10,
            max_voltage=10,
            min_voltage=10,
            max_discharge_power=10,
            min_discharge_power=10,
            max_discharge_current=10,
            min_discharge_current=10,
        )
        dc_cl_limits = EVSEDCCLLimits(
            # Optional in 15118-20 DC CL (Scheduled)
            max_charge_power=10,
            min_charge_power=10,
            max_charge_current=10,
            max_voltage=10,
            # Optional and present in 15118-20 DC BPT CL (Scheduled)
            max_discharge_power=10,
            min_discharge_power=10,
            max_discharge_current=10,
            min_voltage=10,
        )
        rated_limits: EVSERatedLimits = EVSERatedLimits(
            ac_limits=None,
            dc_limits=dc_limits,
        )
        session_limits: EVSESessionLimits = EVSESessionLimits(
            ac_limits=None, dc_limits=dc_cl_limits
        )
        evse_data_context = EVSEDataContext(
            rated_limits=rated_limits, session_limits=session_limits
        )
        evse_data_context.power_ramp_limit = 10
        evse_data_context.current_regulation_tolerance = 10
        evse_data_context.peak_current_ripple = 10
        evse_data_context.energy_to_be_delivered = 10
        return evse_data_context

    @pytest.mark.parametrize(
        "service_type, dc_params, bpt_params",
        [
            (ServiceV20.DC, "", None),
            (ServiceV20.DC_BPT, None, ""),
        ],
    )
    async def test_15118_20_dc_charge_parameter_discovery_res(
        self, service_type, dc_params, bpt_params
    ):
        self.comm_session.selected_energy_service = SelectedEnergyService(
            service=service_type,
            is_free=True,
            parameter_set=None,
        )
        dc_charge_parameter_discovery = DCChargeParameterDiscovery(self.comm_session)
        await dc_charge_parameter_discovery.process_message(
            message=get_v2g_message_dc_charge_parameter_discovery_req(service_type)
        )
        if service_type == ServiceV20.DC:
            assert bpt_params is None
        elif service_type == ServiceV20.DC_BPT:
            assert dc_params is None
        assert dc_charge_parameter_discovery.next_state is ScheduleExchange

    @pytest.mark.parametrize(
        "control_mode, next_state, selected_energy_service",
        [
            (
                ControlMode.SCHEDULED,
                None,
                SelectedEnergyService(
                    service=ServiceV20.DC, is_free=True, parameter_set=None
                ),
            ),
            (
                ControlMode.DYNAMIC,
                None,
                SelectedEnergyService(
                    service=ServiceV20.DC, is_free=True, parameter_set=None
                ),
            ),
            (
                ControlMode.SCHEDULED,
                None,
                SelectedEnergyService(
                    service=ServiceV20.DC_BPT, is_free=True, parameter_set=None
                ),
            ),
            (
                ControlMode.DYNAMIC,
                None,
                SelectedEnergyService(
                    service=ServiceV20.DC_BPT, is_free=True, parameter_set=None
                ),
            ),
        ],
    )
    async def test_15118_20_schedule_exchange_res(
        self,
        control_mode: ControlMode,
        next_state: Type[State],
        selected_energy_service: SelectedEnergyService,
    ):
        self.comm_session.control_mode = control_mode
        self.comm_session.selected_energy_service = selected_energy_service
        schedule_exchange = ScheduleExchange(self.comm_session)
        await schedule_exchange.process_message(
            message=get_schedule_exchange_req_message(control_mode)
        )
        assert schedule_exchange.next_state is None

    @pytest.mark.parametrize(
        "is_contactor_closed, "
        "cable_check_started, "
        "cable_check_status, "
        "expected_state",
        [
            (None, False, None, None),  # First request.
            (
                None,
                False,
                None,
                None,
            ),  # Not first request. Contactor status unknown.
            (True, False, None, None),  # Not first request. Contactor closed.
            (False, False, None, Terminate),  # Contactor close failed.
            (
                True,
                True,
                IsolationLevel.VALID,
                DCPreCharge,
            ),  # noqa Contactor closed. Isolation response received - Valid. Next stage Precharge.
            (
                True,
                True,
                IsolationLevel.INVALID,
                Terminate,
            ),  # noqa Contactor closed. Isolation response received - Invalid. Terminate.
            (
                True,
                True,
                IsolationLevel.WARNING,
                DCPreCharge,
            ),  # noqa Contactor closed. Isolation response received - Warning. Next stage Precharge.
            (
                True,
                True,
                IsolationLevel.FAULT,
                Terminate,
            ),  # noqa Contactor closed. Isolation response received - Fault. Terminate session.
        ],
    )
    async def test_15118_20_dc_cable_check(
        self,
        is_contactor_closed: bool,
        cable_check_started: bool,
        cable_check_status: IsolationLevel,
        expected_state: Type[State],
    ):
        dc_cable_check = DCCableCheck(self.comm_session)
        dc_cable_check.cable_check_started = cable_check_started
        dc_cable_check.contactors_closed = is_contactor_closed
        contactor_status = AsyncMock(return_value=is_contactor_closed)
        self.comm_session.evse_controller.is_contactor_closed = contactor_status
        cable_check_status = AsyncMock(return_value=cable_check_status)
        self.comm_session.evse_controller.get_cable_check_status = cable_check_status
        await dc_cable_check.process_message(message=get_cable_check_req())
        assert dc_cable_check.next_state is expected_state

    @pytest.mark.parametrize(
        "processing, expected_state",
        [(Processing.ONGOING, None), (Processing.FINISHED, PowerDelivery)],
    )
    async def test_15118_20_precharge(
        self, processing: Processing, expected_state: Type[State]
    ):
        dc_pre_charge = DCPreCharge(self.comm_session)
        await dc_pre_charge.process_message(message=get_precharge_req(processing))
        assert dc_pre_charge.next_state is expected_state

    async def test_15118_20_power_delivery(self):
        # TODO
        pass

    @pytest.mark.parametrize(
        "params, selected_service, expected_state, expected_ev_context",
        [
            (
                DCChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_current=RationalNumber(exponent=0, value=300),
                    ev_min_charge_current=RationalNumber(exponent=0, value=10),
                    ev_max_voltage=RationalNumber(exponent=0, value=1000),
                    ev_min_voltage=RationalNumber(exponent=0, value=10),
                    target_soc=80,
                ),
                ServiceV20.DC,
                ScheduleExchange,
                EVDataContext(
                    target_soc=80,
                    rated_limits=EVRatedLimits(
                        dc_limits=EVDCCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_current=300,
                            min_charge_current=10,
                            max_voltage=1000,
                            min_voltage=10,
                        )
                    ),
                ),
            ),
            (
                BPTDCChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_current=RationalNumber(exponent=0, value=300),
                    ev_min_charge_current=RationalNumber(exponent=0, value=10),
                    ev_max_voltage=RationalNumber(exponent=0, value=1000),
                    ev_min_voltage=RationalNumber(exponent=0, value=10),
                    target_soc=80,
                    ev_max_discharge_power=RationalNumber(exponent=0, value=11),
                    ev_min_discharge_power=RationalNumber(exponent=3, value=1),
                    ev_max_discharge_current=RationalNumber(exponent=0, value=11),
                    ev_min_discharge_current=RationalNumber(exponent=0, value=10),
                ),
                ServiceV20.DC_BPT,
                ScheduleExchange,
                EVDataContext(
                    target_soc=80,
                    rated_limits=EVRatedLimits(
                        dc_limits=EVDCCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_current=300,
                            min_charge_current=10,
                            max_voltage=1000,
                            min_voltage=10,
                            max_discharge_power=11,
                            min_discharge_power=1000,
                            max_discharge_current=11,
                            min_discharge_current=10,
                        )
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_dc_charge_parameter_discovery_res_ev_context_update(
        self, params, selected_service, expected_state, expected_ev_context
    ):
        self.comm_session.selected_energy_service = SelectedEnergyService(
            service=selected_service, is_free=True, parameter_set=None
        )
        dc_service_discovery = DCChargeParameterDiscovery(self.comm_session)
        dc_service_discovery_req = get_dc_service_discovery_req(
            params, selected_service
        )
        await dc_service_discovery.process_message(message=dc_service_discovery_req)
        assert dc_service_discovery.next_state is expected_state
        updated_ev_context = self.comm_session.evse_controller.ev_data_context
        assert updated_ev_context == expected_ev_context

    @pytest.mark.parametrize(
        "params, selected_service, control_mode, expected_state, expected_ev_context, evse_data_context",  # noqa: E501
        [
            (
                ScheduledDCChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_target_current=RationalNumber(exponent=2, value=300),
                    ev_target_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.DC,
                ControlMode.SCHEDULED,
                None,
                EVDataContext(
                    target_energy_request=30000,
                    max_energy_request=30000,
                    min_energy_request=30000,
                    target_current=30000,
                    target_voltage=30000,
                    session_limits=EVSessionLimits(
                        dc_limits=EVDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=30000,
                            max_voltage=30000,
                            min_voltage=30000,
                        )
                    ),
                ),
                EVSEDataContext(
                    present_current=100,
                    present_voltage=300,
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=100,
                            max_voltage=300,
                            min_voltage=10,
                            max_discharge_power=30000,
                            min_discharge_power=30000,
                            max_discharge_current=100,
                        )
                    ),
                ),
            ),
            (
                DynamicDCChargeLoopReqParams(
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.DC,
                ControlMode.DYNAMIC,
                None,
                EVDataContext(
                    departure_time=3600,
                    target_energy_request=30000,
                    max_energy_request=30000,
                    min_energy_request=30000,
                    session_limits=EVSessionLimits(
                        dc_limits=EVDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=30000,
                            max_voltage=30000,
                            min_voltage=30000,
                        )
                    ),
                ),
                EVSEDataContext(
                    present_current=100,
                    present_voltage=300,
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=100,
                            max_voltage=300,
                            min_voltage=10,
                            max_discharge_power=30000,
                            min_discharge_power=30000,
                            max_discharge_current=100,
                        )
                    ),
                ),
            ),
            (
                BPTScheduledDCChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_target_current=RationalNumber(exponent=2, value=300),
                    ev_target_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_current=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.DC_BPT,
                ControlMode.SCHEDULED,
                None,
                EVDataContext(
                    target_energy_request=30000,
                    max_energy_request=30000,
                    min_energy_request=30000,
                    target_current=30000,
                    target_voltage=30000,
                    session_limits=EVSessionLimits(
                        dc_limits=EVDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=30000,
                            max_voltage=30000,
                            min_voltage=30000,
                            max_discharge_power=30000,
                            min_discharge_power=30000,
                            max_discharge_current=30000,
                        )
                    ),
                ),
                EVSEDataContext(
                    present_current=100,
                    present_voltage=300,
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=100,
                            max_voltage=300,
                            min_voltage=10,
                            max_discharge_power=30000,
                            min_discharge_power=30000,
                            max_discharge_current=100,
                        )
                    ),
                ),
            ),
            (
                BPTDynamicDCChargeLoopReqParams(
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_current=RationalNumber(exponent=2, value=300),
                    ev_max_v2x_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_v2x_energy_request=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.DC_BPT,
                ControlMode.DYNAMIC,
                None,
                EVDataContext(
                    departure_time=3600,
                    target_energy_request=30000,
                    max_energy_request=30000,
                    min_energy_request=30000,
                    max_v2x_energy_request=30000,
                    min_v2x_energy_request=30000,
                    session_limits=EVSessionLimits(
                        dc_limits=EVDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=30000,
                            max_voltage=30000,
                            min_voltage=30000,
                            max_discharge_power=30000,
                            min_discharge_power=30000,
                            max_discharge_current=30000,
                        )
                    ),
                ),
                EVSEDataContext(
                    present_current=100,
                    present_voltage=300,
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=30000,
                            max_charge_current=100,
                            max_voltage=300,
                            min_voltage=10,
                            max_discharge_power=30000,
                            min_discharge_power=30000,
                            max_discharge_current=100,
                        )
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_dc_charge_charge_loop_res_ev_context_update(
        self,
        params,
        selected_service,
        control_mode,
        expected_state,
        expected_ev_context,
        evse_data_context,
    ):
        self.comm_session.control_mode = control_mode
        self.comm_session.selected_energy_service = SelectedEnergyService(
            service=selected_service, is_free=True, parameter_set=None
        )
        self.comm_session.evse_controller.evse_data_context = evse_data_context
        dc_charge_loop = DCChargeLoop(self.comm_session)
        dc_charge_loop_req = get_dc_charge_loop_req(
            params, selected_service, control_mode
        )

        await dc_charge_loop.process_message(message=dc_charge_loop_req)
        assert dc_charge_loop.next_state is expected_state
        updated_ev_context = self.comm_session.evse_controller.ev_data_context
        assert updated_ev_context.session_limits == expected_ev_context.session_limits

    @pytest.mark.parametrize(
        "req_params, expected_res_params, selected_service, expected_state, expected_evse_context",  # noqa
        [
            (
                DCChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_current=RationalNumber(exponent=0, value=300),
                    ev_min_charge_current=RationalNumber(exponent=0, value=10),
                    ev_max_voltage=RationalNumber(exponent=0, value=1000),
                    ev_min_voltage=RationalNumber(exponent=0, value=10),
                    target_soc=80,
                ),
                DCChargeParameterDiscoveryResParams(
                    evse_max_charge_power=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power=RationalNumber(exponent=-2, value=10000),
                    evse_max_charge_current=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_current=RationalNumber(exponent=-2, value=10000),
                    evse_max_voltage=RationalNumber(exponent=0, value=30000),
                    evse_min_voltage=RationalNumber(exponent=-2, value=10000),
                    evse_power_ramp_limit=RationalNumber(exponent=-2, value=10000),
                ),
                ServiceV20.DC,
                ScheduleExchange,
                EVSEDataContext(
                    rated_limits=EVSERatedLimits(
                        dc_limits=EVSEDCCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_current=30000,
                            min_charge_current=100,
                            max_voltage=30000,
                            min_voltage=100,
                            # power_ramp_limit=100,
                        )
                    ),
                    session_limits=None,
                ),
            ),
            (
                BPTDCChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_current=RationalNumber(exponent=0, value=300),
                    ev_min_charge_current=RationalNumber(exponent=0, value=10),
                    ev_max_voltage=RationalNumber(exponent=0, value=1000),
                    ev_min_voltage=RationalNumber(exponent=0, value=10),
                    target_soc=80,
                    ev_max_discharge_power=RationalNumber(exponent=0, value=11),
                    ev_min_discharge_power=RationalNumber(exponent=3, value=1),
                    ev_max_discharge_current=RationalNumber(exponent=0, value=11),
                    ev_min_discharge_current=RationalNumber(exponent=0, value=10),
                ),
                BPTDCChargeParameterDiscoveryResParams(
                    evse_max_charge_power=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power=RationalNumber(exponent=-2, value=10000),
                    evse_max_charge_current=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_current=RationalNumber(exponent=-2, value=10000),
                    evse_max_voltage=RationalNumber(exponent=0, value=30000),
                    evse_min_voltage=RationalNumber(exponent=-2, value=10000),
                    evse_power_ramp_limit=RationalNumber(exponent=-2, value=10000),
                    evse_max_discharge_power=RationalNumber(exponent=0, value=30000),
                    evse_min_discharge_power=RationalNumber(exponent=-2, value=10000),
                    evse_max_discharge_current=RationalNumber(exponent=0, value=30000),
                    evse_min_discharge_current=RationalNumber(exponent=-2, value=10000),
                ),
                ServiceV20.DC_BPT,
                ScheduleExchange,
                EVSEDataContext(
                    rated_limits=EVSERatedLimits(
                        dc_limits=EVSEDCCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_current=30000,
                            min_charge_current=100,
                            max_voltage=30000,
                            min_voltage=100,
                            # power_ramp_limit=100,
                            max_discharge_power=30000,
                            min_discharge_power=100,
                            max_discharge_current=30000,
                            min_discharge_current=100,
                        )
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_dc_charge_param_discovery_res_evse_context_read(
        self,
        req_params,
        expected_res_params,
        selected_service,
        expected_state,
        expected_evse_context,
    ):
        self.comm_session.selected_energy_service = SelectedEnergyService(
            service=selected_service, is_free=True, parameter_set=None
        )
        self.comm_session.evse_controller.get_dc_charge_params_v20 = AsyncMock(
            return_value=expected_res_params
        )
        dc_service_discovery = DCChargeParameterDiscovery(self.comm_session)
        dc_service_discovery_req = get_dc_service_discovery_req(
            req_params, selected_service
        )
        await dc_service_discovery.process_message(message=dc_service_discovery_req)
        # if the expected ACChargeParameterDiscoveryResParams is correctly returned,
        # the evse data context will be properly updated
        assert (
            self.comm_session.evse_controller.evse_data_context == expected_evse_context
        )
        # These are just sanity checks and should never be different...
        assert dc_service_discovery.next_state is expected_state
        assert isinstance(dc_service_discovery.message, DCChargeParameterDiscoveryRes)
        if selected_service == ServiceV20.DC:
            assert dc_service_discovery.message.dc_params == expected_res_params
        elif selected_service == ServiceV20.DC_BPT:
            assert dc_service_discovery.message.bpt_dc_params == expected_res_params

    @pytest.mark.parametrize(
        "ev_params,expected_charge_loop_res,selected_service,control_mode,expected_state,evse_data_context,",  # noqa
        [
            (
                ScheduledDCChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_target_current=RationalNumber(exponent=2, value=300),
                    ev_target_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                ),
                ScheduledDCChargeLoopResParams(
                    evse_maximum_charge_power=RationalNumber(exponent=0, value=300),
                    evse_minimum_charge_power=RationalNumber(exponent=0, value=600),
                    evse_maximum_charge_current=RationalNumber(exponent=0, value=700),
                    evse_maximum_voltage=RationalNumber(exponent=0, value=800),
                ),
                ServiceV20.DC,
                ControlMode.SCHEDULED,
                None,
                EVSEDataContext(
                    rated_limits=EVSERatedLimits(
                        dc_limits=EVSEDCCPDLimits(
                            max_charge_power=300,
                            min_charge_power=600,
                            max_charge_current=700,
                            max_voltage=800,
                        )
                    ),
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=300,
                            min_charge_power=600,
                            max_charge_current=700,
                            max_voltage=800,
                        )
                    ),
                ),
            ),
            (
                DynamicDCChargeLoopReqParams(
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                ),
                DynamicDCChargeLoopRes(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    evse_maximum_charge_power=RationalNumber(exponent=0, value=30000),
                    evse_minimum_charge_power=RationalNumber(exponent=0, value=400),
                    evse_maximum_charge_current=RationalNumber(exponent=0, value=500),
                    evse_maximum_voltage=RationalNumber(exponent=0, value=600),
                ),
                ServiceV20.DC,
                ControlMode.DYNAMIC,
                None,
                EVSEDataContext(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    rated_limits=EVSERatedLimits(
                        dc_limits=EVSEDCCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=400,
                            max_charge_current=500,
                            max_voltage=600,
                        )
                    ),
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=30000,
                            min_charge_power=400,
                            max_charge_current=500,
                            max_voltage=600,
                        ),
                    ),
                ),
            ),
            (
                BPTScheduledDCChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_target_current=RationalNumber(exponent=2, value=300),
                    ev_target_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_current=RationalNumber(exponent=2, value=300),
                ),
                BPTScheduledDCChargeLoopResParams(
                    evse_maximum_charge_power=RationalNumber(exponent=0, value=300),
                    evse_minimum_charge_power=RationalNumber(exponent=0, value=400),
                    evse_maximum_charge_current=RationalNumber(exponent=0, value=500),
                    evse_maximum_voltage=RationalNumber(exponent=0, value=600),
                    evse_max_discharge_power=RationalNumber(exponent=0, value=800),
                    evse_min_discharge_power=RationalNumber(exponent=0, value=100),
                    evse_max_discharge_current=RationalNumber(exponent=0, value=500),
                    evse_min_voltage=RationalNumber(exponent=0, value=100),
                ),
                ServiceV20.DC_BPT,
                ControlMode.SCHEDULED,
                None,
                EVSEDataContext(
                    rated_limits=EVSERatedLimits(
                        dc_limits=EVSEDCCPDLimits(
                            max_charge_power=300,
                            min_charge_power=400,
                            max_charge_current=500,
                            max_voltage=600,
                            min_voltage=100,
                            max_discharge_power=800,
                            min_discharge_power=100,
                            max_discharge_current=500,
                        )
                    ),
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=300,
                            min_charge_power=400,
                            max_charge_current=500,
                            max_voltage=600,
                            max_discharge_power=800,
                            min_discharge_power=100,
                            max_discharge_current=500,
                            min_voltage=100,
                        )
                    ),
                ),
            ),
            (
                BPTDynamicDCChargeLoopReqParams(
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_current=RationalNumber(exponent=2, value=300),
                    ev_max_voltage=RationalNumber(exponent=2, value=300),
                    ev_min_voltage=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_current=RationalNumber(exponent=2, value=300),
                    ev_max_v2x_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_v2x_energy_request=RationalNumber(exponent=2, value=300),
                ),
                BPTDynamicDCChargeLoopRes(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    evse_maximum_charge_power=RationalNumber(exponent=0, value=10000),
                    evse_minimum_charge_power=RationalNumber(exponent=0, value=20000),
                    evse_maximum_charge_current=RationalNumber(exponent=0, value=30000),
                    evse_maximum_voltage=RationalNumber(exponent=0, value=4000),
                    evse_max_discharge_power=RationalNumber(exponent=0, value=5000),
                    evse_min_discharge_power=RationalNumber(exponent=0, value=6000),
                    evse_max_discharge_current=RationalNumber(exponent=0, value=7000),
                    evse_min_voltage=RationalNumber(exponent=0, value=8000),
                ),
                ServiceV20.DC_BPT,
                ControlMode.DYNAMIC,
                None,
                EVSEDataContext(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    rated_limits=EVSERatedLimits(
                        dc_limits=EVSEDCCPDLimits(
                            max_charge_power=10000,
                            min_charge_power=20000,
                            max_charge_current=30000,
                            max_voltage=4000,
                            min_voltage=8000,
                            max_discharge_power=5000,
                            min_discharge_power=6000,
                            max_discharge_current=7000,
                        )
                    ),
                    session_limits=EVSESessionLimits(
                        dc_limits=EVSEDCCLLimits(
                            max_charge_power=10000,
                            min_charge_power=20000,
                            max_charge_current=30000,
                            max_voltage=4000,
                            max_discharge_power=5000,
                            min_discharge_power=6000,
                            max_discharge_current=7000,
                            min_voltage=8000,
                        ),
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_dc_charge_charge_loop_res_evse_context_read(
        self,
        ev_params,
        expected_charge_loop_res,
        selected_service,
        control_mode,
        expected_state,
        evse_data_context,
    ):
        self.comm_session.control_mode = control_mode
        self.comm_session.selected_energy_service = SelectedEnergyService(
            service=selected_service, is_free=True, parameter_set=None
        )
        self.comm_session.evse_controller.evse_data_context = evse_data_context
        self.comm_session.evse_controller.send_charging_command = AsyncMock(
            return_value=None
        )
        dc_charge_loop = DCChargeLoop(self.comm_session)
        dc_charge_loop_req = get_dc_charge_loop_req(
            ev_params, selected_service, control_mode
        )
        await dc_charge_loop.process_message(message=dc_charge_loop_req)
        assert dc_charge_loop.next_state is expected_state
        assert isinstance(dc_charge_loop.message, DCChargeLoopRes)
        if selected_service == ServiceV20.DC and control_mode == ControlMode.SCHEDULED:
            assert (
                dc_charge_loop.message.scheduled_dc_charge_loop_res
                == expected_charge_loop_res
            )
        elif (
            selected_service == ServiceV20.DC_BPT
            and control_mode == ControlMode.SCHEDULED
        ):
            assert (
                dc_charge_loop.message.bpt_scheduled_dc_charge_loop_res
                == expected_charge_loop_res
            )
        if selected_service == ServiceV20.DC and control_mode == ControlMode.DYNAMIC:
            assert (
                dc_charge_loop.message.dynamic_dc_charge_loop_res
                == expected_charge_loop_res
            )
        elif (
            selected_service == ServiceV20.DC_BPT
            and control_mode == ControlMode.DYNAMIC
        ):
            assert (
                dc_charge_loop.message.bpt_dynamic_dc_charge_loop_res
                == expected_charge_loop_res
            )

    @pytest.mark.parametrize(
        "control_mode, next_state, selected_energy_service, cp_state",
        [
            (
                ControlMode.DYNAMIC,
                DCChargeLoop,
                SelectedEnergyService(
                    service=ServiceV20.DC, is_free=True, parameter_set=None
                ),
                CpState.D2,
            ),
            (
                ControlMode.DYNAMIC,
                DCChargeLoop,
                SelectedEnergyService(
                    service=ServiceV20.DC, is_free=True, parameter_set=None
                ),
                CpState.C2,
            ),
            (
                ControlMode.DYNAMIC,
                DCChargeLoop,
                SelectedEnergyService(
                    service=ServiceV20.DC, is_free=True, parameter_set=None
                ),
                CpState.B2,
            ),
        ],
    )
    async def test_power_delivery_state_check(
        self, control_mode, next_state, selected_energy_service, cp_state
    ):
        self.comm_session.control_mode = control_mode
        self.comm_session.selected_energy_service = selected_energy_service
        power_delivery = PowerDelivery(self.comm_session)
        self.comm_session.evse_controller.get_cp_state = AsyncMock(
            return_value=cp_state
        )
        await power_delivery.process_message(
            message=get_power_delivery_req(Processing.FINISHED, ChargeProgress.START)
        )
        assert power_delivery.next_state is next_state

    @pytest.mark.parametrize(
        "float_value, expected_exponent, expected_value",
        [
            (-6340, 0, -6340),
            (-634, 0, -634),
            (-234, 0, -234),
            (-0.634, -3, -634),
            (-0.634, -3, -634),
            (-0.0634, -3, -63),
            (-0.00634, -3, -6),
            (-0.000634, 0, 0),
            (-0.0000634, 0, 0),
            (0.0, 0, 0),
            (0.0000234, 0, 0),
            (0.000234, 0, 0),
            (0.00234, -3, 2),
            (0.0234, -3, 23),
            (0.234, -3, 234),
            (2.34, -2, 234),
            (23.4, -1, 234),
            (234, 0, 234),
            (2340, 0, 2340),
            (23400, 0, 23400),
            (234000, 1, 23400),
            (0.4, -1, 4),
            (400, 0, 400),
            (32767, 0, 32767),
            (32768, 1, 3276),
        ],
    )
    async def test_exponent_conversion_for_rational_number_type(
        self,
        float_value: float,
        expected_exponent: int,
        expected_value: int,
    ):  # noqa: ANN201
        """Test conversion of a value into its exponent form.

        This test particularly tests the conversion suitable for
        the Rational Number type of ISO 15118-20, considering
        its value range [-32768, 32767].
        The byte range still considers the one from ISO 15118-2:
        [-3, 3]
        """
        rational_repr = RationalNumber.get_rational_repr(float_value)

        assert rational_repr.exponent == expected_exponent
        assert rational_repr.value == expected_value

        exponent, value = PhysicalValue.get_exponent_value_repr(float_value)

        assert exponent == expected_exponent
        assert value == expected_value
