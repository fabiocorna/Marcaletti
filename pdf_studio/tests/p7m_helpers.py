"""Genera buste .p7m di prova con un certificato autofirmato."""
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID


def make_cert(name="Mario Rossi", cf="RSSMRA80A01H501U", key_type="rsa"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if key_type == "rsa" \
        else ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, name),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, f"TINIT-{cf}"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
    ])
    issuer = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CA di Prova"),
                        x509.NameAttribute(NameOID.COMMON_NAME, "CA di Prova")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365)).sign(key, hashes.SHA256()))
    return cert, key


def sign(data: bytes, cert=None, key=None, encoding=serialization.Encoding.DER) -> bytes:
    if cert is None:
        cert, key = make_cert()
    return (pkcs7.PKCS7SignatureBuilder().set_data(data).add_signer(cert, key, hashes.SHA256())
            .sign(encoding, [pkcs7.PKCS7Options.Binary]))
