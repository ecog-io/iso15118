from enum import Enum
from typing import List

from pydantic.v1 import Field

from iso15118.shared.messages import BaseModel


class AppProtocol(BaseModel):
    protocol_ns: str = Field(..., max_length=100, alias="ProtocolNamespace")
    major_version: int = Field(..., alias="VersionNumberMajor")
    minor_version: int = Field(..., alias="VersionNumberMinor")
    # XSD type unsignedByte with value range [0..255]
    schema_id: int = Field(..., ge=0, le=255, alias="SchemaID")
    # XSD type unsignedByte with value range [1..20]
    priority: int = Field(..., ge=1, le=20, alias="Priority")


class ResponseCodeSAP(str, Enum):
    NEGOTIATION_OK = "OK_SuccessfulNegotiation"
    MINOR_DEVIATION = "OK_SuccessfulNegotiationWithMinorDeviation"
    NEGOTIATION_FAILED = "Failed_NoNegotiation"


class SupportedAppProtocolReq(BaseModel):
    app_protocol: List[AppProtocol] = Field(..., alias="AppProtocol")

    def __str__(self):
        # SupportedAppProtocolReq is defined in the XSD with a lower first
        # letter. This is probably a typo and can lead to EXI encoding errors
        # if you're not aware of it!
        return self.__class__.__name__[0].lower() + self.__class__.__name__[1:]


class SupportedAppProtocolRes(BaseModel):
    response_code: ResponseCodeSAP = Field(..., alias="ResponseCode")
    # XSD type unsignedByte with value range [0..255]
    schema_id: int = Field(None, ge=0, le=255, alias="SchemaID")

    def __str__(self):
        # SupportedAppProtocolRes is defined in the XSD with a lower first
        # letter. This is probably a typo and can lead to EXI encoding errors
        # if you're not aware of it!
        return self.__class__.__name__[0].lower() + self.__class__.__name__[1:]
