import time
from enum import Enum
from unittest.mock import Mock, patch

import pytest as pytest

from iso15118.evcc import EVCCConfig
from iso15118.evcc.comm_session_handler import EVCCCommunicationSession
from iso15118.evcc.controller.simulator import SimEVController
from iso15118.evcc.states.din_spec_states import (
    CableCheck,
    ChargeParameterDiscovery,
    ContractAuthentication,
    CurrentDemand,
    PowerDelivery,
    ServiceDiscovery,
    ServicePaymentSelection,
    SessionSetup,
    WeldingDetection,
)
from iso15118.shared.messages.enums import AuthEnum, EnergyTransferModeEnum, Protocol
from iso15118.shared.notifications import StopNotification
from iso15118.shared.states import Terminate
from tests.dinspec.evcc.evcc_mock_messages import (
    get_charge_parameter_discovery_message,
    get_charge_parameter_discovery_on_going_message,
    get_contract_authentication_message,
    get_contract_authentication_ongoing_message,
    get_current_demand_acheived,
    get_power_delivery_res_message,
    get_service_discovery_message,
    get_service_discovery_message_charge_service_not_offered,
    get_service_discovery_message_payment_service_not_offered,
    get_service_payment_selection_fail_message,
    get_service_payment_selection_message,
    get_session_setup_evseid_zero,
    get_v2g_message_current_demand_current_limit_not_achieved,
    get_welding_detection_on_going_message,
)


class MockWriter:
    def get_extra_info(self, query_string: str):
        return "not supported"


@patch("iso15118.shared.states.EXI.to_exi", new=Mock(return_value=b"01"))
@pytest.mark.asyncio
class TestEvScenarios:
    @pytest.fixture(autouse=True)
    def _comm_session(self, comm_evcc_session_mock):
        self.comm_session_mock = Mock(spec=EVCCCommunicationSession)
        self.comm_session_mock.session_id = "F9F9EE8505F55838"
        self.comm_session_mock.stop_reason = StopNotification(False, "pytest")
        evcc_config = EVCCConfig()
        evcc_config.energy_transfer_mode = EnergyTransferModeEnum.DC_EXTENDED
        evcc_config.ongoing_retry_delay = 0
        self.comm_session_mock.ev_controller = SimEVController(evcc_config)
        self.comm_session_mock.config = evcc_config
        self.comm_session_mock.protocol = Protocol.DIN_SPEC_70121
        self.comm_session_mock.selected_schedule = 1
        self.comm_session_mock.selected_services = []
        self.comm_session_mock.selected_energy_mode = EnergyTransferModeEnum.DC_CORE
        self.comm_session_mock.selected_auth_option = AuthEnum.EIM_V2
        self.comm_session_mock.writer = MockWriter()
        self.comm_session_mock.ongoing_timer = -1

    @pytest.fixture(autouse=True)
    def _is_welding_detection_complete(self):
        return False

    async def test_service_discovery_payment_service_not_offered(self):
        service_discovery = ServiceDiscovery(self.comm_session_mock)
        await service_discovery.process_message(
            message=get_service_discovery_message_payment_service_not_offered()
        )
        assert service_discovery.next_state is Terminate

    async def test_service_discovery_charge_service_not_offered(self):
        service_discovery = ServiceDiscovery(self.comm_session_mock)
        await service_discovery.process_message(
            message=get_service_discovery_message_charge_service_not_offered()
        )
        assert service_discovery.next_state is Terminate

    async def test_service_discovery_to_service_payment_selection(self):
        service_discovery = ServiceDiscovery(self.comm_session_mock)
        await service_discovery.process_message(message=get_service_discovery_message())
        assert service_discovery.next_state is ServicePaymentSelection

    async def test_service_payment_selection_fail(self):
        service_payment_selection = ServicePaymentSelection(self.comm_session_mock)
        await service_payment_selection.process_message(
            message=get_service_payment_selection_fail_message()
        )
        assert service_payment_selection.next_state is Terminate

    async def test_service_payment_selection_to_contract_authentication(self):
        service_payment_selection = ServicePaymentSelection(self.comm_session_mock)
        await service_payment_selection.process_message(
            message=get_service_payment_selection_message()
        )
        assert service_payment_selection.next_state is ContractAuthentication

    async def test_contract_authentication_on_going(self):
        contract_authentication = ContractAuthentication(self.comm_session_mock)
        await contract_authentication.process_message(
            message=get_contract_authentication_ongoing_message()
        )
        assert contract_authentication.next_state is None

    @pytest.mark.skip(reason="Takes too long. Need to patch timeout enum")
    async def test_contract_authentication_timeout(self):
        contract_authentication = ContractAuthentication(self.comm_session_mock)
        await contract_authentication.process_message(
            message=get_contract_authentication_ongoing_message()
        )
        assert contract_authentication.next_state is None
        time.sleep(61)
        await contract_authentication.process_message(
            message=get_contract_authentication_ongoing_message()
        )
        assert contract_authentication.next_state is Terminate

    async def test_contract_authentication_to_charge_parameter_discovery(self):
        contract_authentication = ContractAuthentication(self.comm_session_mock)
        await contract_authentication.process_message(
            message=get_contract_authentication_message()
        )
        assert contract_authentication.next_state is ChargeParameterDiscovery

    async def test_current_demand_req_to_power_delivery_req(self):
        current_demand = CurrentDemand(self.comm_session_mock)
        await current_demand.process_message(message=get_current_demand_acheived())
        assert current_demand.next_state is PowerDelivery

    async def test_current_demand_req_to_power_delivery_req_to_welding_detection(self):
        current_demand = CurrentDemand(self.comm_session_mock)
        await current_demand.process_message(message=get_current_demand_acheived())
        assert current_demand.next_state is PowerDelivery
        power_delivery = PowerDelivery(self.comm_session_mock)
        await power_delivery.process_message(message=get_power_delivery_res_message())
        assert power_delivery.next_state is WeldingDetection

    async def test_current_demand_to_current_demand(self):
        current_demand = CurrentDemand(self.comm_session_mock)
        await current_demand.process_message(
            message=get_v2g_message_current_demand_current_limit_not_achieved()
        )
        assert current_demand.next_state is None

    async def test_charge_parameter_discovery_to_cable_check(self):
        charge_parameter_discovery = ChargeParameterDiscovery(self.comm_session_mock)
        await charge_parameter_discovery.process_message(
            message=get_charge_parameter_discovery_message()
        )
        assert charge_parameter_discovery.next_state is CableCheck

    @pytest.mark.skip(reason="Takes too long. Need to patch timeout enum")
    async def test_charge_parameter_discovery_timeout(self):
        charge_parameter_discovery = ChargeParameterDiscovery(self.comm_session_mock)
        await charge_parameter_discovery.process_message(
            message=get_charge_parameter_discovery_on_going_message()
        )
        assert charge_parameter_discovery.next_state is None
        time.sleep(61)
        await charge_parameter_discovery.process_message(
            message=get_charge_parameter_discovery_on_going_message()
        )
        assert charge_parameter_discovery.next_state is Terminate

    async def test_session_setup_to_service_discovery(self):
        session_setup = SessionSetup(self.comm_session_mock)
        await session_setup.process_message(message=get_session_setup_evseid_zero())
        assert session_setup.next_state is ServiceDiscovery

    async def cable_check_req_to_pre_charge(self):
        pass

    async def cable_check_req_to_cable_check_req(self):
        pass

    async def pre_charge_to_pre_charge(self):
        pass

    async def pre_charge_to_power_delivery(self):
        pass

    async def power_delivery_to_current_demand(self):
        pass

    async def current_demand_to_terminate(self):
        pass

    async def current_demand_to_current_demand(self):
        pass

    async def current_demand_to_power_delivery(self):
        pass

    async def test_power_delivery_to_welding_detection(self):
        pass

    async def test_power_delivery_to_session_stop(self):
        pass

    async def test_welding_detection_to_session_stop(self):
        pass

    class Timeouts(float, Enum):
        """
        Timeout restrictions for request/response message pairs and
        message sequences according to both ISO 15118-2 and ISO 15118-20.
        Given in seconds
        """

        SDP_REQ = 0.25
        SUPPORTED_APP_PROTOCOL_REQ = 1
        V2G_EVCC_COMMUNICATION_SETUP_TIMEOUT = 1
        V2G_SECC_SEQUENCE_TIMEOUT = 1
        V2G_EVCC_ONGOING_TIMEOUT = 1

    @pytest.mark.skip(reason="Takes too long. Need to patch timeout")
    async def test_welding_detection_timeout(self, _is_welding_detection_complete):
        welding_detection = WeldingDetection(self.comm_session_mock)
        await welding_detection.process_message(
            message=get_welding_detection_on_going_message()
        )
        time.sleep(2)
        await welding_detection.process_message(
            message=get_welding_detection_on_going_message()
        )
        assert welding_detection.next_state is Terminate
