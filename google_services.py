"""Gmail y Google Calendar mediante OAuth de escritorio y permisos de lectura."""
import base64
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote
import requests

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/calendar.events.readonly']


class GoogleServices:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path.home() / '.config/jarvis'
        self.token_file = self.directory / 'google-token.json'
        self.message_ids = []

    def connected(self):
        return self.token_file.is_file()

    def save(self, credentials):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        fd, temporary = tempfile.mkstemp(prefix='.token-', dir=self.directory)
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(credentials.to_json())
            Path(temporary).chmod(0o600)
            os.replace(temporary, self.token_file)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def connect(self, client_file):
        from google_auth_oauthlib.flow import InstalledAppFlow
        client_file = Path(client_file).expanduser()
        if client_file.stat().st_size > 100_000:
            raise ValueError('El archivo de credenciales de escritorio no es válido.')
        data = json.loads(client_file.read_text())
        if 'installed' not in data:
            raise ValueError('Descargue un cliente OAuth de tipo aplicación de escritorio.')
        flow = InstalledAppFlow.from_client_config(data, SCOPES)
        credentials = flow.run_local_server(host='127.0.0.1', port=0, open_browser=True,
                                           timeout_seconds=180,
                                           authorization_prompt_message='Autorice a Jarvis en el navegador: {url}',
                                           success_message='Jarvis quedó autorizado. Puede cerrar esta pestaña.')
        if not credentials or not credentials.valid:
            raise ValueError('Google no completó la autorización.')
        self.save(credentials)
        print('Gmail y Google Calendar autorizados para lectura. No se concedieron permisos de envío ni edición.')

    def get(self, service, endpoint, params=None):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        if not self.connected():
            raise ValueError('Primero autorice a Jarvis con --connect-google.')
        credentials = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if not credentials.valid:
            if not credentials.refresh_token:
                raise ValueError('Vuelva a autorizar su cuenta de Google.')
            try:
                credentials.refresh(Request())
            except Exception:
                raise ValueError('Google requiere que vuelva a autorizar Jarvis con --connect-google.') from None
            self.save(credentials)
        base = {'gmail': 'https://gmail.googleapis.com/gmail/v1/users/me/',
                'calendar': 'https://www.googleapis.com/calendar/v3/'}[service]
        response = requests.get(base + endpoint,
                                headers={'Authorization': 'Bearer ' + credentials.token},
                                params=params, timeout=20)
        if response.status_code != 200:
            raise ValueError(f'Google devolvió el error {response.status_code}. Revise las APIs habilitadas y la autorización.')
        return response.json()

    @staticmethod
    def headers(message):
        return {h['name'].lower(): h['value'] for h in message.get('payload', {}).get('headers', [])}

    def inbox(self, unread=False):
        data = self.get('gmail', 'messages', {'maxResults': 5, 'q': 'in:inbox is:unread' if unread else 'in:inbox'})
        self.message_ids = [item['id'] for item in data.get('messages', [])]
        if not self.message_ids:
            return 'No hay correos sin leer en la bandeja de entrada.' if unread else 'La bandeja de entrada está vacía.'
        parts = []
        for i, message_id in enumerate(self.message_ids, 1):
            message = self.get('gmail', 'messages/' + quote(message_id, safe=''),
                               {'format': 'metadata', 'metadataHeaders': ['From', 'Subject']})
            headers = self.headers(message)
            sender = re.sub(r'<[^>]*>', '', headers.get('from', 'remitente desconocido')).strip()
            subject = headers.get('subject', 'sin asunto')
            parts.append(f'{i}: de {sender[:100]}, asunto {subject[:180]}')
        return 'Últimos correos. ' + '; '.join(parts) + '. Puede decir lee el correo uno.'

    def read_mail(self, index):
        if not 1 <= index <= len(self.message_ids):
            raise ValueError('Primero pida mis correos y elija un número de la lista.')
        message = self.get('gmail', 'messages/' + quote(self.message_ids[index-1], safe=''), {'format': 'full'})
        headers = self.headers(message)
        chunks = []
        def collect(part, depth=0):
            if depth > 12:
                return
            if part.get('mimeType') == 'text/plain' and not part.get('filename'):
                data = part.get('body', {}).get('data', '')
                if data:
                    chunks.append(base64.urlsafe_b64decode(data[:100000] + '=' * (-len(data[:100000]) % 4)).decode('utf-8', errors='replace'))
            for child in part.get('parts', [])[:30]:
                collect(child, depth+1)
        collect(message.get('payload', {}))
        content = '\n'.join(chunks).strip() or html.unescape(message.get('snippet', 'Sin texto legible.'))
        return f"De {headers.get('from', 'remitente desconocido')[:150]}. Asunto: {headers.get('subject', 'sin asunto')[:200]}. " + content[:3500]

    def agenda(self, period):
        now = dt.datetime.now().astimezone()
        today = now.date()
        if period == 'tomorrow':
            start_date, end_date = today + dt.timedelta(days=1), today + dt.timedelta(days=2)
        elif period == 'week':
            start_date, end_date = today, today + dt.timedelta(days=7)
        else:
            start_date, end_date = today, today + dt.timedelta(days=1)
        # astimezone sobre fechas locales conserva los cambios de horario de verano.
        start = dt.datetime.combine(start_date, dt.time.min).astimezone()
        end = dt.datetime.combine(end_date, dt.time.min).astimezone()
        if period == 'week':
            start = now
        data = self.get('calendar', 'calendars/primary/events',
                        {'timeMin': start.isoformat(), 'timeMax': end.isoformat(),
                         'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': 10})
        events = data.get('items', [])
        if not events:
            return 'No hay eventos en su calendario principal para ese período.'
        parts = []
        for event in events:
            moment = event.get('start', {})
            if 'dateTime' in moment:
                stamp = dt.datetime.fromisoformat(moment['dateTime'].replace('Z', '+00:00')).astimezone()
                when = stamp.strftime('%d/%m a las %H:%M')
            else:
                when = moment.get('date', '') + ', todo el día'
            parts.append(f"{when}: {event.get('summary', 'evento sin título')[:180]}")
        return 'Su agenda: ' + '; '.join(parts) + '.'
