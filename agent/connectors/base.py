from abc import ABC, abstractmethod
from typing import List

from ..models import MetricPoint


class BaseConnector(ABC):
    """Common interface every monitoring tool connector must implement."""

    name: str = "base"

    @abstractmethod
    def fetch(self, lookback_minutes: int) -> List[MetricPoint]:
        """Return the latest metric points for this connector's configured watches."""
        raise NotImplementedError

    def is_configured(self) -> bool:
        """Return False to make the agent skip this connector (e.g. missing credentials)."""
        return True
