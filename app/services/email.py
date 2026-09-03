"""Registration verification-code emails via Azure Communication Services."""
import logging
import os
import secrets

AZURE_COMMUNICATION_CONNECTION_STRING = os.environ.get("AZURE_COMMUNICATION_CONNECTION_STRING")
AZURE_SENDER_EMAIL = os.environ.get("AZURE_SENDER_EMAIL", "DoNotReply@yourdomain.azurecomm.net")
VERIFICATION_CODE_TTL_MINUTES = 5
VERIFICATION_RESEND_COOLDOWN_SECONDS = 60

logger = logging.getLogger(__name__)

if AZURE_COMMUNICATION_CONNECTION_STRING:
    logger.info("[Email] Azure Communication Services configured for verification codes")
else:
    logger.warning("[Email] AZURE_COMMUNICATION_CONNECTION_STRING not set — verification emails will not be sent")


def generate_verification_code() -> str:
    """Generate a random 6-digit numeric verification code."""
    return f"{secrets.randbelow(1000000):06d}"


def send_verification_email(to_email: str, code: str, lang: str = "en") -> bool:
    """Send a verification-code email via Azure Communication Services. Returns True on success."""
    if not AZURE_COMMUNICATION_CONNECTION_STRING:
        logger.warning("[Email] AZURE_COMMUNICATION_CONNECTION_STRING not set — skipping send")
        return False

    brand_color = "#5B9A7D"
    bg_color = "#F4F7F5"

    if lang == "zh-HK":
        subject = "你嘅 The Listening Tree 驗證碼"
        greeting = "你好，"
        lead = "多謝你註冊 The Listening Tree！你嘅驗證碼係："
        expiry_note = f"呢個驗證碼將於 <strong>{VERIFICATION_CODE_TTL_MINUTES} 分鐘</strong>後失效。"
        ignore_note = "如果唔係你本人操作，請忽略呢封郵件。"
        footer_note = "呢封係系統自動發出嘅郵件，請勿直接回覆。"
    else:
        subject = "Your The Listening Tree verification code"
        greeting = "Hello,"
        lead = "Thanks for registering with The Listening Tree! Your verification code is:"
        expiry_note = f"This code expires in <strong>{VERIFICATION_CODE_TTL_MINUTES} minutes</strong>."
        ignore_note = "If you did not request this, you can safely ignore this email."
        footer_note = "This is an automated message — please do not reply directly to this email."

    html = f"""\
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:{bg_color}; font-family:'Segoe UI', Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{bg_color}; padding:32px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="background-color:{brand_color}; padding:28px 32px; text-align:center;">
                            <span style="font-size:28px;">🌳</span>
                            <div style="color:#ffffff; font-size:20px; font-weight:600; margin-top:6px;">The Listening Tree</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <p style="margin:0 0 12px; color:#2D3A33; font-size:16px;">{greeting}</p>
                            <p style="margin:0 0 24px; color:#4A554E; font-size:15px; line-height:1.6;">{lead}</p>
                            <div style="text-align:center; margin:0 0 24px;">
                                <span style="display:inline-block; background-color:{bg_color}; border:1px solid #DCE7E1; border-radius:10px; padding:16px 28px; font-size:32px; font-weight:700; letter-spacing:8px; color:{brand_color};">{code}</span>
                            </div>
                            <p style="margin:0 0 8px; color:#6B786F; font-size:13px; line-height:1.6;">{expiry_note}</p>
                            <p style="margin:0; color:#6B786F; font-size:13px; line-height:1.6;">{ignore_note}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px 28px; border-top:1px solid #EEF2EF;">
                            <p style="margin:16px 0 0; color:#9AA69E; font-size:12px; text-align:center;">{footer_note}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    try:
        from azure.communication.email import EmailClient

        client = EmailClient.from_connection_string(AZURE_COMMUNICATION_CONNECTION_STRING)
        message = {
            "senderAddress": AZURE_SENDER_EMAIL,
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "html": html},
        }
        poller = client.begin_send(message)
        result = poller.result()
        status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
        if status and str(status).lower() not in ("succeeded", "running"):
            logger.error(f"[Email] Azure Email send status: {status}")
            return False
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send verification email: {e}")
        return False
