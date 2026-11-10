import json

import pytest

from iso15118.shared.exi_codec import CustomJSONDecoder
from iso15118.shared.messages.datatypes import (
    PVRemainingTimeToBulkSOC,
    PVRemainingTimeToFullSOC,
)
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from tests.shared.messages.exi_message_container import ExiMessageContainer

# Test strings recorded 28.7.2022 with Comemso Multi Mobile DC Protocol Tester
DIN_TEST_MESSAGES = [
    ExiMessageContainer(
        message_name="SessionSetupReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"0000000000000000"},"Body":'
        '{"SessionSetupReq":{"EVCCID":"0000020000000001"}}}}',
    ),
    ExiMessageContainer(
        message_name="SessionSetupRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "AB9AB72CABAEFC72"},"Body":'
        '{"SessionSetupRes": {"ResponseCode": "OK_NewSessionEstablished",'
        '"EVSEID": "49A89A6360", "DateTimeNow": 1659025085}}}}',
    ),
    ExiMessageContainer(
        message_name="ServiceDiscoveryReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"ServiceDiscoveryReq":{"ServiceCategory":"EVCharging"}}}}',
    ),
    ExiMessageContainer(
        message_name="ServiceDiscoveryRes",
        json_str='{"V2G_Message": {"Header": {"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"ServiceDiscoveryRes": {"ResponseCode": "OK", "PaymentOptions":'
        '{"PaymentOption":["ExternalPayment"]},"ChargeService":{"ServiceTag":'
        '{"ServiceID": 1, "ServiceCategory": "EVCharging"}, "FreeService":'
        'true, "EnergyTransferType": "DC_extended"}}}}}',
    ),
    ExiMessageContainer(
        message_name="ServicePaymentSelectionReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"ServicePaymentSelectionReq":{"SelectedPaymentOption":'
        '"ExternalPayment","SelectedServiceList":{"SelectedService":'
        '[{"ServiceID":1}]}}}}}',
    ),
    ExiMessageContainer(
        message_name="ServicePaymentSelectionRes",
        json_str='{"V2G_Message": {"Header": {"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"ServicePaymentSelectionRes": {"ResponseCode": "OK"}}}}',
    ),
    ExiMessageContainer(
        message_name="ContractAuthenticationReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"ContractAuthenticationReq":{}}}}',
    ),
    ExiMessageContainer(
        message_name="ContractAuthenticationRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "AB9AB72CABAEFC72"},"Body":'
        '{"ContractAuthenticationRes":{"ResponseCode":"OK","EVSEProcessing":'
        '"Finished"}}}}',
    ),
    ExiMessageContainer(
        message_name="ChargeParameterDiscoveryReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"ChargeParameterDiscoveryReq":{"EVRequestedEnergyTransferType":'
        '"DC_extended","DC_EVChargeParameter":{"DC_EVStatus":{"EVReady":'
        'false,"EVCabinConditioning":true,"EVRESSConditioning":true,'
        '"EVErrorCode":"NO_ERROR","EVRESSSOC":20},"EVMaximumCurrentLimit":'
        '{"Multiplier":1,"Unit":"A","Value":8},"EVMaximumPowerLimit":'
        '{"Multiplier":3,"Unit":"W","Value":29},"EVMaximumVoltageLimit":'
        '{"Multiplier":2,"Unit":"V","Value":5},"EVEnergyCapacity":'
        '{"Multiplier":3,"Unit":"Wh","Value":200},"EVEnergyRequest":'
        '{"Multiplier":3,"Unit":"Wh","Value":160},"FullSOC":99,'
        '"BulkSOC":80}}}}}',
    ),
    ExiMessageContainer(
        message_name="ChargeParameterDiscoveryRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "AB9AB72CABAEFC72"},'
        '"Body": {"ChargeParameterDiscoveryRes": {"ResponseCode": "OK",'
        '"EVSEProcessing": "Finished", "SAScheduleList": {"SAScheduleTuple":'
        '[{"SAScheduleTupleID": 1, "PMaxSchedule": {"PMaxScheduleID": 2,'
        '"PMaxScheduleEntry": [{"PMax": 32767, "RelativeTimeInterval":'
        '{"start": 0, "duration": 3600}}]}}]}, "DC_EVSEChargeParameter":'
        '{"DC_EVSEStatus": {"NotificationMaxDelay": 0, "EVSENotification":'
        '"None", "EVSEIsolationStatus": "Invalid", "EVSEStatusCode":'
        '"EVSE_Ready"}, "EVSEMaximumCurrentLimit":{"Value":120,"Multiplier":'
        '0,"Unit":"A"},"EVSEMaximumPowerLimit":{"Value": 4200,"Multiplier":'
        '1, "Unit": "W"}, "EVSEMaximumVoltageLimit": {"Value": 1000,'
        '"Multiplier": 0, "Unit": "V"}, "EVSEMinimumCurrentLimit": {"Value":'
        '4, "Multiplier": 0, "Unit": "A"},"EVSEMinimumVoltageLimit":{"Value":'
        '250, "Multiplier": 0, "Unit":"V"},"EVSECurrentRegulationTolerance":'
        '{"Value": 0, "Multiplier": 0, "Unit": "A"}, "EVSEPeakCurrentRipple":'
        '{"Value": 1, "Multiplier": 0,"Unit":"A"},"EVSEEnergyToBeDelivered":'
        '{"Value": 10000, "Multiplier": 0, "Unit": "Wh"}}}}}}',
    ),
    ExiMessageContainer(
        message_name="CableCheckReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"CableCheckReq":{"DC_EVStatus":{"EVReady":true,'
        '"EVCabinConditioning":true,"EVRESSConditioning":true,"EVErrorCode":'
        '"NO_ERROR","EVRESSSOC":20}}}}}',
    ),
    ExiMessageContainer(
        message_name="CableCheckRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "AB9AB72CABAEFC72"},"Body":'
        '{"CableCheckRes": {"ResponseCode": "OK", "DC_EVSEStatus":'
        '{"NotificationMaxDelay": 0, "EVSENotification": "None",'
        '"EVSEIsolationStatus": "Invalid", "EVSEStatusCode": "EVSE_Ready"},'
        '"EVSEProcessing": "Ongoing"}}}}',
    ),
    ExiMessageContainer(
        message_name="PreChargeReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"PreChargeReq":{"DC_EVStatus":{"EVReady":true,'
        '"EVCabinConditioning":true,"EVRESSConditioning":true,"EVErrorCode":'
        '"NO_ERROR","EVRESSSOC":20},"EVTargetVoltage":{"Multiplier":2,"Unit":'
        '"V","Value":4},"EVTargetCurrent":{"Multiplier":0,"Unit":"A","Value":'
        "0}}}}}",
    ),
    ExiMessageContainer(
        message_name="PreChargeRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "AB9AB72CABAEFC72"},"Body":'
        '{"PreChargeRes": {"ResponseCode": "OK", "DC_EVSEStatus":'
        '{"NotificationMaxDelay": 0, "EVSENotification": "None",'
        '"EVSEIsolationStatus": "Valid", "EVSEStatusCode": "EVSE_Ready"},'
        '"EVSEPresentVoltage": {"Value": 0, "Multiplier": 0,"Unit":"V"}}}}}',
    ),
    ExiMessageContainer(
        message_name="PowerDeliveryReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"AB9AB72CABAEFC72"},"Body":'
        '{"PowerDeliveryReq":{"ReadyToChargeState":true,'
        '"DC_EVPowerDeliveryParameter":{"DC_EVStatus":{"EVReady":true,'
        '"EVCabinConditioning":false,"EVRESSConditioning":true,"EVErrorCode":'
        '"NO_ERROR","EVRESSSOC":20},"BulkChargingComplete":false,'
        '"ChargingComplete":false}}}}}',
    ),
    ExiMessageContainer(
        message_name="PowerDeliveryRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "4FF877E9B597CC1C"},"Body":'
        '{"PowerDeliveryRes": {"ResponseCode": "OK", "DC_EVSEStatus":'
        '{"NotificationMaxDelay": 0, "EVSENotification": "None",'
        '"EVSEIsolationStatus": "Valid", "EVSEStatusCode": "EVSE_Ready"}}}}}',
    ),
    ExiMessageContainer(
        message_name="CurrentDemandReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"4FF877E9B597CC1C"},"Body":'
        '{"CurrentDemandReq":{"DC_EVStatus":{"EVReady":true,'
        '"EVCabinConditioning":true,"EVRESSConditioning":true,"EVErrorCode":'
        '"NO_ERROR","EVRESSSOC":20},"EVTargetCurrent":{"Multiplier":0,"Unit":'
        '"A","Value":0},"EVMaximumVoltageLimit":{"Multiplier":2,"Unit":"V",'
        '"Value":5},"EVMaximumCurrentLimit":{"Multiplier":1,"Unit":"A",'
        '"Value":8},"EVMaximumPowerLimit":{"Multiplier":3,"Unit":"W",'
        '"Value":29},"BulkChargingComplete":false,"ChargingComplete":false,'
        '"RemainingTimeToFullSoC":{"Multiplier":3,"Unit":"s","Value":32767},'
        '"RemainingTimeToBulkSoC":{"Multiplier":3,"Unit":"s","Value":32767},'
        '"EVTargetVoltage":{"Multiplier":1,"Unit":"V","Value":45}}}}}',
    ),
    ExiMessageContainer(
        message_name="CurrentDemandRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "4FF877E9B597CC1C"},'
        '"Body": {"CurrentDemandRes": {"ResponseCode": "OK","DC_EVSEStatus":'
        '{"NotificationMaxDelay": 0, "EVSENotification": "None",'
        '"EVSEIsolationStatus": "Valid", "EVSEStatusCode": "EVSE_Ready"},'
        '"EVSEPresentVoltage": {"Value": 400, "Multiplier": 0, "Unit": "V"},'
        '"EVSEPresentCurrent": {"Value": 0, "Multiplier": 0, "Unit": "A"},'
        '"EVSECurrentLimitAchieved": false, "EVSEVoltageLimitAchieved":'
        'false, "EVSEPowerLimitAchieved": false}}}}',
    ),
    ExiMessageContainer(
        message_name="CurrentDemandReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"4FF877E9B597CC1C"},"Body":'
        '{"CurrentDemandReq":{"DC_EVStatus":{"EVReady":true,'
        '"EVCabinConditioning":true,"EVRESSConditioning":true,'
        '"EVErrorCode":"NO_ERROR","EVRESSSOC":20},"EVTargetCurrent":'
        '{"Multiplier":0,"Unit":"A","Value":15},"EVMaximumVoltageLimit":'
        '{"Multiplier":2,"Unit":"V","Value":5},"EVMaximumCurrentLimit":'
        '{"Multiplier":1,"Unit":"A","Value":8},"EVMaximumPowerLimit":'
        '{"Multiplier":3,"Unit":"W","Value":29},"BulkChargingComplete":'
        'false,"ChargingComplete":false,"RemainingTimeToFullSoC":'
        '{"Multiplier":3,"Unit":"s","Value":32767},"RemainingTimeToBulkSoC":'
        '{"Multiplier":3,"Unit":"s","Value":32767},"EVTargetVoltage":'
        '{"Multiplier":1,"Unit":"V","Value":45}}}}}',
    ),
    ExiMessageContainer(
        message_name="CurrentDemandRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "4FF877E9B597CC1C"},'
        '"Body": {"CurrentDemandRes": {"ResponseCode": "OK", "DC_EVSEStatus":'
        '{"NotificationMaxDelay": 0, "EVSENotification": "None",'
        '"EVSEIsolationStatus": "Valid", "EVSEStatusCode": "EVSE_Ready"},'
        '"EVSEPresentVoltage": {"Value": 400, "Multiplier": 0, "Unit": "V"},'
        '"EVSEPresentCurrent": {"Value": 14, "Multiplier": 0, "Unit": "A"},'
        '"EVSECurrentLimitAchieved": false, "EVSEVoltageLimitAchieved":'
        'false, "EVSEPowerLimitAchieved": false}}}}',
    ),
    ExiMessageContainer(
        message_name="WeldingDetectionReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"4FF877E9B597CC1C"},"Body":'
        '{"WeldingDetectionReq":{"DC_EVStatus":{"EVReady":false,'
        '"EVCabinConditioning":false,"EVRESSConditioning":false,'
        '"EVErrorCode":"NO_ERROR","EVRESSSOC":20}}}}}',
    ),
    ExiMessageContainer(
        message_name="WeldingDetectionRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "4FF877E9B597CC1C"},'
        '"Body":{"WeldingDetectionRes":{"ResponseCode":"OK","DC_EVSEStatus":'
        '{"NotificationMaxDelay": 0, "EVSENotification": "StopCharging",'
        '"EVSEIsolationStatus": "Valid", "EVSEStatusCode": "EVSE_Ready"},'
        '"EVSEPresentVoltage": {"Value": 400,"Multiplier": 0,"Unit":"V"}}}}}',
    ),
    ExiMessageContainer(
        message_name="SessionStopReq",
        json_str='{"V2G_Message":{"Header":{"SessionID":"4FF877E9B597CC1C"},'
        '"Body":{"SessionStopReq":{}}}}',
    ),
    ExiMessageContainer(
        message_name="SessionStopRes",
        json_str='{"V2G_Message": {"Header": {"SessionID": "4FF877E9B597CC1C"},'
        '"Body": {"SessionStopRes": {"ResponseCode": "OK"}}}}',
    ),
    ExiMessageContainer(
        message_name="ChargeParameterDiscoveryReq",
        json_str='{"V2G_Message": {"Header": {"SessionID": "C427C77F5FAA1DD5"},'
        ' "Body": {"ChargeParameterDiscoveryReq": '
        '{"EVRequestedEnergyTransferType": "DC_extended", '
        '"DC_EVChargeParameter": {"DC_EVStatus": {"EVReady": false, '
        '"EVErrorCode": "NO_ERROR", "EVRESSSOC": 43}, '
        '"EVMaximumCurrentLimit": {"Multiplier": -1, "Value": 3500}, '
        '"EVMaximumVoltageLimit": {"Multiplier": -1, "Value": 4690}, '
        '"EVEnergyRequest": {"Multiplier": 0, "Value": 500}}}}}}',
        description="EV: VW ID3; Date: 06.09.2022; Element 'Unit' in "
        "PhysicalValuetype in DIN is optional. "
        "In ISO it is mandatory.",
    ),
    ExiMessageContainer(
        message_name="ChargeParameterDiscoveryRes",
        json_str='{"V2G_Message":{"Body":{"ChargeParameterDiscoveryRes":'
        '{"DC_EVSEChargeParameter":{"DC_EVSEStatus":{"EVSEIsolationStatus":'
        '"Invalid","EVSENotification":"None","EVSEStatusCode":"EVSE_Ready",'
        '"NotificationMaxDelay":0},"EVSEMaximumCurrentLimit":{"Multiplier":-1,'
        '"Unit":"A","Value":4000},"EVSEMaximumPowerLimit":{"Multiplier":2,'
        '"Unit":"W","Value":2000},"EVSEMaximumVoltageLimit":{"Multiplier":-1,'
        '"Unit":"V","Value":5000},"EVSEMinimumCurrentLimit":{"Multiplier":-3,'
        '"Unit":"A","Value":0},"EVSEMinimumVoltageLimit":{"Multiplier":-3,'
        '"Unit":"V","Value":0},"EVSEPeakCurrentRipple":{"Multiplier":-3,'
        '"Unit":"A","Value":1000}},"EVSEProcessing":"Finished","ResponseCode":'
        '"OK","SAScheduleList":{"SAScheduleTuple":[{"PMaxSchedule":'
        '{"PMaxScheduleEntry":[{"PMax":32767,"RelativeTimeInterval":'
        '{"duration":86400,"start":0}}],"PMaxScheduleID":0},'
        '"SAScheduleTupleID":0}]}}},"Header":{"SessionID":"000000000000000B"}}}',
        description="SAScheduleTupleID 0: the DIN SPEC 70121 XSD defines "
        "SAIDType as xs:short without a range restriction, unlike "
        "ISO 15118-2 (unsignedByte 1..255).",
    ),
]


class TestDinSpec_MessageCreation:
    # Test data recorded 28.7.2022 with Comemso Multi Mobile DC Protocol Tester
    # are showing exactly how CCS Protocol is implemented in real world.
    # The Numbers for SOC are exceeding the limits defined in standard.
    PVRemainingTimeToFullSOC._max_limit = 32767000
    PVRemainingTimeToBulkSOC._max_limit = 32767000

    @pytest.mark.parametrize(
        "message",
        DIN_TEST_MESSAGES,
        ids=[f"parse_and_create_{msg.message_name}" for msg in DIN_TEST_MESSAGES],
    )
    def test_common_v2g_messages_can_be_parsed_and_created(
        self, message: ExiMessageContainer
    ):
        decoded_dict = json.loads(message.json_str, cls=CustomJSONDecoder)

        dinspec_message = V2GMessageDINSPEC.parse_obj(decoded_dict["V2G_Message"])
        assert isinstance(dinspec_message, V2GMessageDINSPEC)
