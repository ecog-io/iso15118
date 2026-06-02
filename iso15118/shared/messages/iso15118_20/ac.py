"""
This modules contains classes which implement all the elements of the
ISO 15118-20 XSD file V2G_CI_AC.xsd (see folder 'schemas').
These are the V2GMessages exchanged between the EVCC and the SECC specifically
for AC charging.

All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from pydantic.v1 import Field, root_validator

from iso15118.shared.exceptions import V2GMessageValidationError
from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.iso15118_20.common_types import (
    ChargeLoopReq,
    ChargeLoopRes,
    ChargeParameterDiscoveryReq,
    ChargeParameterDiscoveryRes,
    DynamicChargeLoopReqParams,
    DynamicChargeLoopResParams,
    RationalNumber,
    ResponseCode,
    ScheduledChargeLoopReqParams,
    ScheduledChargeLoopResParams,
)
from iso15118.shared.validators import one_field_must_be_set


class ACChargeParameterDiscoveryReqParams(BaseModel):
    """See section 8.3.5.4.1 in ISO 15118-20"""

    ev_max_charge_power: RationalNumber = Field(..., alias="EVMaximumChargePower")
    ev_max_charge_power_l2: RationalNumber = Field(
        None, alias="EVMaximumChargePower_L2"
    )
    ev_max_charge_power_l3: RationalNumber = Field(
        None, alias="EVMaximumChargePower_L3"
    )
    ev_min_charge_power: RationalNumber = Field(..., alias="EVMinimumChargePower")
    ev_min_charge_power_l2: RationalNumber = Field(
        None, alias="EVMinimumChargePower_L2"
    )
    ev_min_charge_power_l3: RationalNumber = Field(
        None, alias="EVMinimumChargePower_L3"
    )


class ACChargeParameterDiscoveryResParams(BaseModel):
    """See section 8.3.5.4.2 in ISO 15118-20"""

    evse_max_charge_power: RationalNumber = Field(..., alias="EVSEMaximumChargePower")
    evse_max_charge_power_l2: RationalNumber = Field(
        None, alias="EVSEMaximumChargePower_L2"
    )
    evse_max_charge_power_l3: RationalNumber = Field(
        None, alias="EVSEMaximumChargePower_L3"
    )
    evse_min_charge_power: RationalNumber = Field(..., alias="EVSEMinimumChargePower")
    evse_min_charge_power_l2: RationalNumber = Field(
        None, alias="EVSEMinimumChargePower_L2"
    )
    evse_min_charge_power_l3: RationalNumber = Field(
        None, alias="EVSEMinimumChargePower_L3"
    )
    evse_nominal_frequency: RationalNumber = Field(..., alias="EVSENominalFrequency")
    max_power_asymmetry: RationalNumber = Field(None, alias="MaximumPowerAsymmetry")
    evse_power_ramp_limit: RationalNumber = Field(None, alias="EVSEPowerRampLimitation")
    evse_present_active_power: RationalNumber = Field(
        None, alias="EVSEPresentActivePower"
    )
    evse_present_active_power_l2: RationalNumber = Field(
        None, alias="EVSEPresentActivePower_L2"
    )
    evse_present_active_power_l3: RationalNumber = Field(
        None, alias="EVSEPresentActivePower_L3"
    )


class BPTACChargeParameterDiscoveryReqParams(ACChargeParameterDiscoveryReqParams):
    """
    See section 8.3.5.4.7.1 in ISO 15118-20
    BPT = Bidirectional Power Transfer
    """

    ev_max_discharge_power: RationalNumber = Field(..., alias="EVMaximumDischargePower")
    ev_max_discharge_power_l2: RationalNumber = Field(
        None, alias="EVMaximumDischargePower_L2"
    )
    ev_max_discharge_power_l3: RationalNumber = Field(
        None, alias="EVMaximumDischargePower_L3"
    )
    ev_min_discharge_power: RationalNumber = Field(..., alias="EVMinimumDischargePower")
    ev_min_discharge_power_l2: RationalNumber = Field(
        None, alias="EVMinimumDischargePower_L2"
    )
    ev_min_discharge_power_l3: RationalNumber = Field(
        None, alias="EVMinimumDischargePower_L3"
    )


class BPTACChargeParameterDiscoveryResParams(ACChargeParameterDiscoveryResParams):
    """
    See section 8.3.5.4.7.2 in ISO 15118-20
    BPT = Bidirectional Power Transfer
    """

    evse_max_discharge_power: RationalNumber = Field(
        ..., alias="EVSEMaximumDischargePower"
    )
    evse_max_discharge_power_l2: RationalNumber = Field(
        None, alias="EVSEMaximumDischargePower_L2"
    )
    evse_max_discharge_power_l3: RationalNumber = Field(
        None, alias="EVSEMaximumDischargePower_L3"
    )
    evse_min_discharge_power: RationalNumber = Field(
        ..., alias="EVSEMinimumDischargePower"
    )
    evse_min_discharge_power_l2: RationalNumber = Field(
        None, alias="EVSEMinimumDischargePower_L2"
    )
    evse_min_discharge_power_l3: RationalNumber = Field(
        None, alias="EVSEMinimumDischargePower_L3"
    )


class ScheduledACChargeLoopReqParams(ScheduledChargeLoopReqParams):
    """See section 8.3.5.4.4 in ISO 15118-20"""

    ev_max_charge_power: RationalNumber = Field(None, alias="EVMaximumChargePower")
    ev_max_charge_power_l2: RationalNumber = Field(
        None, alias="EVMaximumChargePower_L2"
    )
    ev_max_charge_power_l3: RationalNumber = Field(
        None, alias="EVMaximumChargePower_L3"
    )
    ev_min_charge_power: RationalNumber = Field(None, alias="EVMinimumChargePower")
    ev_min_charge_power_l2: RationalNumber = Field(
        None, alias="EVMinimumChargePower_L2"
    )
    ev_min_charge_power_l3: RationalNumber = Field(
        None, alias="EVMinimumChargePower_L3"
    )
    ev_present_active_power: RationalNumber = Field(..., alias="EVPresentActivePower")
    ev_present_active_power_l2: RationalNumber = Field(
        None, alias="EVPresentActivePower_L2"
    )
    ev_present_active_power_l3: RationalNumber = Field(
        None, alias="EVPresentActivePower_L3"
    )
    ev_present_reactive_power: RationalNumber = Field(
        None, alias="EVPresentReactivePower"
    )
    ev_present_reactive_power_l2: RationalNumber = Field(
        None, alias="EVPresentReactivePower_L2"
    )
    ev_present_reactive_power_l3: RationalNumber = Field(
        None, alias="EVPresentReactivePower_L3"
    )


class ScheduledACChargeLoopResParams(ScheduledChargeLoopResParams):
    """See section 8.3.5.4.6 in ISO 15118-20"""

    evse_target_active_power: RationalNumber = Field(
        None, alias="EVSETargetActivePower"
    )
    evse_target_active_power_l2: RationalNumber = Field(
        None, alias="EVSETargetActivePower_L2"
    )
    evse_target_active_power_l3: RationalNumber = Field(
        None, alias="EVSETargetActivePower_L3"
    )
    evse_target_reactive_power: RationalNumber = Field(
        None, alias="EVSETargetReactivePower"
    )
    evse_target_reactive_power_l2: RationalNumber = Field(
        None, alias="EVSETargetReactivePower_L2"
    )
    evse_target_reactive_power_l3: RationalNumber = Field(
        None, alias="EVSETargetReactivePower_L3"
    )
    evse_present_active_power: RationalNumber = Field(
        None, alias="EVSEPresentActivePower"
    )
    evse_present_active_power_l2: RationalNumber = Field(
        None, alias="EVSEPresentActivePower_L2"
    )
    evse_present_active_power_l3: RationalNumber = Field(
        None, alias="EVSEPresentActivePower_L3"
    )


class BPTScheduledACChargeLoopReqParams(ScheduledACChargeLoopReqParams):
    """See section 8.3.5.4.7.4 in ISO 15118-20"""

    ev_max_discharge_power: RationalNumber = Field(
        None, alias="EVMaximumDischargePower"
    )
    ev_max_discharge_power_l2: RationalNumber = Field(
        None, alias="EVMaximumDischargePower_L2"
    )
    ev_max_discharge_power_l3: RationalNumber = Field(
        None, alias="EVMaximumDischargePower_L3"
    )
    ev_min_discharge_power: RationalNumber = Field(
        None, alias="EVMinimumDischargePower"
    )
    ev_min_discharge_power_l2: RationalNumber = Field(
        None, alias="EVMinimumDischargePower_L2"
    )
    ev_min_discharge_power_l3: RationalNumber = Field(
        None, alias="EVMinimumDischargePower_L3"
    )


class BPTScheduledACChargeLoopResParams(ScheduledACChargeLoopResParams):
    """See section 8.3.5.4.7.6 in ISO 15118-20"""


class DynamicACChargeLoopReqParams(DynamicChargeLoopReqParams):
    """See section 8.3.5.4.3 in ISO 15118-20"""

    ev_max_charge_power: RationalNumber = Field(..., alias="EVMaximumChargePower")
    ev_max_charge_power_l2: RationalNumber = Field(
        None, alias="EVMaximumChargePower_L2"
    )
    ev_max_charge_power_l3: RationalNumber = Field(
        None, alias="EVMaximumChargePower_L3"
    )
    ev_min_charge_power: RationalNumber = Field(..., alias="EVMinimumChargePower")
    ev_min_charge_power_l2: RationalNumber = Field(
        None, alias="EVMinimumChargePower_L2"
    )
    ev_min_charge_power_l3: RationalNumber = Field(
        None, alias="EVMinimumChargePower_L3"
    )
    ev_present_active_power: RationalNumber = Field(..., alias="EVPresentActivePower")
    ev_present_active_power_l2: RationalNumber = Field(
        None, alias="EVPresentActivePower_L2"
    )
    ev_present_active_power_l3: RationalNumber = Field(
        None, alias="EVPresentActivePower_L3"
    )
    ev_present_reactive_power: RationalNumber = Field(
        ..., alias="EVPresentReactivePower"
    )
    ev_present_reactive_power_l2: RationalNumber = Field(
        None, alias="EVPresentReactivePower_L2"
    )
    ev_present_reactive_power_l3: RationalNumber = Field(
        None, alias="EVPresentReactivePower_L3"
    )


class DynamicACChargeLoopResParams(DynamicChargeLoopResParams):
    """See section 8.3.5.4.5 in ISO 15118-20"""

    evse_target_active_power: RationalNumber = Field(..., alias="EVSETargetActivePower")
    evse_target_active_power_l2: RationalNumber = Field(
        None, alias="EVSETargetActivePower_L2"
    )
    evse_target_active_power_l3: RationalNumber = Field(
        None, alias="EVSETargetActivePower_L3"
    )
    evse_target_reactive_power: RationalNumber = Field(
        None, alias="EVSETargetReactivePower"
    )
    evse_target_reactive_power_l2: RationalNumber = Field(
        None, alias="EVSETargetReactivePower_L2"
    )
    evse_target_reactive_power_l3: RationalNumber = Field(
        None, alias="EVSETargetReactivePower_L3"
    )
    evse_present_active_power: RationalNumber = Field(
        None, alias="EVSEPresentActivePower"
    )
    evse_present_active_power_l2: RationalNumber = Field(
        None, alias="EVSEPresentActivePower_L2"
    )
    evse_present_active_power_l3: RationalNumber = Field(
        None, alias="EVSEPresentActivePower_L3"
    )


class BPTDynamicACChargeLoopReqParams(DynamicACChargeLoopReqParams):
    """See section 8.3.5.4.7.3 in ISO 15118-20"""

    ev_max_discharge_power: RationalNumber = Field(..., alias="EVMaximumDischargePower")
    ev_max_discharge_power_l2: RationalNumber = Field(
        None, alias="EVMaximumDischargePower_L2"
    )
    ev_max_discharge_power_l3: RationalNumber = Field(
        None, alias="EVMaximumDischargePower_L3"
    )
    ev_min_discharge_power: RationalNumber = Field(..., alias="EVMinimumDischargePower")
    ev_min_discharge_power_l2: RationalNumber = Field(
        None, alias="EVMinimumDischargePower_L2"
    )
    ev_min_discharge_power_l3: RationalNumber = Field(
        None, alias="EVMinimumDischargePower_L3"
    )
    ev_max_v2x_energy_request: RationalNumber = Field(
        None, alias="EVMaximumV2XEnergyRequest"
    )
    ev_min_v2x_energy_request: RationalNumber = Field(
        None, alias="EVMinimumV2XEnergyRequest"
    )


class BPTDynamicACChargeLoopResParams(DynamicACChargeLoopResParams):
    """See section 8.3.5.4.7.5 in ISO 15118-20"""


class ACChargeParameterDiscoveryReq(ChargeParameterDiscoveryReq):
    """See section 8.3.4.4.2.2 in ISO 15118-20"""

    ac_params: ACChargeParameterDiscoveryReqParams = Field(
        None, alias="AC_CPDReqEnergyTransferMode"
    )
    bpt_ac_params: BPTACChargeParameterDiscoveryReqParams = Field(
        None, alias="BPT_AC_CPDReqEnergyTransferMode"
    )

    @root_validator(pre=True)
    def either_ac_or_ac_bpt_params(cls, values):
        """
        Either ac_params or bpt_ac_params must be set, depending on whether
        unidirectional or bidirectional power transfer was chosen.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        try:
            if one_field_must_be_set(
                [
                    "ac_params",
                    "AC_CPDReqEnergyTransferMode",
                    "bpt_ac_params",
                    "BPT_AC_CPDReqEnergyTransferMode",
                ],
                values,
                True,
            ):
                return values
        except ValueError as exc:
            raise V2GMessageValidationError(
                str(exc),
                ResponseCode.FAILED_WRONG_CHARGE_PARAMETER,
                ChargeParameterDiscoveryReq,
            )

    def __str__(self):
        # The XSD-conform name
        return "AC_ChargeParameterDiscoveryReq"


class ACChargeParameterDiscoveryRes(ChargeParameterDiscoveryRes):
    """See section 8.3.4.4.2.3 in ISO 15118-20"""

    ac_params: ACChargeParameterDiscoveryResParams = Field(
        None, alias="AC_CPDResEnergyTransferMode"
    )
    bpt_ac_params: BPTACChargeParameterDiscoveryResParams = Field(
        None, alias="BPT_AC_CPDResEnergyTransferMode"
    )

    @root_validator(pre=True)
    def either_ac_or_bpt_ac_params(cls, values):
        """
        Either ac_params or bpt_ac_params must be set, depending on whether
        unidirectional or bidirectional power transfer was chosen.

        Pydantic validators are "class methods",
        see https://pydantic-docs.helpmanual.io/usage/validators/
        """
        # pylint: disable=no-self-argument
        # pylint: disable=no-self-use
        if one_field_must_be_set(
            [
                "ac_params",
                "AC_CPDResEnergyTransferMode",
                "bpt_ac_params",
                "BPT_AC_CPDResEnergyTransferMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "AC_ChargeParameterDiscoveryRes"


class ACChargeLoopReq(ChargeLoopReq):
    """See section 8.3.4.4.3.2 in ISO 15118-20"""

    scheduled_params: ScheduledACChargeLoopReqParams = Field(
        None, alias="Scheduled_AC_CLReqControlMode"
    )
    dynamic_params: DynamicACChargeLoopReqParams = Field(
        None, alias="Dynamic_AC_CLReqControlMode"
    )
    bpt_scheduled_params: BPTScheduledACChargeLoopReqParams = Field(
        None, alias="BPT_Scheduled_AC_CLReqControlMode"
    )
    bpt_dynamic_params: BPTDynamicACChargeLoopReqParams = Field(
        None, alias="BPT_Dynamic_AC_CLReqControlMode"
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
                "Scheduled_AC_CLReqControlMode",
                "dynamic_params",
                "Dynamic_AC_CLReqControlMode",
                "bpt_scheduled_params",
                "BPT_Scheduled_AC_CLReqControlMode",
                "bpt_dynamic_params",
                "BPT_Dynamic_AC_CLReqControlMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "AC_ChargeLoopReq"


class ACChargeLoopRes(ChargeLoopRes):
    """See section 8.3.4.4.3.3 in ISO 15118-20"""

    evse_target_frequency: RationalNumber = Field(None, alias="EVSETargetFrequency")
    scheduled_params: ScheduledACChargeLoopResParams = Field(
        None, alias="Scheduled_AC_CLResControlMode"
    )
    dynamic_params: DynamicACChargeLoopResParams = Field(
        None, alias="Dynamic_AC_CLResControlMode"
    )
    bpt_scheduled_params: BPTScheduledACChargeLoopResParams = Field(
        None, alias="BPT_Scheduled_AC_CLResControlMode"
    )
    bpt_dynamic_params: BPTDynamicACChargeLoopResParams = Field(
        None, alias="BPT_Dynamic_AC_CLResControlMode"
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
                "Scheduled_AC_CLResControlMode",
                "dynamic_params",
                "Dynamic_AC_CLResControlMode",
                "bpt_scheduled_params",
                "BPT_Scheduled_AC_CLResControlMode",
                "bpt_dynamic_params",
                "BPT_Dynamic_AC_CLResControlMode",
            ],
            values,
            True,
        ):
            return values

    def __str__(self):
        # The XSD-conform name
        return "AC_ChargeLoopRes"
