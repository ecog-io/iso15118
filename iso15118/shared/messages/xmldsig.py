"""
DataTypes for the construction of the XML signature syntax
Please check:
Section 7.9.2.4.2 XML Signature mechanism from ISO 15118-2
https://en.wikipedia.org/wiki/XML_Signature
https://www.w3.org/TR/xmldsig-core1/
"""

from typing import List

from pydantic.v1 import Field, HttpUrl

from iso15118.shared.messages import BaseModel


class Transform(BaseModel):
    algorithm: HttpUrl = Field(..., alias="Algorithm")


class Transforms(BaseModel):
    """
    According to requirement [V2G2-767], the maximum number of transforms
    is limited to one (1), i.e. just one single Transform algorithm can be
    indicated.
    """

    transform: List[Transform] = Field(..., max_items=1, alias="Transform")


class DigestMethod(BaseModel):
    algorithm: HttpUrl = Field(..., alias="Algorithm")


class SignatureMethod(BaseModel):
    algorithm: HttpUrl = Field(..., alias="Algorithm")


class CanonicalizationMethod(BaseModel):
    algorithm: HttpUrl = Field(..., alias="Algorithm")


class Reference(BaseModel):
    """
    Reference is an object that represents the Reference XML element of a Signature.
    This element is a reference to the element of a V2G body message that will
    be signed.

    According to xmldisg-core-schema, "Id", "URI" and "Type" all belong to the
    Reference complex type, however, according to requirement [V2G2-771], Type
    shall not be used. Also, the URI is enough to reference the Id attribute of
    the element in the message body.

    In order to understand how Reference is used and the connection to the V2G
    body message, the user is invited to check the example in annex J, section
    J.2 of the ISO 15118-2, which is partially transcribed here:

    V2G body element contains Id="ID1"

    <v2gci_b:AuthorizationReq v2gci_b:Id="ID1">
        <v2gci_b:GenChallenge>U29tZSBSYW5kb20gRGF0YQ==</v2gci_b:GenChallenge>
    </v2gci_b:AuthorizationReq>

    The Signature contains the Reference element with a URI which refers to the
    V2G body element (ID1)

    <xmlsig:Signature>
        <xmlsig:SignedInfo>
            <xmlsig:CanonicalizationMethod Algorithm="http://www.w3.org/TR/canonical-exi/"/>
            <xmlsig:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"/> # noqa: E501
            <xmlsig:Reference URI="#ID1">
                <xmlsig:Transforms>
                    <xmlsig:Transform Algorithm="http://www.w3.org/TR/canonical-exi/"/>
                </xmlsig:Transforms>
                <xmlsig:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                <xmlsig:DigestValue>0bXgPQBlvuVrMXmERTBR61TKGPwOCRYXT4s8d6mPSqk=</xmlsig:DigestValue> # noqa: E501
            </xmlsig:Reference>
        </xmlsig:SignedInfo>
        <xmlsig:SignatureValue></xmlsig:SignatureValue>
    </xmlsig:Signature>

    """

    transforms: Transforms = Field(..., alias="Transforms")
    digest_method: DigestMethod = Field(..., alias="DigestMethod")
    digest_value: bytes = Field(..., alias="DigestValue")
    # id and uri are both attributes of the Reference element and not elements
    id: str = Field(None, alias="Id")
    uri: str = Field(None, alias="URI")


class SignedInfo(BaseModel):
    """
    SignedInfo is an object that belongs to the Signature element as exemplified
    in annex J, section J.2 of the ISO 15118-2.

    According to the schema, the Reference attribute is unbounded, however, according
    to requirement [V2G2-909]:
        "The signature shall not reference more than 4 signed elements"
    Therefore, a limit of 4 to the number of items of the `Reference` is enforced.
    """

    canonicalization_method: CanonicalizationMethod = Field(
        ..., alias="CanonicalizationMethod"
    )
    signature_method: SignatureMethod = Field(..., alias="SignatureMethod")
    reference: List[Reference] = Field(..., max_items=4, alias="Reference")

    def __str__(self):
        return type(self).__name__


class SignatureValue(BaseModel):
    value: bytes = Field(..., alias="value")


class Signature(BaseModel):
    signed_info: SignedInfo = Field(..., alias="SignedInfo")
    signature_value: SignatureValue = Field(..., alias="SignatureValue")


class X509IssuerSerial(BaseModel):
    x509_issuer_name: str = Field(..., alias="X509IssuerName")
    x509_serial_number: int = Field(..., alias="X509SerialNumber")


class SignedElement(BaseModel):
    """
    The element of a BodyBase (the message inside the Body element of a
    V2GMessage) that needs to be digitally signed and referenced in the
    SignedInfo field of the header.

    Example:
    For the AuthorizationReq it's the complete message.
    For the CertificateInstallationRes, it's four elements of the message, not
    the complete message.
    """
