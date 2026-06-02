"""
This modules contains classes which implement all the elements of the
DIN SPEC 72101 XSD file V2G_CI_MsgDef.xsd (see folder 'schemas').
In particular, this is the root element itself, the V2GMessage, which is
exchanged between the EVCC and the SECC. The V2GMessage consists of a header
and a body element (defined in the respective XSD files).


All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from pydantic.v1 import Field

from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.din_spec.body import Body
from iso15118.shared.messages.din_spec.header import MessageHeader


class V2GMessage(BaseModel):
    """See section 9.3.2 in DIN SPEC 70121"""

    header: MessageHeader = Field(..., alias="Header")
    body: Body = Field(..., alias="Body")

    def __str__(self):
        return str(self.body.get_message_name())
