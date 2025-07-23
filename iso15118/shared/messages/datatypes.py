from enum import Enum
from typing import List, Literal, Tuple, Union

from pydantic.v1 import Field, root_validator

from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.enums import (
    INT_16_MAX,
    INT_16_MIN,
    IsolationLevel,
    UnitSymbol,
)


class PhysicalValue(BaseModel):
    """
    All classes inheriting from PhysicalValue start with 'PV'
    (abbreviation for 'Physical Value') and define value and unit fields.
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    ISO 15118-2 sets limits to the physical values, however DIN 70121 and
    ISO 15118-20 do not. During field tests was also raised that the physical
    limits are a restriction that in practice make no sense. In favor of
    enhancing the charging experience the limits were lifted.

    If it is desired to add limits back on, the classes must inherit
    the private attribute `#_max_limit`, which is used to set the maximum
    limit of each specific physical type and used in the `validate_value_range`
    method. This private attribute is not added to the Pydantic model in
    anyway: https://github.com/samuelcolvin/pydantic/issues/655
    """

    _max_limit: int = 0
    _min_limit: int = 0
    # XSD int16 range [-32768, 32767]
    value: int = Field(..., ge=INT_16_MIN, le=INT_16_MAX, alias="Value")
    # XSD type byte with value range [-3..3]
    multiplier: int = Field(..., ge=-3, le=3, alias="Multiplier")

    @root_validator
    def validate_value_range(cls, values):
        """
        Validator for the range of the PhysicalValue type

        Raises:
            ValueError, if the calculated value exceeds the limits set
        """
        value = values.get("value")
        multiplier = values.get("multiplier")
        calculated_value = value * 10**multiplier
        if (
            0 < cls._max_limit < calculated_value
            or calculated_value < cls._min_limit < 0
        ):
            raise ValueError(
                f"{cls.__name__[2:] }"  # type: ignore[attr-defined]
                f"value limit exceeded: {calculated_value} \n"
                f"Max: {cls._max_limit} \n"
                f"Min: {cls._min_limit}"
            )
        return values

    def get_decimal_value(self) -> float:
        return self.value * 10**self.multiplier

    @classmethod
    def get_exponent_value_repr(
        cls,
        value: Union[int, float],
        min_limit: int = INT_16_MIN,
        max_limit: int = INT_16_MAX,
    ) -> Tuple[int, int]:
        return get_exponent_value_repr(value, min_limit, max_limit)


class PVChargingProfileEntryMaxPower(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for ChargingProfileEntryMaxPower.
    """

    unit: Literal[UnitSymbol.WATT] = Field(..., alias="Unit")


class PVEAmount(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for EAmount.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(..., alias="Unit")


class PVEVEnergyCapacity(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for EVEnergyCapacity.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(..., alias="Unit")


class PVEVEnergyRequest(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for EVEnergyRequest.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(..., alias="Unit")


class PVEVMaxCurrent(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVMaxCurrentLimit(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVMaxPowerLimit(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for EVMaxPowerLimit.
    """

    unit: Literal[UnitSymbol.WATT] = Field(..., alias="Unit")


class PVEVMaxVoltage(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 1000
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVEVMaxVoltageLimit(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 1000
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVEVMinCurrent(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSECurrentRegulationTolerance(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSEEnergyToBeDelivered(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for EVSEEnergyToBeDelivered.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(..., alias="Unit")


class PVEVSEMaxCurrent(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    """See section 9.5.2.4 in DIN SPEC 70121"""

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSEMaxCurrentLimit(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSEMaxPowerLimit(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2

    Value is of XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for EVSEMaxPowerLimit.
    """

    unit: Literal[UnitSymbol.WATT] = Field(..., alias="Unit")


class PVEVSEMaxVoltageLimit(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 1000
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVEVSENominalVoltage(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVEVSEMinCurrentLimit(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSEMinVoltageLimit(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 1000
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVEVSEPeakCurrentRipple(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSEPresentCurrent(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVSEPresentVoltage(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 1000
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVEVTargetCurrent(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 400
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(..., alias="Unit")


class PVEVTargetVoltage(PhysicalValue):
    """
    Table 68 in section 8.5.2.7 in ISO 15118-2
    sets limit to 1000
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(..., alias="Unit")


class PVPMax(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2
    XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for PMax.
    """

    unit: Literal[UnitSymbol.WATT] = Field(..., alias="Unit")


class PVRemainingTimeToBulkSOC(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2
    XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 172800 for RemainingTimeToBulkSOC.
    """

    unit: Literal[UnitSymbol.SECONDS] = Field(..., alias="Unit")


class PVRemainingTimeToFullSOC(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2
    XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 172800 for RemainingTimeToFullSOC.
    """

    unit: Literal[UnitSymbol.SECONDS] = Field(..., alias="Unit")


class PVStartValue(PhysicalValue):
    """
    See Table 68 in section 8.5.2.7 in ISO 15118-2
    XSD type short (16 bit integer) with value range [-32768..32767].
    Table 68 shows a max value of 200000 for StartValue.
    """

    unit: Literal[UnitSymbol.WATT] = Field(..., alias="Unit")


class PVEVEnergyCapacityDin(PVEVEnergyCapacity):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(None, alias="Unit")


class PVEVEnergyRequestDin(PVEVEnergyRequest):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(None, alias="Unit")


class PVEVMaxCurrentLimitDin(PVEVMaxCurrentLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVMaxPowerLimitDin(PVEVMaxPowerLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.WATT] = Field(None, alias="Unit")


class PVEVMaxVoltageLimitDin(PVEVMaxVoltageLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(None, alias="Unit")


class PVEVSECurrentRegulationToleranceDin(PVEVSECurrentRegulationTolerance):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVSEEnergyToBeDeliveredDin(PVEVSEEnergyToBeDelivered):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.WATT_HOURS] = Field(None, alias="Unit")


class PVEVSEMaxCurrentLimitDin(PVEVSEMaxCurrentLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVSEMaxPowerLimitDin(PVEVSEMaxPowerLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.WATT] = Field(None, alias="Unit")


class PVEVSEMaxVoltageLimitDin(PVEVSEMaxVoltageLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(None, alias="Unit")


class PVEVSEMinCurrentLimitDin(PVEVSEMinCurrentLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVSEMinVoltageLimitDin(PVEVSEMinVoltageLimit):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(None, alias="Unit")


class PVEVSEPeakCurrentRippleDin(PVEVSEPeakCurrentRipple):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVSEPresentCurrentDin(PVEVSEPresentCurrent):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVSEPresentVoltageDin(PVEVSEPresentVoltage):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(None, alias="Unit")


class PVEVTargetCurrentDin(PVEVTargetCurrent):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    In DIN there is no range for the value specified.
    There are EVs that sometimes send values below zero
    (e.g. Skoda Enyaq).
    """

    unit: Literal[UnitSymbol.AMPERE] = Field(None, alias="Unit")


class PVEVTargetVoltageDin(PVEVTargetVoltage):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.VOLTAGE] = Field(None, alias="Unit")


class PVRemainingTimeToFullSOCDin(PVRemainingTimeToFullSOC):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.SECONDS] = Field(None, alias="Unit")


class PVRemainingTimeToBulkSOCDin(PVRemainingTimeToBulkSOC):
    """
    See section 9.5.2.4 in DIN SPEC 70121

    In DIN the Element unit is optional, in ISO it is mandatory.
    """

    unit: Literal[UnitSymbol.SECONDS] = Field(None, alias="Unit")


class DCEVChargeParams(BaseModel):
    dc_max_current_limit: PVEVMaxCurrentLimit
    dc_max_power_limit: PVEVMaxPowerLimit
    dc_max_voltage_limit: PVEVMaxVoltageLimit
    dc_energy_capacity: PVEVEnergyCapacity
    dc_target_current: PVEVTargetCurrent
    dc_target_voltage: PVEVTargetVoltage


class DCEVSEStatusCode(str, Enum):
    """See section 8.5.4.1 in ISO 15118-2"""

    EVSE_NOT_READY = "EVSE_NotReady"
    EVSE_READY = "EVSE_Ready"
    EVSE_SHUTDOWN = "EVSE_Shutdown"
    # XSD typo in "Interrupt"
    EVSE_UTILITY_INTERUPT_EVENT = "EVSE_UtilityInterruptEvent"
    EVSE_ISOLATION_MONITORING_ACTIVE = "EVSE_IsolationMonitoringActive"
    EVSE_EMERGENCY_SHUTDOWN = "EVSE_EmergencyShutdown"
    EVSE_MALFUNCTION = "EVSE_Malfunction"
    RESERVED_8 = "Reserved_8"
    RESERVED_9 = "Reserved_9"
    RESERVED_A = "Reserved_A"
    RESERVED_B = "Reserved_B"
    RESERVED_C = "Reserved_C"


class EVSENotification(str, Enum):
    """See sections 8.5.3.1 and 8.5.4.1 in ISO 15118-2"""

    NONE = "None"
    STOP_CHARGING = "StopCharging"
    RE_NEGOTIATION = "ReNegotiation"


class EVSEStatus(BaseModel):
    """See sections 8.5.3.1 and 8.5.4.1 in ISO 15118-2"""

    # XSD type unsignedShort (16 bit integer) with value range [0..65535]
    notification_max_delay: int = Field(
        ..., ge=0, le=65535, alias="NotificationMaxDelay"
    )
    evse_notification: EVSENotification = Field(..., alias="EVSENotification")


class DCEVSEStatus(EVSEStatus):
    """See section 8.5.4.1 in ISO 15118-2"""

    evse_isolation_status: IsolationLevel = Field(None, alias="EVSEIsolationStatus")
    evse_status_code: DCEVSEStatusCode = Field(..., alias="EVSEStatusCode")


class DCEVSEChargeParameter(BaseModel):
    """See section 8.5.4.4 in ISO 15118-2"""

    dc_evse_status: DCEVSEStatus = Field(..., alias="DC_EVSEStatus")
    evse_maximum_current_limit: PVEVSEMaxCurrentLimit = Field(
        ..., alias="EVSEMaximumCurrentLimit"
    )
    evse_maximum_power_limit: PVEVSEMaxPowerLimit = Field(
        ..., alias="EVSEMaximumPowerLimit"
    )
    evse_maximum_voltage_limit: PVEVSEMaxVoltageLimit = Field(
        ..., alias="EVSEMaximumVoltageLimit"
    )
    evse_minimum_current_limit: PVEVSEMinCurrentLimit = Field(
        ..., alias="EVSEMinimumCurrentLimit"
    )
    evse_minimum_voltage_limit: PVEVSEMinVoltageLimit = Field(
        ..., alias="EVSEMinimumVoltageLimit"
    )
    evse_current_regulation_tolerance: PVEVSECurrentRegulationTolerance = Field(
        None, alias="EVSECurrentRegulationTolerance"
    )
    evse_peak_current_ripple: PVEVSEPeakCurrentRipple = Field(
        ..., alias="EVSEPeakCurrentRipple"
    )
    evse_energy_to_be_delivered: PVEVSEEnergyToBeDelivered = Field(
        None, alias="EVSEEnergyToBeDelivered"
    )


class SelectedService(BaseModel):
    """See section 9.5.2.14 in DIN SPEC 70121"""

    """See section 8.5.2.25 in ISO 15118-2"""

    # XSD type unsignedShort (16 bit integer) with value range [0..65535]
    service_id: int = Field(..., ge=0, le=65535, alias="ServiceID")
    # XSD type unsignedShort (16 bit integer) with value range [0..65535]
    # Table 87 says short, Table 106 says unsignedShort. We go with
    # unsignedShort as it makes more sense (no negative values).
    parameter_set_id: int = Field(None, ge=0, le=65535, alias="ParameterSetID")


class SelectedServiceList(BaseModel):
    """See section 9.5.2.13 in DIN SPEC 70121"""

    """See section 8.5.2.24 in ISO 15118-2"""

    selected_service: List[SelectedService] = Field(
        ..., max_items=16, alias="SelectedService"
    )


def get_exponent_value_repr(
    value: Union[int, float],
    min_limit: int = INT_16_MIN,
    max_limit: int = INT_16_MAX,
) -> Tuple[int, int]:
    """Convert to exponent number, by finding the best fit exponent.
    taking into consideration the min -32768 and max 32767 limits.
    Examples:
    value = 0.0000234 => exponent = -7, return value = 234
    value = 0.000234 => exponent = -6, return value = 234
    value = 0.00234 => exponent = -5, return value = 234
    value = 0.0234 => exponent = -4, return value = 234
    value = 0.234 => exponent = -3, return value = 234
    value = 2.34 => exponent = -2, return value = 234
    value = 23.4 => exponent = -1, return value = 234
    value = 234 => exponent = 0, return value = 234
    value = 2340 => exponent = 0, return value = 2340
    value = 23400 => exponent = 0, return value = 23400
    value = 234000 => exponent = 1, return value = 23400
    value = 2340000 => exponent = 2, return value = 23400

    value = 2340000 => exponent = 2, return value = 23400
    value = 23400000 => exponent = 3, return value = 23400

    value = 0.4 => exponent = -1, return value = 4
    value = 0.356 => exponent = -3, return value = 356
    value = 0.157 => exponent = -3, return value = 157
    value = 0.00356 => exponent = -5, return value = 356
    value = 0.634 => exponent = -3, return value = 634

    Note:
        In ISO 15118-2, the min limit is 0 and the max is
        dependent on the field.
        In ISO 15118-20, the limits are defined by the
        RationalNumber type which are the limits of the
        int16 range: [-32768, 32767].
        Also, in ISO 15118-20, the exponent assumes the range
        of [-128, 127], but currently that is not being
        taken into consideration.
    Args:
        value (int, float): parameter value

    Returns:
        a tuple where the first item is the exponent and other is the
        int value with the applied exponent
    """
    exponent = 0
    # In theory in -20 we can have exponents in the range [-128, 127]
    # but up to 3 decimal cases is a good enough approximation
    # and avoids any overflow issues due to python float precision/representation
    while value != int(value):
        value *= 10
        exponent -= 1
        if exponent == -3:
            if int(value) == 0:
                exponent = 0
            break
    while not (min_limit <= value <= max_limit):
        if abs(value) >= 10:
            value /= 10
            exponent += 1
        elif abs(value) < 1 and value != 0:
            value *= 10
            exponent -= 1

    return exponent, int(value)
