"""EmailAdapter — AdapterProtocol implementation for email channel."""

from __future__ import annotations

import logging

from adapters.email.outbound import send_gate_email
from adapters.protocol import AdapterProtocol, GateContext

logger = logging.getLogger(__name__)

__all__ = ["EmailAdapter"]


class EmailAdapter(AdapterProtocol):
    """Surfaces gates as email threads via SMTP.

    D-06: aiosmtplib for SMTP outbound.
    D-08: Gate surfacing uses a reply-to-resolve pattern (signed URL in body).
    eligible_actor_ids are treated as email addresses in v1.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_addr: str = "eclusa@localhost",
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._from_addr = from_addr

    async def surface_gate(self, context: GateContext) -> None:
        """Send a gate surfacing email to eligible actors.

        For v1: eligible_actor_ids are email addresses (actor.identity column holds email).
        Sends to all eligible actors in a single SMTP call.
        """
        to_addresses = context.eligible_actor_ids
        if not to_addresses:
            logger.warning(
                "Gate %s: no eligible actors — email not sent", context.stage_id
            )
            return
        await send_gate_email(
            to_addresses=to_addresses,
            context=context,
            smtp_host=self._smtp_host,
            smtp_port=self._smtp_port,
            smtp_user=self._smtp_user,
            smtp_password=self._smtp_password,
            from_addr=self._from_addr,
        )
        logger.info(
            "Gate email sent for stage %s to %d actor(s)",
            context.stage_id,
            len(to_addresses),
        )
