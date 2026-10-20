"""Normalize read-only Calendar results for bounded proactive notices."""
from datetime import date, datetime


def calendar_agenda(events, now):
    """Return today's agenda and timed events starting in the next ten minutes."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('calendar observation requires an aware datetime')
    agenda, reminders = [], []
    for event in events:
        if not isinstance(event, dict) or event.get('status') == 'cancelled':
            continue
        raw = event.get('start')
        if not isinstance(raw, str):
            continue
        title = event.get('summary')
        item = {'title': title[:200] if isinstance(title, str) and title else '(no title)'}
        try:
            if len(raw) == 10:
                start_day = date.fromisoformat(raw)
                end_day = date.fromisoformat(event.get('end', raw))
                if start_day == now.date() or start_day <= now.date() < end_day:
                    agenda.append({**item, 'all_day': True, 'start': raw})
                continue
            start = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if start.tzinfo is None or start.utcoffset() is None:
                continue
        except (ValueError, TypeError):
            continue
        local = start.astimezone(now.tzinfo)
        item.update(start=local.isoformat(), all_day=False)
        if local.date() == now.date():
            agenda.append(item)
        seconds = (start - now).total_seconds()
        identity = event.get('id')
        if 0 < seconds <= 600 and isinstance(identity, str) and identity:
            reminders.append({**item, 'id': identity[:1024],
                              'minutes_until': max(1, int((seconds + 59) // 60))})
    agenda.sort(key=lambda item: (not item['all_day'], item['start']))
    reminders.sort(key=lambda item: item['start'])
    return agenda[:50], reminders[:50]
