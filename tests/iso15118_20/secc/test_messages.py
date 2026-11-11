import time
from typing import Union

from iso15118.shared.messages.enums import AuthEnum, ControlMode, ServiceV20
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeLoopReq,
    ACChargeParameterDiscoveryReq,
    ACChargeParameterDiscoveryReqParams,
    BPTACChargeParameterDiscoveryReqParams,
    BPTDynamicACChargeLoopReqParams,
    BPTScheduledACChargeLoopReqParams,
    DynamicACChargeLoopReqParams,
    ScheduledACChargeLoopReqParams,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationReq,
    ChargeProgress,
    ContractCertificateChain,
    DynamicEVPowerProfile,
    DynamicScheduleExchangeReqParams,
    EIMAuthReqParams,
    EVPowerProfile,
    EVPowerProfileEntryList,
    PnCAuthReqParams,
    PowerDeliveryReq,
    PowerScheduleEntry,
    ScheduledScheduleExchangeReqParams,
    ScheduleExchangeReq,
    ServiceDetailReq,
    SubCertificates,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    MessageHeader,
    Processing,
    RationalNumber,
)
from iso15118.shared.messages.iso15118_20.dc import (
    BPTDCChargeParameterDiscoveryReqParams,
    BPTDynamicDCChargeLoopReqParams,
    BPTScheduledDCChargeLoopReqParams,
    DCCableCheckReq,
    DCChargeLoopReq,
    DCChargeParameterDiscoveryReq,
    DCChargeParameterDiscoveryReqParams,
    DCPreChargeReq,
    DynamicDCChargeLoopReqParams,
    ScheduledDCChargeLoopReqParams,
)
from iso15118.shared.security import get_random_bytes
from tests.tools import MOCK_SESSION_ID


def get_v2g_message_service_detail_req(service_list: int) -> ServiceDetailReq:
    return ServiceDetailReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        service_id=service_list,
    )


def get_v2g_message_authorization_req(auth_service: AuthEnum) -> AuthorizationReq:
    eim_params = None
    pnc_params = None
    if auth_service == AuthEnum.EIM:
        eim_params = EIMAuthReqParams()
    else:
        pnc_params = PnCAuthReqParams(
            gen_challenge=get_random_bytes(16),
            contract_cert_chain=ContractCertificateChain(
                certificate=b"00", sub_certificates=SubCertificates(certificates=[])
            ),
        )
    return AuthorizationReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        selected_auth_service=auth_service,
        eim_params=eim_params,
        pnc_params=pnc_params,
    )


def get_v2g_message_dc_charge_parameter_discovery_req(
    service: ServiceV20,
) -> DCChargeParameterDiscoveryReq:
    dc_params = DCChargeParameterDiscoveryReqParams(
        ev_max_charge_power=RationalNumber(exponent=3, value=300),
        ev_min_charge_power=RationalNumber(exponent=0, value=100),
        ev_max_charge_current=RationalNumber(exponent=0, value=300),
        ev_min_charge_current=RationalNumber(exponent=0, value=10),
        ev_max_voltage=RationalNumber(exponent=0, value=1000),
        ev_min_voltage=RationalNumber(exponent=0, value=10),
    )
    bpt_dc_params = None
    if service == ServiceV20.DC_BPT:
        bpt_dc_params = BPTDCChargeParameterDiscoveryReqParams(
            **(dc_params.dict()),
            ev_max_discharge_power=RationalNumber(exponent=3, value=11),
            ev_min_discharge_power=RationalNumber(exponent=3, value=1),
            ev_max_discharge_current=RationalNumber(exponent=0, value=11),
            ev_min_discharge_current=RationalNumber(exponent=0, value=0),
        )
        dc_params = None

    return DCChargeParameterDiscoveryReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        dc_params=dc_params,
        bpt_dc_params=bpt_dc_params,
    )


def get_schedule_exchange_req_message(control_mode: ControlMode):
    scheduled_params, dynamic_params = None, None
    if control_mode == ControlMode.SCHEDULED:
        scheduled_params = ScheduledScheduleExchangeReqParams(
            departure_time=7200,
            ev_target_energy_request=RationalNumber(exponent=3, value=10),
            ev_max_energy_request=RationalNumber(exponent=3, value=20),
            ev_min_energy_request=RationalNumber(exponent=-2, value=5),
        )

    if control_mode == ControlMode.DYNAMIC:
        dynamic_params = DynamicScheduleExchangeReqParams(
            departure_time=7200,
            min_soc=30,
            target_soc=80,
            ev_target_energy_request=RationalNumber(exponent=3, value=40),
            ev_max_energy_request=RationalNumber(exponent=1, value=6000),
            ev_min_energy_request=RationalNumber(exponent=0, value=-20000),
            ev_max_v2x_energy_request=RationalNumber(exponent=0, value=5000),
            ev_min_v2x_energy_request=RationalNumber(exponent=0, value=0),
        )

    return ScheduleExchangeReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        max_supporting_points=12,
        scheduled_params=scheduled_params,
        dynamic_params=dynamic_params,
    )


def get_cable_check_req():
    return DCCableCheckReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        )
    )


def get_precharge_req(processing: Processing):
    return DCPreChargeReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        ev_processing=processing,
        ev_present_voltage=RationalNumber(exponent=0, value=10),
        ev_target_voltage=RationalNumber(exponent=0, value=10),
    )


def get_power_delivery_req(processing: Processing, charge_progress: ChargeProgress):
    return PowerDeliveryReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        ev_processing=processing,
        charge_progress=charge_progress,
        ev_power_profile=EVPowerProfile(
            time_anchor=0,
            entry_list=EVPowerProfileEntryList(
                entries=[
                    PowerScheduleEntry(
                        duration=10, power=RationalNumber(exponent=0, value=10)
                    )
                ]
            ),
            dynamic_profile=DynamicEVPowerProfile(),
        ),
    )


def get_dc_service_discovery_req(
    params: Union[
        DCChargeParameterDiscoveryReqParams, BPTDCChargeParameterDiscoveryReqParams
    ],
    service: ServiceV20,
) -> DCChargeParameterDiscoveryReq:
    dc_params = None
    dc_bpt_params = None
    if service == ServiceV20.DC:
        dc_params = params
    else:
        dc_bpt_params = params
    return DCChargeParameterDiscoveryReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        dc_params=dc_params,
        bpt_dc_params=dc_bpt_params,
    )


def get_ac_service_discovery_req(
    params: Union[
        ACChargeParameterDiscoveryReqParams, BPTACChargeParameterDiscoveryReqParams
    ],
    service: ServiceV20,
) -> ACChargeParameterDiscoveryReq:
    ac_params = None
    ac_bpt_params = None
    if service == ServiceV20.AC:
        ac_params = params
    else:
        ac_bpt_params = params
    return ACChargeParameterDiscoveryReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        ac_params=ac_params,
        bpt_ac_params=ac_bpt_params,
    )


def get_ac_charge_loop_req(
    params: Union[
        ScheduledACChargeLoopReqParams,
        DynamicACChargeLoopReqParams,
        BPTScheduledACChargeLoopReqParams,
        BPTDynamicACChargeLoopReqParams,
    ],
    service: ServiceV20,
    control_mode: ControlMode,
) -> ACChargeLoopReq:
    scheduled_params = None
    dynamic_params = None
    bpt_scheduled_params = None
    bpt_dynamic_params = None

    if service == ServiceV20.AC:
        if control_mode == ControlMode.SCHEDULED:
            scheduled_params = params
        else:
            dynamic_params = params
    elif service == ServiceV20.AC_BPT:
        if control_mode == ControlMode.SCHEDULED:
            bpt_scheduled_params = params
        else:
            bpt_dynamic_params = params

    return ACChargeLoopReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        scheduled_params=scheduled_params,
        dynamic_params=dynamic_params,
        bpt_scheduled_params=bpt_scheduled_params,
        bpt_dynamic_params=bpt_dynamic_params,
        meter_info_requested=False,
    )


def get_dc_charge_loop_req(
    params: Union[
        ScheduledDCChargeLoopReqParams,
        DynamicDCChargeLoopReqParams,
        BPTScheduledDCChargeLoopReqParams,
        BPTDynamicDCChargeLoopReqParams,
    ],
    service: ServiceV20,
    control_mode: ControlMode,
) -> DCChargeLoopReq:
    scheduled_params = None
    dynamic_params = None
    bpt_scheduled_params = None
    bpt_dynamic_params = None

    if service == ServiceV20.DC:
        if control_mode == ControlMode.SCHEDULED:
            scheduled_params = params
        else:
            dynamic_params = params
    elif service == ServiceV20.DC_BPT:
        if control_mode == ControlMode.SCHEDULED:
            bpt_scheduled_params = params
        else:
            bpt_dynamic_params = params
    return DCChargeLoopReq(
        header=MessageHeader(
            session_id=MOCK_SESSION_ID,
            timestamp=int(time.time() * 1_000_000),
        ),
        ev_present_voltage=RationalNumber(exponent=0, value=300),
        scheduled_params=scheduled_params,
        dynamic_params=dynamic_params,
        bpt_scheduled_params=bpt_scheduled_params,
        bpt_dynamic_params=bpt_dynamic_params,
        meter_info_requested=False,
    )
