"""Email templates for gate surfacing — plain text and HTML variants.

Plan 05 implements the full template rendering.
"""

from __future__ import annotations

from adapters.protocol import GateContext

__all__ = ["gate_email_plain", "gate_email_html"]


def gate_email_plain(context: GateContext) -> str:
    """Render the plain-text body for a gate surfacing email."""
    recommendation_block = ""
    if context.model_recommendation:
        recommendation_block = (
            f"Model recommendation: {context.model_recommendation}\n\n"
        )

    return (
        "[Eclusa] Gate requires your decision\n\n"
        "A gate in your cascade requires attention.\n\n"
        f"Gate ID: {context.stage_id[:8]}\n"
        f"Description: {context.gate_description}\n"
        f"Cascade: {context.cascade_id}\n\n"
        f"{recommendation_block}"
        "To resolve this gate, visit:\n"
        f"{context.resolve_url}\n\n"
        "This link expires in 72 hours.\n"
        "---\n"
        "Eclusa — every decision traced\n"
    )


def gate_email_html(context: GateContext) -> str:
    """Render the HTML body for a gate surfacing email."""
    recommendation_html = ""
    if context.model_recommendation:
        recommendation_html = (
            f'<blockquote style="border-left: 3px solid #ccc; margin: 16px 0; '
            f'padding: 8px 16px; color: #555;">'
            f"<strong>Model recommendation:</strong> {context.model_recommendation}"
            f"</blockquote>"
        )

    return (
        "<!DOCTYPE html>"
        "<html>"
        '<body style="font-family: sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">'
        '<h2 style="color: #111;">Gate requires your decision</h2>'
        f"<p>{context.gate_description}</p>"
        f"{recommendation_html}"
        '<p style="margin-top: 24px;">'
        f'<a href="{context.resolve_url}" '
        'style="background: #0066cc; color: white; padding: 10px 20px; '
        'text-decoration: none; border-radius: 4px; display: inline-block;">Resolve Gate</a>'
        "</p>"
        f'<p style="color: #555; font-size: 14px;">Or copy this link: {context.resolve_url}</p>'
        f'<small style="color: #999;">Link expires in 72 hours. Gate: {context.stage_id[:8]}</small>'
        "</body>"
        "</html>"
    )
