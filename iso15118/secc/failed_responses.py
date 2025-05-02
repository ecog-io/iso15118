from iso15118.shared.messages.datatypes import (
    DCEVSEChargeParameter,
    DCEVSEStatus,
    DCEVSEStatusCode,
    EVSENotification,
    PVEVSECurrentRegulationTolerance,
    PVEVSEEnergyToBeDelivered,
    PVEVSEMaxCurrent,
    PVEVSEMaxCurrentLimit,
    PVEVSEMaxPowerLimit,
    PVEVSEMaxVoltageLimit,
    PVEVSEMinCurrentLimit,
    PVEVSEMinVoltageLimit,
    PVEVSENominalVoltage,
    PVEVSEPeakCurrentRipple,
    PVEVSEPresentCurrent,
    PVEVSEPresentVoltage,
)
from iso15118.shared.messages.din_spec.body import CableCheckReq as CableCheckReqDINSPEC
from iso15118.shared.messages.din_spec.body import CableCheckRes as CableCheckResDINSPEC
from iso15118.shared.messages.din_spec.body import (
    ChargeParameterDiscoveryReq as ChargeParameterDiscoveryReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    ChargeParameterDiscoveryRes as ChargeParameterDiscoveryResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    ContractAuthenticationReq as ContractAuthenticationReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    ContractAuthenticationRes as ContractAuthenticationResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    CurrentDemandReq as CurrentDemandReqDINPEC,
)
from iso15118.shared.messages.din_spec.body import (
    CurrentDemandRes as CurrentDemandResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    PowerDeliveryReq as PowerDeliveryReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    PowerDeliveryRes as PowerDeliveryResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import PreChargeReq as PreChargeReqDINSPEC
from iso15118.shared.messages.din_spec.body import PreChargeRes as PreChargeResDINSPEC
from iso15118.shared.messages.din_spec.body import (
    ServiceDiscoveryReq as ServiceDiscoveryReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    ServiceDiscoveryRes as ServiceDiscoveryResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    ServicePaymentSelectionReq as ServicePaymentSelectionReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    ServicePaymentSelectionRes as ServicePaymentSelectionResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    SessionSetupReq as SessionSetupReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    SessionSetupRes as SessionSetupResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    SessionStopReq as SessionStopReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    SessionStopRes as SessionStopResDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    WeldingDetectionReq as WeldingDetectionReqDINSPEC,
)
from iso15118.shared.messages.din_spec.body import (
    WeldingDetectionRes as WeldingDetectionResDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    AuthOptionList as AuthOptionListDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    ChargeService as ChargeServiceDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    DCEVSEStatusCode as DCEVSEStatusCodeDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    EVSENotification as EVSENotificationDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    ResponseCode as ResponseCodeDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    ServiceCategory as ServiceCategoryDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import (
    ServiceDetails as ServiceDetailsDINSPEC,
)
from iso15118.shared.messages.din_spec.datatypes import ServiceID as ServiceIDDINSPEC
from iso15118.shared.messages.enums import (
    AuthEnum,
    EnergyTransferModeEnum,
    EVSEProcessing,
    IsolationLevel,
    ISOV20PayloadTypes,
    Namespace,
    UnitSymbol,
)
from iso15118.shared.messages.iso15118_2.body import (
    EMAID,
)
from iso15118.shared.messages.iso15118_2.body import (
    AuthorizationReq as AuthorizationReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    AuthorizationRes as AuthorizationResV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    CableCheckReq,
    CableCheckRes,
)
from iso15118.shared.messages.iso15118_2.body import (
    CertificateInstallationReq as CertificateInstallationReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    CertificateInstallationRes as CertificateInstallationResV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    CertificateUpdateReq,
    CertificateUpdateRes,
    ChargeParameterDiscoveryReq,
    ChargeParameterDiscoveryRes,
    ChargingStatusReq,
    ChargingStatusRes,
    CurrentDemandReq,
    CurrentDemandRes,
    MeteringReceiptReq,
    MeteringReceiptRes,
    PaymentDetailsReq,
    PaymentDetailsRes,
    PaymentServiceSelectionReq,
    PaymentServiceSelectionRes,
)
from iso15118.shared.messages.iso15118_2.body import (
    PowerDeliveryReq as PowerDeliveryReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    PowerDeliveryRes as PowerDeliveryResV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    PreChargeReq,
    PreChargeRes,
)
from iso15118.shared.messages.iso15118_2.body import ResponseCode as ResponseCodeV2
from iso15118.shared.messages.iso15118_2.body import (
    ServiceDetailReq as ServiceDetailReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    ServiceDetailRes as ServiceDetailResV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    ServiceDiscoveryReq as ServiceDiscoveryReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    ServiceDiscoveryRes as ServiceDiscoveryResV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    SessionSetupReq as SessionSetupReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    SessionSetupRes as SessionSetupResV2,
)
from iso15118.shared.messages.iso15118_2.body import SessionStopReq as SessionStopReqV2
from iso15118.shared.messages.iso15118_2.body import SessionStopRes as SessionStopResV2
from iso15118.shared.messages.iso15118_2.body import (
    WeldingDetectionReq as WeldingDetectionReqV2,
)
from iso15118.shared.messages.iso15118_2.body import (
    WeldingDetectionRes as WeldingDetectionResV2,
)
from iso15118.shared.messages.iso15118_2.datatypes import (
    ACEVSEChargeParameter,
    ACEVSEStatus,
    AuthOptionList,
)
from iso15118.shared.messages.iso15118_2.datatypes import (
    CertificateChain as CertificateChainV2,
)
from iso15118.shared.messages.iso15118_2.datatypes import (
    ChargeService,
    DHPublicKey,
    EncryptedPrivateKey,
    EnergyTransferModeList,
    ServiceCategory,
    ServiceID,
)
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeLoopReq,
    ACChargeLoopRes,
    ACChargeParameterDiscoveryReq,
    ACChargeParameterDiscoveryRes,
    ACChargeParameterDiscoveryResParams,
    ScheduledACChargeLoopResParams,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationReq as AuthorizationReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationRes as AuthorizationResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationSetupReq,
    AuthorizationSetupRes,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    CertificateChain as CertificateChainV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    CertificateInstallationReq as CertificateInstallationReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    CertificateInstallationRes as CertificateInstallationResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    DynamicScheduleExchangeResParams,
    ECDHCurve,
    EIMAuthSetupResParams,
    MeteringConfirmationReq,
    MeteringConfirmationRes,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    PowerDeliveryReq as PowerDeliveryReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    PowerDeliveryRes as PowerDeliveryResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    PriceLevelSchedule,
    PriceLevelScheduleEntryList,
    ScheduleExchangeReq,
    ScheduleExchangeRes,
    Service,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ServiceDetailReq as ServiceDetailReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ServiceDetailRes as ServiceDetailResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ServiceDiscoveryReq as ServiceDiscoveryReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ServiceDiscoveryRes as ServiceDiscoveryResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    ServiceList,
    ServiceParameterList,
    ServiceSelectionReq,
    ServiceSelectionRes,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    SessionSetupReq as SessionSetupReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    SessionSetupRes as SessionSetupResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    SessionStopReq as SessionStopReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    SessionStopRes as SessionStopResV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    SignedInstallationData,
    SubCertificates,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    MessageHeader as MessageHeaderV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    Processing,
    RationalNumber,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    ResponseCode as ResponseCodeV20,
)
from iso15118.shared.messages.iso15118_20.dc import (
    DCCableCheckReq,
    DCCableCheckRes,
    DCChargeLoopReq,
    DCChargeLoopRes,
    DCChargeParameterDiscoveryReq,
    DCChargeParameterDiscoveryRes,
    DCChargeParameterDiscoveryResParams,
    DCPreChargeReq,
    DCPreChargeRes,
    DCWeldingDetectionReq,
    DCWeldingDetectionRes,
    ScheduledDCChargeLoopResParams,
)


def init_failed_responses_din_spec_70121() -> dict:
    """
    Initiates a dictionary containing the XSD compliant failed responses with
    minimal payload (e.g. only mandatory fields set, bytes objects only 1 byte
    big) for DIN SPEC 70121 messages.

    Note: When sending the actual response, you must override the preset
          response code with the failure response code that is most fitting.
    """
    failed_response_iso_dinspec = {
        SessionSetupReqDINSPEC: SessionSetupResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED, evse_id="1234567"
        ),
        ServiceDiscoveryReqDINSPEC: ServiceDiscoveryResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            auth_option_list=AuthOptionListDINSPEC(auth_options=[AuthEnum.EIM_V2]),
            charge_service=ChargeServiceDINSPEC(
                service_tag=ServiceDetailsDINSPEC(
                    service_id=ServiceIDDINSPEC.CHARGING,
                    service_category=ServiceCategoryDINSPEC.CHARGING,
                ),
                free_service=False,
                energy_transfer_type=EnergyTransferModeEnum.DC_EXTENDED,
            ),
        ),
        ServicePaymentSelectionReqDINSPEC: ServicePaymentSelectionResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED
        ),
        ContractAuthenticationReqDINSPEC: ContractAuthenticationResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            evse_processing=EVSEProcessing.FINISHED,
        ),
        ChargeParameterDiscoveryReqDINSPEC: ChargeParameterDiscoveryResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            evse_processing=EVSEProcessing.FINISHED,
            dc_charge_parameter=DCEVSEChargeParameter(
                dc_evse_status=DCEVSEStatus(
                    notification_max_delay=1000,
                    evse_notification=EVSENotificationDINSPEC.STOP_CHARGING,
                    evse_isolation_status=IsolationLevel.INVALID,
                    evse_status_code=DCEVSEStatusCodeDINSPEC.EVSE_NOT_READY,
                ),
                evse_maximum_power_limit=PVEVSEMaxPowerLimit(
                    multiplier=0, value=0, unit=UnitSymbol.WATT
                ),
                evse_maximum_current_limit=PVEVSEMaxCurrentLimit(
                    multiplier=0, value=0, unit=UnitSymbol.AMPERE
                ),
                evse_maximum_voltage_limit=PVEVSEMaxVoltageLimit(
                    multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
                ),
                evse_minimum_current_limit=PVEVSEMinCurrentLimit(
                    multiplier=0, value=0, unit=UnitSymbol.AMPERE
                ),
                evse_minimum_voltage_limit=PVEVSEMinVoltageLimit(
                    multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
                ),
                evse_current_regulation_tolerance=PVEVSECurrentRegulationTolerance(
                    multiplier=0, value=0, unit=UnitSymbol.AMPERE
                ),
                evse_peak_current_ripple=PVEVSEPeakCurrentRipple(
                    multiplier=0, value=0, unit=UnitSymbol.AMPERE
                ),
                evse_energy_to_be_delivered=PVEVSEEnergyToBeDelivered(
                    multiplier=0, value=0, unit=UnitSymbol.WATT_HOURS
                ),
            ),
        ),
        CableCheckReqDINSPEC: CableCheckResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            dc_evse_status=DCEVSEStatus(
                notification_max_delay=1000,
                evse_notification=EVSENotificationDINSPEC.STOP_CHARGING,
                evse_isolation_status=IsolationLevel.INVALID,
                evse_status_code=DCEVSEStatusCodeDINSPEC.EVSE_NOT_READY,
            ),
            evse_processing=EVSEProcessing.FINISHED,
        ),
        PreChargeReqDINSPEC: PreChargeResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            dc_evse_status=DCEVSEStatus(
                notification_max_delay=1000,
                evse_notification=EVSENotificationDINSPEC.STOP_CHARGING,
                evse_isolation_status=IsolationLevel.INVALID,
                evse_status_code=DCEVSEStatusCodeDINSPEC.EVSE_NOT_READY,
            ),
            evse_present_voltage=PVEVSEPresentVoltage(
                multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
            ),
        ),
        PowerDeliveryReqDINSPEC: PowerDeliveryResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            dc_evse_status=DCEVSEStatus(
                notification_max_delay=1000,
                evse_notification=EVSENotificationDINSPEC.STOP_CHARGING,
                evse_isolation_status=IsolationLevel.INVALID,
                evse_status_code=DCEVSEStatusCodeDINSPEC.EVSE_NOT_READY,
            ),
        ),
        CurrentDemandReqDINPEC: CurrentDemandResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            dc_evse_status=DCEVSEStatus(
                notification_max_delay=1000,
                evse_notification=EVSENotificationDINSPEC.STOP_CHARGING,
                evse_isolation_status=IsolationLevel.INVALID,
                evse_status_code=DCEVSEStatusCodeDINSPEC.EVSE_NOT_READY,
            ),
            evse_present_voltage=PVEVSEPresentVoltage(
                multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
            ),
            evse_present_current=PVEVSEPresentCurrent(
                multiplier=0, value=0, unit=UnitSymbol.AMPERE
            ),
            evse_current_limit_achieved=False,
            evse_voltage_limit_achieved=False,
            evse_power_limit_achieved=False,
            evse_max_voltage_limit=PVEVSEMaxVoltageLimit(
                multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
            ),
            evse_max_current_limit=PVEVSEMaxCurrentLimit(
                multiplier=0, value=0, unit=UnitSymbol.AMPERE
            ),
            evse_max_power_limit=PVEVSEMaxPowerLimit(
                multiplier=0, value=0, unit=UnitSymbol.WATT
            ),
        ),
        WeldingDetectionReqDINSPEC: WeldingDetectionResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED,
            dc_evse_status=DCEVSEStatus(
                notification_max_delay=1000,
                evse_notification=EVSENotificationDINSPEC.STOP_CHARGING,
                evse_isolation_status=IsolationLevel.INVALID,
                evse_status_code=DCEVSEStatusCodeDINSPEC.EVSE_NOT_READY,
            ),
            evse_present_voltage=PVEVSEPresentVoltage(
                multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
            ),
        ),
        SessionStopReqDINSPEC: SessionStopResDINSPEC(
            response_code=ResponseCodeDINSPEC.FAILED
        ),
    }
    return failed_response_iso_dinspec


def init_failed_responses_iso_v2() -> dict:
    """
    Initiates a dictionary containing the XSD compliant failed responses with
    minimal payload (e.g. only mandatory fields set, bytes objects only 1 byte
    big) for ISO 15118-2 messages, as required by ISO 15118 in case of sending
    a response with a response code starting with "FAILED".

    Note: When sending the actual response, you must override the preset
          response code with the failure response code that is most fitting.
    """
    failed_response_iso_v2 = {
        SessionSetupReqV2: SessionSetupResV2(
            response_code=ResponseCodeV2.FAILED, evse_id="1234567"
        ),
        ServiceDiscoveryReqV2: ServiceDiscoveryResV2(
            response_code=ResponseCodeV2.FAILED,
            auth_option_list=AuthOptionList(auth_options=[AuthEnum.EIM_V2]),
            charge_service=ChargeService(
                service_id=ServiceID.CHARGING,
                service_category=ServiceCategory.CHARGING,
                free_service=False,
                supported_energy_transfer_mode=EnergyTransferModeList(
                    energy_modes=[EnergyTransferModeEnum.DC_CORE]
                ),
            ),
        ),
        ServiceDetailReqV2: ServiceDetailResV2(
            response_code=ResponseCodeV2.FAILED, service_id=0
        ),
        PaymentServiceSelectionReq: PaymentServiceSelectionRes(
            response_code=ResponseCodeV2.FAILED
        ),
        CertificateInstallationReqV2: CertificateInstallationResV2(
            response_code=ResponseCodeV2.FAILED,
            cps_cert_chain=CertificateChainV2(certificate=bytes(1)),
            contract_cert_chain=CertificateChainV2(certificate=bytes(1)),
            encrypted_private_key=EncryptedPrivateKey(id="1", value=bytes(1)),
            dh_public_key=DHPublicKey(id="1", value=bytes(1)),
            emaid=EMAID(id="1", value="123456789ABCDE"),
        ),
        CertificateUpdateReq: CertificateUpdateRes(
            response_code=ResponseCodeV2.FAILED,
            cps_cert_chain=CertificateChainV2(certificate=bytes(1)),
            contract_cert_chain=CertificateChainV2(certificate=bytes(1)),
            encrypted_private_key=EncryptedPrivateKey(id="", value=bytes(1)),
            dh_public_key=DHPublicKey(id="1", value=bytes(1)),
            emaid=EMAID(id="1", value="123456789ABCDE"),
        ),
        PaymentDetailsReq: PaymentDetailsRes(
            response_code=ResponseCodeV2.FAILED,
            gen_challenge=bytes(16),
            evse_timestamp=0,
        ),
        AuthorizationReqV2: AuthorizationResV2(
            response_code=ResponseCodeV2.FAILED, evse_processing=EVSEProcessing.FINISHED
        ),
        ChargeParameterDiscoveryReq: ChargeParameterDiscoveryRes(
            response_code=ResponseCodeV2.FAILED,
            evse_processing=EVSEProcessing.FINISHED,
            ac_charge_parameter=ACEVSEChargeParameter(
                ac_evse_status=ACEVSEStatus(
                    notification_max_delay=0,
                    evse_notification=EVSENotification.NONE,
                    rcd=False,
                ),
                evse_nominal_voltage=PVEVSENominalVoltage(
                    multiplier=0, value=0, unit=UnitSymbol.VOLTAGE
                ),
                evse_max_current=PVEVSEMaxCurrent(
                    multiplier=0, value=0, unit=UnitSymbol.AMPERE
                ),
            ),
        ),
        PowerDeliveryReqV2: PowerDeliveryResV2(
            response_code=ResponseCodeV2.FAILED,
            ac_evse_status=ACEVSEStatus(
                notification_max_delay=0,
                evse_notification=EVSENotification.NONE,
                rcd=False,
            ),
        ),
        ChargingStatusReq: ChargingStatusRes(
            response_code=ResponseCodeV2.FAILED,
            evse_id="1234567",
            sa_schedule_tuple_id=1,
            ac_evse_status=ACEVSEStatus(
                notification_max_delay=0,
                evse_notification=EVSENotification.NONE,
                rcd=False,
            ),
        ),
        CableCheckReq: CableCheckRes(
            response_code=ResponseCodeV2.FAILED,
            dc_evse_status=DCEVSEStatus(
                evse_notification=EVSENotification.NONE,
                notification_max_delay=0,
                evse_isolation_status=IsolationLevel.VALID,
                evse_status_code=DCEVSEStatusCode.EVSE_READY,
            ),
            evse_processing=EVSEProcessing.FINISHED,
        ),
        PreChargeReq: PreChargeRes(
            response_code=ResponseCodeV2.FAILED,
            dc_evse_status=DCEVSEStatus(
                evse_notification=EVSENotification.NONE,
                notification_max_delay=0,
                evse_isolation_status=IsolationLevel.VALID,
                evse_status_code=DCEVSEStatusCode.EVSE_READY,
            ),
            evse_present_voltage=PVEVSEPresentVoltage(
                multiplier=0, value=230, unit="V"
            ),
        ),
        CurrentDemandReq: CurrentDemandRes(
            response_code=ResponseCodeV2.FAILED,
            dc_evse_status=DCEVSEStatus(
                evse_notification=EVSENotification.NONE,
                notification_max_delay=0,
                evse_isolation_status=IsolationLevel.VALID,
                evse_status_code=DCEVSEStatusCode.EVSE_READY,
            ),
            evse_present_voltage=PVEVSEPresentVoltage(
                multiplier=0, value=230, unit="V"
            ),
            evse_present_current=PVEVSEPresentCurrent(multiplier=0, value=10, unit="A"),
            evse_current_limit_achieved=False,
            evse_voltage_limit_achieved=False,
            evse_power_limit_achieved=False,
            evse_id="1234567",
            sa_schedule_tuple_id=1,
        ),
        MeteringReceiptReq:
        # TODO: Need to find a way to circumvent the root_validator
        MeteringReceiptRes(response_code=ResponseCodeV2.FAILED),
        WeldingDetectionReqV2: WeldingDetectionResV2(
            response_code=ResponseCodeV2.FAILED,
            dc_evse_status=DCEVSEStatus(
                evse_notification=EVSENotification.NONE,
                notification_max_delay=0,
                evse_isolation_status=IsolationLevel.VALID,
                evse_status_code=DCEVSEStatusCode.EVSE_READY,
            ),
            evse_present_voltage=PVEVSEPresentVoltage(
                multiplier=0, value=230, unit="V"
            ),
        ),
        SessionStopReqV2: SessionStopResV2(response_code=ResponseCodeV2.FAILED),
    }

    return failed_response_iso_v2


def init_failed_responses_iso_v20() -> dict:
    """
    Initiates a dictionary containing the XSD compliant failed responses with
    minimal payload (e.g. only mandatory fields set, bytes objects only 1 byte
    big) for ISO 15118-20 messages, as required by ISO 15118 in case of sending
    a response with a response code starting with "FAILED".

    When sending the actual response, you must override the preset response
    code with the failure response code that is most fitting.
    """
    header = MessageHeaderV20(session_id=bytes(1).hex().upper(), timestamp=1)

    failed_response_iso_v20 = {
        SessionSetupReqV20: (
            SessionSetupResV20(
                header=header, response_code=ResponseCodeV20.FAILED, evse_id=""
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        AuthorizationReqV20: (
            AuthorizationResV20(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_processing=Processing.FINISHED,
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        AuthorizationSetupReq: (
            AuthorizationSetupRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                auth_services=[AuthEnum.EIM],
                cert_install_service=False,
                eim_as_res=EIMAuthSetupResParams(),
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        CertificateInstallationReqV20: (
            CertificateInstallationResV20(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_processing=Processing.FINISHED,
                cps_certificate_chain=CertificateChainV20(certificate=bytes(1)),
                signed_installation_data=SignedInstallationData(
                    contract_cert_chain=CertificateChainV20(
                        certificate=bytes(1),
                        sub_certificates=SubCertificates(certificates=[bytes(1)]),
                    ),
                    ecdh_curve=ECDHCurve.x448,
                    dh_public_key=bytes(1),
                    x448_encrypted_private_key=bytes(84),
                    id="1",
                ),
                remaining_contract_cert_chains=0,
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        ServiceDiscoveryReqV20: (
            ServiceDiscoveryResV20(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                service_renegotiation_supported=False,
                energy_service_list=ServiceList(
                    services=[Service(service_id=0, free_service=False)],
                ),
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        ServiceDetailReqV20: (
            ServiceDetailResV20(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                service_id=0,
                service_parameter_list=ServiceParameterList(parameter_sets=[]),
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        ServiceSelectionReq: (
            ServiceSelectionRes(header=header, response_code=ResponseCodeV20.FAILED),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        ACChargeParameterDiscoveryReq: (
            ACChargeParameterDiscoveryRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                ac_params=ACChargeParameterDiscoveryResParams(
                    evse_max_charge_power=RationalNumber(exponent=0, value=0),
                    evse_min_charge_power=RationalNumber(exponent=0, value=0),
                    evse_nominal_frequency=RationalNumber(exponent=0, value=0),
                ),
            ),
            Namespace.ISO_V20_AC,
            ISOV20PayloadTypes.AC_MAINSTREAM,
        ),
        DCChargeParameterDiscoveryReq: (
            DCChargeParameterDiscoveryRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                dc_params=DCChargeParameterDiscoveryResParams(
                    evse_max_charge_power=RationalNumber(exponent=0, value=0),
                    evse_min_charge_power=RationalNumber(exponent=0, value=0),
                    evse_max_charge_current=RationalNumber(exponent=0, value=0),
                    evse_min_charge_current=RationalNumber(exponent=0, value=0),
                    evse_max_voltage=RationalNumber(exponent=0, value=0),
                    evse_min_voltage=RationalNumber(exponent=0, value=0),
                ),
            ),
            Namespace.ISO_V20_DC,
            ISOV20PayloadTypes.DC_MAINSTREAM,
        ),
        # TODO Need to add DC messages for ISO 15118-20
        #     None,
        # WPTChargeParameterDiscoveryReq:
        # TODO Need to add WPT messages for ISO 15118-20
        #     None,
        # WPTFinePositioningSetupReq:
        # TODO Need to add WPT messages for ISO 15118-20
        #     None,
        # WPTFinePositioningReq:
        # TODO Need to add WPT messages for ISO 15118-20
        #     None,
        # WPTPairingReq:
        # TODO Need to add WPT messages for ISO 15118-20
        #     None,
        # WPTAlignmentCheckReq:
        # TODO Need to add WPT messages for ISO 15118-20
        #     None,
        # ACDPVehiclePositioningReq:
        # TODO Need to add ACDP messages for ISO 15118-20
        #     None,
        # ACDPConnectReq:
        # TODO Need to add ACDP messages for ISO 15118-20
        #     None,
        # ACDPDisconnectReq:
        # TODO Need to add ACDP messages for ISO 15118-20
        #     None,
        ScheduleExchangeReq: (
            ScheduleExchangeRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_processing=Processing.ONGOING,
                dynamic_params=DynamicScheduleExchangeResParams(
                    price_level_schedule=PriceLevelSchedule(
                        time_anchor=0,
                        schedule_id=1,
                        num_price_levels=0,
                        schedule_entries=PriceLevelScheduleEntryList(entries=[]),
                    )
                ),
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        PowerDeliveryReqV20: (
            PowerDeliveryResV20(header=header, response_code=ResponseCodeV20.FAILED),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        ACChargeLoopReq: (
            ACChargeLoopRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                scheduled_params=ScheduledACChargeLoopResParams(),
            ),
            Namespace.ISO_V20_AC,
            ISOV20PayloadTypes.AC_MAINSTREAM,
        ),
        DCChargeLoopReq: (
            DCChargeLoopRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_present_current=RationalNumber(exponent=0, value=0),
                evse_present_voltage=RationalNumber(exponent=0, value=0),
                evse_power_limit_achieved=True,
                evse_current_limit_achieved=True,
                evse_voltage_limit_achieved=True,
                scheduled_dc_charge_loop_res=ScheduledDCChargeLoopResParams(
                    evse_maximum_charge_power=RationalNumber(exponent=0, value=0)
                ),
            ),
            Namespace.ISO_V20_DC,
            ISOV20PayloadTypes.DC_MAINSTREAM,
        ),
        # WPTChargeLoopReq:
        # TODO Need to add WPT messages for ISO 15118-20
        #     None,
        MeteringConfirmationReq: (
            MeteringConfirmationRes(
                header=header, response_code=ResponseCodeV20.FAILED
            ),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
        DCPreChargeReq: (
            DCPreChargeRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_present_voltage=RationalNumber(exponent=0, value=0),
            ),
            Namespace.ISO_V20_DC,
            ISOV20PayloadTypes.DC_MAINSTREAM,
        ),
        DCCableCheckReq: (
            DCCableCheckRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_processing=Processing.FINISHED,
            ),
            Namespace.ISO_V20_DC,
            ISOV20PayloadTypes.DC_MAINSTREAM,
        ),
        DCWeldingDetectionReq: (
            DCWeldingDetectionRes(
                header=header,
                response_code=ResponseCodeV20.FAILED,
                evse_present_voltage=RationalNumber(exponent=0, value=0),
            ),
            Namespace.ISO_V20_DC,
            ISOV20PayloadTypes.DC_MAINSTREAM,
        ),
        # VehicleCheckInReq:
        # TODO Need to add messages for ISO 15118-20
        #     None,
        # VehicleCheckOutReq:
        # TODO Need to add messages for ISO 15118-20
        #     None,
        SessionStopReqV20: (
            SessionStopResV20(header=header, response_code=ResponseCodeV20.FAILED),
            Namespace.ISO_V20_COMMON_MSG,
            ISOV20PayloadTypes.MAINSTREAM,
        ),
    }

    return failed_response_iso_v20
