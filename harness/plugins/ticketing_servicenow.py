"""Ticketing plugin "servicenow": creates and reads records through the ServiceNow Table API.

    POST {instance}/api/now/table/{table}            create
    GET  {instance}/api/now/table/{table}/{sys_id}   read

Settings: APP_SERVICENOW_INSTANCE_URL, APP_SERVICENOW_USER, APP_SERVICENOW_TABLE (default
"incident"). The password is read from the secrets provider under the name SERVICENOW_PASSWORD.

Status: written against the documented Table API and tested against a simulated server.
It has not been run against a live ServiceNow instance; field mappings (urgency, impact,
correlation_id) are the standard ones and may need adjusting to your instance's configuration.
"""
from __future__ import annotations

import httpx

from harness.plugins import register
from harness.plugins.secrets import secrets_for
from harness.plugins.ticketing import Ticket, TicketingError, TicketRequest

# ServiceNow: 1 = High, 2 = Medium, 3 = Low (for both urgency and impact).
_SEVERITY = {"critical": ("1", "1"), "high": ("1", "2"), "medium": ("2", "2"), "low": ("3", "3")}


class ServiceNowTicketing:
    def __init__(self, instance_url: str, user: str, password: str, table: str = "incident",
                 transport: httpx.BaseTransport | None = None, timeout_s: float = 20.0):
        if not instance_url.startswith("https://"):
            raise ValueError("APP_SERVICENOW_INSTANCE_URL must be an https:// address")
        if not user or not password:
            raise ValueError("ServiceNow needs APP_SERVICENOW_USER and the SERVICENOW_PASSWORD secret")
        self.instance_url = instance_url.rstrip("/")
        self.table = table
        self._client = httpx.Client(base_url=self.instance_url, auth=(user, password), timeout=timeout_s,
                                    headers={"Accept": "application/json"}, transport=transport)

    def _ticket(self, record: dict) -> Ticket:
        sys_id = record["sys_id"]
        return Ticket(id=sys_id, number=record.get("number", ""), status=str(record.get("state", "")),
                      url=f"{self.instance_url}/nav_to.do?uri={self.table}.do?sys_id={sys_id}")

    def create(self, request: TicketRequest) -> Ticket:
        urgency, impact = _SEVERITY[request.severity]
        body = {"short_description": request.title[:160], "description": request.description,
                "urgency": urgency, "impact": impact,
                "comments": f"Requested by {request.requested_by}"}
        if request.external_ref:
            body["correlation_id"] = request.external_ref
        try:
            response = self._client.post(f"/api/now/table/{self.table}", json=body)
            response.raise_for_status()
            return self._ticket(response.json()["result"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise TicketingError(f"ServiceNow create failed: {type(exc).__name__}") from exc

    def get(self, ticket_id: str) -> Ticket | None:
        try:
            response = self._client.get(f"/api/now/table/{self.table}/{ticket_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._ticket(response.json()["result"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise TicketingError(f"ServiceNow read failed: {type(exc).__name__}") from exc


@register("ticketing", "servicenow")
def build(settings) -> ServiceNowTicketing:
    password = secrets_for(settings).get("SERVICENOW_PASSWORD") or ""
    return ServiceNowTicketing(settings.servicenow_instance_url, settings.servicenow_user, password,
                               settings.servicenow_table)
