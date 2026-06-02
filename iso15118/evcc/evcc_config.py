import json
import logging
from typing import List, Optional

from aiofile import async_open
from pydantic.v1 import BaseModel, Field, validator

from iso15118.shared.messages.enums import (
    UINT_16_MAX,
    EnergyTransferModeEnum,
    Protocol,
    ServiceV20,
)
from iso15118.shared.utils import (
    load_requested_energy_services,
    load_requested_protocols,
)

logger = logging.getLogger(__name__)


class EVCCConfig(BaseModel):
    _default_protocols = [
        "DIN_SPEC_70121",
        "ISO_15118_2",
        "ISO_15118_20_AC",
        "ISO_15118_20_DC",
    ]
    _default_supported_energy_services = ["AC"]
    raw_supported_energy_services: List[str] = Field(
        _default_supported_energy_services, max_items=4, alias="supportedEnergyServices"
    )
    supported_energy_services: List[ServiceV20] = None
    is_cert_install_needed: bool = Field(False, alias="isCertInstallNeeded")
    # Indicates the security level (either TCP (unencrypted) or TLS (encrypted))
    # the EVCC shall send in the SDP request
    use_tls: Optional[bool] = Field(True, alias="useTls")
    # How often shall SDP (SECC Discovery Protocol) retries happen before reverting
    # to using nominal duty cycle PWM-based charging?
    sdp_retry_cycles: Optional[int] = Field(1, alias="sdpRetryCycles")
    # For ISO 15118-20 only
    # Maximum amount of contract certificates (and associated certificate chains)
    # the EV can store. That value is used in the CertificateInstallationReq.
    # Must be an integer between 0 and 65535, should be bigger than 0.
    max_contract_certs: Optional[int] = Field(3, alias="maxContractCerts")
    # Indicates whether or not the EVCC should always enforce a TLS-secured
    # communication session.
    # If True, the EVCC will only continue setting up a communication session if
    # the SECC's SDP response has the Security field set
    # to the enum value Security.TLS.
    # If the USE_TLS setting is set to False and ENFORCE_TLS is set to True, then
    # ENFORCE_TLS overrules USE_TLS.
    enforce_tls: bool = Field(False, alias="enforceTls")
    # Supported protocols, used for SupportedAppProtocol (SAP). The order in which
    # the protocols are listed here determines the priority (i.e. first list entry
    # the protocols are listed here determines the priority (i.e. first list entry
    # has higher priority than second list entry). A list entry must be a member
    # of the Protocol enum
    raw_supported_protocols: Optional[List[str]] = Field(
        _default_protocols, max_items=6, alias="supportedProtocols"
    )
    supported_protocols: Optional[List[Protocol]] = None
    energy_transfer_mode: Optional[EnergyTransferModeEnum] = Field(
        EnergyTransferModeEnum.AC_THREE_PHASE_CORE, alias="energyTransferMode"
    )
    # Indicates the maximum number of entries the EVCC supports within the
    # sub-elements of a ScheduleTuple (e.g. PowerScheduleType and PriceRuleType in
    # ISO 15118-20 as well as PMaxSchedule and SalesTariff in ISO 15118-2).
    # The SECC must not transmit more entries than defined in this parameter.
    max_supporting_points: Optional[int] = Field(1024, alias="maxSupportingPoints")

    # charge cycle count
    charge_loop_cycle: Optional[int] = Field(10, alias="chargeLoopCycle")
    # charge loop cycle delay before next cycle
    charge_loop_delay_time: Optional[int] = Field(0, alias="chargeLoopDelay")

    def load_raw_values(self):
        # conversion of list of strings to enum types.
        self.supported_energy_services = load_requested_energy_services(
            self.raw_supported_energy_services
        )
        self.supported_protocols = load_requested_protocols(
            self.raw_supported_protocols
        )

    @validator("max_supporting_points", pre=True, always=True)
    def check_max_supporting_points(cls, value):
        if not 0 <= value <= 1024:
            raise ValueError(
                "Wrong range for max_supporting_points in config file. "
                "Should be in [0..1024]"
            )
        return value

    @validator("sdp_retry_cycles", pre=True, always=True)
    def check_sdp_retry_cycle(cls, value):
        if value < 0:
            raise ValueError(
                "Wrong range for sdp_retry_cycles in config file. " "Should be in [0..]"
            )
        return value

    @validator("max_contract_certs", pre=True, always=True)
    def check_max_contract_certs(cls, value):
        if not 1 < value < UINT_16_MAX:
            raise ValueError(
                "Wrong range for max_contract_certs in config file. "
                "Should be in [1..UINT_16_MAX]"
            )
        return value


async def load_from_file(file_name: str) -> EVCCConfig:
    try:
        async with async_open(file_name, "r") as f:
            json_content = await f.read()
            data = json.loads(json_content)
            ev_config = EVCCConfig(**data)
            ev_config.load_raw_values()
            logger.info("EVCC Settings")
            for key, value in ev_config.dict().items():
                if not key.startswith("raw"):
                    logger.info(f"{key:30}: {value}")
        return ev_config
    except Exception as err:
        logger.debug(f"Error on loading evcc config file:{err}")
    return EVCCConfig()
