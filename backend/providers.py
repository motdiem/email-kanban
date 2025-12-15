import httpx
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")


def get_date_string(dt: datetime) -> str:
    """Get date string in YYYY-MM-DD format in Paris timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(PARIS_TZ).strftime("%Y-%m-%d")


def get_start_of_week_paris() -> datetime:
    """Get start of current week (Monday) in Paris timezone."""
    now = datetime.now(PARIS_TZ)
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


class MicrosoftProvider:
    """Microsoft Graph API provider."""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    async def get_emails(self, start_date: datetime, shared_mailbox: str = None) -> list:
        """Fetch emails from inbox."""
        start_iso = start_date.isoformat()

        if shared_mailbox:
            endpoint = f"{self.BASE_URL}/users/{shared_mailbox}/mailFolders/inbox/messages"
        else:
            endpoint = f"{self.BASE_URL}/me/mailFolders/inbox/messages"

        all_emails = []
        url = f"{endpoint}?$filter=receivedDateTime ge {start_iso}&$select=id,subject,from,receivedDateTime,webLink,flag&$orderby=receivedDateTime desc&$top=200"

        async with httpx.AsyncClient() as client:
            while url:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()

                for email in data.get("value", []):
                    all_emails.append({
                        "id": email["id"],
                        "subject": email.get("subject") or "(No subject)",
                        "sender": email.get("from", {}).get("emailAddress", {}).get("name")
                                  or email.get("from", {}).get("emailAddress", {}).get("address")
                                  or "Unknown",
                        "receivedDateTime": email["receivedDateTime"],
                        "webLink": email.get("webLink"),
                        "provider": "office365",
                        "isFlagged": email.get("flag", {}).get("flagStatus") == "flagged"
                    })

                url = data.get("@odata.nextLink")

        return all_emails

    async def archive_email(self, email_id: str, shared_mailbox: str = None) -> bool:
        """Move email to archive."""
        if shared_mailbox:
            endpoint = f"{self.BASE_URL}/users/{shared_mailbox}/messages/{email_id}/move"
        else:
            endpoint = f"{self.BASE_URL}/me/messages/{email_id}/move"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                headers=self.headers,
                json={"destinationId": "archive"}
            )
            response.raise_for_status()
            return True

    async def toggle_flag(self, email_id: str, flagged: bool, shared_mailbox: str = None) -> bool:
        """Toggle email flag."""
        if shared_mailbox:
            endpoint = f"{self.BASE_URL}/users/{shared_mailbox}/messages/{email_id}"
        else:
            endpoint = f"{self.BASE_URL}/me/messages/{email_id}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                endpoint,
                headers=self.headers,
                json={"flag": {"flagStatus": "flagged" if flagged else "notFlagged"}}
            )
            response.raise_for_status()
            return True


class GmailProvider:
    """Gmail API provider."""

    BASE_URL = "https://gmail.googleapis.com/gmail/v1"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def get_emails(self, start_date: datetime, gmail_account_number: int = 0) -> list:
        """Fetch emails from inbox."""
        start_timestamp = int(start_date.timestamp())

        async with httpx.AsyncClient() as client:
            # Get message IDs
            all_message_ids = []
            next_page_token = None

            while True:
                url = f"{self.BASE_URL}/users/me/messages?q=in:inbox after:{start_timestamp}&maxResults=100"
                if next_page_token:
                    url += f"&pageToken={next_page_token}"

                response = await client.get(url, headers=self.headers)

                if response.status_code == 429:
                    import asyncio
                    await asyncio.sleep(2)
                    continue

                response.raise_for_status()
                data = response.json()

                all_message_ids.extend(data.get("messages", []))
                next_page_token = data.get("nextPageToken")

                if not next_page_token:
                    break

            # Fetch message details
            emails = []
            for msg in all_message_ids:
                try:
                    response = await client.get(
                        f"{self.BASE_URL}/users/me/messages/{msg['id']}?format=metadata&metadataHeaders=Subject&metadataHeaders=From",
                        headers=self.headers
                    )

                    if not response.is_success:
                        continue

                    data = response.json()
                    headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

                    from_header = headers.get("From", "")
                    sender = from_header.split("<")[0].strip().strip('"') or from_header

                    timestamp = int(data.get("internalDate", 0))
                    received_dt = datetime.fromtimestamp(timestamp / 1000).isoformat() if timestamp else None

                    emails.append({
                        "id": msg["id"],
                        "subject": headers.get("Subject") or "(No subject)",
                        "sender": sender or "Unknown",
                        "receivedDateTime": received_dt,
                        "webLink": f"https://mail.google.com/mail/u/{gmail_account_number}/#inbox/{msg['id']}",
                        "provider": "gmail",
                        "isStarred": "STARRED" in data.get("labelIds", [])
                    })
                except Exception:
                    continue

            return sorted(emails, key=lambda x: x.get("receivedDateTime") or "", reverse=True)

    async def archive_email(self, email_id: str) -> bool:
        """Remove email from inbox."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/users/me/messages/{email_id}/modify",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"removeLabelIds": ["INBOX"]}
            )
            response.raise_for_status()
            return True

    async def toggle_star(self, email_id: str, starred: bool) -> bool:
        """Toggle email star."""
        async with httpx.AsyncClient() as client:
            body = {"addLabelIds": ["STARRED"]} if starred else {"removeLabelIds": ["STARRED"]}
            response = await client.post(
                f"{self.BASE_URL}/users/me/messages/{email_id}/modify",
                headers={**self.headers, "Content-Type": "application/json"},
                json=body
            )
            response.raise_for_status()
            return True


class TickTickProvider:
    """TickTick API provider."""

    BASE_URL = "https://api.ticktick.com/open/v1"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def get_tasks(self) -> list:
        """Fetch all tasks from all projects."""
        async with httpx.AsyncClient() as client:
            # Get projects
            response = await client.get(f"{self.BASE_URL}/project", headers=self.headers)
            response.raise_for_status()
            projects = response.json()

            project_names = {p["id"]: p["name"] for p in projects}

            all_tasks = []

            # Fetch tasks from each project
            for project in projects:
                try:
                    response = await client.get(
                        f"{self.BASE_URL}/project/{project['id']}/data",
                        headers=self.headers
                    )
                    if response.is_success:
                        data = response.json()
                        for task in data.get("tasks", []):
                            task["projectId"] = project["id"]
                            task["projectName"] = project["name"]
                            all_tasks.append(task)
                except Exception:
                    continue

            # Try inbox
            inbox_ids = ["inbox", "INBOX", "none"]
            has_inbox = any(p["id"] in inbox_ids or p.get("name", "").lower() == "inbox" for p in projects)

            if not has_inbox:
                for inbox_id in inbox_ids:
                    try:
                        response = await client.get(
                            f"{self.BASE_URL}/project/{inbox_id}/data",
                            headers=self.headers
                        )
                        if response.is_success:
                            data = response.json()
                            for task in data.get("tasks", []):
                                task["projectId"] = inbox_id
                                task["projectName"] = "Inbox"
                                all_tasks.append(task)
                            break
                    except Exception:
                        continue

            # Filter and transform tasks
            tasks = []
            for task in all_tasks:
                kind = (task.get("kind") or "").upper()
                if kind == "NOTE":
                    continue
                if not task.get("title"):
                    continue
                if not task.get("dueDate") and not task.get("startDate"):
                    continue

                due_date = task.get("dueDate") or task.get("startDate")
                completed_time = task.get("completedTime")

                tasks.append({
                    "id": task["id"],
                    "projectId": task["projectId"],
                    "projectName": task.get("projectName", "Inbox"),
                    "title": task["title"],
                    "content": task.get("content", ""),
                    "dueDate": due_date,
                    "completedTime": completed_time,
                    "isCompleted": task.get("status") == 2,
                    "priority": task.get("priority", 0),
                    "webLink": f"https://ticktick.com/webapp/#p/{task['projectId']}/tasks/{task['id']}",
                    "provider": "ticktick"
                })

            return tasks

    async def complete_task(self, project_id: str, task_id: str) -> bool:
        """Mark task as complete."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/project/{project_id}/task/{task_id}/complete",
                headers=self.headers
            )
            response.raise_for_status()
            return True

    async def uncomplete_task(self, project_id: str, task_id: str) -> bool:
        """Mark task as incomplete."""
        async with httpx.AsyncClient() as client:
            # TickTick API might need different approach for uncomplete
            response = await client.post(
                f"{self.BASE_URL}/project/{project_id}/task/{task_id}",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"status": 0}
            )
            response.raise_for_status()
            return True
