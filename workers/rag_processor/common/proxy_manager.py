import requests
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

class ProxyManager:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self._proxy_cache: Optional[Dict] = None
        self._last_fetch_time: Optional[datetime] = None
        self._timeout_seconds: Optional[int] = None

    def _fetch_new_proxy(self) -> Dict:
        """Fetch new proxy from API"""
        response = requests.get(self.api_url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch proxy: {response.status_code}")
        
        data = response.json()
        if data.get("status") != 100:
            raise Exception(f"Invalid proxy response: {data}")
        
        # Extract timeout from message
        timeout_str = data["message"].split("sau ")[1].split("s")[0]
        self._timeout_seconds = int(timeout_str)
        
        return data

    def get_proxy(self) -> Dict:
        """Get current proxy, fetching new one if needed"""
        current_time = datetime.now()
        
        # Check if we need to fetch new proxy
        if (self._proxy_cache is None or 
            self._last_fetch_time is None or 
            self._timeout_seconds is None or
            (current_time - self._last_fetch_time).total_seconds() >= self._timeout_seconds):
            
            self._proxy_cache = self._fetch_new_proxy()
            self._last_fetch_time = current_time
            
        return self._proxy_cache

    def get_http_proxy(self) -> str:
        """Get HTTP proxy string"""
        proxy_data = self.get_proxy()
        proxy_parts = proxy_data["proxyhttp"].split(":")
        return f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"

    def get_socks5_proxy(self) -> str:
        """Get SOCKS5 proxy string"""
        proxy_data = self.get_proxy()
        proxy_parts = proxy_data["proxysocks5"].split(":")
        return f"socks5://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}" 