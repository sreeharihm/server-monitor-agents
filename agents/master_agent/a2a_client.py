"""A2A HTTP client used by the master agent to call sub-agents.

Wraps a single POST /tasks/send call in an error-safe, logged function.
Uses httpx (sync) so it fits naturally into the existing APScheduler poll loop.
"""

import json
import logging
import uuid
from typing import Any, Dict

import httpx

from agents.a2a_schema import Message, TaskSendRequest, TextPart

log = logging.getLogger("a2a-client")

_DEFAULT_TIMEOUT = 10.0  # seconds


class A2AClient:
    """Sends A2A tasks to a remote sub-agent and returns the raw response dict."""

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def send_task(self, agent_url: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """POST a TaskSendRequest to {agent_url}/tasks/send.

        Args:
            agent_url: Base URL of the target A2A agent (e.g. http://localhost:8001).
            input_data: Arbitrary dict that will be JSON-serialized into the
                        first TextPart of the request message.

        Returns:
            Parsed JSON response dict, or an empty dict on any error.
        """
        request = TaskSendRequest(
            id=str(uuid.uuid4()),
            message=Message(
                role="user",
                parts=[TextPart(text=json.dumps(input_data))],
            ),
        )
        endpoint = f"{agent_url.rstrip('/')}/tasks/send"
        try:
            resp = httpx.post(endpoint, json=request.model_dump(), timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            log.warning(f"A2A task timed out calling {endpoint}")
        except httpx.HTTPStatusError as exc:
            log.warning(f"A2A agent {endpoint} returned HTTP {exc.response.status_code}")
        except Exception as exc:  # noqa: BLE001
            log.warning(f"A2A task failed for {endpoint}: {exc}")
        return {}
