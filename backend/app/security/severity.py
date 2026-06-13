from enum import Enum


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def coerce(cls, value: "Severity | str") -> "Severity":
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().upper()
        try:
            return cls(normalized)
        except ValueError:
            return cls.LOW
