"""SMTP outbound — send gate surfacing emails with signed resolve URLs.

D-08: Gate surfacing uses plain-text + HTML multipart email via aiosmtplib.
"""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from adapters.email.templates import gate_email_html, gate_email_plain
from adapters.protocol import GateContext

__all__ = ["send_gate_email"]


async def send_gate_email(
    to_addresses: list[str],
    context: GateContext,
    smtp_host: str,
    smtp_port: int = 587,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    from_addr: str = "eclusa@localhost",
) -> None:
    """Send a multipart gate surfacing email via SMTP.

    Builds a plain-text + HTML multipart EmailMessage and sends it via
    aiosmtplib with STARTTLS. Sends to all eligible actors in a single call.
    """
    subject = f"[Eclusa] Gate requires decision: {context.stage_id[:8]}"
    plain_body = gate_email_plain(context)
    html_body = gate_email_html(context)

    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = ", ".join(to_addresses)
    message["Subject"] = subject
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
        start_tls=True,
    )
