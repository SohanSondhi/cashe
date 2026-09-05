"""Host-enforced access policy. Profiles are operator configuration, never model output."""

import json
import re
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from cashe.config import settings


class BrowserPolicyError(ValueError):
    pass


def load_profile(source_id: str) -> dict:
    profiles = json.loads(settings.browser_profiles_path.read_text(encoding="utf-8"))
    if source_id not in profiles:
        raise BrowserPolicyError("browser_profile_not_configured")
    return profiles[source_id]


class PortalPolicy:
    def __init__(self, source: dict, profile: dict, record_id: str):
        if not source["entitlements"].get("browser") or source["permission"] != "read_only":
            raise BrowserPolicyError("read_only_browser_access_required")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", record_id):
            raise BrowserPolicyError("invalid_record_id")
        self.base = urlsplit(source["base_url"].rstrip("/"))
        if (self.base.scheme not in {"http", "https"} or self.base.username or self.base.password
                or self.base.query or self.base.fragment
                or self.base.hostname not in source["allowed_hosts"]):
            raise BrowserPolicyError("invalid_registered_origin")
        self.profile = profile
        self.paths = {self.base.path + path.replace("{record_id}", record_id)
                      for path in profile["read_paths"]}
        self.assets = set(profile.get("asset_paths", []))
        self.entry_url = urlunsplit((self.base.scheme, self.base.netloc,
                                    self.base.path + profile["entry_path"], "", ""))
        if not self.allows(self.entry_url):
            raise BrowserPolicyError("entry_path_not_readable")

    def allows(self, url: str, method: str = "GET", *, resource_type: str = "document") -> bool:
        try:
            target = urlsplit(url)
            if method != "GET" or target.username or target.password:
                return False
            if (target.scheme, target.hostname, target.port) != (self.base.scheme, self.base.hostname, self.base.port):
                return False
            path = unquote(target.path)
            if "\\" in path or "%" in path or any(p in {".", ".."} for p in path.split("/")):
                return False
            if resource_type in {"stylesheet", "image", "font"}:
                return path in self.assets and not target.query
            if resource_type != "document" or path not in self.paths:
                return False
            return all(k in self.profile.get("query_parameters", [])
                       for k, _ in parse_qsl(target.query, keep_blank_values=True))
        except ValueError:
            return False

    def require(self, url: str) -> None:
        if not self.allows(url):
            raise BrowserPolicyError("navigation_outside_registered_read_paths")
