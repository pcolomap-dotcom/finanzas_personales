"""Catálogo de remitentes de correo de bancos/fintech chilenas.

Basado en la lista de reenvío que usan servicios tipo Kuanto: los bancos envían
avisos de compra, transferencias y cartolas desde estas direcciones. Con este
catálogo el app filtra la casilla y reconoce el banco de cada correo.
"""
from __future__ import annotations

import re

# dirección de correo (minúsculas) -> nombre del banco/fintech
BANK_SENDERS: dict[str, str] = {
    "probando@kuanto.cl": "Kuanto",
    # BICE
    "reply@info.bice.cl": "Banco BICE",
    "biceinforma@bancobice.cl": "Banco BICE",
    "bancobice@eeccvirtual.cl": "Banco BICE",
    # Banco de Chile / Edwards
    "serviciodetransferencias@bancochile.cl": "Banco de Chile",
    "serviciotransferencias@bancochile.cl": "Banco de Chile",
    "enviodigital@bancochile.cl": "Banco de Chile",
    "notificaciones@bancochile.cl": "Banco de Chile",
    "enviodigital@bancoedwards.cl": "Banco Edwards",
    # Falabella / CMR
    "cartoladigital@bancofalabella.cl": "Banco Falabella",
    "notificaciones@cl.bancofalabella.com": "Banco Falabella",
    "estadodecuenta@cmr.cl": "CMR Falabella",
    # Santander
    "mensajeria@santander.cl": "Banco Santander",
    "mensajes@santander.cl": "Banco Santander",
    "bdp@santander.cl": "Banco Santander",
    # BCI / Líder
    "contacto@bci.cl": "BCI",
    "transferencias@bci.cl": "BCI",
    "bcimail@bci.cl": "BCI",
    "bci@eeccvirtual.cl": "BCI",
    "notificaciones@bciplus.cl": "BCI",
    "estadodecuenta@correo.tarjetaliderbci.cl": "Líder BCI",
    # Itaú
    "itau@eeccvirtual.cl": "Itaú",
    "transferencias@itau.cl": "Itaú",
    "itaupersonas@itau.cl": "Itaú",
    "cartola@itau.cl": "Itaú",
    # Scotiabank / Cencosud
    "scotiabank@eeccdigital.cl": "Scotiabank",
    "avisos.info@scotiabank.cl": "Scotiabank",
    "cartolas.info@scotiabank.cl": "Scotiabank",
    "avisos.empresa.info@scotiabank.cl": "Scotiabank",
    "comprobantes.info@scotiabank.cl": "Scotiabank",
    "notificaciones@cencosudscotiabank.cl": "Cencosud Scotiabank",
    # Tenpo
    "no-reply@tenpo.cl": "Tenpo",
    "no-reply@tenpobank.cl": "Tenpo",
    "inversiones@tenpo.cl": "Tenpo",
    # Mach
    "no-reply@mail.machbank.cl": "Mach",
    "contacto@mail.machbank.cl": "Mach",
    "contacto@mail.somosmach.com": "Mach",
    "noreply@somosmach.com": "Mach",
    # BancoEstado
    "bancoestado@correo.bancoestado.cl": "BancoEstado",
    "bancoestado@eeccvirtual.cl": "BancoEstado",
    "notificaciones@correo.bancoestado.cl": "BancoEstado",
    "noreply@correo.bancoestado.cl": "BancoEstado",
    # Mercado Pago
    "info@mercadopago.com": "Mercado Pago",
    # Consorcio
    "bancoconsorcio@bancoconsorcio.cl": "Banco Consorcio",
    "mensajes@bancoconsorcio.cl": "Banco Consorcio",
    # Ripley
    "bancoripleyinforma@bancoripley.com": "Banco Ripley",
    "informaciones@bancoripley.cl": "Banco Ripley",
    # Security
    "noresponder@bancosecurity.cl": "Banco Security",
    # Coopeuch
    "notificaciones@transaccionalcoopeuch.com": "Coopeuch",
    # Copec Pay
    "mensajeria@copecpay.cl": "Copec Pay",
    # Global66
    "contacto@mail.global66.com": "Global66",
    "no-reply@sender.global66.com": "Global66",
    # Los Héroes / Caja Los Andes
    "mensajeria@heroesprepago.cl": "Los Héroes",
    "transferenciaprepago@losheroes.cl": "Los Héroes",
    "no.reply@losandesprepago.cl": "Caja Los Andes",
    # Otros prepago / fintech
    "operaciones@infotapp.cl": "Tapp",
    "hola@fintual.com": "Fintual",
    "donotreply@metromuv.cl": "MetroMuv",
    "info@prexcard.cl": "Prex",
    # Banco Internacional
    "bancointernacional@internacional.cl": "Banco Internacional",
    "bancointernacional@eeccvirtual.cl": "Banco Internacional",
    "no-reply@internacional.cl": "Banco Internacional",
    "transferencias@transferencias.internacional.cl": "Banco Internacional",
}

_EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+")


def extract_address(sender: str | None) -> str:
    """Obtiene la dirección de un header From tipo 'Nombre <a@b.cl>'."""
    m = _EMAIL_RE.search((sender or "").lower())
    return m.group(0) if m else ""


def bank_for_sender(sender: str | None) -> str | None:
    """Devuelve el banco del remitente (exacto o por dominio), o None."""
    addr = extract_address(sender)
    if not addr:
        return None
    if addr in BANK_SENDERS:
        return BANK_SENDERS[addr]
    domain = addr.split("@")[-1]
    for known, bank in BANK_SENDERS.items():
        if known.split("@")[-1] == domain:
            return bank
    return None


def is_bank_sender(sender: str | None) -> bool:
    return bank_for_sender(sender) is not None


def gmail_from_query(since_days: int = 30) -> str:
    """Construye una búsqueda estilo Gmail: from:(a OR b ...) newer_than:Nd."""
    addresses = " OR ".join(sorted(BANK_SENDERS))
    return f"from:({addresses}) newer_than:{since_days}d"
