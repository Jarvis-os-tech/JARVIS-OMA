"""Workspace adapters extracted from the registry facade."""
from connectors import google_workspace
from skills.errors import SkillError


ADAPTERS = {
    'google.gmail_search': '_adapter_google_gmail_search',
    'google.gmail_read': '_adapter_google_gmail_read',
    'google.gmail_create_draft': '_adapter_google_gmail_create_draft',
    'google.gmail_send_draft': '_adapter_google_gmail_send_draft',
    'google.gmail_list_labels': '_adapter_google_gmail_list_labels',
    'google.calendar_list_events': '_adapter_google_calendar_list_events',
    'google.calendar_get_event': '_adapter_google_calendar_get_event',
    'google.calendar_create_event': '_adapter_google_calendar_create_event',
    'google.calendar_list_calendars': '_adapter_google_calendar_list_calendars',
    'google.calendar_current_time': '_adapter_google_calendar_current_time',
    'google.calendar_update_event': '_adapter_google_calendar_update_event',
    'google.calendar_delete_event': '_adapter_google_calendar_delete_event',
    'google.calendar_check_availability': '_adapter_google_calendar_check_availability',
    'google.calendar_create_calendar': '_adapter_google_calendar_create_calendar',
    'google.calendar_delete_calendar': '_adapter_google_calendar_delete_calendar',
    'google.calendar_add_attachment': '_adapter_google_calendar_add_attachment',
    'google.tasks_list_lists': '_adapter_google_tasks_list_lists',
    'google.tasks_list_tasks': '_adapter_google_tasks_list_tasks',
    'google.tasks_create_task': '_adapter_google_tasks_create_task',
    'google.tasks_complete_task': '_adapter_google_tasks_complete_task',
    'google.google_authorize': '_adapter_google_authorize',
    'google.google_connection_status': '_adapter_google_connection_status',
    'google.drive_search_files': '_adapter_google_drive_search_files',
    'google.drive_get_file': '_adapter_google_drive_get_file',
    'google.drive_read_text_file': '_adapter_google_drive_read_text_file',
    'google.docs_read_document': '_adapter_google_docs_read_document',
    'google.sheets_get_spreadsheet': '_adapter_google_sheets_get_spreadsheet',
    'google.sheets_read_range': '_adapter_google_sheets_read_range',
}

ADAPTER_COMMANDS = {
    'google.gmail_search': (),
    'google.gmail_read': (),
    'google.gmail_create_draft': (),
    'google.gmail_send_draft': (),
    'google.gmail_list_labels': (),
    'google.calendar_list_events': (),
    'google.calendar_get_event': (),
    'google.calendar_create_event': (),
    'google.calendar_list_calendars': (),
    'google.calendar_current_time': (),
    'google.calendar_update_event': (),
    'google.calendar_delete_event': (),
    'google.calendar_check_availability': (),
    'google.calendar_create_calendar': (),
    'google.calendar_delete_calendar': (),
    'google.calendar_add_attachment': (),
    'google.tasks_list_lists': (),
    'google.tasks_list_tasks': (),
    'google.tasks_create_task': (),
    'google.tasks_complete_task': (),
    'google.google_authorize': (),
    'google.google_connection_status': (),
    'google.drive_search_files': (),
    'google.drive_get_file': (),
    'google.drive_read_text_file': (),
    'google.docs_read_document': (),
    'google.sheets_get_spreadsheet': (),
    'google.sheets_read_range': (),
}


class WorkspaceDomain:
    async def _google(self, tool, arguments):
        try:
            result = await google_workspace.dispatch(tool, arguments)
            if isinstance(result, dict) and result.get('setup_required'):
                result.setdefault('message', result.get('error') or
                                  "Say 'open Google authorization' to connect your Google account.")
            return result
        except (OSError, RuntimeError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_google_gmail_search(self, query, max_results=10):
        return await self._google('gmail_search', {'query': query, 'max_results': max_results})

    async def _adapter_google_gmail_read(self, message_id):
        return await self._google('gmail_read', {'message_id': message_id})

    async def _adapter_google_gmail_create_draft(self, to, subject, body, cc=''):
        return await self._google('gmail_create_draft', {'to': to, 'subject': subject, 'body': body, 'cc': cc})

    async def _adapter_google_gmail_send_draft(self, draft_id):
        return await self._google('gmail_send_draft', {'draft_id': draft_id})

    async def _adapter_google_gmail_list_labels(self):
        return await self._google('gmail_list_labels', {})

    async def _adapter_google_calendar_list_events(self, **arguments):
        return await self._google('calendar_list_events', arguments)

    async def _adapter_google_calendar_get_event(self, event_id, calendar_id='primary'):
        return await self._google('calendar_get_event', {'event_id': event_id, 'calendar_id': calendar_id})

    async def _adapter_google_calendar_create_event(self, summary, start_datetime, end_datetime,
                                                    description='', location='', attendees=None,
                                                    calendar_id='primary', time_zone='Asia/Kolkata', recurrence_rule=None, reminder_minutes=None, attachments=None):
        return await self._google('calendar_create_event', {
            'summary': summary, 'start_datetime': start_datetime, 'end_datetime': end_datetime,
            'description': description, 'location': location,
            'attendees': ([item.strip() for item in attendees.split(',') if item.strip()]
                          if isinstance(attendees, str) else attendees),
            'calendar_id': calendar_id, 'time_zone': time_zone,
            'recurrence_rule': recurrence_rule, 'reminder_minutes': reminder_minutes, 'attachments': attachments})

    async def _adapter_google_calendar_current_time(self, **arguments):
        return await self._google('calendar_current_time', arguments)

    async def _adapter_google_calendar_update_event(self, **arguments):
        return await self._google('calendar_update_event', arguments)

    async def _adapter_google_calendar_delete_event(self, **arguments):
        return await self._google('calendar_delete_event', arguments)

    async def _adapter_google_calendar_check_availability(self, **arguments):
        return await self._google('calendar_check_availability', arguments)

    async def _adapter_google_calendar_list_calendars(self):
        return await self._google('calendar_list_calendars', {})

    async def _adapter_google_calendar_create_calendar(self, summary, description='', location='', time_zone='Asia/Kolkata'):
        return await self._google('calendar_create_calendar', {'summary': summary, 'description': description,
                                                               'location': location, 'time_zone': time_zone})

    async def _adapter_google_calendar_delete_calendar(self, calendar_id):
        return await self._google('calendar_delete_calendar', {'calendar_id': calendar_id})

    async def _adapter_google_calendar_add_attachment(self, **arguments):
        return await self._google('calendar_add_attachment', arguments)

    async def _adapter_google_tasks_list_lists(self):
        return await self._google('tasks_list_lists', {})

    async def _adapter_google_tasks_list_tasks(self, list_id='@default'):
        return await self._google('tasks_list_tasks', {'list_id': list_id})

    async def _adapter_google_tasks_create_task(self, title, list_id='@default'):
        return await self._google('tasks_create_task', {'title': title, 'list_id': list_id})

    async def _adapter_google_tasks_complete_task(self, task_id, list_id='@default'):
        return await self._google('tasks_complete_task', {'task_id': task_id, 'list_id': list_id})

    async def _adapter_google_authorize(self):
        return await self._google('google_authorize', {})

    async def _adapter_google_connection_status(self):
        return await self._google('google_connection_status', {})

    async def _adapter_google_drive_search_files(self, query='', max_results=10):
        return await self._google('drive_search_files', {'query': query, 'max_results': max_results})

    async def _adapter_google_drive_get_file(self, file_id):
        return await self._google('drive_get_file', {'file_id': file_id})

    async def _adapter_google_drive_read_text_file(self, file_id):
        return await self._google('drive_read_text_file', {'file_id': file_id})

    async def _adapter_google_docs_read_document(self, document_id):
        return await self._google('docs_read_document', {'document_id': document_id})

    async def _adapter_google_sheets_get_spreadsheet(self, spreadsheet_id):
        return await self._google('sheets_get_spreadsheet', {'spreadsheet_id': spreadsheet_id})

    async def _adapter_google_sheets_read_range(self, spreadsheet_id, cell_range='A1:J25'):
        return await self._google('sheets_read_range', {'spreadsheet_id': spreadsheet_id, 'cell_range': cell_range})


