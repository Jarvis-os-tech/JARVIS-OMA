"""Explicit calendar wall times with an IST default and no silent offset shifts."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_ZONE = 'Asia/Kolkata'


def calendar_zone(name=DEFAULT_ZONE):
    if name == 'IST':
        name = DEFAULT_ZONE
    if not isinstance(name, str) or not name:
        raise ValueError('Invalid timezone; use an IANA name such as Asia/Kolkata.')
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError('Invalid timezone; use an IANA name such as Asia/Kolkata.') from None


def calendar_datetime(value, zone):
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError('Provide an explicit date and time, for example 2026-10-26T15:00:00.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Invalid calendar date/time; use an ISO date and time.') from None
    if parsed.tzinfo is not None:
        local = parsed.astimezone(zone)
        if parsed.utcoffset() != local.utcoffset():
            raise ValueError('Datetime offset conflicts with the requested timezone; confirm the intended local time instead of shifting it silently.')
        return local
    candidates = []
    for fold in (0, 1):
        candidate = parsed.replace(tzinfo=zone, fold=fold)
        if candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == parsed:
            if not any(item.utcoffset() == candidate.utcoffset() for item in candidates):
                candidates.append(candidate)
    if len(candidates) != 1:
        raise ValueError('Local time is ambiguous or nonexistent in this timezone; provide an explicit valid UTC offset.')
    return candidates[0]


def calendar_interval(start, end, time_zone=DEFAULT_ZONE):
    zone = calendar_zone(time_zone)
    first, last = calendar_datetime(start, zone), calendar_datetime(end, zone)
    if last.astimezone(timezone.utc) <= first.astimezone(timezone.utc):
        raise ValueError('Event end must be after its start.')
    return ({'dateTime': first.isoformat(), 'timeZone': zone.key},
            {'dateTime': last.isoformat(), 'timeZone': zone.key})
