"""Discord webhook notifications for Turtle Trading alerts."""

import os
from decimal import Decimal

import httpx


def get_webhook_url() -> str:
    """Get Discord webhook URL from environment (checked at runtime)."""
    return os.getenv("DISCORD_WEBHOOK_URL", "")


async def send_discord_alert(
    symbol: str,
    alert_type: str,
    direction: str,
    system: str,
    price: Decimal,
    details: dict | None = None,
) -> bool:
    """Send an alert notification to Discord.

    Args:
        symbol: Market symbol (e.g., "QQQ")
        alert_type: Type of alert (e.g., "ENTRY_SIGNAL")
        direction: Trade direction ("long" or "short")
        system: Trading system ("S1" or "S2")
        price: Signal/trigger price
        details: Additional details (channel_value, n_value, etc.)

    Returns:
        True if sent successfully, False otherwise
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        return False

    # Format the message
    emoji = "🟢" if direction.lower() == "long" else "🔴"
    direction_str = direction.upper()

    # Build message content
    channel_value = details.get("channel_value", "") if details else ""
    n_value = details.get("n_value", "") if details else ""

    message = f"""
{emoji} **{alert_type.replace("_", " ")}** - {symbol}

**Direction:** {direction_str}
**System:** {system}
**Price:** ${float(price):.2f}
"""

    if channel_value:
        message += f"**Channel:** ${float(channel_value):.2f}\n"
    if n_value:
        message += f"**N (ATR):** ${float(n_value):.2f}\n"

    # Discord embed for nicer formatting
    embed = {
        "title": f"{emoji} {symbol} - {system} {direction_str}",
        "description": alert_type.replace("_", " ").title(),
        "color": 0x00FF00 if direction.lower() == "long" else 0xFF0000,
        "fields": [
            {"name": "Price", "value": f"${float(price):.2f}", "inline": True},
            {"name": "System", "value": system, "inline": True},
            {"name": "Direction", "value": direction_str, "inline": True},
        ],
    }

    if channel_value:
        embed["fields"].append(
            {"name": "Channel", "value": f"${float(channel_value):.2f}", "inline": True}
        )
    if n_value:
        embed["fields"].append(
            {"name": "N (ATR)", "value": f"${float(n_value):.2f}", "inline": True}
        )

    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10.0,
            )
            return response.status_code == 204
    except Exception as e:
        print(f"Discord notification failed: {e}")
        return False
