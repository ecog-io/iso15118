"""
This modules contains classes which implement all the elements of the
ISO 15118-20 XSD file V2G_CI_CommonTypes.xsd (see folder 'schemas').
These are the data types used by both the header and the body elements of the
V2GMessages exchanged between the EVCC and the SECC.

All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from abc import ABC
from enum import Enum
from typing import List, Optional, Union

from pydantic.v1 import Field, conbytes, conint, constr, validator
from typing_extensions import TypeAlias

from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.datatypes import get_exponent_value_repr
from iso15118.shared.messages.enums import (
    INT_8_MAX,
    INT_8_MIN,
    INT_16_MAX,
    INT_16_MIN,
    UINT_32_MAX,
)
from iso15118.shared.messages.xmldsig import Signature, X509IssuerSerial

# https://pydantic-docs.helpmanual.io/usage/types/#constrained-types
# Check Annex C.1 or V2G_CI_CommonTypes.xsd
# certificateType (a DER encoded X.509 certificate)
Certificate: TypeAlias = conbytes(max_length=1600)  # type: ignore
# identifierType
Identifier: TypeAlias = constr(max_length=255)  # type: ignore
# numericIDType
NumericID: TypeAlias = conint(ge=1, le=UINT_32_MAX)  # type: ignore
# nameType
Name: TypeAlias = constr(max_length=80)  # type: ignore
# descriptionType
Description: TypeAlias = constr(max_length=160)  # type: ignore


class MessageHeader(BaseModel):
    """See section 8.3.3 in ISO 15118-20"""

    # XSD type hexBinary with max 8 bytes encoded as 16 hexadecimal characters
    session_id: str = Field(..., max_length=16, alias="SessionID")
    timestamp: int = Field(..., alias="TimeStamp")
    signature: Signature = Field(None, alias="Signature")

    @validator("session_id")
    def check_sessionid_is_hexbinary(cls, value):
        """
        Checks whether the session_id field is a hexadecimal representation of
        8 bytes.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        try:
            int(value, 16)
            return value
        except ValueError as exc:
            raise ValueError(
                f"Invalid value '{value}' for SessionID (must be "
                f"hexadecimal representation of max 8 bytes)"
            ) from exc


class V2GMessage(BaseModel, ABC):
    """See section 8.3 in ISO 15118-20
    This class model follows the schemas, where the
    V2GMessage type is defined, in the V2G_CI_CommonTypes.xsd schema.
    This type is the base of all messages and contains the Header

    This is a tiny but quite important difference in respect to ISO 15118-2 payload
    structure, where the header is not included within each Request and Response message
    """

    header: MessageHeader = Field(..., alias="Header")

    def __str__(self):
        return self.__class__.__name__


class V2GRequest(V2GMessage, ABC):
    """Base class for all V2GMessages that are request messages
    This class also follows the structure defined in the V2G_CI_CommonTypes.xsd schema
    where the V2GRequestType is an extension of the V2GMessageType
    """


class ResponseCode(str, Enum):
    """See page 465 of Annex A in ISO 15118-20"""

    OK = "OK"
    OK_CERT_EXPIRES_SOON = "OK_CertificateExpiresSoon"
    OK_NEW_SESSION_ESTABLISHED = "OK_NewSessionEstablished"
    OK_OLD_SESSION_JOINED = "OK_OldSessionJoined"
    OK_POWER_TOLERANCE_CONFIRMED = "OK_PowerToleranceConfirmed"
    WARN_AUTH_SELECTION_INVALID = "WARNING_AuthorizationSelectionInvalid"
    WARN_CERT_EXPIRED = "WARNING_CertificateExpired"
    WARN_CERT_NOT_YET_VALID = "WARNING_CertificateNotYetValid"
    WARN_CERT_REVOKED = "WARNING_CertificateRevoked"
    WARN_CERT_VALIDATION_ERROR = "WARNING_CertificateValidationError"
    WARN_CHALLENGE_INVALID = "WARNING_ChallengeInvalid"
    WARN_EIM_AUTH_FAILED = "WARNING_EIMAuthorizationFailure"
    WARN_EMSP_UNKNOWN = "WARNING_eMSPUnknown"
    WARN_EV_POWER_PROFILE_VIOLATION = "WARNING_EVPowerProfileViolation"
    WARN_GENERAL_PNC_AUTH_ERROR = "WARNING_GeneralPnCAuthorizationError"
    WARN_NO_CERT_AVAILABLE = "WARNING_NoCertificateAvailable"
    WARN_NO_CONTRACT_MATCHING_PCID_FOUND = "WARNING_NoContractMatchingPCIDFound"
    WARN_POWER_TOLERANCE_NOT_CONFIRMED = "WARNING_PowerToleranceNotConfirmed"
    WARN_SCHEDULE_RENEGOTIATION_FAILED = "WARNING_ScheduleRenegotiationFailed"
    WARN_STANDBY_NOT_ALLOWED = "WARNING_StandbyNotAllowed"
    WARN_WPT = "WARNING_WPT"
    FAILED = "FAILED"
    FAILED_ASSOCIATION_ERROR = "FAILED_AssociationError"
    FAILED_CONTACTOR_ERROR = "FAILED_ContactorError"
    FAILED_EV_POWER_PROFILE_INVALID = "FAILED_EVPowerProfileInvalid"
    FAILED_EV_POWER_PROFILE_VIOLATION = "FAILED_EVPowerProfileViolation"
    FAILED_METERING_SIGNATURE_NOT_VALID = "FAILED_MeteringSignatureNotValid"
    FAILED_NO_ENERGY_TRANSFER_SERVICE_SELECTED = (
        "FAILED_NoEnergyTransferServiceSelected"
    )
    FAILED_NO_SERVICE_RENEGOTIATION_SUPPORTED = "FAILED_NoServiceRenegotiationSupported"
    FAILED_PAUSE_NOT_ALLOWED = "FAILED_PauseNotAllowed"
    FAILED_POWER_DELIVERY_NOT_APPLIED = "FAILED_PowerDeliveryNotApplied"
    FAILED_POWER_TOLERANCE_NOT_CONFIRMED = "FAILED_PowerToleranceNotConfirmed"
    FAILED_SCHEDULE_RENEGOTIATION = "FAILED_ScheduleRenegotiation"
    FAILED_SCHEDULE_SELECTION_INVALID = "FAILED_ScheduleSelectionInvalid"
    FAILED_SEQUENCE_ERROR = "FAILED_SequenceError"
    FAILED_SERVICE_ID_INVALID = "FAILED_ServiceIDInvalid"
    FAILED_SERVICE_SELECTION_INVALID = "FAILED_ServiceSelectionInvalid"
    FAILED_SIGNATURE_ERROR = "FAILED_SignatureError"
    FAILED_UNKNOWN_SESSION = "FAILED_UnknownSession"
    FAILED_WRONG_CHARGE_PARAMETER = "FAILED_WrongChargeParameter"


class V2GResponse(V2GMessage, ABC):
    """A base class for all V2GMessages that are response messages
    This class also follows the structure defined in the V2G_CI_CommonTypes.xsd schema
    where the V2GResponseType is an extension of the V2GMessageType
    """

    response_code: ResponseCode = Field(..., alias="ResponseCode")


class ChargeParameterDiscoveryReq(V2GRequest, ABC):
    """
    A base class for ACChargeParameterDiscoveryReq,
    DCChargeParameterDiscoveryReq, and WPTChargeParameterDiscoveryReq
    """


class ChargeParameterDiscoveryRes(V2GResponse, ABC):
    """
    A base class for ACChargeParameterDiscoveryRes,
    DCChargeParameterDiscoveryRes, and WPTChargeParameterDiscoveryRes
    """


class RationalNumber(BaseModel):
    """See section 8.3.5.3.8 in ISO 15118-20"""

    # XSD type byte with value range [-128..127]
    exponent: int = Field(..., ge=INT_8_MIN, le=INT_8_MAX, alias="Exponent")
    # XSD type short (16 bit integer) with value range [-32768..32767]
    value: int = Field(..., ge=INT_16_MIN, le=INT_16_MAX, alias="Value")

    def get_decimal_value(self) -> float:
        return self.value * 10**self.exponent

    @classmethod
    def get_rational_repr(cls, float_value: Optional[Union[float, int]]):
        if float_value is None:
            return None
        exponent, value = get_exponent_value_repr(float_value)
        return RationalNumber(exponent=exponent, value=value)


class EVSENotification(str, Enum):
    """See section 8.3.5.3.26 in ISO 15118-20"""

    PAUSE = "Pause"
    EXIT_STANDBY = "ExitStandby"
    TERMINATE = "Terminate"
    METERING_CONFIRMATION = "MeteringConfirmation"
    SCHEDULE_RENEGOTIATION = "ScheduleRenegotiation"
    SERVICE_RENEGOTIATION = "ServiceRenegotiation"


class EVSEStatus(BaseModel):
    """See section 8.3.5.3.26 in ISO 15118-20"""

    notification_max_delay: int = Field(..., alias="NotificationMaxDelay")
    evse_notification: EVSENotification = Field(..., alias="EVSENotification")


class DisplayParameters(BaseModel):
    """See section 8.3.5.3.28 in ISO 15118-20"""

    # XSD type byte with value range [0..100]
    present_soc: int = Field(None, ge=0, le=100, alias="PresentSOC")
    # XSD type byte with value range [0..100]
    min_soc: int = Field(None, ge=0, le=100, alias="MinimumSOC")
    # XSD type byte with value range [0..100]
    target_soc: int = Field(None, ge=0, le=100, alias="TargetSOC")
    # XSD type byte with value range [0..100]
    max_soc: int = Field(None, ge=0, le=100, alias="MaximumSOC")
    remaining_time_to_min_soc: int = Field(None, alias="RemainingTimeToMinimumSOC")
    remaining_time_to_target_soc: int = Field(None, alias="RemainingTimeToTargetSOC")
    remaining_time_to_max_soc: int = Field(None, alias="RemainingTimeToMaximumSOC")
    charging_complete: bool = Field(..., alias="ChargingComplete")
    battery_energy_capacity: RationalNumber = Field(None, alias="BatteryEnergyCapacity")
    inlet_hot: bool = Field(None, alias="InletHot")


class ChargeLoopReq(V2GRequest, ABC):
    """
    A base class for ACChargeLoopReq, DCChargeLoopReq, and WPTChargeLoopReq
    See page 464 in Annex A in ISO 15118-20
    """

    display_parameters: DisplayParameters = Field(None, alias="DisplayParameters")
    meter_info_requested: bool = Field(..., alias="MeterInfoRequested")


class MeterInfo(BaseModel):
    """See section 8.3.5.3.7 in ISO 15118-20"""

    meter_id: str = Field(..., max_length=32, alias="MeterID")
    charged_energy_reading_wh: int = Field(..., alias="ChargedEnergyReadingWh")
    bpt_discharged_energy_reading_wh: int = Field(
        None, alias="BPTDischargedEnergyReadingWh"
    )
    capacitive_energy_reading_varh: int = Field(
        None, alias="CapacitiveEnergyReadingVARh"
    )
    bpt_inductive_energy_reading_varh: int = Field(
        None, alias="BPTInductiveEnergyReadingVARh"
    )
    meter_signature: bytes = Field(None, max_length=64, alias="MeterSignature")
    meter_status: int = Field(None, alias="MeterStatus")
    meter_timestamp: int = Field(None, alias="MeterTimestamp")


class DetailedCost(BaseModel):
    """See section 8.3.5.3.61 in ISO 15118-20"""

    amount: RationalNumber = Field(..., alias="Amount")
    cost_per_unit: RationalNumber = Field(..., alias="CostPerUnit")


class DetailedTax(BaseModel):
    """See section 8.3.5.3.60 in ISO 15118-20"""

    tax_rule_id: int = Field(..., ge=1, le=UINT_32_MAX, alias="TaxRuleID")
    amount: RationalNumber = Field(..., alias="Amount")


class Receipt(BaseModel):
    """See section 8.3.5.3.59 in ISO 15118-20"""

    time_anchor: int = Field(..., alias="TimeAnchor")
    energy_costs: DetailedCost = Field(None, alias="EnergyCosts")
    occupancy_costs: DetailedCost = Field(None, alias="OccupancyCosts")
    additional_services_costs: DetailedCost = Field(
        None, alias="AdditionalServicesCosts"
    )
    overstay_costs: DetailedCost = Field(None, alias="OverstayCosts")
    tax_costs: List[DetailedTax] = Field(
        None, min_items=0, max_items=10, alias="TaxCosts"
    )


class ChargeLoopRes(V2GResponse, ABC):
    """
    A base class for ACChargeLoopRes, DCChargeLoopRes, and WPTChargeLoopRes
    See page 464 in Annex A in ISO 15118-20
    """

    meter_info: MeterInfo = Field(None, alias="MeterInfo")
    receipt: Receipt = Field(None, alias="Receipt")
    evse_status: EVSEStatus = Field(None, alias="EVSEStatus")


class ScheduledChargeLoopReqParams(BaseModel, ABC):
    """
    A base class for ScheduledACChargeLoopReqParams and
    ScheduledDCChargeLoopReqParams
    See page 464 of Annex A in ISO 15118-20
    """

    ev_target_energy_request: RationalNumber = Field(
        None, alias="EVTargetEnergyRequest"
    )
    ev_max_energy_request: RationalNumber = Field(None, alias="EVMaximumEnergyRequest")
    ev_min_energy_request: RationalNumber = Field(None, alias="EVMinimumEnergyRequest")


class ScheduledChargeLoopResParams(BaseModel, ABC):
    """
    A base class for ScheduledACChargeLoopResParams and
    ScheduledDCChargeLoopResParams
    See page 464 of Annex A in ISO 15118-20
    """


class DynamicChargeLoopReqParams(BaseModel, ABC):
    """
    A base class for DynamicACChargeLoopReqParams and
    DynamicDCChargeLoopReqParams
    See page 464 of Annex A in ISO 15118-20
    """

    departure_time: int = Field(None, ge=0, le=UINT_32_MAX, alias="DepartureTime")
    ev_target_energy_request: RationalNumber = Field(..., alias="EVTargetEnergyRequest")
    ev_max_energy_request: RationalNumber = Field(..., alias="EVMaximumEnergyRequest")
    ev_min_energy_request: RationalNumber = Field(..., alias="EVMinimumEnergyRequest")


class DynamicChargeLoopResParams(BaseModel):
    """
    A base class for DynamicACChargeLoopResParams and
    DynamicDCChargeLoopResParams
    See page 465 of Annex A in ISO 15118-20
    """

    departure_time: int = Field(None, ge=0, le=UINT_32_MAX, alias="DepartureTime")
    # XSD type byte with value range [0..100]
    min_soc: int = Field(None, ge=0, le=100, alias="MinimumSOC")
    # XSD type byte with value range [0..100]
    target_soc: int = Field(None, ge=0, le=100, alias="TargetSOC")
    ack_max_delay: int = Field(None, alias="AckMaxDelay")


class Processing(str, Enum):
    """
    See usage in sections 8.3.4.3.3.2 (AuthorizationRes),
    8.3.4.3.7.3 (ScheduleExchangeRes), 8.3.4.3.8.2 (PowerDeliveryReq),
    8.3.4.3.9.3 (CertificateInstallationRes),
    8.3.4.5.3.3 (DCCableCheckRes), 8.3.4.5.4.2 (DCPreChargeReq),
    8.3.4.5.6.2 (DCWeldingDetectionReq),
    8.3.4.6.2.2. (WPTFinePositioningSetupReq),
    8.3.4.6.3.2. (WPTFinePositioningReq), 8.3.4.6.3.3. (WPTFinePositioningRes),
    8.3.4.6.4.2 (WPTPairingReq), 8.3.4.6.4.3 (WPTPairingRes),
    8.3.4.6.6.2 (WPTAlignmentCheckReq), 8.3.4.6.6.3 (WPTAlignmentCheckRes),
    8.3.4.7.5.3 (ACDPVehiclePositioningRes),
    8.3.4.7.6.3 (ACDPVehicleConnectRes), and
    8.3.4.7.7.2 (ACDPVehicleDisconnectRes) in ISO 15118-20
    """

    FINISHED = "Finished"
    ONGOING = "Ongoing"
    WAITING_FOR_CUSTOMER = "Ongoing_WaitingForCustomerInteraction"


class RootCertificateIDList(BaseModel):
    """See section 8.3.5.3.27 in ISO 15118-20"""

    root_cert_ids: List[X509IssuerSerial] = Field(
        ..., max_items=20, alias="RootCertificateID"
    )
