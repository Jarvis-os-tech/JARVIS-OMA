"""Retained terminal notices for text jobs in the active voice delivery path."""

TERMINAL = frozenset({'completed', 'failed', 'cancelled'})


def pending_model_notices(desktop):
    jobs = getattr(desktop, '_model_jobs', None)
    if jobs is None:
        return []
    notices = []
    for key, job in jobs.jobs.items():
        state = job.get('status')
        if state not in TERMINAL or job.get('notice_acknowledged'):
            continue
        label = 'Analysis' if job.get('route') == 'reasoning' else 'Text processing'
        if state == 'completed':
            text = f"{label} completed. {str(job.get('result') or 'No result text was returned.')[:2100]}"
        elif state == 'failed':
            text = f"{label} failed: {str(job.get('error') or 'No verified result is available.')[:200]}"
        else:
            text = f"{label} was cancelled."
        notices.append({'id': 'model:' + key, 'text': text})
    return notices


def acknowledge_model_notice(desktop, identity):
    jobs = getattr(desktop, '_model_jobs', None)
    job = jobs.jobs.get(identity.removeprefix('model:')) if jobs is not None else None
    if job is not None and job.get('status') in TERMINAL:
        job['notice_acknowledged'] = True
