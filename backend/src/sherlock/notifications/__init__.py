"""Outbound notification adapters."""

from sherlock.notifications.discord import (
    DiscordWebhookError,
    DiscordWebhookNotifier,
    format_discord_embed,
)

__all__ = [
    "DiscordWebhookError",
    "DiscordWebhookNotifier",
    "format_discord_embed",
]
