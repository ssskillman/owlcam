from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from animal_identifier.config import (
    ALERT_COOLDOWN_SECONDS,
    ALERT_SLACK_WEBHOOK,
    ALERT_SPECIES,
)
from animal_identifier.store import AlertCooldownStore

logger = logging.getLogger(__name__)


def maybe_send_species_alert(
    *,
    species: str,
    confidence: float,
    source: str,
    cooldowns: AlertCooldownStore,
) -> bool:
    if not ALERT_SLACK_WEBHOOK:
        return False
    normalized = species.strip().lower()
    if normalized not in ALERT_SPECIES:
        return False
    if not cooldowns.may_send(normalized, ALERT_COOLDOWN_SECONDS):
        logger.info("alert cooldown active for %s", normalized)
        return False

    text = (
        f"OwlCam: {species} detected "
        f"(confidence {confidence:.2f}, source {source})"
    )
    body = json.dumps({"text": text}).encode()
    request = urllib.request.Request(
        ALERT_SLACK_WEBHOOK,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 400:
                logger.warning("slack alert HTTP %s", response.status)
                return False
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("slack alert failed: %s", exc)
        return False

    cooldowns.mark_sent(normalized)
    return True
