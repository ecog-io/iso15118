"""
This modules contains classes which implement all the elements of the
ISO 15118-20 XSD file V2G_CI_CommonMessages.xsd (see folder 'schemas').
These are the V2GMessages exchanged between the EVCC and the SECC specifically
for AC charging.

All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

from pydantic.v1 import Field, root_validator, validator

from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.enums import (
    INT_8_MAX,
    INT_8_MIN,
    INT_16_MAX,
    INT_16_MIN,
    UINT_8_MAX,
    UINT_16_MAX,
    AuthEnum,
    ServiceV20,
)
from iso15118.shared.messages.iso15118_20.common_types import (
    UINT_32_MAX,
    Certificate,
    Description,
    EVSEStatus,
    Identifier,
    MeterInfo,
    Name,
    NumericID,
    Processing,
    RationalNumber,
    Receipt,
    RootCertificateIDList,
    V2GRequest,
    V2GResponse,
)
from iso15118.shared.validators import one_field_must_be_set


class ECDHCurve(str, Enum):
    """
    See section 8.3.5.3.39 in ISO 15118-20.
    Elliptic curves used for the Elliptic Curve Diffie Hellman (ECDH) key
    agreement protocol."""

    secp_521 = "SECP521"
    x448 = "X448"


class EMAIDList(BaseModel):
    """See Annex C.1 in ISO 15118-20"""

    emaids: List[Identifier] = Field(..., max_items=8, alias="EMAID")


class SubCertificates(BaseModel):
    """A list of DER encoded X.509 certificates"""

    certificates: List[Certificate] = Field(..., max_items=3, alias="Certificate")


class CertificateChain(BaseModel):
    """See section 8.3.5.3.3 in ISO 15118-20"""

    # Note that the type here must be bytes and not Certificate, otherwise we
    # end up with a json structure that does not match the XSD schema
    certificate: bytes = Field(..., max_length=800, alias="Certificate")
    sub_certificates: SubCertificates = Field(None, alias="SubCertificates")


class SignedCertificateChain(BaseModel):
    """See section 8.3.5.3.4 in ISO 15118-20"""

    # 'Id' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    id: str = Field(..., max_length=255, alias="Id")
    # Note that the type here must be bytes and not Certificate, otherwise we
    # end up with a json structure that does not match the XSD schema
    certificate: bytes = Field(..., max_length=800, alias="Certificate")
    sub_certificates: SubCertificates = Field(None, alias="SubCertificates")

    def __str__(self):
        return type(self).__name__


class ContractCertificateChain(BaseModel):
    """See section 8.3.5.3.5 in ISO 15118-20"""

    # Note that the type here must be bytes and not Certificate, otherwise we
    # end up with a json structure that does not match the XSD schema
    certificate: bytes = Field(..., max_length=800, alias="Certificate")
    sub_certificates: SubCertificates = Field(..., alias="SubCertificates")


class SessionSetupReq(V2GRequest):
    """See section 8.3.4.3.1.1 in ISO 15118-20"""

    evcc_id: str = Field(..., max_length=255, alias="EVCCID")


class SessionSetupRes(V2GResponse):
    """See section 8.3.4.3.1.2 in ISO 15118-20"""

    evse_id: str = Field(..., max_length=255, alias="EVSEID")


class AuthorizationSetupReq(V2GRequest):
    """See section 8.3.4.3.2.1 in ISO 15118-20"""


class ProviderID(BaseModel):
    provider_id: Name = Field(..., alias="ProviderID")


class PnCAuthSetupResParams(BaseModel):
    """See section 8.3.4.3.2.1 in ISO 15118-20"""

    gen_challenge: bytes = Field(
        ..., min_length=16, max_length=16, alias="GenChallenge"
    )
    supported_providers: List[ProviderID] = Field(
        None, max_items=128, alias="SupportedProviders"
    )


class EIMAuthSetupResParams(BaseModel):
    """See section 8.3.5.3.33 in ISO 15118-20"""


class AuthorizationSetupRes(V2GResponse):
    """See section 8.3.4.3.2.2 in ISO 15118-20"""

    auth_services: List[AuthEnum] = Field(
        ..., max_items=2, alias="AuthorizationServices"
    )
    cert_install_service: bool = Field(..., alias="CertificateInstallationService")
    pnc_as_res: PnCAuthSetupResParams = Field(None, alias="PnC_ASResAuthorizationMode")
    eim_as_res: EIMAuthSetupResParams = Field(None, alias="EIM_ASResAuthorizationMode")

    @root_validator(pre=True)
    def exactly_one_authorization_mode(cls, values):
        """
        Either pnc_as_res orand eim_as_res must be set, depending on
        whether both Plug & Charge is offered or not. In the latter case, only
        eim_as_res modes is offered.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "pnc_as_res",
                "PnC_ASResAuthorizationMode",
                "eim_as_res",
                "EIM_ASResAuthorizationMode",
            ],
            values,
            True,
        ):
            return values


class PnCAuthReqParams(BaseModel):
    """
    See section 8.3.5.3.32 in ISO 15118-20
    PnCAuthReq = Plug and Charge Authorization Request
    """

    # 'Id' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    id: str = Field(None, max_length=255, alias="Id")
    gen_challenge: bytes = Field(
        ..., min_length=16, max_length=16, alias="GenChallenge"
    )
    contract_cert_chain: ContractCertificateChain = Field(
        ..., alias="ContractCertificateChain"
    )

    def __str__(self):
        # We need to sign this element, which means it will be EXI encoded and we need
        # its XSD-conform name
        return "PnC_AReqAuthorizationMode"


class EIMAuthReqParams(BaseModel):
    """
    See section 8.3.5.3.31 in ISO 15118-20
    EIMAuthReq = External Identification Means Authorization Request
    """


class AuthorizationReq(V2GRequest):
    """See section 8.3.4.3.3.1 in ISO 15118-20"""

    selected_auth_service: AuthEnum = Field(..., alias="SelectedAuthorizationService")
    pnc_params: PnCAuthReqParams = Field(None, alias="PnC_AReqAuthorizationMode")
    eim_params: EIMAuthReqParams = Field(None, alias="EIM_AReqAuthorizationMode")

    @root_validator(pre=True)
    def at_least_one_authorization_mode(cls, values):
        """
        At least one of pnc_params and eim_params must be set, depending on
        whether both Plug & Charge and EIM or just one of these authorization
        modes is offered.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "pnc_params",
                "PnC_AReqAuthorizationMode",
                "eim_params",
                "EIM_AReqAuthorizationMode",
            ],
            values,
            False,
        ):
            return values


class AuthorizationRes(V2GResponse):
    """See section 8.3.4.3.3.2 in ISO 15118-20"""

    evse_processing: Processing = Field(..., alias="EVSEProcessing")


class ServiceIDList(BaseModel):
    """See section 8.3.5.3.29 in ISO 15118-20"""

    service_ids: List[int] = Field(..., max_items=16, alias="ServiceID")


class ServiceDiscoveryReq(V2GRequest):
    """See section 8.3.4.3.4.2 in ISO 15118-20"""

    supported_service_ids: ServiceIDList = Field(None, alias="SupportedServiceIDs")


class Service(BaseModel):
    """See section 8.3.5.3.1 in ISO 15118-20"""

    service_id: int = Field(..., alias="ServiceID")
    free_service: bool = Field(..., alias="FreeService")


class ServiceList(BaseModel):
    """See section 8.3.5.3.2 in ISO 15118-20"""

    services: List[Service] = Field(..., max_items=8, alias="Service")


class ServiceDiscoveryRes(V2GResponse):
    """See section 8.3.4.3.4.3 in ISO 15118-20"""

    service_renegotiation_supported: bool = Field(
        ..., alias="ServiceRenegotiationSupported"
    )
    energy_service_list: ServiceList = Field(..., alias="EnergyTransferServiceList")
    vas_list: ServiceList = Field(None, alias="VASList")


class ServiceDetailReq(V2GRequest):
    """See section 8.3.4.3.5.1 in ISO 15118-20"""

    service_id: int = Field(..., alias="ServiceID")


class Parameter(BaseModel):
    """See section 8.3.5.3.23 in ISO 15118-20"""

    # 'Name' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    name: Name = Field(..., alias="Name")
    bool_value: bool = Field(None, alias="boolValue")
    # XSD type byte with value range [-128..127]
    byte_value: int = Field(None, ge=INT_8_MIN, le=INT_8_MAX, alias="byteValue")
    # XSD type short (16 bit integer) with value range [-32768..32767]
    short_value: int = Field(None, ge=INT_16_MIN, le=INT_16_MAX, alias="shortValue")
    int_value: int = Field(None, alias="intValue")
    rational_number: RationalNumber = Field(None, alias="rationalNumber")
    finite_str: Name = Field(None, alias="finiteString")

    @root_validator(pre=True)
    def at_least_one_parameter_value(cls, values):
        """
        Either bool_value, byte_value, short_value, int_value, rational_number,
        or finite_str must be set, depending on the datatype of the parameter.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "bool_value",
                "boolValue",
                "byte_value",
                "byteValue",
                "short_value",
                "shortValue",
                "int_value",
                "intValue",
                "rational_number",
                "rationalNumber",
                "finite_str",
                "finiteString",
            ],
            values,
            True,
        ):
            return values


class ParameterSet(BaseModel):
    """See section 8.3.5.3.22 in ISO 15118-20"""

    id: int = Field(..., alias="ParameterSetID")
    parameters: List[Parameter] = Field(..., max_items=32, alias="Parameter")


class ServiceParameterList(BaseModel):
    """See section 8.3.5.3.21 in ISO 15118-20"""

    parameter_sets: List[ParameterSet] = Field(..., max_items=32, alias="ParameterSet")


class ServiceDetailRes(V2GResponse):
    """See section 8.3.4.3.5.2 in ISO 15118-20"""

    service_id: int = Field(..., alias="ServiceID")
    service_parameter_list: ServiceParameterList = Field(
        ..., alias="ServiceParameterList"
    )


class SelectedService(BaseModel):
    """See section 8.3.5.3.25 in ISO 15118-20"""

    service_id: int = Field(..., alias="ServiceID")
    parameter_set_id: int = Field(..., alias="ParameterSetID")


class SelectedServiceList(BaseModel):
    """See section 8.3.5.3.24 in ISO 15118-20"""

    selected_services: List[SelectedService] = Field(
        ..., max_items=16, alias="SelectedService"
    )


class ServiceSelectionReq(V2GRequest):
    """See section 8.3.4.3.6.2 in ISO 15118-20"""

    selected_energy_service: SelectedService = Field(
        ..., alias="SelectedEnergyTransferService"
    )
    selected_vas_list: SelectedServiceList = Field(None, alias="SelectedVASList")


class ServiceSelectionRes(V2GResponse):
    """See section 8.3.4.3.6.3 in ISO 15118-20"""


class EVPowerScheduleEntry(BaseModel):
    """See section 8.3.5.3.44 in ISO 15118-20"""

    duration: int = Field(..., alias="Duration")
    power: RationalNumber = Field(..., alias="Power")


class EVPowerScheduleEntryList(BaseModel):
    """See section 8.3.5.3.43 in ISO 15118-20"""

    entries: List[EVPowerScheduleEntry] = Field(
        ..., max_items=1024, alias="EVPowerScheduleEntry"
    )


class EVPowerSchedule(BaseModel):
    """See section 8.3.5.3.42 in ISO 15118-20"""

    time_anchor: int = Field(..., alias="TimeAnchor")
    ev_power_schedule_entries: EVPowerScheduleEntryList = Field(
        ..., alias="EVPowerScheduleEntries"
    )


class EVPriceRule(BaseModel):
    """See section 8.3.5.3.48 in ISO 15118-20"""

    energy_fee: RationalNumber = Field(..., alias="EnergyFee")
    power_range_start: RationalNumber = Field(..., alias="PowerRangeStart")


class EVPriceRuleStack(BaseModel):
    """See section 8.3.5.3.47 in ISO 15118-20"""

    duration: int = Field(..., alias="Duration")
    ev_price_rules: List[EVPriceRule] = Field(..., max_items=8, alias="EVPriceRule")


class EVPriceRuleStackList(BaseModel):
    """See section 8.3.5.3.46 in ISO 15118-20"""

    ev_price_rule_stacks: List[EVPriceRuleStack] = Field(
        ..., max_items=1024, alias="EVPriceRuleStack"
    )


class EVAbsolutePriceSchedule(BaseModel):
    """See section 8.3.5.3.45 in ISO 15118-20"""

    time_anchor: int = Field(..., alias="TimeAnchor")
    currency: str = Field(..., max_length=3, alias="Currency")
    price_algorithm: str = Field(..., max_length=255, alias="PriceAlgorithm")
    ev_price_rule_stacks: EVPriceRuleStackList = Field(..., alias="EVPriceRuleStacks")


class EVEnergyOffer(BaseModel):
    """See section 8.3.5.3.41 in ISO 15118-20"""

    ev_power_schedule: EVPowerSchedule = Field(..., alias="EVPowerSchedule")
    ev_absolute_price_schedule: EVAbsolutePriceSchedule = Field(
        ..., alias="EVAbsolutePriceSchedule"
    )


class ScheduledScheduleExchangeReqParams(BaseModel):
    """See section 8.3.5.3.14 in ISO 15118-20"""

    departure_time: int = Field(None, ge=0, le=UINT_32_MAX, alias="DepartureTime")
    ev_target_energy_request: RationalNumber = Field(
        None, alias="EVTargetEnergyRequest"
    )
    ev_max_energy_request: RationalNumber = Field(None, alias="EVMaximumEnergyRequest")
    ev_min_energy_request: RationalNumber = Field(None, alias="EVMinimumEnergyRequest")
    ev_energy_offer: EVEnergyOffer = Field(None, alias="EVEnergyOffer")


class DynamicScheduleExchangeReqParams(BaseModel):
    """See section 8.3.5.3.13 in ISO 15118-20"""

    departure_time: int = Field(..., ge=0, le=UINT_32_MAX, alias="DepartureTime")
    # XSD type byte with value range [0..100]
    min_soc: int = Field(None, ge=0, le=100, alias="MinimumSOC")
    # XSD type byte with value range [0..100]
    target_soc: int = Field(None, ge=0, le=100, alias="TargetSOC")
    ev_target_energy_request: RationalNumber = Field(..., alias="EVTargetEnergyRequest")
    ev_max_energy_request: RationalNumber = Field(..., alias="EVMaximumEnergyRequest")
    ev_min_energy_request: RationalNumber = Field(..., alias="EVMinimumEnergyRequest")
    ev_max_v2x_energy_request: RationalNumber = Field(
        None, alias="EVMaximumV2XEnergyRequest"
    )
    ev_min_v2x_energy_request: RationalNumber = Field(
        None, alias="EVMinimumV2XEnergyRequest"
    )

    @root_validator(pre=True)
    def both_v2x_fields_must_be_set(cls, values):
        max_v2x, min_v2x = (
            values.get("ev_max_v2x_energy_request"),
            values.get("ev_min_v2x_energy_request"),
        )

        if max_v2x is None and min_v2x is None:
            # When decoding from EXI to JSON dict
            max_v2x, min_v2x = (
                values.get("EVMaximumV2XEnergyRequest"),
                values.get("EVMinimumV2XEnergyRequest"),
            )

        if (max_v2x and not min_v2x) or (min_v2x and not max_v2x):
            raise ValueError(
                "EVMaximumV2XEnergyRequest and EVMinimumV2XEnergyRequest of type "
                "Dynamic_SEReqControlModeType must either be both set or both omitted. "
                "Only one of them was set ([V2G20-2681])"
            )

        return values


class ScheduleExchangeReq(V2GRequest):
    """See section 8.3.4.3.7.2 in ISO 15118-20"""

    max_supporting_points: int = Field(
        ..., ge=12, le=1024, alias="MaximumSupportingPoints"
    )
    scheduled_params: ScheduledScheduleExchangeReqParams = Field(
        None, alias="Scheduled_SEReqControlMode"
    )
    dynamic_params: DynamicScheduleExchangeReqParams = Field(
        None, alias="Dynamic_SEReqControlMode"
    )

    @root_validator(pre=True)
    def either_scheduled_or_dynamic(cls, values):
        """
        Either scheduled_params or dynamic_params must be set, depending on
        whether the charging process is governed by charging schedules or
        dynamic charging settings from the SECC.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "scheduled_params",
                "Scheduled_SEReqControlMode",
                "dynamic_params",
                "Dynamic_SEReqControlMode",
            ],
            values,
            True,
        ):
            return values


class PowerScheduleEntry(BaseModel):
    """See section 8.3.5.3.20 in ISO 15118-20"""

    duration: int = Field(..., alias="Duration")
    power: RationalNumber = Field(..., alias="Power")
    power_l2: RationalNumber = Field(None, alias="Power_L2")
    power_l3: RationalNumber = Field(None, alias="Power_L3")


class PowerScheduleEntryList(BaseModel):
    """See section 8.3.5.3.19 in ISO 15118-20"""

    entries: List[PowerScheduleEntry] = Field(
        ..., max_items=1024, alias="PowerScheduleEntry"
    )


class PowerSchedule(BaseModel):
    """See section 8.3.5.3.18 in ISO 15118-20"""

    time_anchor: int = Field(..., alias="TimeAnchor")
    available_energy: RationalNumber = Field(None, alias="AvailableEnergy")
    power_tolerance: RationalNumber = Field(None, alias="PowerTolerance")
    schedule_entry_list: PowerScheduleEntryList = Field(
        ..., alias="PowerScheduleEntries"
    )


class PriceSchedule(BaseModel):
    """See sections 8.3.5.3.49 and 8.3.5.3.62 in ISO 15118-20"""

    time_anchor: int = Field(..., alias="TimeAnchor")
    schedule_id: NumericID = Field(..., alias="PriceScheduleID")
    schedule_description: Description = Field(None, alias="PriceScheduleDescription")


class PriceLevelScheduleEntry(BaseModel):
    """See section 8.3.5.3.64 in ISO 15118-20"""

    duration: int = Field(..., ge=0, le=UINT_32_MAX, alias="Duration")
    # XSD type unsignedByte with value range [0..255]
    price_level: int = Field(..., ge=0, le=UINT_8_MAX, alias="PriceLevel")


class PriceLevelScheduleEntryList(BaseModel):
    """See section 8.3.5.3.63 in ISO 15118-20"""

    entries: List[PriceLevelScheduleEntry] = Field(
        ..., max_items=1024, alias="PriceLevelScheduleEntry"
    )


class PriceLevelSchedule(PriceSchedule):
    """See section 8.3.5.3.62 in ISO 15118-20"""

    # 'Id' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    id: str = Field(None, max_length=255, alias="Id")
    # XSD type unsignedByte with value range [0..255]
    num_price_levels: int = Field(..., ge=0, le=UINT_8_MAX, alias="NumberOfPriceLevels")
    schedule_entries: PriceLevelScheduleEntryList = Field(
        ..., alias="PriceLevelScheduleEntries"
    )


class TaxRule(BaseModel):
    """See section 8.3.5.3.51 in ISO 15118-20"""

    tax_rule_id: NumericID = Field(..., alias="TaxRuleID")
    tax_rule_name: Name = Field(None, alias="TaxRuleName")
    tax_rate: RationalNumber = Field(..., alias="TaxRate")
    tax_included_in_price: bool = Field(None, alias="TaxIncludedInPrice")
    applies_to_energy_fee: bool = Field(..., alias="AppliesToEnergyFee")
    applies_to_parking_fee: bool = Field(..., alias="AppliesToParkingFee")
    applies_to_overstay_fee: bool = Field(..., alias="AppliesToOverstayFee")
    applies_to_min_max_cost: bool = Field(..., alias="AppliesMinimumMaximumCost")


class TaxRuleList(BaseModel):
    """See section 8.3.5.3.50 in ISO 15118-20"""

    tax_rule: List[TaxRule] = Field(..., max_items=10, alias="TaxRule")


class PriceRule(BaseModel):
    """See section 8.3.5.3.54 in ISO 15118-20"""

    energy_fee: RationalNumber = Field(..., alias="EnergyFee")
    parking_fee: RationalNumber = Field(None, alias="ParkingFee")
    parking_fee_period: int = Field(None, le=UINT_32_MAX, alias="ParkingFeePeriod")
    carbon_dioxide_emission: int = Field(
        None, le=UINT_16_MAX, alias="CarbonDioxideEmission"
    )
    # XSD type unsignedByte with value range [0..255]
    renewable_energy_percentage: int = Field(
        None, ge=0, le=255, alias="RenewableGenerationPercentage"
    )
    power_range_start: RationalNumber = Field(..., alias="PowerRangeStart")


class PriceRuleStack(BaseModel):
    """See section 8.3.5.3.53 in ISO 15118-20"""

    duration: int = Field(..., ge=0, le=UINT_32_MAX, alias="Duration")
    price_rules: List[PriceRule] = Field(..., max_items=8, alias="PriceRule")


class PriceRuleStackList(BaseModel):
    """See section 8.3.5.3.52 in ISO 15118-20"""

    price_rule_stacks: List[PriceRuleStack] = Field(
        ..., max_items=1024, alias="PriceRuleStack"
    )


class OverstayRule(BaseModel):
    """See section 8.3.5.3.56 in ISO 15118-20"""

    description: Description = Field(None, alias="OverstayRuleDescription")
    start_time: int = Field(..., ge=0, le=UINT_32_MAX, alias="StartTime")
    fee: RationalNumber = Field(..., alias="OverstayFee")
    fee_period: int = Field(..., ge=0, le=UINT_32_MAX, alias="OverstayFeePeriod")


class OverstayRuleList(BaseModel):
    """See section 8.3.5.3.55 in ISO 15118-20"""

    time_threshold: int = Field(
        None, ge=0, le=UINT_32_MAX, alias="OverstayTimeThreshold"
    )
    power_threshold: RationalNumber = Field(None, alias="OverstayPowerThreshold")
    rules: List[OverstayRule] = Field(..., max_items=5, alias="OverstayRule")


class AdditionalService(BaseModel):
    """See section 8.3.5.3.58 in ISO 15118-20"""

    service_name: Name = Field(..., alias="ServiceName")
    service_fee: RationalNumber = Field(..., alias="ServiceFee")


class AdditionalServiceList(BaseModel):
    """See section 8.3.5.3.57 in ISO 15118-20"""

    additional_services: List[AdditionalService] = Field(
        ..., max_items=5, alias="AdditionalService"
    )


class AbsolutePriceSchedule(PriceSchedule):
    """See section 8.3.5.3.45 in ISO 15118-20"""

    # 'Id' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    id: str = Field(None, alias="Id")
    currency: str = Field(..., max_length=3, alias="Currency")
    language: str = Field(..., max_length=3, alias="Language")
    price_algorithm: str = Field(..., max_length=255, alias="PriceAlgorithm")
    min_cost: RationalNumber = Field(None, alias="MinimumCost")
    max_cost: RationalNumber = Field(None, alias="MaximumCost")
    tax_rules: TaxRuleList = Field(None, alias="TaxRules")
    price_rule_stacks: PriceRuleStackList = Field(..., alias="PriceRuleStacks")
    overstay_rules: OverstayRuleList = Field(None, alias="OverstayRules")
    additional_services: AdditionalServiceList = Field(
        None, alias="AdditionalSelectedServices"
    )


class ChargingSchedule(BaseModel):
    """See section 8.3.5.3.40 in ISO 15118-20"""

    power_schedule: PowerSchedule = Field(..., alias="PowerSchedule")
    price_level_schedule: PriceLevelSchedule = Field(None, alias="PriceLevelSchedule")
    absolute_price_schedule: AbsolutePriceSchedule = Field(
        None, alias="AbsolutePriceSchedule"
    )

    @root_validator(pre=True)
    def either_price_levels_or_absolute_prices(cls, values):
        """
        Either price_level_schedule or absolute_price_schedule must be set,
        depending on whether abstract price levels or absolute prices are used
        to indicate costs for the charging session.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "price_level_schedule",
                "PriceLevelSchedule",
                "absolute_price_schedule",
                "AbsolutePriceSchedule",
            ],
            values,
            True,
        ):
            return values


class DischargingSchedule(BaseModel):
    """See section 8.3.5.3.40 in ISO 15118-20"""

    power_schedule: PowerSchedule = Field(..., alias="PowerSchedule")
    price_level_schedule: PriceLevelSchedule = Field(None, alias="PriceLevelSchedule")
    absolute_price_schedule: AbsolutePriceSchedule = Field(
        None, alias="AbsolutePriceSchedule"
    )

    # TODO Need to add a root validator to check if power schedule entries are negative
    #      for discharging (also heck other discharging fields in other types)

    @root_validator(pre=True)
    def either_price_levels_or_absolute_prices(cls, values):
        """
        Either price_level_schedule or absolute_price_schedule must be set,
        depending on abstract price levels or absolute prices are used to
        indicate costs for the charging session.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "price_level_schedule",
                "PriceLevelSchedule",
                "absolute_price_schedule",
                "AbsolutePriceSchedule",
            ],
            values,
            True,
        ):
            return values


class ScheduleTuple(BaseModel):
    """See section 8.3.5.3.17 in ISO 15118-20"""

    schedule_tuple_id: NumericID = Field(..., alias="ScheduleTupleID")
    charging_schedule: ChargingSchedule = Field(..., alias="ChargingSchedule")
    discharging_schedule: DischargingSchedule = Field(None, alias="DischargingSchedule")


class ScheduledScheduleExchangeResParams(BaseModel):
    """See section 8.3.5.3.16 in ISO 15118-20"""

    schedule_tuples: List[ScheduleTuple] = Field(
        ..., max_items=3, alias="ScheduleTuple"
    )


class DynamicScheduleExchangeResParams(BaseModel):
    """See section 8.3.5.3.15 in ISO 15118-20"""

    departure_time: int = Field(None, ge=0, le=UINT_32_MAX, alias="DepartureTime")
    # XSD type byte with value range [0..100]
    min_soc: int = Field(None, ge=0, le=100, alias="MinimumSOC")
    # XSD type byte with value range [0..100]
    target_soc: int = Field(None, ge=0, le=100, alias="TargetSOC")
    price_level_schedule: PriceLevelSchedule = Field(None, alias="PriceLevelSchedule")
    absolute_price_schedule: AbsolutePriceSchedule = Field(
        None, alias="AbsolutePriceSchedule"
    )

    @root_validator(pre=True)
    def min_soc_less_than_or_equal_to_target_soc(cls, values):
        """
        The min_soc value must be smaller or equal to target_soc ([V2G20-1640]).

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        # TODO Also check other classes that contain min_soc and target_soc
        min_soc, target_soc = values.get("min_soc"), values.get("target_soc")
        if min_soc is None and target_soc is None:
            # When decoding from EXI to JSON dict
            min_soc, target_soc = values.get("MinimumSOC"), values.get("TargetSOC")

        if (min_soc and target_soc) and min_soc > target_soc:
            raise ValueError(
                "MinimumSOC must be less than or equal to TargetSOC.\n"
                f"MinimumSOC: {min_soc}, TargetSOC: {target_soc}"
            )

        return values


class ScheduleExchangeRes(V2GResponse):
    """See section 8.3.4.3.7.3 in ISO 15118-20"""

    evse_processing: Processing = Field(..., alias="EVSEProcessing")
    scheduled_params: ScheduledScheduleExchangeResParams = Field(
        None, alias="Scheduled_SEResControlMode"
    )
    dynamic_params: DynamicScheduleExchangeResParams = Field(
        None, alias="Dynamic_SEResControlMode"
    )
    go_to_pause: bool = Field(None, alias="GoToPause")

    @root_validator(pre=True)
    def either_scheduled_or_dynamic(cls, values):
        """
        Either scheduled_params or dynamic_params must be set, depending on
        whether the charging process is governed by charging schedules or
        dynamic charging settings from the SECC.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        evse_processing = values.get("evse_processing")
        if evse_processing is None:
            # When decoding from EXI to JSON dict
            evse_processing = values.get("EVSEProcessing")
        if evse_processing == Processing.ONGOING:
            return values

        # Check if either the dynamic or scheduled parameters are set, but only in case
        # evse_processing is set to FINISHED
        if one_field_must_be_set(
            [
                "scheduled_params",
                "Scheduled_SEResControlMode",
                "dynamic_params",
                "Dynamic_SEResControlMode",
            ],
            values,
            True,
        ):
            return values


class EVPowerProfileEntryList(BaseModel):
    """See section 8.3.5.3.10 in ISO 15118-20"""

    entries: List[PowerScheduleEntry] = Field(
        ..., max_items=2048, alias="EVPowerProfileEntry"
    )


class PowerToleranceAcceptance(str, Enum):
    """See section 8.3.5.3.12 in ISO 15118-20"""

    NOT_CONFIRMED = "PowerToleranceNotConfirmed"
    CONFIRMED = "PowerToleranceConfirmed"


class ScheduledEVPowerProfile(BaseModel):
    """See section 8.3.5.3.12 in ISO 15118-20"""

    selected_schedule_tuple_id: NumericID = Field(..., alias="SelectedScheduleTupleID")
    power_tolerance_acceptance: PowerToleranceAcceptance = Field(
        ..., alias="PowerToleranceAcceptance"
    )


class DynamicEVPowerProfile(BaseModel):
    """See section 8.3.5.3.11 in ISO 15118-20"""


class EVPowerProfile(BaseModel):
    """See section 8.3.5.3.9 in ISO 15118-20"""

    time_anchor: int = Field(..., alias="TimeAnchor")
    entry_list: EVPowerProfileEntryList = Field(..., alias="EVPowerProfileEntries")
    scheduled_profile: ScheduledEVPowerProfile = Field(
        None, alias="Scheduled_EVPPTControlMode"
    )
    dynamic_profile: DynamicEVPowerProfile = Field(
        None, alias="Dynamic_EVPPTControlMode"
    )

    @root_validator(pre=True)
    def either_scheduled_or_dynamic(cls, values):
        """
        Either scheduled_profile or dynamic_profile must be set, depending on whether
        the charging process is governed by charging schedules or dynamic charging
        settings from the SECC.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "scheduled_profile",
                "Scheduled_EVPPTControlMode",
                "dynamic_profile",
                "Dynamic_EVPPTControlMode",
            ],
            values,
            True,
        ):
            return values


class ChannelSelection(str, Enum):
    """See section 8.3.4.3.8.2 in ISO 15118-20"""

    CHARGE = "Charge"
    DISCHARGE = "Discharge"


class ChargeProgress(str, Enum):
    """See section 8.3.4.3.8.2 in ISO 15118-20"""

    START = "Start"
    STOP = "Stop"
    STANDBY = "Standby"
    SCHEDULE_RENEGOTIATION = "ScheduleRenegotiation"


class PowerDeliveryReq(V2GRequest):
    """See section 8.3.4.3.8.2 in ISO 15118-20"""

    ev_processing: Processing = Field(..., alias="EVProcessing")
    charge_progress: ChargeProgress = Field(..., alias="ChargeProgress")
    ev_power_profile: EVPowerProfile = Field(None, alias="EVPowerProfile")
    bpt_channel_selection: ChannelSelection = Field(None, alias="BPT_ChannelSelection")

    @root_validator(pre=True)
    def set_ev_power_profile_if_processing_finished_and_start_charging(cls, values):
        """
        The optional ev_power_profile field must be set once the EVCC finishes
        processing, thereby setting the field ev_processing to FINISHED, and if the
        charge_progress is set to START.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use

        ev_processing = values.get("ev_processing")
        charge_progress = values.get("charge_progress")
        if ev_processing is None:
            # When decoding from EXI to JSON dict
            ev_processing = values.get("EVProcessing")
        if charge_progress is None:
            # When decoding from EXI to JSON dict
            charge_progress = values.get("ChargeProgress")
        if (
            ev_processing == Processing.ONGOING
            or charge_progress == ChargeProgress.STOP
        ):
            return values

        ev_power_profile = values.get("ev_power_profile")
        if ev_power_profile is None:
            # When decoding from EXI to JSON dict
            ev_power_profile = values.get("EVPowerProfile")

        if ev_power_profile is None:
            raise ValueError(
                "EVPowerProfile is not set although EVProcessing is set to FINISHED"
            )

        return values


class PowerDeliveryRes(V2GResponse):
    """See section 8.3.4.3.8.3 in ISO 15118-20"""

    evse_status: EVSEStatus = Field(None, alias="EVSEStatus")


class ScheduledSignedMeterData(BaseModel):
    """See section 8.3.5.3.38 in ISO 15118-20"""

    selected_schedule_tuple_id: NumericID = Field(..., alias="SelectedScheduleTupleID")


class DynamicSignedMeterData(BaseModel):
    """See section 8.3.5.3.37 in ISO 15118-20"""


class SignedMeteringData(BaseModel):
    """See section 8.3.5.3.36 in ISO 15118-20"""

    # 'Id' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    id: str = Field(..., max_length=255, alias="Id")
    session_id: str = Field(..., max_length=16, alias="SessionID")
    meter_info: MeterInfo = Field(..., alias="MeterInfo")
    receipt: Receipt = Field(None, alias="Receipt")
    scheduled_smart_meter_data: ScheduledSignedMeterData = Field(
        None, alias="Scheduled_SMDTControlMode"
    )
    dynamic_smart_meter_data: DynamicSignedMeterData = Field(
        None, alias="Dynamic_SMDTControlMode"
    )

    @root_validator(pre=True)
    def either_scheduled_or_dynamic(cls, values):
        """
        Either scheduled_smart_meter_data or dynamic_smart_meter_data must be
        set, depending on whether the charging process is governed by charging s
        chedules or dynamic charging settings from the SECC.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "scheduled_smart_meter_data",
                "Scheduled_SMDTControlMode",
                "dynamic_smart_meter_data",
                "Dynamic_SMDTControlMode",
            ],
            values,
            True,
        ):
            return values

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


class MeteringConfirmationReq(V2GRequest):
    """See section 8.3.4.3.11.2 in ISO 15118-20"""

    signed_metering_data: SignedMeteringData = Field(..., alias="SignedMeteringData")


class MeteringConfirmationRes(V2GResponse):
    """See section 8.3.4.3.11.3 in ISO 15118-20"""


class ChargingSession(str, Enum):
    """See section 8.3.4.3.10.2 in ISO 15118-20"""

    PAUSE = "Pause"
    TERMINATE = "Terminate"
    SERVICE_RENEGOTIATION = "ServiceRenegotiation"


class SessionStopReq(V2GRequest):
    """See section 8.3.4.3.10.2 in ISO 15118-20"""

    charging_session: ChargingSession = Field(..., alias="ChargingSession")
    ev_termination_code: Name = Field(None, alias="EVTerminationCode")
    ev_termination_explanation: str = Field(
        None, max_length=160, alias="EVTerminationExplanation"
    )


class SessionStopRes(V2GResponse):
    """See section 8.3.4.3.10.3 in ISO 15118-20"""


class CertificateInstallationReq(V2GRequest):
    """See section 8.3.4.3.9.2 in ISO 15118-20"""

    oem_prov_cert_chain: SignedCertificateChain = Field(
        ..., alias="OEMProvisioningCertificateChain"
    )
    root_cert_id_list: RootCertificateIDList = Field(
        ..., alias="ListOfRootCertificateIDs"
    )
    # XSD type unsignedShort (16 bit integer) with value range [0..65535]
    max_contract_cert_chains: int = Field(
        ..., ge=0, le=UINT_16_MAX, alias="MaximumContractCertificateChains"
    )
    prioritized_emaids: EMAIDList = Field(None, alias="PrioritizedEMAIDs")


class SignedInstallationData(BaseModel):
    """See section 8.3.5.3.39 in ISO 15118-20"""

    # 'Id' is actually an XML attribute, but JSON (our serialisation method)
    # doesn't have attributes. The EXI codec has to en-/decode accordingly.
    id: str = Field(..., max_length=255, alias="Id")
    contract_cert_chain: ContractCertificateChain = Field(
        ..., alias="ContractCertificateChain"
    )
    ecdh_curve: ECDHCurve = Field(..., alias="ECDHCurve")
    dh_public_key: bytes = Field(..., max_length=133, alias="DHPublicKey")
    secp521_encrypted_private_key: bytes = Field(
        None, min_length=94, max_length=94, alias="SECP521_EncryptedPrivateKey"
    )
    x448_encrypted_private_key: bytes = Field(
        None, min_length=84, max_length=84, alias="X448_EncryptedPrivateKey"
    )
    tpm_encrypted_private_key: bytes = Field(
        None, min_length=209, max_length=209, alias="TPM_EncryptedPrivateKey"
    )

    @root_validator(pre=True)
    def one_encryption_mode(cls, values):
        """
        Either secp521_encrypted_private_key or x448_encrypted_private_key or
        tpm_encrypted_private_key must be set, depending on which encryption
        algorithm is used to encrypt the private key associated with the
        contract certificate.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "secp521_encrypted_private_key",
                "SECP521_EncryptedPrivateKey",
                "x448_encrypted_private_key",
                "X448_EncryptedPrivateKey",
                "tpm_encrypted_private_key",
                "TPM_EncryptedPrivateKey",
            ],
            values,
            True,
        ):
            return values


class CertificateInstallationRes(V2GResponse):
    """See section 8.3.4.3.9.3 in ISO 15118-20"""

    evse_processing: Processing = Field(..., alias="EVSEProcessing")
    cps_certificate_chain: CertificateChain = Field(..., alias="CPSCertificateChain")
    signed_installation_data: SignedInstallationData = Field(
        ..., alias="SignedInstallationData"
    )
    # XSD type unsignedByte with value range [0..255]
    remaining_contract_cert_chains: int = Field(
        ..., ge=0, le=255, alias="RemainingContractCertificateChains"
    )


class EVCheckInStatus(str, Enum):
    """See section 8.3.4.8.1.1.2 in ISO 15118-20"""

    check_in = "CheckIn"
    processing = "Processing"
    completed = "Completed"


class EVCheckOutStatus(str, Enum):
    """See section 8.3.4.8.1.2.2 in ISO 15118-20"""

    check_out = "CheckOut"
    processing = "Processing"
    completed = "Completed"


class EVSECheckOutStatus(str, Enum):
    """See section 8.3.4.8.1.2.3 in ISO 15118-20"""

    scheduled = "Scheduled"
    completed = "Completed"


class ParkingMethod(str, Enum):
    """See section 8.3.4.8.1.1.2 in ISO 15118-20"""

    auto_parking = "AutoParking"
    mv_guided_manual = "MVGuideManual"
    manual = "Manual"


class TargetPosition(BaseModel):
    """Defined in XSD schema but not used in any message"""

    target_offset_x: int = Field(..., alias="TargetOffsetX")
    target_offset_y: int = Field(..., alias="TargetOffsetY")


class VehicleCheckInReq(V2GRequest):
    """See section 8.3.4.8.1.1.2 in ISO 15118-20"""

    ev_check_in_status: EVCheckInStatus = Field(..., alias="EVCheckInStatus")
    parking_method: ParkingMethod = Field(None, alias="ParkingMethod")


class VehicleCheckInRes(V2GResponse):
    """See section 8.3.4.8.1.1.3 in ISO 15118-20"""

    vehicle_space: int = Field(..., alias="VehicleSpace")
    target_offset: TargetPosition = Field(None, alias="TargetOffset")


class VehicleCheckOutReq(V2GRequest):
    """See section 8.3.4.8.1.2.2 in ISO 15118-20"""

    ev_check_out_status: EVCheckOutStatus = Field(..., alias="EVCheckOutStatus")
    check_out_time: int = Field(..., alias="CheckOutTime")


class VehicleCheckOutRes(V2GResponse):
    """See section 8.3.4.8.1.3.2 in ISO 15118-20"""

    evse_check_out_status: EVSECheckOutStatus = Field(..., alias="EVSECheckOutStatus")


# ============================================================================
# |            HELPFUL CUSTOM CLASSES FOR A COMMUNICATION SESSION            |
# ============================================================================


@dataclass
class MatchedService:
    """
    This class puts all service-related information into one place. ISO 15118-20
    messages and data types scatter information about service ID, typeo of service
    (energy or value-added service) parameter sets, and whether a service is free.
    This custom class provides easier access to all this information, which comes in
    handy throughout the various states.
    """

    service: ServiceV20
    # If it's not an energy transfer service, then it's a value-added service (VAS)
    is_energy_service: bool
    is_free: bool
    parameter_sets: List[ParameterSet]

    def service_parameter_set_ids(self) -> List[Tuple[int, int]]:
        service_param_set_ids: List[Tuple[int, int]] = []
        for parameter_set in self.parameter_sets:
            service_param_set_ids.append((self.service.id, parameter_set.id))
        return service_param_set_ids


@dataclass
class SelectedEnergyService:
    """
    This class puts all necessary information about the energy service, which the EVCC
    selects for a charging session, in one place. A SelectedService instance (datatype
    used in ISO 15118-20) only contains a ServiceID and a ParameterSetID, but not the
    actual parameter sets, for which we'd have to look elsewhere and loop through a
    list of offered parameter sets. The parameter sets describe important service
    details, which we need throughout the state machine.
    """

    service: ServiceV20
    is_free: bool
    parameter_set: ParameterSet

    @property
    def service_id(self) -> int:
        return self.service.id

    @property
    def parameter_set_id(self) -> int:
        return self.parameter_set.id


@dataclass
class SelectedVAS:
    """
    Similar to the custom class SelectedEnergyService, but for the value-added services
    (VAS), which the EVCC selects for a charging session.
    """

    service: ServiceV20
    is_free: bool
    parameter_set: ParameterSet
