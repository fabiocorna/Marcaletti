"""Validazione contro lo schema XSD ufficiale di CENED+2.0 (calcolo.xsd e importati).

Gli XSD non sono nel repository: si cercano in $MARCALETTI_RISORSE/SCHEMA_XSD o in
./risorse/SCHEMA_XSD. Serve `lxml`; se manca o mancano gli XSD, `valida` restituisce None.
"""
import os
from functools import lru_cache
from pathlib import Path


def _cartella() -> Path:
    base = os.environ.get("MARCALETTI_RISORSE", str(Path(__file__).resolve().parent.parent / "risorse"))
    return Path(base) / "SCHEMA_XSD"


@lru_cache(maxsize=1)
def _schema():
    try:
        from lxml import etree
    except ImportError:
        return None
    xsd = _cartella() / "calcolo.xsd"
    if not xsd.exists():
        return None
    return etree.XMLSchema(etree.parse(str(xsd)))


def disponibile() -> bool:
    return _schema() is not None


def valida(xml: str | bytes) -> list[str] | None:
    """Lista degli errori di validazione (vuota se valido); None se la validazione non è possibile."""
    schema = _schema()
    if schema is None:
        return None
    from lxml import etree
    doc = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    if schema.validate(doc):
        return []
    return [f"riga {e.line}: {e.message}" for e in schema.error_log]
