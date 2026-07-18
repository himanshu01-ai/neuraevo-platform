"""Transactional email templates (Sprint 18.1A).

Pure rendering: each function turns its inputs into a rendered
:class:`EmailMessage`. No I/O, no provider, no business rules. Every template
ships an HTML body and a plain-text fallback with the same information, so the
email is fully usable in a text-only client.

Templates are plain Python string formatting rather than Jinja: the set is
small and fixed, and this keeps the dependency surface unchanged. All
interpolated values are HTML-escaped.
"""

from html import escape

from app.services.email.models import EmailMessage

_BASE_STYLES = (
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
    "Helvetica,Arial,sans-serif;line-height:1.5;color:#0f172a"
)
_BUTTON_STYLES = (
    "display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;"
    "text-decoration:none;border-radius:6px;font-weight:600"
)
_CODE_STYLES = (
    "display:inline-block;padding:12px 20px;background:#f1f5f9;"
    "border:1px solid #e2e8f0;border-radius:6px;font-family:monospace;"
    "font-size:28px;letter-spacing:8px;font-weight:700;color:#0f172a"
)


def _shell(product: str, heading: str, body_html: str) -> str:
    """Wrap a template body in the shared HTML shell."""
    return (
        f'<div style="{_BASE_STYLES};max-width:560px;margin:0 auto;padding:32px 24px">'
        f'<p style="font-size:18px;font-weight:700;margin:0 0 24px">{escape(product)}</p>'
        f'<h1 style="font-size:22px;margin:0 0 16px">{escape(heading)}</h1>'
        f"{body_html}"
        f'<hr style="border:none;border-top:1px solid #e2e8f0;margin:32px 0 16px">'
        f'<p style="font-size:12px;color:#64748b;margin:0">'
        f"You received this email because someone used this address on "
        f"{escape(product)}. If that wasn't you, you can safely ignore it."
        f"</p></div>"
    )


def render_verification_email(
    *, to: str, code: str, product_name: str, expires_minutes: int
) -> EmailMessage:
    """Email carrying a one-time email-verification code."""
    heading = "Confirm your email address"
    body_html = (
        f'<p style="margin:0 0 20px">Enter this code to finish setting up your '
        f"{escape(product_name)} account:</p>"
        f'<p style="margin:0 0 20px"><span style="{_CODE_STYLES}">{escape(code)}</span></p>'
        f'<p style="margin:0;color:#475569">This code expires in '
        f"{expires_minutes} minutes and can only be used once.</p>"
    )
    text_body = (
        f"Confirm your email address\n\n"
        f"Enter this code to finish setting up your {product_name} account:\n\n"
        f"    {code}\n\n"
        f"This code expires in {expires_minutes} minutes and can only be used once.\n\n"
        f"If you didn't create a {product_name} account, you can safely ignore this email."
    )
    return EmailMessage(
        to=to,
        subject=f"Your {product_name} verification code",
        html_body=_shell(product_name, heading, body_html),
        text_body=text_body,
    )


def render_password_reset_email(
    *, to: str, reset_url: str, product_name: str, expires_minutes: int
) -> EmailMessage:
    """Email carrying a single-use password-reset link."""
    heading = "Reset your password"
    safe_url = escape(reset_url, quote=True)
    body_html = (
        f'<p style="margin:0 0 20px">We received a request to reset the password '
        f"for your {escape(product_name)} account. Choose a new one here:</p>"
        f'<p style="margin:0 0 20px"><a href="{safe_url}" style="{_BUTTON_STYLES}">'
        f"Reset password</a></p>"
        f'<p style="margin:0 0 20px;color:#475569">This link expires in '
        f"{expires_minutes} minutes and can only be used once.</p>"
        f'<p style="margin:0;font-size:12px;color:#64748b;word-break:break-all">'
        f"If the button doesn't work, paste this into your browser:<br>{safe_url}</p>"
    )
    text_body = (
        f"Reset your password\n\n"
        f"We received a request to reset the password for your {product_name} "
        f"account. Open this link to choose a new one:\n\n"
        f"    {reset_url}\n\n"
        f"This link expires in {expires_minutes} minutes and can only be used once.\n\n"
        f"If you didn't request a password reset, you can safely ignore this "
        f"email — your password will not change."
    )
    return EmailMessage(
        to=to,
        subject=f"Reset your {product_name} password",
        html_body=_shell(product_name, heading, body_html),
        text_body=text_body,
    )
