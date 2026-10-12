#!/usr/bin/env python3
"""
Zero-Dependency RFC 6455 Chrome DevTools Protocol (CDP) Navigator & Visual Actuator v2.0
(Clean-Room Customer Edition — Zero Proprietary Auth Dependencies).
Features:
1. Pure-Python RFC 6455 WebSocket Client (`StandaloneCDP`) over standard library `socket`/`struct`
2. Shadow-DOM Piercing Interactive Element Collector (`SHADOW_DOM_COLLECTOR_JS`)
3. React Fiber In-Memory File Upload Bypass (`build_react_fiber_upload_js`)
4. Visual Bounding-Box Overlay Injector (`VISUAL_BBOX_OVERLAY_JS`)
"""

import os
import json
import base64
import socket
import struct
import urllib.request
from typing import Dict, Any, List, Optional

SHADOW_DOM_COLLECTOR_JS = r"""
(() => {
  const results = [];
  function walk(root) {
    for (const el of root.querySelectorAll('*')) {
      if (el.shadowRoot) walk(el.shadowRoot);
      const tag = el.tagName.toLowerCase();
      if (['button', 'a', 'input', 'select', 'textarea'].includes(tag) || el.getAttribute('role') === 'button') {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          results.append ? results.append(tag) : results.push({
            tag,
            text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 80),
            x: Math.round(r.x + r.width / 2),
            y: Math.round(r.y + r.height / 2)
          });
        }
      }
    }
  }
  walk(document);
  return results;
})()
"""


def build_react_fiber_upload_js(selector: str, filename: str, mime_type: str, b64_content: str) -> str:
    """Constructs an in-memory File + DataTransfer synthetic React Fiber upload script."""
    return f"""
    (() => {{
      const input = document.querySelector({json.dumps(selector)});
      if (!input) return {{ ok: false, error: 'Selector not found' }};
      const bin = atob({json.dumps(b64_content)});
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const file = new File([bytes], {json.dumps(filename)}, {{ type: {json.dumps(mime_type)} }});
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', {{ bubbles: true }}));
      const fk = Object.keys(input).find(k => k.startsWith('__reactProps$') || k.startsWith('__reactEventHandlers$'));
      if (fk && input[fk] && typeof input[fk].onChange === 'function') {{
        input[fk].onChange({{ target: input, currentTarget: input, nativeEvent: new Event('change') }});
      }}
      return {{ ok: true, filename: file.name, size: file.size }};
    }})()
    """


class StandaloneCDP:
    """Minimal RFC 6455 WebSocket client using only Python stdlib."""
    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port
        self._msg_id = 0

    def list_tabs(self) -> List[Dict[str, Any]]:
        url = f"http://{self.host}:{self.port}/json/list"
        with urllib.request.urlopen(url, timeout=3) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw or "[]")
