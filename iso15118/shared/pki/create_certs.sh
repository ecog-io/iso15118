#!/bin/bash

# ===============================================================================================================
# This shell script can be used to create all necessary certificates needed to
# - successfully perform a TLS handshake between the EVCC (TLS client) and the
#   SECC (TLS server) and
# - install a contract certificate in the EVCC.
#
# This file contains all information needed to create your own certificate chains.
#
# Helpful information about using OpenSSL is provided by Ivan Ristic's book
# "Bulletproof SSL and TLS". Furthermore, you should have OpenSSL >= 1.0.2
# installed to comply with all security requirements of ISO 15118.
# Some MacOS X installations unfortunately still use openssl < v1.0.2. You could use Homebrew to install openssl.
#
# Author: Dr. Marc Mültin (marc@switch-ev.com)
# ===============================================================================================================


# Change the validity periods (given in number of days) to test
# - valid certificates (e.g. contract certificate or Sub-CA certificate)
# - expired certificates (e.g. contract certificate or Sub-CA certificates)
#   -> you need to reset your system time to the past to create expired certificates
# - a to-be-updated contract certificate
VALIDITY_CONTRACT_LEAF_CERT=730
VALIDITY_MO_SUBCA2_CERT=1460
VALIDITY_MO_SUBCA1_CERT=1460
VALIDITY_MO_ROOT_CERT=3650
VALIDITY_OEM_LEAF_CERT=1460
VALIDITY_OEM_SUBCA2_CERT=1460
VALIDITY_OEM_SUBCA1_CERT=1460
VALIDITY_OEM_ROOT_CERT=3650
VALIDITY_CPS_LEAF_CERT=90
VALIDITY_CPS_SUBCA2_CERT=730
VALIDITY_CPS_SUBCA1_CERT=1460
VALIDITY_SECC_LEAF_CERT=60
VALIDITY_CPO_SUBCA1_CERT=1460
VALIDITY_CPO_SUBCA2_CERT=365
VALIDITY_V2G_ROOT_CERT=3650

ISO_2="iso-2"
ISO_20="iso-20"

usage() {
  echo "
  Usage: "$0" [-h] [-v <iso-2|iso-20>] [-p password] [-k] [--ocsp-req] [--ocsp-resp]

  Options:
   -h --help          Returns this helper
   -v --version       ISO version to run the script for: 'iso-2' refers to ISO 15118-2,
                      whereas 'iso-20' refers to ISO 15118-20
   -p --password      The password to encrypt and decrypt the private keys
   -k --keysight      Generate certificates to be used while pairing with Keysight test system,
                      alongside this iso15118 project.
      --ocsp-req      Don't generate any certificates - instead, send an OCSP request to
                      validate the SECC leaf certificate.
      --ocsp-resp     Don't generate any certificates - instead, start an OCSP responder for
                      validating SECC leaf certificates.


  Description:
    You can use this script to create all the private keys and public key certificates
    necessary to run an ISO 15118 Plug & Charge session (for testing purposes only).
    You need to provide the ISO 15118 version with the '-v' flag, choosing between the
    two admissible options stated above.

    This script uses by default a password value of 12345, which can be modified
    if -p option is used as exemplified above.

    NOTE: This script will create the following folder structure, if not already
    existing, depending on the protocol version you choose and place the corresponding
    private keys, certificate signing requests (csrs), and certificates (certs) in the
    right folder, overwriting any files with the same name:

    |__ iso15118_2 (or iso15118_20)
      |__ certs
      |__ csrs
      |__ private_keys
  "
  exit 0;
}

validate_option() {
    # Check if the version provided is valid, if not it returns
    if [ "$1" != $ISO_2 ] && [ "$1" != $ISO_20 ]; then
        echo "The version provided is invalid"
        usage
    fi
}


if [ -z $1 ]; then echo "No options were provided"; usage; fi

while [ -n "$1" ]; do
    case "$1" in
        -h|--help)
            usage
            ;;
        -v|--version)
            validate_option $2
            version=$2
            shift  # params with args need an extra shift
            ;;
        -p|--password)
            password=$2
            shift
            ;;
        -k|--keysight)
            keysight_certs="1"
            ;;
        --ocsp-req)
            ocsp_request="1"
            ;;
        --ocsp-resp)
            ocsp_responder="1"
            ;;
         *)
            echo "Unknown option $1"
            usage
            ;;
    esac
    shift
done

# Set the cryptographic parameters, depending on whether to create certificates and key
# material for ISO 15118-2 or ISO 15118-20

if [ $version == $ISO_2 ];
then
    ISO_FOLDER=iso15118_2
    SYMMETRIC_CIPHER=-aes-128-cbc
    SYMMETRIC_CIPHER_PKCS12=-aes128
    SHA=-sha256
    # Note: OpenSSL does not use the named curve 'secp256r1' (as stated in
    # ISO 15118-2) but the equivalent 'prime256v1'
    EC_CURVE=prime256v1
else
    ISO_FOLDER=iso15118_20
    SYMMETRIC_CIPHER=-aes-128-cbc  # TODO Check correct version for ISO 15118-20
    SYMMETRIC_CIPHER_PKCS12=-aes128  # TODO Check correct version for ISO 15118-20
    SHA=-sha256  # TODO Check correct version for ISO 15118-20
    EC_CURVE=prime256v1  # TODO Check correct version for ISO 15118-20
    # TODO: Also enable cipher suite TLS_CHACHA20_POLY1305_SHA256
fi

# The password used to encrypt (and decrypt) private keys
# Security note: this is for testing purposes only!
if [ -z $password ]; then
    password=12345
fi

echo "Password used is: '$password'"

CERT_PATH=$ISO_FOLDER/certs
KEY_PATH=$ISO_FOLDER/private_keys
CSR_PATH=$ISO_FOLDER/csrs
NEWCERT_PATH=$ISO_FOLDER/newcerts

if [ "$ocsp_request" == "1" ];
then
    openssl ocsp -verify_other $CERT_PATH/ocspLocalhost.pem -trust_other -url localhost:8080 -resp_text -issuer $CERT_PATH/cpoSubCA2Cert.pem -cert $CERT_PATH/seccLeafCert.pem
    exit
fi

if [ "$ocsp_responder" == "1" ];
then
    openssl ocsp -host localhost -port 8080 -text -index index.txt -CA $CERT_PATH/cpoSubCA2Cert.pem -rkey $KEY_PATH/ocspLocalhost.key -rsigner $CERT_PATH/ocspLocalhost.pem
    exit
fi

# 0) Create directories if not yet existing
mkdir -p $CERT_PATH
mkdir -p $CSR_PATH
mkdir -p $KEY_PATH
mkdir -p $NEWCERT_PATH
echo -n "" > index.txt
echo "00" > serial
sync


# 1) Create a self-signed V2GRootCA certificate
# ---------------------------------------------
# 1.1) Create a
#	- private key -> -genkey
#	- with elliptic curve parameters -> ecparam
#	- using the chosen named elliptic curve $EC_CURVE -> -name $EC_CURVE
#	- encrypt the key with chosen symmetric cipher $SYMMETRIC_CIPHER using the
#	  'ec' utility command -> ec $SYMMETRIC_CIPHER
# - the passphrase for the encryption of the private key is provided in a file
#   -> -passout pass:$password
#	- save the encrypted private key at the location provided -> -out
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/v2gRootCA.key
# 1.2) Create a certificate signing request (CSR)
#	- new -> -new
#	- certificate signing request -> req
# - using the previously created private key from which the public key can be
#   derived -> -key
#	- use the password to decrypt the private key -> -passin
#	- take the values needed for the Distinguished Name (DN) from the
#	  configuration file -> -config
#	- save the CSR at the location provided -> -out
openssl req -new -key $KEY_PATH/v2gRootCA.key -passin pass:$password -config configs/v2gRootCACert.cnf -out $CSR_PATH/v2gRootCA.csr
# 1.3) Create an X.509 certificate
#	- use the X.509 utility command -> x509
#	- requesting a new X.509 certificate -> -req
#	- using a CSR file that is located at -> -in
#	- we need an X.509v3 (version 3) certificate that allows for extensions.
#	  Those are specified in an extensions file -> -extfile
#	- that contains a section marked with 'ext' -> -extensions
# - self-sign the certificate with the previously generated private key -> -signkey
#	- use the password to decrypt the private key -> -passin
#	- tell OpenSSL to use the chosen hash algorithm $SHA for creating the digital
#	  signature (otherwise SHA1 would be used) -> $SHA
#	- each issued certificate must contain a unique serial number assigned by the CA (must be unique within the issuers number range) -> -set_serial
#	- save the certificate at the location provided -> -out
# 	- make the certificate valid for 40 years (give in days) -> -days
yes | openssl ca -in $CSR_PATH/v2gRootCA.csr -config configs/ca.cnf -extfile configs/v2gRootCACert.cnf -extensions ext -outdir $NEWCERT_PATH -selfsign -keyfile $KEY_PATH/v2gRootCA.key -passin pass:$password -out $CERT_PATH/v2gRootCACert.pem -days $VALIDITY_V2G_ROOT_CERT

# 2) Create an intermediate CPO sub-CA 1 certificate which is directly signed
#    by the V2GRootCA certificate
# ---------------------------------------------------------------------------
# 2.1) Create a private key (same procedure as for V2GRootCA)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/cpoSubCA1.key
# 2.2) Create a CSR (same procedure as for V2GRootCA)
openssl req -new -key $KEY_PATH/cpoSubCA1.key -passin pass:$password -config configs/cpoSubCA1Cert.cnf -out $CSR_PATH/cpoSubCA1.csr
# 2.3) Create an X.509 certificate (same procedure as for V2GRootCA, but with
#      the difference that we need the ‘-CA’ switch to point to the CA
#      certificate, followed by the ‘-CAkey’ switch that tells OpenSSL where to
#      find the CA’s private key. We need the private key to create the signature
#      and the public key certificate to make sure that the CA’s certificate and
#      private key match.
yes | openssl ca -in $CSR_PATH/cpoSubCA1.csr -config configs/ca.cnf -extfile configs/cpoSubCA1Cert.cnf -extensions ext -outdir $NEWCERT_PATH -cert $CERT_PATH/v2gRootCACert.pem -keyfile $KEY_PATH/v2gRootCA.key -passin pass:$password -out $CERT_PATH/cpoSubCA1Cert.pem -days $VALIDITY_CPO_SUBCA1_CERT


# 3) Create a second intermediate CPO sub-CA certificate (sub-CA 2) just the way
#    the previous intermedia certificate was created, which is directly signed
#    by the CPOSubCA1
# Differences between CPOSubCA1 and CPOSubCA2:
#	- basicConstraints in config file sets PathLength to 0 (meaning that no
#	  further sub-CA certificates may be signed with this certificate, a leaf
#	  certificate must follow this certificate in a certificate chain)
#	- validity period differs
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/cpoSubCA2.key
openssl req -new -key $KEY_PATH/cpoSubCA2.key -passin pass:$password -config configs/cpoSubCA2Cert.cnf -out $CSR_PATH/cpoSubCA2.csr
yes | openssl ca -in $CSR_PATH/cpoSubCA2.csr -config configs/ca.cnf -extfile configs/cpoSubCA2Cert.cnf -extensions ext -outdir $NEWCERT_PATH -cert $CERT_PATH/cpoSubCA1Cert.pem -keyfile $KEY_PATH/cpoSubCA1.key -passin pass:$password -days $VALIDITY_CPO_SUBCA2_CERT -out $CERT_PATH/cpoSubCA2Cert.pem


# 4) Create an SECC certificate, which is the leaf certificate belonging to
#    the charging station that authenticates itself to the EVCC during a TLS
#    handshake, signed by CPOSubCA2
# Differences between CPOSubCA2 and SECC certificate:
# - basicConstraints sets CA to false, no PathLength is therefore set
# - keyusage is set to digitalSignature instead of keyCertSign and crlSign
# - validity period differs
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/seccLeaf.key
openssl req -new -key $KEY_PATH/seccLeaf.key -passin pass:$password -config configs/seccLeafCert.cnf -out $CSR_PATH/seccLeafCert.csr
yes | openssl ca -in $CSR_PATH/seccLeafCert.csr -config configs/ca.cnf -extfile configs/seccLeafCert.cnf -extensions ext  -outdir $NEWCERT_PATH -cert $CERT_PATH/cpoSubCA2Cert.pem -keyfile $KEY_PATH/cpoSubCA2.key -passin pass:$password -days $VALIDITY_SECC_LEAF_CERT -out $CERT_PATH/seccLeafCert.pem
# 4.1) Concatenate the SECC certificate with the CPO Sub-2 and Sub-1 certificates to
#      provide a certificate chain that can be used for an SSL context when
#      implementing the TLS handshake
cat $CERT_PATH/seccLeafCert.pem $CERT_PATH/cpoSubCA2Cert.pem $CERT_PATH/cpoSubCA1Cert.pem > $CERT_PATH/cpoCertChain.pem


# 5) Create a self-signed OEMRootCA certificate (validity is up to the OEM)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/oemRootCA.key
openssl req -new -key $KEY_PATH/oemRootCA.key -passin pass:$password -config configs/oemRootCACert.cnf -out $CSR_PATH/oemRootCA.csr
openssl x509 -req -in $CSR_PATH/oemRootCA.csr -extfile configs/oemRootCACert.cnf -extensions ext -signkey $KEY_PATH/oemRootCA.key -passin pass:$password $SHA -set_serial 12349 -out $CERT_PATH/oemRootCACert.pem -days $VALIDITY_OEM_ROOT_CERT


# 6) Create an intermediate OEM sub-CA certificate, which is directly signed by
#    the OEMRootCA certificate (validity is up to the OEM)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/oemSubCA1.key
openssl req -new -key $KEY_PATH/oemSubCA1.key -passin pass:$password -config configs/oemSubCA1Cert.cnf -out $CSR_PATH/oemSubCA1.csr
openssl x509 -req -in $CSR_PATH/oemSubCA1.csr -extfile configs/oemSubCA1Cert.cnf -extensions ext -CA $CERT_PATH/oemRootCACert.pem -CAkey $KEY_PATH/oemRootCA.key -passin pass:$password -set_serial 12350 -days $VALIDITY_OEM_SUBCA1_CERT -out $CERT_PATH/oemSubCA1Cert.pem


# 7) Create a second intermediate OEM sub-CA certificate, which is directly
#    signed by the OEMSubCA1 certificate (validity is up to the OEM)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/oemSubCA2.key
openssl req -new -key $KEY_PATH/oemSubCA2.key -passin pass:$password -config configs/oemSubCA2Cert.cnf -out $CSR_PATH/oemSubCA2.csr
openssl x509 -req -in $CSR_PATH/oemSubCA2.csr -extfile configs/oemSubCA2Cert.cnf -extensions ext -CA $CERT_PATH/oemSubCA1Cert.pem -CAkey $KEY_PATH/oemSubCA1.key -passin pass:$password -set_serial 12351 -days $VALIDITY_OEM_SUBCA2_CERT -out $CERT_PATH/oemSubCA2Cert.pem


# 8) Create an OEM provisioning certificate, which is the leaf certificate
#    belonging to the OEM certificate chain (used for contract certificate
#    installation)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/oemLeaf.key
openssl req -new -key $KEY_PATH/oemLeaf.key -passin pass:$password -config configs/oemLeafCert.cnf -out $CSR_PATH/oemLeafCert.csr
openssl x509 -req -in $CSR_PATH/oemLeafCert.csr -extfile configs/oemLeafCert.cnf -extensions ext -CA $CERT_PATH/oemSubCA2Cert.pem -CAkey $KEY_PATH/oemSubCA2.key -passin pass:$password -set_serial 12352 -days $VALIDITY_OEM_LEAF_CERT -out $CERT_PATH/oemLeafCert.pem
# 8.1) Concatenate the OEM certificate with the OEM Sub-2 and Sub-1 certificates to
#      provide a certificate chain that can be used for an SSL context when
#      implementing the TLS handshake. This applies only to TLS 1.3 for 15118-20
cat $CERT_PATH/oemLeafCert.pem $CERT_PATH/oemSubCA2Cert.pem $CERT_PATH/oemSubCA1Cert.pem > $CERT_PATH/oemCertChain.pem


# 9) Create a self-signed MORootCA (mobility operator) certificate
#    (validity is up to the MO)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/moRootCA.key
openssl req -new -key $KEY_PATH/moRootCA.key -passin pass:$password -config configs/moRootCACert.cnf -out $CSR_PATH/moRootCA.csr
openssl x509 -req -in $CSR_PATH/moRootCA.csr -extfile configs/moRootCACert.cnf -extensions ext -signkey $KEY_PATH/moRootCA.key -passin pass:$password $SHA -set_serial 12353 -out $CERT_PATH/moRootCACert.pem -days $VALIDITY_MO_ROOT_CERT


# 10) Create an intermediate MO sub-CA certificate, which is directly signed by
#     the MORootCA (validity is up to the MO)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/moSubCA1.key
openssl req -new -key $KEY_PATH/moSubCA1.key -passin pass:$password -config configs/moSubCA1Cert.cnf -extensions ext -out $CSR_PATH/moSubCA1.csr
openssl x509 -req -in $CSR_PATH/moSubCA1.csr -extfile configs/moSubCA1Cert.cnf -extensions ext -CA $CERT_PATH/moRootCACert.pem -CAkey $KEY_PATH/moRootCA.key -passin pass:$password -set_serial 12354 -days $VALIDITY_MO_SUBCA1_CERT -out $CERT_PATH/moSubCA1Cert.pem


# 11) Create a second intermediate MO sub-CA certificate, which is directly
#     signed by the MOSubCA1 (validity is up to the MO)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/moSubCA2.key
openssl req -new -key $KEY_PATH/moSubCA2.key -passin pass:$password -config configs/moSubCA2Cert.cnf -out $CSR_PATH/moSubCA2.csr
openssl x509 -req -in $CSR_PATH/moSubCA2.csr -extfile configs/moSubCA2Cert.cnf -extensions ext -CA $CERT_PATH/moSubCA1Cert.pem -CAkey $KEY_PATH/moSubCA1.key -passin pass:$password -set_serial 12355 -days $VALIDITY_MO_SUBCA2_CERT -out $CERT_PATH/moSubCA2Cert.pem


# 12) Create a contract certificate, which is the leaf certificate belonging to
#     the MO certificate chain (used for contract certificate installation)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/contractLeaf.key
openssl req -new -key $KEY_PATH/contractLeaf.key -passin pass:$password -config configs/contractLeafCert.cnf -out $CSR_PATH/contractLeafCert.csr
openssl x509 -req -in $CSR_PATH/contractLeafCert.csr -extfile configs/contractLeafCert.cnf -extensions ext -CA $CERT_PATH/moSubCA2Cert.pem -CAkey $KEY_PATH/moSubCA2.key -passin pass:$password -set_serial 12356 -days $VALIDITY_CONTRACT_LEAF_CERT -out $CERT_PATH/contractLeafCert.pem
# This is how you would put the contract certificate chain and private key in
# a PKCS12 container, if need be:
cat $CERT_PATH/moSubCA2Cert.pem $CERT_PATH/moSubCA1Cert.pem > $CERT_PATH/intermediateMOCACerts.pem
openssl pkcs12 -export -inkey $KEY_PATH/contractLeaf.key -in $CERT_PATH/contractLeafCert.pem -certfile $CERT_PATH/intermediateMOCACerts.pem $SYMMETRIC_CIPHER_PKCS12 -passin pass:$password -passout pass:$password -name contract_leaf_cert -out $CERT_PATH/moCertChain.p12


# 13) Create an intermediate provisioning service sub-CA certificate, which is
#     directly signed by the V2GRootCA
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/cpsSubCA1.key
openssl req -new -key $KEY_PATH/cpsSubCA1.key -passin pass:$password -config configs/cpsSubCA1Cert.cnf -out $CSR_PATH/cpsSubCA1.csr
openssl x509 -req -in $CSR_PATH/cpsSubCA1.csr -extfile configs/cpsSubCA1Cert.cnf -extensions ext -CA $CERT_PATH/v2gRootCACert.pem -CAkey $KEY_PATH/v2gRootCA.key -passin pass:$password -set_serial 12357 -days $VALIDITY_CPS_SUBCA1_CERT -out $CERT_PATH/cpsSubCA1Cert.pem


# 14) Create a second intermediate provisioning sub-CA certificate, which is
#     directly signed by the CPSSubCA1
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/cpsSubCA2.key
openssl req -new -key $KEY_PATH/cpsSubCA2.key -passin pass:$password -config configs/cpsSubCA2Cert.cnf -out $CSR_PATH/cpsSubCA2.csr
openssl x509 -req -in $CSR_PATH/cpsSubCA2.csr -extfile configs/cpsSubCA2Cert.cnf -extensions ext -CA $CERT_PATH/cpsSubCA1Cert.pem -CAkey $KEY_PATH/cpsSubCA1.key -passin pass:$password -set_serial 12358 -days $VALIDITY_CPS_SUBCA2_CERT -out $CERT_PATH/cpsSubCA2Cert.pem


# 15) Create a provisioning service certificate, which is the leaf certificate
#     belonging to the certificate provisioning service chain (used for contract
#     certificate installation)
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/cpsLeaf.key
openssl req -new -key $KEY_PATH/cpsLeaf.key -passin pass:$password -config configs/cpsLeafCert.cnf -out $CSR_PATH/cpsLeafCert.csr
openssl x509 -req -in $CSR_PATH/cpsLeafCert.csr -extfile configs/cpsLeafCert.cnf -extensions ext -CA $CERT_PATH/cpsSubCA2Cert.pem -CAkey $KEY_PATH/cpsSubCA2.key -passin pass:$password -set_serial 12359 -days $VALIDITY_CPS_LEAF_CERT -out $CERT_PATH/cpsLeafCert.pem
cat $CERT_PATH/cpsSubCA2Cert.pem $CERT_PATH/cpsSubCA1Cert.pem > $CERT_PATH/intermediateCPSCACerts.pem
openssl pkcs12 -export -inkey $KEY_PATH/cpsLeaf.key -in $CERT_PATH/cpsLeafCert.pem -certfile $CERT_PATH/intermediateCPSCACerts.pem $SYMMETRIC_CIPHER_PKCS12 -passin pass:$password -passout pass:$password -name cps_leaf_cert -out $CERT_PATH/cpsCertChain.p12


# 16) Finally we need to convert the certificates from PEM format to DER format
#     (PEM is the default format, but ISO 15118 only allows DER format)
openssl x509 -inform PEM -in $CERT_PATH/v2gRootCACert.pem -outform DER -out $CERT_PATH/v2gRootCACert.der
openssl x509 -inform PEM -in $CERT_PATH/cpsSubCA1Cert.pem -outform DER -out $CERT_PATH/cpsSubCA1Cert.der
openssl x509 -inform PEM -in $CERT_PATH/cpsSubCA2Cert.pem -outform DER -out $CERT_PATH/cpsSubCA2Cert.der
openssl x509 -inform PEM -in $CERT_PATH/cpsLeafCert.pem 	-outform DER -out $CERT_PATH/cpsLeafCert.der
openssl x509 -inform PEM -in $CERT_PATH/cpoSubCA1Cert.pem -outform DER -out $CERT_PATH/cpoSubCA1Cert.der
openssl x509 -inform PEM -in $CERT_PATH/cpoSubCA2Cert.pem -outform DER -out $CERT_PATH/cpoSubCA2Cert.der
openssl x509 -inform PEM -in $CERT_PATH/seccLeafCert.pem  -outform DER -out $CERT_PATH/seccLeafCert.der
openssl x509 -inform PEM -in $CERT_PATH/oemRootCACert.pem -outform DER -out $CERT_PATH/oemRootCACert.der
openssl x509 -inform PEM -in $CERT_PATH/oemSubCA1Cert.pem -outform DER -out $CERT_PATH/oemSubCA1Cert.der
openssl x509 -inform PEM -in $CERT_PATH/oemSubCA2Cert.pem -outform DER -out $CERT_PATH/oemSubCA2Cert.der
openssl x509 -inform PEM -in $CERT_PATH/oemLeafCert.pem   -outform DER -out $CERT_PATH/oemLeafCert.der
openssl x509 -inform PEM -in $CERT_PATH/moRootCACert.pem  -outform DER -out $CERT_PATH/moRootCACert.der
openssl x509 -inform PEM -in $CERT_PATH/moSubCA1Cert.pem  -outform DER -out $CERT_PATH/moSubCA1Cert.der
openssl x509 -inform PEM -in $CERT_PATH/moSubCA2Cert.pem  -outform DER -out $CERT_PATH/moSubCA2Cert.der
openssl x509 -inform PEM -in $CERT_PATH/contractLeafCert.pem -outform DER -out $CERT_PATH/contractLeafCert.der
# Since the intermediate certificates need to be in PEM format when putting them
# in a PKCS12 container and the resulting PKCS12 file is a binary format, it
# might be sufficient. Otherwise, I have currently no idea how to covert the
# intermediate certificates in DER without running into problems when creating
# the PKCS12 container.


# 17) In case you want the private keys in PKCS#8 file format and DER encoded,
#     use this command.
openssl pkcs8 -topk8 -in $KEY_PATH/moSubCA2.key -inform PEM -passin pass:$password -passout pass:$password -outform DER -out $KEY_PATH/moSubCA2.pkcs8.der -v1 PBE-SHA1-3DES

# Side notes for OCSP stapling in Java: see http://openjdk.java.net/jeps/249

# 18) Place all passwords to generated private keys in separate text files.
#     In this script, even though we use a single password for all certificates,
#     certificates from a different source could have been generated with a different
#     passphrase/passkey/password altogether. Leave them empty if no password is required.
echo $password > $KEY_PATH/seccLeafPassword.txt
echo $password > $KEY_PATH/oemLeafPassword.txt
echo $password > $KEY_PATH/contractLeafPassword.txt
echo $password > $KEY_PATH/cpsLeafPassword.txt
echo $password > $KEY_PATH/moSubCA2LeafPassword.txt


# 19) Create an OCSP cryptographic pair, signed by cpoSubCA2, allowing us to verify seccLeafCert.
#     The OCSP cryptographic pair must be signed by the same CA that signed the
#     certificate being checked.
openssl ecparam -genkey -name $EC_CURVE | openssl ec $SYMMETRIC_CIPHER -passout pass:$password -out $KEY_PATH/ocspLocalhost.key
openssl req -new -key $KEY_PATH/ocspLocalhost.key -passin pass:$password -config configs/ocspLocalhost.cnf -out $CSR_PATH/ocspLocalhost.csr
openssl x509 -req -in $CSR_PATH/ocspLocalhost.csr -extfile configs/ocspLocalhost.cnf -extensions ext -CA $CERT_PATH/cpoSubCA2Cert.pem -CAkey $KEY_PATH/cpoSubCA2.key -passin pass:$password -out $CERT_PATH/ocspLocalhost.pem


if [ "$keysight_certs" == "1" ];
then
  # The following portion of the script is to help convert the generated certificates work with Keysight test system.
  # The certificates could be used to replace the PKI-Ext folder under "generated-pki" folder
  # For SECC testing, only the certificates for sut_secc folder are generated.
  # TODO: Add an option to generate iso15118 certificates from Keysight provided certs.
  # This could be useful for future Testivals.

  # Target folders
  PKI_EXT="pki-ext"
  SUT_SECC="sut_secc"
  PREFIX="PKI-Ext_CRT"

  # Create directory for Keysight certificates
  CERTS_DIR_SECC=$PKI_EXT/certs/$SUT_SECC
  PRIVATE_KEYS_DIR_SECC=$PKI_EXT/privateKeys/$SUT_SECC

  mkdir -p $CERTS_DIR_SECC
  mkdir -p $PRIVATE_KEYS_DIR_SECC

  # Write passphrase to file.
  echo $password > $PKI_EXT/privateKeys/passphrase.txt

  # Copy all certificates to sut_secc folder. We could simply make a copy of the entire folder too.
  # Leaving it like this so we could see what is going on.
  cp -f $CERT_PATH/v2gRootCACert.pem $CERTS_DIR_SECC/${PREFIX}_V2G_ROOT_VALID.pem
  cp -f $CERT_PATH/cpsSubCA1Cert.pem $CERTS_DIR_SECC/${PREFIX}_CPS_SUB1_VALID.pem
  cp -f $CERT_PATH/cpsSubCA2Cert.pem $CERTS_DIR_SECC/${PREFIX}_CPS_SUB2_VALID.pem
  cp -f $CERT_PATH/cpsLeafCert.pem $CERTS_DIR_SECC/${PREFIX}_CPS_LEAF_VALID.pem

  cp -f $CERT_PATH/cpoSubCA1Cert.pem $CERTS_DIR_SECC/${PREFIX}_CPO_SUB1_VALID.pem
  cp -f $CERT_PATH/cpoSubCA2Cert.pem $CERTS_DIR_SECC/${PREFIX}_CPO_SUB2_VALID.pem
  cp -f $CERT_PATH/seccLeafCert.pem $CERTS_DIR_SECC/${PREFIX}_EVSE_LEAF_VALID.pem

  cp -f $CERT_PATH/oemRootCACert.pem $CERTS_DIR_SECC/${PREFIX}_OEM_ROOT_VALID.pem
  cp -f $CERT_PATH/oemSubCA1Cert.pem $CERTS_DIR_SECC/${PREFIX}_OEM_SUB1_VALID.pem
  cp -f $CERT_PATH/oemSubCA2Cert.pem $CERTS_DIR_SECC/${PREFIX}_OEM_SUB2_VALID.pem
  cp -f $CERT_PATH/oemLeafCert.pem $CERTS_DIR_SECC/${PREFIX}_OEM_LEAF_VALID.pem

  cp -f $CERT_PATH/moRootCACert.pem $CERTS_DIR_SECC/${PREFIX}_MO_ROOT_VALID.pem
  cp -f $CERT_PATH/moSubCA1Cert.pem $CERTS_DIR_SECC/${PREFIX}_MO_SUB1_VALID.pem
  cp -f $CERT_PATH/moSubCA2Cert.pem $CERTS_DIR_SECC/${PREFIX}_MO_SUB2_VALID.pem
  cp -f $CERT_PATH/contractLeafCert.pem $CERTS_DIR_SECC/${PREFIX}_CONTRACT_LEAF_VALID.pem

  # Generate .der versions of the above certificates.
  openssl x509 -inform PEM -in $CERT_PATH/v2gRootCACert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_V2G_ROOT_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/cpsSubCA1Cert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_CPS_SUB1_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/cpsSubCA2Cert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_CPS_SUB2_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/cpsLeafCert.pem 	-outform DER -out $CERTS_DIR_SECC/${PREFIX}_CPS_LEAF_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/cpoSubCA1Cert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_CPO_SUB1_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/cpoSubCA2Cert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_CPO_SUB2_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/seccLeafCert.pem  -outform DER -out $CERTS_DIR_SECC/${PREFIX}_EVSE_LEAF_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/oemRootCACert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_OEM_ROOT_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/oemSubCA1Cert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_OEM_SUB1_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/oemSubCA2Cert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_OEM_SUB2_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/oemLeafCert.pem   -outform DER -out $CERTS_DIR_SECC/${PREFIX}_OEM_LEAF_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/moRootCACert.pem  -outform DER -out $CERTS_DIR_SECC/${PREFIX}_MO_ROOT_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/moSubCA1Cert.pem  -outform DER -out $CERTS_DIR_SECC/${PREFIX}_MO_SUB1_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/moSubCA2Cert.pem  -outform DER -out $CERTS_DIR_SECC/${PREFIX}_MO_SUB2_VALID.der
  openssl x509 -inform PEM -in $CERT_PATH/contractLeafCert.pem -outform DER -out $CERTS_DIR_SECC/${PREFIX}_CONTRACT_LEAF_VALID.der

  # Keysight requires pkcs8 versions of the private keys.
  openssl pkcs8 -topk8 -inform PEM -passin pass:$password -passout pass:$password -outform PEM -nocrypt -in $KEY_PATH/oemLeaf.key -out $PRIVATE_KEYS_DIR_SECC/${PREFIX}_OEM_LEAF_VALID_pkcs8.key
  openssl pkcs8 -topk8 -inform PEM -passin pass:$password -passout pass:$password -outform PEM -nocrypt -in $KEY_PATH/seccLeaf.key -out $PRIVATE_KEYS_DIR_SECC/${PREFIX}_EVSE_LEAF_VALID_pkcs8.key
  openssl pkcs8 -topk8 -inform PEM -passin pass:$password -passout pass:$password -outform PEM -nocrypt -in $KEY_PATH/contractLeaf.key -out $PRIVATE_KEYS_DIR_SECC/${PREFIX}_CONTRACT_LEAF_VALID_pkcs8.key

  # Some Keysight systems expect the certificates in java keystore (.jks) format.
  # The remainder of the script is to generate this.
  KEYSTORE="keystore"
  KEYSTORE_DIR=$PKI_EXT/$KEYSTORE
  mkdir -p $KEYSTORE_DIR

  # This is not the passphrase from the private key. This password is required to open the keystore
  # This should be a minimum of 6 characters which is why we are not reusing the passphrase used above.
  password_keystore=123456
  echo $password_keystore > $KEYSTORE_DIR/password.txt

  # The alias provided is based on certificates received from Keysight in the past
  keytool -import -keystore $KEYSTORE_DIR/truststore.jks -alias v2g_root_ca -file $CERT_PATH/v2gRootCACert.der -storepass:file $KEYSTORE_DIR/password.txt -noprompt

  # 1. To import a certificate with key and chain, first concatenate the sub2 and sub1 in pem format
  # 2. Export the key, corresponding cert and the chain built in step 1 in pkcs12 format. Now we have the entire chain until the leaf node.
  # 3. This can be imported to the keystore. The password required to open the chain is specified in srcstorepass.
  #    The destination - .jks files needs a password and this has to be at least 6 chars.
  # This chain is required by EVCC to build PaymentDetailsReq in 15118-2
  cat $CERT_PATH/moSubCA2Cert.pem $CERT_PATH/moSubCA1Cert.pem > $KEYSTORE_DIR/IntermediateMOCACerts.pem
  openssl pkcs12 -export -inkey $KEY_PATH/contractLeaf.key -in $CERT_PATH/contractLeafCert.pem -name contract_cert -certfile $KEYSTORE_DIR/IntermediateMOCACerts.pem -caname mo_subca_2 -caname mo_subca_1 -aes128 -passin pass:$password -passout pass:$password -out $KEYSTORE_DIR/moCertChain.p12
  keytool -importkeystore -srckeystore $KEYSTORE_DIR/moCertChain.p12 -srcstoretype pkcs12 -srcstorepass $password -srcalias contract_cert -destalias contract_cert -destkeystore $KEYSTORE_DIR/keystore.jks -storepass $password_keystore -noprompt

  cat $CERT_PATH/oemSubCA2Cert.pem $CERT_PATH/oemSubCA1Cert.pem > $KEYSTORE_DIR/IntermediateOEMCACerts.pem
  openssl pkcs12 -export -inkey $KEY_PATH/oemLeaf.key -in $CERT_PATH/oemLeafCert.pem -name oem_leaf -certfile $KEYSTORE_DIR/IntermediateOEMCACerts.pem -caname oem_subca_2 -caname oem_subca_1 -aes128 -passin pass:$password -passout pass:$password -out $KEYSTORE_DIR/oemCertChain.p12
  keytool -importkeystore -srckeystore $KEYSTORE_DIR/oemCertChain.p12 -srcstoretype pkcs12 -srcstorepass $password -srcalias oem_leaf -destalias oem_leaf -destkeystore $KEYSTORE_DIR/keystore.jks -storepass $password_keystore -noprompt

  echo "Certificates for Keysight tests are generated under $PKI_EXT"
fi
