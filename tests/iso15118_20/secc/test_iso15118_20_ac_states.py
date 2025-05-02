from unittest.mock import AsyncMock, Mock, patch

import pytest

from iso15118.secc.comm_session_handler import SECCCommunicationSession
from iso15118.secc.controller.ev_data import (
    EVACCLLimits,
    EVACCPDLimits,
    EVDataContext,
    EVRatedLimits,
    EVSessionLimits,
)
from iso15118.secc.controller.evse_data import (
    EVSEACCLLimits,
    EVSEACCPDLimits,
    EVSEDataContext,
    EVSERatedLimits,
    EVSESessionLimits,
)
from iso15118.secc.controller.interface import AuthorizationResponse
from iso15118.secc.controller.simulator import SimEVSEController
from iso15118.secc.failed_responses import init_failed_responses_iso_v20
from iso15118.secc.states.iso15118_20_states import (
    ACChargeLoop,
    ACChargeParameterDiscovery,
    Authorization,
    PowerDelivery,
    ScheduleExchange,
    ServiceDetail,
)
from iso15118.shared.messages.enums import (
    AuthEnum,
    AuthorizationStatus,
    ControlMode,
    CpState,
    EnergyTransferModeEnum,
    Protocol,
    ServiceV20,
)
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeLoopRes,
    ACChargeParameterDiscoveryReqParams,
    ACChargeParameterDiscoveryRes,
    ACChargeParameterDiscoveryResParams,
    BPTACChargeParameterDiscoveryReqParams,
    BPTACChargeParameterDiscoveryResParams,
    BPTDynamicACChargeLoopReqParams,
    BPTDynamicACChargeLoopResParams,
    BPTScheduledACChargeLoopReqParams,
    BPTScheduledACChargeLoopResParams,
    DynamicACChargeLoopReqParams,
    DynamicACChargeLoopResParams,
    ScheduledACChargeLoopReqParams,
    ScheduledACChargeLoopResParams,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ChargeProgress,
    MatchedService,
    SelectedEnergyService,
    Service,
    ServiceDetailRes,
    ServiceList,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    Processing,
    RationalNumber,
    ResponseCode,
)
from iso15118.shared.notifications import StopNotification
from iso15118.shared.settings import load_shared_settings
from iso15118.shared.states import Terminate
from tests.dinspec.secc.test_dinspec_secc_states import MockWriter
from tests.iso15118_20.secc.test_messages import (
    get_ac_charge_loop_req,
    get_ac_service_discovery_req,
    get_power_delivery_req,
    get_v2g_message_authorization_req,
    get_v2g_message_service_detail_req,
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
        self.comm_session.protocol = Protocol.ISO_15118_20_AC
        self.comm_session.failed_responses_isov20 = init_failed_responses_iso_v20()
        self.comm_session.writer = MockWriter()
        self.comm_session.evse_controller = SimEVSEController()
        self.comm_session.evse_controller.evse_data_context = self.get_evse_data()
        self.comm_session.evse_controller.ev_data_context = EVDataContext(
            rated_limits=EVRatedLimits(ac_limits=EVACCPDLimits())
        )
        self.comm_session.evse_controller.ev_data_context.selected_energy_mode = (
            EnergyTransferModeEnum.AC_THREE_PHASE_CORE
        )
        load_shared_settings()

    def get_evse_data(self) -> EVSEDataContext:
        ac_limits = EVSEACCPDLimits(
            max_current=10,
            max_charge_power=10,
            max_charge_power_l2=10,
            max_charge_power_l3=10,
            min_charge_power=10,
            min_charge_power_l2=10,
            min_charge_power_l3=10,
            max_discharge_power=10,
            max_discharge_power_l2=10,
            max_discharge_power_l3=10,
            min_discharge_power=10,
            min_discharge_power_l2=10,
            min_discharge_power_l3=10,
        )
        ac_cl_limits = EVSEACCLLimits(
            max_charge_power=10,
            max_charge_power_l2=10,
            max_charge_power_l3=10,
            max_charge_reactive_power=10,
            max_charge_reactive_power_l2=10,
            max_charge_reactive_power_l3=10,
        )
        rated_limits: EVSERatedLimits = EVSERatedLimits(
            ac_limits=ac_limits, dc_limits=None
        )
        session_limits: EVSESessionLimits = EVSESessionLimits(
            ac_limits=ac_cl_limits, dc_limits=None
        )

        evse_data_context = EVSEDataContext(
            rated_limits=rated_limits, session_limits=session_limits
        )
        evse_data_context.nominal_voltage = 10
        evse_data_context.nominal_frequency = 10
        evse_data_context.max_power_asymmetry = 10
        evse_data_context.power_ramp_limit = 10
        evse_data_context.present_active_power = 10
        evse_data_context.present_active_power_l2 = 10
        evse_data_context.present_active_power_l3 = 10
        return evse_data_context

    @pytest.mark.parametrize(
        "service_id_input, response_code",
        [
            (1, ResponseCode.OK),
            (5, ResponseCode.OK),
            (2, ResponseCode.FAILED_SERVICE_ID_INVALID),
        ],
    )
    async def test_service_detail_service_id_is_in_offered_list(
        self, service_id_input, response_code
    ):
        # [V2G20-464] The message "ServiceDetailRes" shall contain the
        # ResponseCode "FAILED_ServiceIDInvalid" if the ServiceID contained
        # in the ServiceDetailReq message was not part of the offered
        # EnergyTransferServiceList or VASList during ServiceDiscovery.

        self.comm_session.matched_services_v20 = []
        self.comm_session.evse_controller = SimEVSEController()
        service_ids = [1, 5]
        offered_energy_services: ServiceList = ServiceList(services=[])
        for service_id in service_ids:
            offered_energy_services.services.append(
                Service(service_id=service_id, free_service=False)
            )

        for energy_service in offered_energy_services.services:
            self.comm_session.matched_services_v20.append(
                MatchedService(
                    service=ServiceV20.get_by_id(energy_service.service_id),
                    is_energy_service=True,
                    is_free=energy_service.free_service,
                    # Parameter sets are available with ServiceDetailRes
                    parameter_sets=[],
                )
            )

        service_details = ServiceDetail(self.comm_session)
        await service_details.process_message(
            message=get_v2g_message_service_detail_req(service_id_input)
        )
        assert isinstance(service_details.message, ServiceDetailRes)
        assert service_details.message.response_code is response_code
        assert isinstance(self.comm_session.current_state, ServiceDetail)

    @pytest.mark.parametrize(
        "is_authorized_response, auth_mode, next_req_is_auth_req",
        [
            (
                AuthorizationResponse(AuthorizationStatus.ACCEPTED, ResponseCode.OK),
                AuthEnum.EIM,
                False,
            ),
            (
                AuthorizationResponse(AuthorizationStatus.ONGOING, ResponseCode.OK),
                AuthEnum.EIM,
                True,
            ),
            (
                AuthorizationResponse(
                    AuthorizationStatus.REJECTED, ResponseCode.FAILED
                ),
                AuthEnum.EIM,
                False,
            ),
        ],
    )
    async def test_eim_authorization_15118_20(
        self,
        is_authorized_response,
        auth_mode,
        next_req_is_auth_req,
    ):
        mock_is_authorized = AsyncMock(return_value=is_authorized_response)
        self.comm_session.evse_controller.is_authorized = mock_is_authorized

        authorization = Authorization(self.comm_session)

        await authorization.process_message(
            message=get_v2g_message_authorization_req(auth_mode)
        )
        assert authorization.expecting_authorization_req is next_req_is_auth_req

    @pytest.mark.parametrize(
        "params, selected_service, expected_state, expected_ev_context,",
        [
            (
                ACChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                ServiceV20.AC,
                ScheduleExchange,
                EVDataContext(
                    evcc_id=None,
                    rated_limits=EVRatedLimits(
                        ac_limits=EVACCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                        )
                    ),
                ),
            ),
            (
                BPTACChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=0, value=100),
                    ev_max_discharge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_discharge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                ServiceV20.AC_BPT,
                ScheduleExchange,
                EVDataContext(
                    evcc_id=None,
                    rated_limits=EVRatedLimits(
                        ac_limits=EVACCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                            max_discharge_power=30000,
                            min_discharge_power=100,
                            max_discharge_power_l2=30000,
                            min_discharge_power_l2=100,
                            max_discharge_power_l3=30000,
                            min_discharge_power_l3=100,
                        )
                    ),
                ),
            ),
            (
                ACChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                ServiceV20.AC,
                Terminate,
                EVDataContext(
                    evcc_id=None,
                    rated_limits=EVRatedLimits(
                        ac_limits=EVACCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                        )
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_ac_charge_parameter_discovery_res_ev_context_update(
        self, params, selected_service, expected_state, expected_ev_context
    ):
        self.comm_session.selected_energy_service = SelectedEnergyService(
            service=selected_service, is_free=True, parameter_set=None
        )
        if expected_state is Terminate:
            # force an error when getting the EV context
            # that will raise a UnknownService exception
            self.comm_session.selected_energy_service.service = None
        ac_service_discovery = ACChargeParameterDiscovery(self.comm_session)
        ac_service_discovery_req = get_ac_service_discovery_req(
            params, selected_service
        )
        await ac_service_discovery.process_message(message=ac_service_discovery_req)
        assert ac_service_discovery.next_state is expected_state
        updated_ev_context = self.comm_session.evse_controller.ev_data_context
        assert updated_ev_context == expected_ev_context

    @pytest.mark.parametrize(
        "params, selected_service, control_mode, expected_state, expected_ev_context, evse_data_context",  # noqa
        [
            (
                ScheduledACChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.AC,
                ControlMode.SCHEDULED,
                None,
                EVDataContext(
                    session_limits=EVSessionLimits(
                        ac_limits=EVACCLLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                        )
                    ),
                ),
                EVSEDataContext(
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                        )
                    ),
                ),
            ),
            (
                DynamicACChargeLoopReqParams(
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.AC,
                ControlMode.DYNAMIC,
                None,
                EVDataContext(
                    session_limits=EVSessionLimits(
                        ac_limits=EVACCLLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                        )
                    ),
                ),
                EVSEDataContext(
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                        )
                    ),
                ),
            ),
            (
                BPTScheduledACChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                ServiceV20.AC_BPT,
                ControlMode.SCHEDULED,
                None,
                EVDataContext(
                    session_limits=EVSessionLimits(
                        ac_limits=EVACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            min_charge_power=100,
                            min_charge_power_l2=100,
                            min_charge_power_l3=100,
                            max_discharge_power=30000,
                            max_discharge_power_l2=30000,
                            max_discharge_power_l3=30000,
                            min_discharge_power=100,
                            min_discharge_power_l2=100,
                            min_discharge_power_l3=100,
                        )
                    ),
                ),
                EVSEDataContext(
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            max_discharge_power=30000,
                            max_discharge_power_l2=30000,
                            max_discharge_power_l3=30000,
                        )
                    ),
                ),
            ),
            (
                BPTDynamicACChargeLoopReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_max_v2x_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_v2x_energy_request=RationalNumber(exponent=2, value=300),
                ),
                ServiceV20.AC_BPT,
                ControlMode.DYNAMIC,
                None,
                EVDataContext(
                    session_limits=EVSessionLimits(
                        ac_limits=EVACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            min_charge_power=100,
                            min_charge_power_l2=100,
                            min_charge_power_l3=100,
                            max_discharge_power=30000,
                            max_discharge_power_l2=30000,
                            max_discharge_power_l3=30000,
                            min_discharge_power=100,
                            min_discharge_power_l2=100,
                            min_discharge_power_l3=100,
                        )
                    ),
                ),
                EVSEDataContext(
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            max_discharge_power=30000,
                            max_discharge_power_l2=30000,
                            max_discharge_power_l3=30000,
                        )
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_ac_charge_charge_loop_res_ev_context_update(
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
        ac_charge_loop = ACChargeLoop(self.comm_session)
        ac_charge_loop_req = get_ac_charge_loop_req(
            params, selected_service, control_mode
        )
        await ac_charge_loop.process_message(message=ac_charge_loop_req)
        assert ac_charge_loop.next_state is expected_state
        updated_ev_context = self.comm_session.evse_controller.ev_data_context
        assert updated_ev_context.session_limits == expected_ev_context.session_limits

    @pytest.mark.parametrize(
        "req_params, expected_res_params, selected_service, expected_state, expected_evse_context",  # noqa
        [
            (
                ACChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=0, value=30000),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=0, value=30000),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=0, value=30000),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                ACChargeParameterDiscoveryResParams(
                    evse_max_charge_power=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power=RationalNumber(exponent=-2, value=10000),
                    evse_max_charge_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power_l2=RationalNumber(exponent=-2, value=10000),
                    evse_max_charge_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power_l3=RationalNumber(exponent=-2, value=10000),
                    evse_nominal_frequency=RationalNumber(exponent=-3, value=10000),
                    evse_power_ramp_limit=RationalNumber(exponent=-3, value=10000),
                    evse_present_active_power=RationalNumber(exponent=-2, value=10000),
                    evse_present_active_power_l2=RationalNumber(
                        exponent=-2, value=10000
                    ),
                    evse_present_active_power_l3=RationalNumber(
                        exponent=-2, value=10000
                    ),
                ),
                ServiceV20.AC,
                ScheduleExchange,
                EVSEDataContext(
                    rated_limits=EVSERatedLimits(
                        ac_limits=EVSEACCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                        )
                    ),
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(),
                    ),
                ),
            ),
            (
                BPTACChargeParameterDiscoveryReqParams(
                    ev_max_charge_power=RationalNumber(exponent=0, value=30000),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=0, value=30000),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=0, value=30000),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_max_discharge_power=RationalNumber(exponent=0, value=30000),
                    ev_min_discharge_power=RationalNumber(exponent=0, value=100),
                    ev_max_discharge_power_l2=RationalNumber(exponent=0, value=30000),
                    ev_min_discharge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_discharge_power_l3=RationalNumber(exponent=0, value=30000),
                    ev_min_discharge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                BPTACChargeParameterDiscoveryResParams(
                    evse_max_charge_power=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power=RationalNumber(exponent=-2, value=10000),
                    evse_max_charge_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power_l2=RationalNumber(exponent=-2, value=10000),
                    evse_max_charge_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_min_charge_power_l3=RationalNumber(exponent=-2, value=10000),
                    evse_nominal_frequency=RationalNumber(exponent=-3, value=10000),
                    evse_power_ramp_limit=RationalNumber(exponent=-3, value=10000),
                    evse_present_active_power=RationalNumber(exponent=-2, value=10000),
                    evse_present_active_power_l2=RationalNumber(
                        exponent=-2, value=10000
                    ),
                    evse_present_active_power_l3=RationalNumber(
                        exponent=-2, value=10000
                    ),
                    evse_max_discharge_power=RationalNumber(exponent=0, value=30000),
                    evse_min_discharge_power=RationalNumber(exponent=-2, value=10000),
                    evse_max_discharge_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_min_discharge_power_l2=RationalNumber(
                        exponent=-2, value=10000
                    ),
                    evse_max_discharge_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_min_discharge_power_l3=RationalNumber(
                        exponent=-2, value=10000
                    ),
                ),
                ServiceV20.AC_BPT,
                ScheduleExchange,
                EVSEDataContext(
                    rated_limits=EVSERatedLimits(
                        ac_limits=EVSEACCPDLimits(
                            max_charge_power=30000,
                            min_charge_power=100,
                            max_charge_power_l2=30000,
                            min_charge_power_l2=100,
                            max_charge_power_l3=30000,
                            min_charge_power_l3=100,
                            max_discharge_power=30000,
                            min_discharge_power=100,
                            max_discharge_power_l2=30000,
                            min_discharge_power_l2=100,
                            max_discharge_power_l3=30000,
                            min_discharge_power_l3=100,
                        ),
                    ),
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(),
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_ac_charge_param_discovery_res_evse_context_read(
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
        self.comm_session.evse_controller.get_ac_charge_params_v20 = AsyncMock(
            return_value=expected_res_params
        )
        ac_service_discovery = ACChargeParameterDiscovery(self.comm_session)
        ac_service_discovery_req = get_ac_service_discovery_req(
            req_params, selected_service
        )
        await ac_service_discovery.process_message(message=ac_service_discovery_req)
        # if the expected ACChargeParameterDiscoveryResParams is correctly returned,
        # the evse data context will be properly updated
        assert (
            self.comm_session.evse_controller.evse_data_context == expected_evse_context
        )
        # These are just sanity checks and should never be different...
        assert ac_service_discovery.next_state is expected_state
        assert isinstance(ac_service_discovery.message, ACChargeParameterDiscoveryRes)
        if selected_service == ServiceV20.AC:
            assert ac_service_discovery.message.ac_params == expected_res_params
        elif selected_service == ServiceV20.AC_BPT:
            assert ac_service_discovery.message.bpt_ac_params == expected_res_params

    @pytest.mark.parametrize(
        "ev_params, expected_evse_params, selected_service, control_mode, expected_state, evse_data_context",  # noqa
        [
            (
                ScheduledACChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                ),
                ScheduledACChargeLoopResParams(
                    evse_target_active_power=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_target_reactive_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power=RationalNumber(exponent=0, value=30000),
                    evse_present_active_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                ),
                ServiceV20.AC,
                ControlMode.SCHEDULED,
                None,
                EVSEDataContext(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    present_active_power=30000,
                    present_active_power_l2=30000,
                    present_active_power_l3=30000,
                    rated_limits=EVSERatedLimits(ac_limits=EVSEACCPDLimits()),
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            max_charge_reactive_power=30000,
                            max_charge_reactive_power_l2=30000,
                            max_charge_reactive_power_l3=30000,
                        ),
                    ),
                ),
            ),
            (
                DynamicACChargeLoopReqParams(
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                ),
                DynamicACChargeLoopResParams(
                    evse_target_active_power=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_target_reactive_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power=RationalNumber(exponent=0, value=30000),
                    evse_present_active_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                ),
                ServiceV20.AC,
                ControlMode.DYNAMIC,
                None,
                EVSEDataContext(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    present_active_power=30000,
                    present_active_power_l2=30000,
                    present_active_power_l3=30000,
                    rated_limits=EVSERatedLimits(ac_limits=EVSEACCPDLimits()),
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            max_charge_reactive_power=30000,
                            max_charge_reactive_power_l2=30000,
                            max_charge_reactive_power_l3=30000,
                        ),
                    ),
                ),
            ),
            (
                BPTScheduledACChargeLoopReqParams(
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l3=RationalNumber(exponent=0, value=100),
                ),
                BPTScheduledACChargeLoopResParams(
                    evse_target_active_power=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_target_reactive_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power=RationalNumber(exponent=0, value=30000),
                    evse_present_active_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                ),
                ServiceV20.AC_BPT,
                ControlMode.SCHEDULED,
                None,
                EVSEDataContext(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    present_active_power=30000,
                    present_active_power_l2=30000,
                    present_active_power_l3=30000,
                    rated_limits=EVSERatedLimits(ac_limits=EVSEACCPDLimits()),
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            max_charge_reactive_power=30000,
                            max_charge_reactive_power_l2=30000,
                            max_charge_reactive_power_l3=30000,
                        ),
                    ),
                ),
            ),
            (
                BPTDynamicACChargeLoopReqParams(
                    ev_max_charge_power=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_charge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_charge_power=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_charge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_present_active_power=RationalNumber(exponent=2, value=300),
                    ev_present_active_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_active_power_l3=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power=RationalNumber(exponent=2, value=300),
                    ev_present_reactive_power_l2=RationalNumber(exponent=0, value=100),
                    ev_present_reactive_power_l3=RationalNumber(exponent=2, value=300),
                    departure_time=3600,
                    ev_target_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_energy_request=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l2=RationalNumber(exponent=2, value=300),
                    ev_max_discharge_power_l3=RationalNumber(exponent=2, value=300),
                    ev_min_discharge_power=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l2=RationalNumber(exponent=0, value=100),
                    ev_min_discharge_power_l3=RationalNumber(exponent=0, value=100),
                    ev_max_v2x_energy_request=RationalNumber(exponent=2, value=300),
                    ev_min_v2x_energy_request=RationalNumber(exponent=2, value=300),
                ),
                BPTDynamicACChargeLoopResParams(
                    evse_target_active_power=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l2=RationalNumber(exponent=0, value=30000),
                    evse_target_active_power_l3=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power=RationalNumber(exponent=0, value=30000),
                    evse_target_reactive_power_l2=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_target_reactive_power_l3=RationalNumber(
                        exponent=0, value=30000
                    ),
                    evse_present_active_power=RationalNumber(exponent=0, value=1),
                    evse_present_active_power_l2=RationalNumber(exponent=-2, value=5),
                    evse_present_active_power_l3=RationalNumber(exponent=1, value=5000),
                ),
                ServiceV20.AC_BPT,
                ControlMode.DYNAMIC,
                None,
                EVSEDataContext(
                    departure_time=3600,
                    min_soc=30,
                    target_soc=80,
                    ack_max_delay=15,
                    present_active_power=1,
                    present_active_power_l2=0.05,
                    present_active_power_l3=50000,
                    rated_limits=EVSERatedLimits(ac_limits=EVSEACCPDLimits()),
                    session_limits=EVSESessionLimits(
                        ac_limits=EVSEACCLLimits(
                            max_charge_power=30000,
                            max_charge_power_l2=30000,
                            max_charge_power_l3=30000,
                            max_charge_reactive_power=30000,
                            max_charge_reactive_power_l2=30000,
                            max_charge_reactive_power_l3=30000,
                        ),
                    ),
                ),
            ),
        ],
    )
    async def test_15118_20_ac_charge_charge_loop_res_evse_context_read(
        self,
        ev_params,
        expected_evse_params,
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
        ac_charge_loop = ACChargeLoop(self.comm_session)
        ac_charge_loop_req = get_ac_charge_loop_req(
            ev_params, selected_service, control_mode
        )
        await ac_charge_loop.process_message(message=ac_charge_loop_req)
        assert ac_charge_loop.next_state is expected_state
        assert isinstance(ac_charge_loop.message, ACChargeLoopRes)
        if selected_service == ServiceV20.AC and control_mode == ControlMode.SCHEDULED:
            assert ac_charge_loop.message.scheduled_params == expected_evse_params
        elif (
            selected_service == ServiceV20.AC_BPT
            and control_mode == ControlMode.SCHEDULED
        ):
            assert ac_charge_loop.message.bpt_scheduled_params == expected_evse_params
        if selected_service == ServiceV20.AC and control_mode == ControlMode.DYNAMIC:
            assert ac_charge_loop.message.dynamic_params == expected_evse_params
        elif (
            selected_service == ServiceV20.AC_BPT
            and control_mode == ControlMode.DYNAMIC
        ):
            assert ac_charge_loop.message.bpt_dynamic_params == expected_evse_params

    @pytest.mark.parametrize(
        "control_mode, next_state, selected_energy_service, cp_state",
        [
            (
                ControlMode.DYNAMIC,
                ACChargeLoop,
                SelectedEnergyService(
                    service=ServiceV20.AC, is_free=True, parameter_set=None
                ),
                CpState.D2,
            ),
            (
                ControlMode.DYNAMIC,
                ACChargeLoop,
                SelectedEnergyService(
                    service=ServiceV20.AC, is_free=True, parameter_set=None
                ),
                CpState.C2,
            ),
            (
                ControlMode.DYNAMIC,
                ACChargeLoop,
                SelectedEnergyService(
                    service=ServiceV20.AC, is_free=True, parameter_set=None
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
