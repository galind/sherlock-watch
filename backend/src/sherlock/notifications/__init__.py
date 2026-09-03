"""Outbound notification adapters."""

from sherlock.notifications.discord import (
    DiscordWebhookError,
    DiscordWebhookNotifier,
    format_discord_message,
)

__all__ = [
    "DiscordWebhookError",
    "DiscordWebhookNotifier",
    "format_discord_message",
]
