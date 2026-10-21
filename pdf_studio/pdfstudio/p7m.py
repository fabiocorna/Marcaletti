"""Lettura dei file firmati digitalmente in formato CAdES (.p7m).

Estrae il documento contenuto (anche con buste annidate, es. ``file.pdf.p7m.p7m``),
elenca i firmatari e verifica l'integrità crittografica di ogni firma.
La verifica dell'attendibilità del certificatore (elenco pubblico AgID/eIDAS) non
viene eseguita: lo stato è riportato come informazione, non come validazione legale.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from asn1crypto import cms, core, x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509 import load_der_x509_certificate

P7M_EXTENSIONS = (".p7m", ".p7s")

_HASHES = {
    "sha1": (hashlib.sha1, hashes.SHA1),
    "sha224": (hashlib.sha224, hashes.SHA224),
    "sha256": (hashlib.sha256, hashes.SHA256),
    "sha384": (hashlib.sha384, hashes.SHA384),
    "sha512": (hashlib.sha512, hashes.SHA512),
}


class P7MError(Exception):
    pass


@dataclass
class SignerInfo:
    name: str
    fiscal_code: str = ""
    organization: str = ""
    email: str = ""
    issuer: str = ""
    serial: str = ""
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    signing_time: datetime | None = None
    digest_algorithm: str = ""
    integrity_ok: bool = False
    error: str = ""
    level: int = 1  # livello di busta (1 = più esterna)

    @property
    def cert_valid_at_signing(self) -> bool | None:
        when = self.signing_time or datetime.now(timezone.utc)
        if not self.valid_from or not self.valid_to:
            return None
        return self.valid_from <= when <= self.valid_to

    def summary(self) -> str:
        parts = [f"<b>{self.name}</b>"]
        if self.fiscal_code:
            parts.append(f"Codice fiscale: {self.fiscal_code}")
        if self.organization:
            parts.append(f"Organizzazione: {self.organization}")
        if self.issuer:
            parts.append(f"Certificatore: {self.issuer}")
        if self.signing_time:
            parts.append(f"Data firma: {self.signing_time.astimezone():%d/%m/%Y %H:%M}")
        if self.valid_from and self.valid_to:
            parts.append(f"Certificato valido dal {self.valid_from:%d/%m/%Y} al {self.valid_to:%d/%m/%Y}")
        status = "✔ Firma integra" if self.integrity_ok else f"✘ Firma NON valida: {self.error}"
        parts.append(status)
        validity = self.cert_valid_at_signing
        if validity is False:
            parts.append("⚠ Certificato non valido alla data della firma")
        return "<br>".join(parts)


@dataclass
class P7MContent:
    data: bytes
    filename: str
    signers: list[SignerInfo] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return bool(self.signers) and all(s.integrity_ok for s in self.signers)

    @property
    def is_pdf(self) -> bool:
        return self.data[:1024].lstrip().startswith(b"%PDF") or b"%PDF-" in self.data[:1024]


def _decode_container(raw: bytes) -> bytes:
    """Gestisce p7m in DER, PEM o Base64 semplice."""
    stripped = raw.strip()
    if stripped[:1] == b"\x30":
        return raw
    text = stripped
    if b"-----BEGIN" in text:
        text = re.sub(rb"-----(BEGIN|END)[^-]*-----", b"", text)
    try:
        decoded = base64.b64decode(re.sub(rb"\s+", b"", text), validate=False)
    except Exception as exc:
        raise P7MError("Formato del file non riconosciuto") from exc
    if decoded[:1] != b"\x30":
        raise P7MError("Il file non è una busta firmata PKCS#7/CAdES valida")
    return decoded


def _name_attr(name: x509.Name, key: str) -> str:
    try:
        value = name.native.get(key, "")
    except Exception:
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")


def _fiscal_code(subject: x509.Name) -> str:
    serial = _name_attr(subject, "serial_number")
    # Formato tipico CNS/firma: "TINIT-RSSMRA80A01H501U" o "IT:RSSMRA80A01H501U"
    m = re.search(r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]|\d{11})", serial.upper())
    return m.group(1) if m else serial


def _find_certificate(signed_data, sid) -> x509.Certificate | None:
    for c in signed_data["certificates"] or []:
        if c.name != "certificate":
            continue
        cert = c.chosen
        if sid.name == "issuer_and_serial_number":
            isn = sid.chosen
            if cert.issuer == isn["issuer"] and cert.serial_number == isn["serial_number"].native:
                return cert
        elif sid.name == "subject_key_identifier":
            if cert.key_identifier == sid.chosen.native:
                return cert
    return None


def _verify_signer(signer, signed_data, content: bytes, level: int) -> SignerInfo:
    info = SignerInfo(name="(sconosciuto)", level=level)
    digest_name = signer["digest_algorithm"]["algorithm"].native
    info.digest_algorithm = digest_name
    cert = _find_certificate(signed_data, signer["sid"])
    if cert is None:
        info.error = "certificato del firmatario non presente"
        return info
    subject = cert.subject
    info.name = _name_attr(subject, "common_name") or subject.human_friendly
    info.fiscal_code = _fiscal_code(subject)
    info.organization = _name_attr(subject, "organization_name")
    info.email = _name_attr(subject, "email_address")
    info.issuer = _name_attr(cert.issuer, "organization_name") or _name_attr(cert.issuer, "common_name")
    info.serial = format(cert.serial_number, "x")
    info.valid_from = cert["tbs_certificate"]["validity"]["not_before"].native
    info.valid_to = cert["tbs_certificate"]["validity"]["not_after"].native

    if digest_name not in _HASHES:
        info.error = f"algoritmo {digest_name} non supportato"
        return info
    hashlib_fn, crypto_hash = _HASHES[digest_name]
    signed_attrs = signer["signed_attrs"]
    try:
        if signed_attrs and len(signed_attrs):
            message_digest = None
            for attr in signed_attrs:
                t = attr["type"].native
                if t == "message_digest":
                    message_digest = attr["values"][0].native
                elif t == "signing_time":
                    info.signing_time = attr["values"][0].native
            if message_digest is None:
                info.error = "attributo message-digest mancante"
                return info
            if hashlib_fn(content).digest() != message_digest:
                info.error = "il documento è stato modificato dopo la firma"
                return info
            # La firma è calcolata sugli attributi codificati come SET OF (tag 0x31)
            to_verify = signed_attrs.untag().dump()
            to_verify = b"\x31" + to_verify[1:]
        else:
            to_verify = content
        pub = load_der_x509_certificate(cert.dump()).public_key()
        sig = signer["signature"].native
        if isinstance(pub, rsa.RSAPublicKey):
            sig_alg = signer["signature_algorithm"]["algorithm"].native
            if sig_alg == "rsassa_pss":
                params = signer["signature_algorithm"]["parameters"]
                salt = params["salt_length"].native if params else 20
                pss_hash = _HASHES.get(params["hash_algorithm"]["algorithm"].native, _HASHES[digest_name])[1]
                pub.verify(sig, to_verify, padding.PSS(mgf=padding.MGF1(pss_hash()), salt_length=salt), pss_hash())
            else:
                pub.verify(sig, to_verify, padding.PKCS1v15(), crypto_hash())
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(sig, to_verify, ec.ECDSA(crypto_hash()))
        else:
            info.error = "tipo di chiave non supportato"
            return info
        info.integrity_ok = True
    except InvalidSignature:
        info.error = "la firma non corrisponde al documento"
    except Exception as exc:  # struttura inattesa: la segnaliamo senza bloccare l'apertura
        info.error = f"verifica non riuscita ({exc})"
    return info


def read_p7m(raw: bytes, filename: str = "documento.p7m") -> P7MContent:
    """Estrae il contenuto e verifica le firme, aprendo le buste annidate."""
    signers: list[SignerInfo] = []
    data = raw
    name = filename
    level = 0
    while True:
        level += 1
        try:
            info = cms.ContentInfo.load(_decode_container(data))
            if info["content_type"].native != "signed_data":
                raise P7MError("La busta non contiene dati firmati")
            signed = info["content"]
            content = signed["encap_content_info"]["content"].native
        except P7MError:
            raise
        except Exception as exc:
            raise P7MError(f"Busta firmata non leggibile: {exc}") from exc
        if content is None:
            raise P7MError("Firma 'detached': il documento non è contenuto nel file (.p7s separato)")
        if isinstance(content, core.Any):
            content = content.dump()
        for signer in signed["signer_infos"]:
            signers.append(_verify_signer(signer, signed, content, level))
        data = content
        base, ext = os.path.splitext(name)
        if ext.lower() in P7M_EXTENSIONS:
            name = base
        # Busta annidata?
        if os.path.splitext(name)[1].lower() in P7M_EXTENSIONS or _looks_like_p7m(data):
            continue
        break
    return P7MContent(data=data, filename=os.path.basename(name), signers=signers)


def _looks_like_p7m(data: bytes) -> bool:
    if data[:1] != b"\x30":
        return False
    try:
        info = cms.ContentInfo.load(data)
        return info["content_type"].native == "signed_data"
    except Exception:
        return False


def read_p7m_file(path: str) -> P7MContent:
    with open(path, "rb") as f:
        return read_p7m(f.read(), os.path.basename(path))
