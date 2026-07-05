"""Lectura de emails de aviso bancario por IMAP (Gmail, Outlook, etc.).

Uso típico: crea una contraseña de aplicación en tu proveedor (p. ej. Gmail
"App Password") y configura una regla que reenvíe/etiquete los avisos del banco.
La app se conecta en modo lectura y NO guarda la contraseña.
"""
from __future__ import annotations

import datetime as dt
import email
import imaplib
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

from .bank_senders import bank_for_sender, gmail_from_query, is_bank_sender


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    out = ""
    for text, enc in decode_header(value):
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _body_text(msg: email.message.Message) -> str:
    plain, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get("Content-Disposition", "").startswith("attachment"):
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if ctype == "text/plain":
                plain += content
            elif ctype == "text/html":
                html += content
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        content = payload.decode(charset, errors="replace") if payload else ""
        if msg.get_content_type() == "text/html":
            html = content
        else:
            plain = content
    return plain.strip() or _strip_html(html)


def fetch_bank_emails(
    host: str,
    user: str,
    password: str,
    sender_filter: str | None = None,
    since_days: int = 30,
    folder: str = "INBOX",
    limit: int = 200,
    use_bank_senders: bool = False,
) -> list[dict]:
    """Devuelve dicts {subject, body, sender, date, bank} de emails recientes.

    Si ``use_bank_senders`` es True, filtra a los remitentes bancarios conocidos
    (usando la búsqueda nativa de Gmail cuando está disponible, o filtrando en
    cliente en cualquier otro proveedor).
    """
    conn = imaplib.IMAP4_SSL(host)
    is_gmail = "gmail" in host.lower() or "google" in host.lower()
    try:
        conn.login(user, password)
        conn.select(folder, readonly=True)
        since = (dt.date.today() - dt.timedelta(days=since_days)).strftime("%d-%b-%Y")

        typ = data = None
        if use_bank_senders and is_gmail:
            try:
                typ, data = conn.search(None, "X-GM-RAW", gmail_from_query(since_days))
            except imaplib.IMAP4.error:
                typ = None
        if typ != "OK" or data is None:
            criteria = ["FROM", sender_filter, "SINCE", since] if sender_filter else ["SINCE", since]
            typ, data = conn.search(None, *criteria)
        if typ != "OK":
            return []

        ids = data[0].split()[-limit:]
        out: list[dict] = []
        for msg_id in ids:
            typ, raw = conn.fetch(msg_id, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            sender = _decode_header(msg.get("From"))
            if use_bank_senders and not is_bank_sender(sender):
                continue  # descarta lo que no sea de un banco conocido
            try:
                received = parsedate_to_datetime(msg.get("Date")).date()
            except Exception:
                received = dt.date.today()
            out.append({
                "subject": _decode_header(msg.get("Subject")),
                "sender": sender,
                "body": _body_text(msg),
                "date": received,
                "bank": bank_for_sender(sender),
            })
        return out
    finally:
        try:
            conn.logout()
        except Exception:
            pass
