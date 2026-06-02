"""
This modules contains classes which implement all the elements of the
ISO 15118-20 XSD file V2G_CI_DC.xsd (see folder 'schemas').
These are the V2GMessages exchanged between the EVCC and the SECC specifically
for DC charging.

All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from pydantic.v1 import Field, root_validator

from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.iso15118_20.common_types import (
    ChargeLoopReq,
    ChargeLoopRes,
    ChargeParameterDiscoveryReq,
    ChargeParameterDiscoveryRes,
    DynamicChargeLoopReqParams,
    DynamicChargeLoopResParams,
    Processing,
    RationalNumber,
    ScheduledChargeLoopReqParams,
    ScheduledChargeLoopResParams,
    V2GRequest,
    V2GResponse,
)
from iso15118.shared.validators import one_field_must_be_set


class DCChargeParameterDiscoveryReqParams(BaseModel):
    """See section 8.3.5.5.1 in ISO 15118-20"""

    ev_max_charge_power: RationalNumber = Field(..., alias="EVMaximumChargePower")
    ev_min_charge_power: RationalNumber = Field(..., alias="EVMinimumChargePower")
    ev_max_charge_current: RationalNumber = Field(..., alias="EVMaximumChargeCurrent")
    ev_min_charge_current: RationalNumber = Field(..., alias="EVMinimumChargeCurrent")
    ev_max_voltage: RationalNumber = Field(..., alias="EVMaximumVoltage")
    ev_min_voltage: RationalNumber = Field(..., alias="EVMinimumVoltage")
    target_soc: int = Field(None, ge=0, le=100, alias="TargetSOC")


class DCChargeParameterDiscoveryResParams(BaseModel):
    """See section 8.3.5.5.2 in ISO 15118-20"""

    evse_max_charge_power: RationalNumber = Field(..., alias="EVSEMaximumChargePower")
    evse_min_charge_power: RationalNumber = Field(..., alias="EVSEMinimumChargePower")
    evse_max_charge_current: RationalNumber = Field(
        ..., alias="EVSEMaximumChargeCurrent"
    )
    evse_min_charge_current: RationalNumber = Field(
        ..., alias="EVSEMinimumChargeCurrent"
    )
    evse_max_voltage: RationalNumber = Field(..., alias="EVSEMaximumVoltage")
    evse_min_voltage: RationalNumber = Field(..., alias="EVSEMinimumVoltage")
    evse_power_ramp_limit: RationalNumber = Field(None, alias="EVSEPowerRampLimitation")


class BPTDCChargeParameterDiscoveryReqParams(DCChargeParameterDiscoveryReqParams):
    """
    See section 8.3.5.5.7.1 in ISO 15118-20
    BPT = Bidirectional Power Transfer
    """

    ev_max_discharge_power: RationalNumber = Field(..., alias="EVMaximumDischargePower")
    ev_min_discharge_power: RationalNumber = Field(..., alias="EVMinimumDischargePower")
    ev_max_discharge_current: RationalNumber = Field(
        ..., alias="EVMaximumDischargeCurrent"
    )
    ev_min_discharge_current: RationalNumber = Field(
        ..., alias="EVMinimumDischargeCurrent"
    )


class BPTDCChargeParameterDiscoveryResParams(DCChargeParameterDiscoveryResParams):
    """
    See section 8.3.5.5.7.2 in ISO 15118-20
    BPT = Bidirectional Power Transfer
    """

    evse_max_discharge_power: RationalNumber = Field(
        ..., alias="EVSEMaximumDischargePower"
    )
    evse_min_discharge_power: RationalNumber = Field(
        ..., alias="EVSEMinimumDischargePower"
    )
    evse_max_discharge_current: RationalNumber = Field(
        ..., alias="EVSEMaximumDischargeCurrent"
    )
    evse_min_discharge_current: RationalNumber = Field(
        ..., alias="EVSEMinimumDischargeCurrent"
    )


class ScheduledDCChargeLoopReqParams(ScheduledChargeLoopReqParams):
    """See section 8.3.5.5.4 in ISO 15118-20"""

    ev_target_current: RationalNumber = Field(..., alias="EVTargetCurrent")
    ev_target_voltage: RationalNumber = Field(..., alias="EVTargetVoltage")
    ev_max_charge_power: RationalNumber = Field(None, alias="EVMaximumChargePower")
    ev_min_charge_power: RationalNumber = Field(None, alias="EVMinimumChargePower")
    ev_max_charge_current: RationalNumber = Field(None, alias="EVMaximumChargeCurrent")
    ev_max_voltage: RationalNumber = Field(None, alias="EVMaximumVoltage")
    ev_min_voltage: RationalNumber = Field(None, alias="EVMinimumVoltage")

    # TODO: Validator for ensuring only one of target current and target voltage
    #  is provided V2G20-2183


class ScheduledDCChargeLoopResParams(ScheduledChargeLoopResParams):
    """See section 8.3.5.5.6 in ISO 15118-20"""

    evse_maximum_charge_power: RationalNumber = Field(
        None, alias="EVSEMaximumChargePower"
    )
    evse_minimum_charge_power: RationalNumber = Field(
        None, alias="EVSEMinimumChargePower"
    )
    evse_maximum_charge_current: RationalNumber = Field(
        None, alias="EVSEMaximumChargeCurrent"
    )
    evse_maximum_voltage: RationalNumber = Field(None, alias="EVSEMaximumVoltage")


class BPTScheduledDCChargeLoopReqParams(ScheduledDCChargeLoopReqParams):
    """See section 8.3.5.5.7.4 in ISO 15118-20"""

    ev_max_discharge_power: RationalNumber = Field(
        None, alias="EVMaximumDischargePower"
    )
    ev_min_discharge_power: RationalNumber = Field(
        None, alias="EVMinimumDischargePower"
    )
    ev_max_discharge_current: RationalNumber = Field(
        None, alias="EVMaximumDischargeCurrent"
    )


class BPTScheduledDCChargeLoopResParams(ScheduledDCChargeLoopResParams):
    """See section 8.3.5.5.7.4 in ISO 15118-20"""

    evse_max_discharge_power: RationalNumber = Field(
        None, alias="EVSEMaximumDischargePower"
    )
    evse_min_discharge_power: RationalNumber = Field(
        None, alias="EVSEMinimumDischargePower"
    )
    evse_max_discharge_current: RationalNumber = Field(
        None, alias="EVSEMaximumDischargeCurrent"
    )
    evse_min_voltage: RationalNumber = Field(None, alias="EVSEMinimumVoltage")


class DynamicDCChargeLoopReqParams(DynamicChargeLoopReqParams):
    """See section 8.3.5.5.3 in ISO 15118-20"""

    ev_max_charge_power: RationalNumber = Field(..., alias="EVMaximumChargePower")
    ev_min_charge_power: RationalNumber = Field(..., alias="EVMinimumChargePower")
    ev_max_charge_current: RationalNumber = Field(..., alias="EVMaximumChargeCurrent")
    ev_max_voltage: RationalNumber = Field(..., alias="EVMaximumVoltage")
    ev_min_voltage: RationalNumber = Field(..., alias="EVMinimumVoltage")


class DynamicDCChargeLoopRes(DynamicChargeLoopResParams):
    """See section 8.3.5.5.5 in ISO 15118-20"""

    evse_maximum_charge_power: RationalNumber = Field(
        ..., alias="EVSEMaximumChargePower"
    )
    evse_minimum_charge_power: RationalNumber = Field(
        ..., alias="EVSEMinimumChargePower"
    )
    evse_maximum_charge_current: RationalNumber = Field(
        ..., alias="EVSEMaximumChargeCurrent"
    )
    evse_maximum_voltage: RationalNumber = Field(..., alias="EVSEMaximumVoltage")


class BPTDynamicDCChargeLoopReqParams(DynamicDCChargeLoopReqParams):
    """See section 8.3.5.5.7.3 in ISO 15118-20"""

    ev_max_discharge_power: RationalNumber = Field(..., alias="EVMaximumDischargePower")
    ev_min_discharge_power: RationalNumber = Field(..., alias="EVMinimumDischargePower")
    ev_max_discharge_current: RationalNumber = Field(
        ..., alias="EVMaximumDischargeCurrent"
    )
    ev_max_v2x_energy_request: RationalNumber = Field(
        None, alias="EVMaximumV2XEnergyRequest"
    )
    ev_min_v2x_energy_request: RationalNumber = Field(
        None, alias="EVMinimumV2XEnergyRequest"
    )


class BPTDynamicDCChargeLoopRes(DynamicDCChargeLoopRes):
    """See section 8.3.5.5.7.5 in ISO 15118-20"""

    evse_max_discharge_power: RationalNumber = Field(
        ..., alias="EVSEMaximumDischargePower"
    )
    evse_min_discharge_power: RationalNumber = Field(
        ..., alias="EVSEMinimumDischargePower"
    )
    evse_max_discharge_current: RationalNumber = Field(
        ..., alias="EVSEMaximumDischargeCurrent"
    )
    evse_min_voltage: RationalNumber = Field(..., alias="EVSEMinimumVoltage")


class DCChargeParameterDiscoveryReq(ChargeParameterDiscoveryReq):
    """See section 8.3.4.5.2.2 in ISO 15118-20"""

    dc_params: DCChargeParameterDiscoveryReqParams = Field(
        None, alias="DC_CPDReqEnergyTransferMode"
    )
    bpt_dc_params: BPTDCChargeParameterDiscoveryReqParams = Field(
        None, alias="BPT_DC_CPDReqEnergyTransferMode"
    )

    @root_validator(pre=True)
    def either_dc_or_dc_bpt_params(cls, values):
        """
        Either dc_params or bpt_dc_params must be set, depending on whether
        unidirectional or bidirectional power transfer was chosen.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "dc_params",
                "DC_CPDReqEnergyTransferMode",
                "bpt_dc_params",
                "BPT_DC_CPDReqEnergyTransferMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "DC_ChargeParameterDiscoveryReq"


class DCChargeParameterDiscoveryRes(ChargeParameterDiscoveryRes):
    """See section 8.3.4.5.2.3 in ISO 15118-20"""

    dc_params: DCChargeParameterDiscoveryResParams = Field(
        None, alias="DC_CPDResEnergyTransferMode"
    )
    bpt_dc_params: BPTDCChargeParameterDiscoveryResParams = Field(
        None, alias="BPT_DC_CPDResEnergyTransferMode"
    )

    @root_validator(pre=True)
    def either_dc_or_bpt_dc_params(cls, values):
        """
        Either dc_params or bpt_dc_params must be set, depending on whether
        unidirectional or bidirectional power transfer was chosen.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "dc_params",
                "DC_CPDResEnergyTransferMode",
                "bpt_dc_params",
                "BPT_DC_CPDResEnergyTransferMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "DC_ChargeParameterDiscoveryRes"


class DCChargeLoopReq(ChargeLoopReq):
    """See section 8.3.4.5.5.2 in ISO 15118-20"""

    ev_present_voltage: RationalNumber = Field(..., alias="EVPresentVoltage")
    scheduled_params: ScheduledDCChargeLoopReqParams = Field(
        None, alias="Scheduled_DC_CLReqControlMode"
    )
    dynamic_params: DynamicDCChargeLoopReqParams = Field(
        None, alias="Dynamic_DC_CLReqControlMode"
    )
    bpt_scheduled_params: BPTScheduledDCChargeLoopReqParams = Field(
        None, alias="BPT_Scheduled_DC_CLReqControlMode"
    )
    bpt_dynamic_params: BPTDynamicDCChargeLoopReqParams = Field(
        None, alias="BPT_Dynamic_DC_CLReqControlMode"
    )

    @root_validator(pre=True)
    def either_scheduled_or_dynamic_bpt(cls, values):
        """
        Either scheduled_params or dynamic_params or bpt_scheduled_params or
        bpt_dynamic_params must be set, depending on whether unidirectional or
        bidirectional power transfer and whether scheduled or dynamic mode was chosen.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "scheduled_params",
                "Scheduled_DC_CLReqControlMode",
                "dynamic_params",
                "Dynamic_DC_CLReqControlMode",
                "bpt_scheduled_params",
                "BPT_Scheduled_DC_CLReqControlMode",
                "bpt_dynamic_params",
                "BPT_Dynamic_DC_CLReqControlMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "DC_ChargeLoopReq"


class DCChargeLoopRes(ChargeLoopRes):
    """See section 8.3.4.5.5.3 in ISO 15118-20"""

    evse_present_current: RationalNumber = Field(..., alias="EVSEPresentCurrent")
    evse_present_voltage: RationalNumber = Field(..., alias="EVSEPresentVoltage")
    evse_power_limit_achieved: bool = Field(..., alias="EVSEPowerLimitAchieved")
    evse_current_limit_achieved: bool = Field(..., alias="EVSECurrentLimitAchieved")
    evse_voltage_limit_achieved: bool = Field(..., alias="EVSEVoltageLimitAchieved")
    scheduled_dc_charge_loop_res: ScheduledDCChargeLoopResParams = Field(
        None, alias="Scheduled_DC_CLResControlMode"
    )
    dynamic_dc_charge_loop_res: DynamicDCChargeLoopRes = Field(
        None, alias="Dynamic_DC_CLResControlMode"
    )
    bpt_scheduled_dc_charge_loop_res: BPTScheduledDCChargeLoopResParams = Field(
        None, alias="BPT_Scheduled_DC_CLResControlMode"
    )
    bpt_dynamic_dc_charge_loop_res: BPTDynamicDCChargeLoopRes = Field(
        None, alias="BPT_Dynamic_DC_CLResControlMode"
    )

    @root_validator(pre=True)
    def either_scheduled_or_dynamic_bpt(cls, values):
        """
        Either scheduled_dc_charge_loop_res or scheduled_dc_charge_loop_res or
        bpt_scheduled_dc_charge_loop_res or bpt_dynamic_dc_charge_loop_res
        must be set, depending on whether unidirectional or bidirectional power
        transfer and whether scheduled or dynamic mode was chosen.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "scheduled_dc_charge_loop_res",
                "Scheduled_DC_CLResControlMode",
                "dynamic_dc_charge_loop_res",
                "Dynamic_DC_CLResControlMode",
                "bpt_scheduled_dc_charge_loop_res",
                "BPT_Scheduled_DC_CLResControlMode",
                "bpt_dynamic_dc_charge_loop_res",
                "BPT_Dynamic_DC_CLResControlMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "DC_ChargeLoopRes"


class DCCableCheckReq(V2GRequest):
    """See section 8.3.4.5.3.2 in ISO 15118-20"""

    def __str__(self):
        # The XSD-conform name
        return "DC_CableCheckReq"


class DCCableCheckRes(V2GResponse):
    """See section 8.3.4.5.3.3 in ISO 15118-20"""

    evse_processing: Processing = Field(..., alias="EVSEProcessing")

    def __str__(self):
        # The XSD-conform name
        return "DC_CableCheckRes"


class DCPreChargeReq(V2GRequest):
    """See section 8.3.4.5.4.1 in ISO 15118-20"""

    ev_processing: Processing = Field(..., alias="EVProcessing")
    ev_present_voltage: RationalNumber = Field(..., alias="EVPresentVoltage")
    ev_target_voltage: RationalNumber = Field(..., alias="EVTargetVoltage")

    def __str__(self):
        # The XSD-conform name
        return "DC_PreChargeReq"


class DCPreChargeRes(V2GResponse):
    """See section 8.3.4.5.4.3 in ISO 15118-20"""

    evse_present_voltage: RationalNumber = Field(..., alias="EVSEPresentVoltage")

    def __str__(self):
        # The XSD-conform name
        return "DC_PreChargeRes"


class DCWeldingDetectionReq(V2GRequest):
    """See section 8.3.4.5.6.2 in ISO 15118-20"""

    ev_processing: Processing = Field(..., alias="EVProcessing")

    def __str__(self):
        # The XSD-conform name
        return "DC_WeldingDetectionReq"


class DCWeldingDetectionRes(V2GResponse):
    """See section 8.3.4.5.6.3 in ISO 15118-20"""

    evse_present_voltage: RationalNumber = Field(..., alias="EVSEPresentVoltage")

    def __str__(self):
        # The XSD-conform name
        return "DC_WeldingDetectionRes"
