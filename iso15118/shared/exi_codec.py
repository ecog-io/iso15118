import json
import logging
from base64 import b64decode, b64encode
from typing import Optional, Type, Union

from pydantic.v1 import ValidationError

from iso15118.shared.exceptions import (
    EXIDecodingError,
    EXIEncodingError,
    V2GMessageValidationError,
)
from iso15118.shared.exificient_exi_codec import ExificientEXICodec
from iso15118.shared.iexi_codec import IEXICodec
from iso15118.shared.messages import BaseModel
from iso15118.shared.messages.app_protocol import (
    SupportedAppProtocolReq,
    SupportedAppProtocolRes,
)
from iso15118.shared.messages.din_spec.body import BodyBase as BodyBaseDINSPEC
from iso15118.shared.messages.din_spec.body import get_msg_type as get_msg_type_dinspec
from iso15118.shared.messages.din_spec.msgdef import V2GMessage as V2GMessageDINSPEC
from iso15118.shared.messages.enums import Namespace
from iso15118.shared.messages.iso15118_2.body import BodyBase as BodyBaseV2
from iso15118.shared.messages.iso15118_2.body import get_msg_type
from iso15118.shared.messages.iso15118_2.datatypes import ResponseCode
from iso15118.shared.messages.iso15118_2.msgdef import V2GMessage as V2GMessageV2
from iso15118.shared.messages.iso15118_20.ac import (
    ACChargeLoopReq,
    ACChargeLoopRes,
    ACChargeParameterDiscoveryReq,
    ACChargeParameterDiscoveryRes,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationReq as AuthorizationReqV20,
)
from iso15118.shared.messages.iso15118_20.common_messages import (
    AuthorizationRes,
    AuthorizationSetupReq,
    AuthorizationSetupRes,
    CertificateInstallationReq,
    CertificateInstallationRes,
    PowerDeliveryReq,
    PowerDeliveryRes,
    ScheduleExchangeReq,
    ScheduleExchangeRes,
    ServiceDetailReq,
    ServiceDetailRes,
    ServiceDiscoveryReq,
    ServiceDiscoveryRes,
    ServiceSelectionReq,
    ServiceSelectionRes,
    SessionSetupReq,
    SessionSetupRes,
    SessionStopReq,
    SessionStopRes,
)
from iso15118.shared.messages.iso15118_20.common_types import V2GMessage
from iso15118.shared.messages.iso15118_20.common_types import (
    V2GMessage as V2GMessageV20,
)
from iso15118.shared.messages.iso15118_20.dc import (
    DCCableCheckReq,
    DCCableCheckRes,
    DCChargeLoopReq,
    DCChargeLoopRes,
    DCChargeParameterDiscoveryReq,
    DCChargeParameterDiscoveryRes,
    DCPreChargeReq,
    DCPreChargeRes,
    DCWeldingDetectionReq,
    DCWeldingDetectionRes,
)
from iso15118.shared.settings import SettingKey, shared_settings

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to allow the encoding of raw bytes to Base64 encoded
    strings to conform with their XSD type base64Binary. Also, JSON cannot
    encode bytes by default, so the base64Binary type comes in handy.
    """

    # pylint: disable=method-hidden
    def default(self, o):
        if isinstance(o, bytes):
            return b64encode(o).decode()
        return json.JSONEncoder.default(self, o)


class CustomJSONDecoder(json.JSONDecoder):
    """
    Custom JSON decoder to allow the decoding of Base64 encoded bytes back to
    raw bytes.

    We use a custom object_hook() function for json.JSONDecoder to match the
    corresponding ISO 15118 message and datatype fields that we know have a
    bytes value and are serialised as Base64 encoded (base64_encoded_fields_set)
    and then decode each matching dict entry from Base64 back to raw bytes.
    """

    base64_encoded_fields_set = {
        "Certificate",
        "DHPublicKey",
        "GenChallenge",
        "MeterSignature",
        "OEMProvisioningCert",
        "SECP521_EncryptedPrivateKey",
        "SigMeterReading",
        "TPM_EncryptedPrivateKey",
        "Value",
        "value",
        "X448_EncryptedPrivateKey",
        "DigestValue",
    }

    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, dct) -> dict:
        for field in self.base64_encoded_fields_set.intersection(set(dct)):
            # 'Value' (or 'value') can be an integer field in the pydantic model
            # PhysicalValue (ISO 15118-2) and RationalNumber (ISO 15118-20) and
            # a string in EMAID. But it can also be a bytes field in the
            # pydantic model EncryptedPrivateKey. So we need to make sure to
            # only Base64 decode the one that is for sure not of type integer
            # or string. But for the string case, we need to distinguish
            # between a Base64 encoded string and a normal string (like the
            # one in EMAID).
            # TODO Need to find a better way, feels more and more like a hack
            if field in ("Value", "value") and isinstance(dct[field], int):
                continue

            if field in ("Value", "value") and isinstance(dct[field], str):
                # Trying to distinguish and EMAID value string from an
                # EncryptedPrivateKey value string. The latter is Base64
                # encoded. An EMAID is 14 or 15 characters long, a Base64
                # encoded EncryptedPrivateKey is definitely bigger.
                # Feels like a hack, is a hack, but what else shall we do ...?
                if len(dct[field]) <= 15:
                    continue

            if field == "Certificate" and isinstance(dct[field], list):
                # The types CertificateChain and SubCertificates both have fields
                # with the name `Certificate`. However, in `CertificateChain`
                # the field is of the type bytes, whilst in `SubCertificates` is
                # of the type list[bytes].
                # This difference needs to be taken into account; so here we look
                # for the list type, decode its elements and substitute the entry
                # in the dict with the new list.
                certificate_list = [b64decode(value) for value in dct[field]]
                dct[field] = certificate_list
                continue

            dct[field] = b64decode(dct[field])
        return dct


class EXI:
    """
    This Singleton class holds onto the EXI codec this session is initialized with.
    If a codec is not specified an instance of the fallback codec is returned.
    The codec to be used will be requested during encode and decode operations.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EXI, cls).__new__(cls)
            cls._instance.exi_codec = None
        return cls._instance

    def set_exi_codec(self, codec: IEXICodec):
        logger.info(f"EXI Codec version: {codec.get_version()}")
        self.exi_codec = codec

    def get_exi_codec(self) -> IEXICodec:
        """
        If exi_codec is not specified return an instance of the default codec Exificient
        """
        if self.exi_codec is None:
            self.exi_codec = ExificientEXICodec()
        return self.exi_codec

    def to_exi(self, msg_element: BaseModel, protocol_ns: str) -> bytes:
        """
        Encodes the message into a bytes stream using the EXI codec

        Args:
            msg_element: The V2G message (or message element) to be EXI encoded
            protocol_ns: The protocol namespace that uniquely identifies the XSD
                         schema, which the EXI encoder needs to use for the encoding
                         process

        Returns:
            A bytes object, representing the EXI encoded message
        """
        msg_to_dct: dict = msg_element.dict(by_alias=True, exclude_none=True)
        try:
            # Pydantic does not export the name of the model itself to a dict,
            # so we need to add it (the message names like 'SessionSetupReq')
            if (
                str(msg_element) == "CertificateChain"
                and protocol_ns == Namespace.ISO_V2_MSG_DEF
            ):
                # TODO: If we add `ContractSignatureCertChain` as the return of __str__
                #       for the CertificateChain class, do we still need this if clause?
                # In case of CertificateInstallationRes and CertificateUpdateRes,
                # str(message) would not be 'ContractSignatureCertChain' but
                # 'CertificateChain' (the type of ContractSignatureCertChain)
                message_dict = {"ContractSignatureCertChain": msg_to_dct}
            elif str(msg_element) == "CertificateChain" and protocol_ns.startswith(
                Namespace.ISO_V20_BASE
            ):
                # TODO: If we add `CPSCertificateChain` as the return of __str__
                #       for a unique class for V20 or even call it CPSCertificateChain
                #       do we still need this if clause?
                # In case of CertificateInstallationRes,
                # str(message) would not be 'CPSCertificateChain' but
                # 'CertificateChain' (the type of CPSCertificateChain)
                message_dict = {"CPSCertificateChain": msg_to_dct}
            elif str(msg_element) == "SignedCertificateChain":
                # TODO: If we add `OEMProvisioningCertificateChain` as the
                #  return of __str__ for the SignedCertificateChain class, do we still
                #  need this if clause?
                # In case of CertificateInstallationReq,
                # str(message) would not be 'OEMProvisioningCertificateChain' but
                # 'SignedCertificateChain' (the type of OEMProvisioningCertificateChain)
                message_dict = {"OEMProvisioningCertificateChain": msg_to_dct}
            elif isinstance(msg_element, V2GMessageV2) or isinstance(
                msg_element, V2GMessageDINSPEC
            ):
                message_dict = {"V2G_Message": msg_to_dct}
            else:
                message_dict = {str(msg_element): msg_to_dct}

            msg_content = json.dumps(message_dict, cls=CustomJSONEncoder)
        except Exception as exc:
            raise EXIEncodingError(
                f"EXIEncodingError for {str(msg_element)}: \
                                   {exc}"
            ) from exc

        if shared_settings[SettingKey.MESSAGE_LOG_JSON]:
            logger.info(f"Message to encode (ns={protocol_ns}): {msg_content}")

        try:
            exi_stream = self.exi_codec.encode(msg_content, protocol_ns)
        except Exception as exc:
            logger.error(
                f"EXIEncodingError in {protocol_ns} with {str(msg_content)}: {exc}"
            )
            raise EXIEncodingError(
                f"EXIEncodingError for {str(msg_element)}: " f"{exc}"
            ) from exc

        if shared_settings[SettingKey.MESSAGE_LOG_EXI]:
            logger.debug(f"EXI-encoded message: {exi_stream.hex()}")

        return exi_stream

    def from_exi(self, exi_message: bytes, namespace: str) -> Union[
        SupportedAppProtocolReq,
        SupportedAppProtocolRes,
        V2GMessageV2,
        V2GMessageV20,
        V2GMessageDINSPEC,
    ]:
        """
        Decodes the EXI encoded bytearray into a message according to the payload
        type provided.

        Args:
            exi_message: The EXI-encoded message, given as a bytes stream
            namespace: The XSD namespace used to encode that message, so
                      we know how to de-serialise the decoded message

        Raises:
            EXIDecodingError
        """
        if shared_settings[SettingKey.MESSAGE_LOG_EXI]:
            logger.debug(f"EXI-encoded message (ns={namespace}): {exi_message.hex()}")

        try:
            exi_decoded = self.exi_codec.decode(exi_message, namespace)
        except Exception as exc:
            raise EXIDecodingError(
                f"EXIDecodingError ({exc.__class__.__name__}): " f"{exc}"
            ) from exc
        try:
            decoded_dict = json.loads(exi_decoded, cls=CustomJSONDecoder)
        except json.JSONDecodeError as exc:
            raise EXIDecodingError(
                f"JSON decoding error ({exc.__class__.__name__}) while "
                f"processing decoded EXI: {exc}"
            ) from exc

        if shared_settings[SettingKey.MESSAGE_LOG_JSON]:
            logger.info(f"Decoded message (ns={namespace}): {exi_decoded}")

        try:
            if namespace == Namespace.SAP and "supportedAppProtocolReq" in decoded_dict:
                return SupportedAppProtocolReq.parse_obj(
                    decoded_dict["supportedAppProtocolReq"]
                )

            if namespace == Namespace.SAP and "supportedAppProtocolRes" in decoded_dict:
                return SupportedAppProtocolRes.parse_obj(
                    decoded_dict["supportedAppProtocolRes"]
                )

            if namespace == Namespace.DIN_MSG_DEF:
                return V2GMessageDINSPEC.parse_obj(decoded_dict["V2G_Message"])

            if namespace == Namespace.ISO_V2_MSG_DEF:
                return V2GMessageV2.parse_obj(decoded_dict["V2G_Message"])

            if namespace.startswith(Namespace.ISO_V20_BASE):
                # The message name is the first key of the dict
                msg_name = next(iter(decoded_dict))
                # When parsing the dict, we need to remove the first key, which is
                # the message name itself (e.g. SessionSetupReq)
                msg_dict = decoded_dict[msg_name]
                msg_classes_dict: dict[str, Type[V2GMessage]] = {
                    "SessionSetupReq": SessionSetupReq,
                    "SessionSetupRes": SessionSetupRes,
                    "AuthorizationSetupReq": AuthorizationSetupReq,
                    "AuthorizationSetupRes": AuthorizationSetupRes,
                    "CertificateInstallationReq": CertificateInstallationReq,
                    "CertificateInstallationRes": CertificateInstallationRes,
                    "AuthorizationReq": AuthorizationReqV20,
                    "AuthorizationRes": AuthorizationRes,
                    "ServiceDiscoveryReq": ServiceDiscoveryReq,
                    "ServiceDiscoveryRes": ServiceDiscoveryRes,
                    "ServiceDetailReq": ServiceDetailReq,
                    "ServiceDetailRes": ServiceDetailRes,
                    "ServiceSelectionReq": ServiceSelectionReq,
                    "ServiceSelectionRes": ServiceSelectionRes,
                    "AC_ChargeParameterDiscoveryReq": ACChargeParameterDiscoveryReq,
                    "AC_ChargeParameterDiscoveryRes": ACChargeParameterDiscoveryRes,
                    "DC_ChargeParameterDiscoveryReq": DCChargeParameterDiscoveryReq,
                    "DC_ChargeParameterDiscoveryRes": DCChargeParameterDiscoveryRes,
                    "ScheduleExchangeReq": ScheduleExchangeReq,
                    "ScheduleExchangeRes": ScheduleExchangeRes,
                    "DC_CableCheckReq": DCCableCheckReq,
                    "DC_CableCheckRes": DCCableCheckRes,
                    "DC_PreChargeReq": DCPreChargeReq,
                    "DC_PreChargeRes": DCPreChargeRes,
                    "PowerDeliveryReq": PowerDeliveryReq,
                    "PowerDeliveryRes": PowerDeliveryRes,
                    "AC_ChargeLoopReq": ACChargeLoopReq,
                    "AC_ChargeLoopRes": ACChargeLoopRes,
                    "DC_ChargeLoopReq": DCChargeLoopReq,
                    "DC_ChargeLoopRes": DCChargeLoopRes,
                    "DC_WeldingDetectionReq": DCWeldingDetectionReq,
                    "DC_WeldingDetectionRes": DCWeldingDetectionRes,
                    "SessionStopReq": SessionStopReq,
                    "SessionStopRes": SessionStopRes,
                    # TODO add all the other message types and states
                }
                msg_class: Type[V2GMessage] = msg_classes_dict.get(msg_name)
                if not msg_class:
                    logger.error(
                        "Unable to identify message to parse given the message "
                        f"name {msg_name}"
                    )
                    raise EXIDecodingError(f"Unable to decode {msg_name}")

                return msg_class.parse_obj(msg_dict)

            raise EXIDecodingError("Can't identify protocol to use for decoding")
        except ValidationError as exc:
            msg_type: Optional[
                Type[
                    Union[
                        BodyBaseDINSPEC,
                        BodyBaseV2,
                        V2GMessage,
                        SupportedAppProtocolReq,
                        SupportedAppProtocolRes,
                    ]
                ],
            ] = None
            if namespace == Namespace.ISO_V2_MSG_DEF:
                msg_name = next(iter(decoded_dict["V2G_Message"]["Body"]))
                msg_type = get_msg_type(msg_name)
            elif namespace == Namespace.DIN_MSG_DEF:
                msg_name = next(iter(decoded_dict["V2G_Message"]["Body"]))
                msg_type = get_msg_type_dinspec(msg_name)
            elif namespace.startswith(Namespace.ISO_V20_BASE):
                msg_type = msg_class
            elif namespace == Namespace.SAP:
                if "supportedAppProtocolReq" in decoded_dict:
                    msg_type = SupportedAppProtocolReq
                elif "supportedAppProtocolRes" in decoded_dict:
                    msg_type = SupportedAppProtocolRes

            raise V2GMessageValidationError(
                f"Validation error: {exc}. \n\nDecoded dict: " f"{decoded_dict}",
                ResponseCode.FAILED,
                msg_type,
            ) from exc

        except V2GMessageValidationError as exc:
            raise exc
        except EXIDecodingError as exc:
            raise EXIDecodingError(
                f"EXI decoding error: {exc}. \n\nDecoded dict: " f"{decoded_dict}"
            ) from exc
