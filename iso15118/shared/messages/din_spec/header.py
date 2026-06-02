"""
This modules contains classes which implement all the elements of the
DIN SPEC 70121 XSD file V2G_CI_MsgHeader.xsd (see folder 'schemas').
In particular, this is the header element of the V2GMessages exchanged between
the EVCC and the SECC.


All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from pydantic.v1 import Field, validator

from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.din_spec.datatypes import Notification
from iso15118.shared.messages.xmldsig import Signature


class MessageHeader(BaseModel):
    """See section 9.3.3 in DIN SPEC 70121"""

    # XSD type hexBinary with max 8 bytes encoded as 16 hexadecimal characters
    session_id: str = Field(..., max_length=16, alias="SessionID")
    notification: Notification = Field(None, alias="Notification")
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
            # convert value to int, assuming base 16
            int(value, 16)
            return value
        except ValueError as exc:
            raise ValueError(
                f"Invalid value '{value}' for SessionID (must be "
                f"hexadecimal representation of max 8 bytes)"
            ) from exc
