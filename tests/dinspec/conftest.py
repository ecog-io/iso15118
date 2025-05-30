import pytest

from iso15118.shared.messages.datatypes import (
    DCEVChargeParams,
    PVEVEnergyCapacity,
    PVEVMaxCurrentLimit,
    PVEVMaxPowerLimit,
    PVEVMaxVoltageLimit,
    PVEVTargetCurrent,
    PVEVTargetVoltage,
    PVRemainingTimeToBulkSOC,
    PVRemainingTimeToFullSOC,
)
from iso15118.shared.messages.din_spec.body import (
    Body,
    CurrentDemandReq,
    PowerDeliveryReq,
)
from iso15118.shared.messages.din_spec.datatypes import (
    DCEVPowerDeliveryParameter,
    DCEVStatus,
)
from iso15118.shared.messages.din_spec.header import MessageHeader
from iso15118.shared.messages.din_spec.msgdef import V2GMessage
from iso15118.shared.messages.enums import DCEVErrorCode, UnitSymbol
from tests.tools import MOCK_SESSION_ID


def get_dc_ev_status() -> DCEVStatus:
    return DCEVStatus(
        ev_ready=True,
        ev_error_code=DCEVErrorCode.NO_ERROR,
        ev_ress_soc=60,
    )


def get_dc_charge_params():
    return DCEVChargeParams(
        dc_max_current_limit=PVEVMaxCurrentLimit(
            multiplier=-3, value=32000, unit=UnitSymbol.AMPERE
        ),
        dc_max_power_limit=PVEVMaxPowerLimit(
            multiplier=1, value=8000, unit=UnitSymbol.WATT
        ),
        dc_max_voltage_limit=PVEVMaxVoltageLimit(
            multiplier=1, value=40, unit=UnitSymbol.VOLTAGE
        ),
        dc_energy_capacity=PVEVEnergyCapacity(
            multiplier=1, value=7000, unit=UnitSymbol.WATT_HOURS
        ),
        dc_target_current=PVEVTargetCurrent(
            multiplier=0, value=1, unit=UnitSymbol.AMPERE
        ),
        dc_precharge_target_current=PVEVTargetCurrent(
            multiplier=0, value=1, unit=UnitSymbol.AMPERE
        ),
        dc_target_voltage=PVEVTargetVoltage(
            multiplier=0, value=400, unit=UnitSymbol.VOLTAGE
        ),
    )


def build_dummy_current_demand_req() -> CurrentDemandReq:
    dc_charge_params = get_dc_charge_params()
    current_demand_req: CurrentDemandReq = CurrentDemandReq(
        dc_ev_status=get_dc_ev_status(),
        ev_target_current=dc_charge_params.dc_target_current,
        ev_max_voltage_limit=dc_charge_params.dc_max_voltage_limit,
        ev_max_current_limit=dc_charge_params.dc_max_current_limit,
        ev_max_power_limit=dc_charge_params.dc_max_power_limit,
        bulk_charging_complete=False,
        charging_complete=False,
        remaining_time_to_full_soc=PVRemainingTimeToFullSOC(
            multiplier=0, value=80, unit="s"
        ),
        remaining_time_to_bulk_soc=PVRemainingTimeToBulkSOC(
            multiplier=0, value=80, unit="s"
        ),
        ev_target_voltage=dc_charge_params.dc_target_voltage,
    )
    return current_demand_req


@pytest.fixture
def current_on_going_req():
    current_demand_req = build_dummy_current_demand_req()
    return V2GMessage(
        header=MessageHeader(session_id=MOCK_SESSION_ID),
        body=Body(current_demand_req=current_demand_req),
    )


@pytest.fixture
def power_delivery_req_charge_start():
    power_delivery_req = PowerDeliveryReq(
        ready_to_charge=True,
        dc_ev_power_delivery_parameter=DCEVPowerDeliveryParameter(
            dc_ev_status=DCEVStatus(
                ev_ready=True,
                ev_error_code=DCEVErrorCode.NO_ERROR,
                ev_ress_soc=60,
            ),
            charging_complete=False,
        ),
    )

    return V2GMessage(
        header=MessageHeader(session_id=MOCK_SESSION_ID),
        body=Body(power_delivery_req=power_delivery_req),
    )


@pytest.fixture
def power_delivery_req_charge_stop():
    power_delivery_req = PowerDeliveryReq(
        ready_to_charge=False,
        dc_ev_power_delivery_parameter=DCEVPowerDeliveryParameter(
            dc_ev_status=DCEVStatus(
                ev_ready=True, ev_error_code=DCEVErrorCode.NO_ERROR, ev_ress_soc=90
            ),
            charging_complete=False,
        ),
    )

    return V2GMessage(
        header=MessageHeader(session_id=MOCK_SESSION_ID),
        body=Body(power_delivery_req=power_delivery_req),
    )
