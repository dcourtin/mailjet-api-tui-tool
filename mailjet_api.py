import random
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from mailjet_rest import Client

MESSAGE_STATES = {
    1: 'Queued',
    2: 'Sent',
    3: 'Opened',
    4: 'Clicked',
    5: 'Bounced',
    6: 'Spam',
    7: 'Unsubscribed',
    8: 'Blocked',
    9: 'Soft Bounced',
    10: 'Deferred',
}

# Mailjet's API returns lowercase/abbreviated status strings — map them to our display labels
MAILJET_STATUS_TO_DISPLAY = {
    'queued':       'Queued',
    'sent':         'Sent',
    'opened':       'Opened',
    'clicked':      'Clicked',
    'bounce':       'Bounced',
    'hardbounced':  'Bounced',
    'softbounced':  'Soft Bounced',
    'spam':         'Spam',
    'unsub':        'Unsubscribed',
    'blocked':      'Blocked',
    'deferred':     'Deferred',
    'unknown':      'Unknown',
}

class MailjetAPI:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.has_credentials = bool(api_key and api_secret)
        if self.has_credentials:
            self.client = Client(auth=(api_key, api_secret), version='v3')
            self.senders_cache = {}   # SenderID -> email
            self.contacts_cache = {}  # ContactID -> email
        else:
            self.client = None

    def _fetch_senders(self):
        """Pre-populate a cache of SenderID -> email for fallback use."""
        if not self.has_credentials:
            return
        if not self.senders_cache:
            try:
                res = self.client.sender.get(filters={'Limit': 1000})
                if res.status_code == 200:
                    for s in res.json().get('Data', []):
                        self.senders_cache[str(s['ID'])] = s.get('Email', '')
            except Exception:
                pass

    def get_messages(self, limit: int = 250, status: str = None, sender: str = None, recipient: str = None, date_filter: str = None, date_end: str = None) -> List[Dict[str, Any]]:
        """
        Fetch messages from Mailjet or return mock data if not configured.
        """
        if not self.has_credentials:
            return self._generate_mock_data(limit, status, sender, recipient, date_filter, date_end)

        self._fetch_senders()

        # FromTS based on date_filter or today
        if date_filter:
            try:
                start_of_day = datetime.strptime(date_filter, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
        from_ts = start_of_day.strftime("%Y-%m-%dT%H:%M:%S")

        # ToTS : fin du jour de date_end si fourni, sinon fin du jour de date_filter
        if date_end:
            try:
                end_day = datetime.strptime(date_end, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
            except ValueError:
                end_day = start_of_day + timedelta(days=1)
        else:
            end_day = start_of_day + timedelta(days=1)
        to_ts = end_day.strftime("%Y-%m-%dT%H:%M:%S")

        filters = {
            'ShowSubject': 'true',
            'ShowContactAlt': 'true',
            'ShowExtraData': 'true',
            'Limit': limit,
            'FromTS': from_ts,
            'ToTS': to_ts
        }
        # Note: We do NOT pass MessageState here — its integer values don't map
        # reliably to the 'Status' string field. We normalize status in-memory below.

        try:
            res = self.client.message.get(filters=filters)
            if res.status_code == 200:
                data = res.json().get('Data', [])
                processed_data = []
                for d in data:
                    # SenderAlt is returned when ShowExtraData=true — most reliable source
                    sender_email = (
                        d.get('SenderAlt')
                        or self.senders_cache.get(str(d.get('SenderID', '')))
                        or str(d.get('SenderID', 'Unknown'))
                    )
                    # Normalize the raw API status string to a display label
                    raw_status = (d.get('Status') or '').lower()
                    msg_status = MAILJET_STATUS_TO_DISPLAY.get(
                        raw_status,
                        # fallback: try the integer MessageState mapping
                        MESSAGE_STATES.get(d.get('MessageState'), raw_status or 'Unknown')
                    )

                    # Recipient: ContactAlt (now populated thanks to ShowContactAlt=true)
                    rec_email = d.get('ContactAlt', '').strip() or str(d.get('ContactID', 'Unknown'))

                    # Subject: Subject (now populated thanks to ShowSubject=true)
                    msg_subject = d.get('Subject', '').strip() or '—'

                    # In-memory filtering
                    if status and status != 'All' and msg_status.lower() != status.lower():
                        continue
                    if sender and sender.lower() not in sender_email.lower():
                        continue
                    if recipient and recipient.lower() not in rec_email.lower():
                        continue

                    # Parse ArrivedAt to a simpler string
                    arrived_at = d.get('ArrivedAt', '')
                    
                    processed_data.append({
                        'id': d.get('ID'),
                        'sender': sender_email,
                        'recipient': rec_email,
                        'status': msg_status,
                        'time': arrived_at,
                        'subject': msg_subject
                    })
                return processed_data
            else:
                return []
        except Exception as e:
            return [{'id': 'error', 'sender': 'Error fetching API', 'recipient': str(e), 'status': 'Error', 'time': '', 'subject': ''}]

    def _generate_mock_data(self, limit, status, sender, recipient, date_filter=None, date_end=None):
        # Generate some mock data
        states = list(MESSAGE_STATES.values())
        mock_senders = ['contact@example.com', 'noreply@example.com', 'support@example.com']
        mock_recipients = ['alice@test.com', 'bob@test.com', 'charlie@test.com', 'david@test.com']
        mock_subjects = ['Welcome', 'Your Invoice', 'Password Reset', 'Weekly Newsletter']
        
        if date_filter:
            try:
                base_date = datetime.strptime(date_filter, "%Y-%m-%d")
            except ValueError:
                base_date = datetime.now()
        else:
            base_date = datetime.now()
            
        start_of_day = base_date.replace(hour=0, minute=0, second=0, microsecond=0)

        if date_end:
            try:
                end_of_range = datetime.strptime(date_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except ValueError:
                end_of_range = base_date.replace(hour=23, minute=59, second=59)
        else:
            end_of_range = base_date.replace(hour=23, minute=59, second=59)

        # Clamp to now if end_of_range is in the future
        now = datetime.now()
        if end_of_range > now:
            end_of_range = now
        max_minutes = max(1, int((end_of_range - start_of_day).total_seconds() // 60))
        
        data = []
        for i in range(limit):
            mock_time = start_of_day + timedelta(minutes=random.randint(0, max_minutes))
            msg = {
                'id': 1000000 + i,
                'sender': random.choice(mock_senders),
                'recipient': random.choice(mock_recipients),
                'status': random.choice(states),
                'time': mock_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'subject': random.choice(mock_subjects)
            }
            data.append(msg)
            
        data.sort(key=lambda x: x['time'], reverse=True)
            
        # Apply filters
        if status and status != 'All':
            data = [d for d in data if d['status'].lower() == status.lower()]
        if sender:
            data = [d for d in data if sender.lower() in d['sender'].lower()]
        if recipient:
            data = [d for d in data if recipient.lower() in d['recipient'].lower()]
            
        return data
