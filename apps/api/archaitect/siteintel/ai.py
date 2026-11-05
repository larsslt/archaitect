"""AI design generation: text (+ reference images) -> massing, through an exchangeable model provider.

Providers
- ollama (default, local): text model ARCHAITECT_OLLAMA_MODEL (default qwen3:8b), vision model ARCHAITECT_OLLAMA_VISION (default qwen2.5vl:7b),
  host OLLAMA_HOST (default http://localhost:11434). JSON-schema-constrained output via the ``format`` field.
- meta (remote): Meta Model API, OpenAI-compatible (https://api.meta.ai/v1), key META_API_KEY, model ARCHAITECT_META_MODEL (default muse-spark-1.3),
  ``response_format: json_schema``. Photoreal rendering uses /v1/images/edits (muse-image-1.0) with our 3D view as input image.

The model never decides legality: its output is parsed into the massing model, then ``regs.fit`` forces every volume inside the hard limits
(plot, kept buildings, verified B-Plan values) and ``regs.evaluate`` checks it. The model sees the plot only as numbers in a plot-aligned frame.
"""
from __future__ import annotations
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

DEFAULT_PROVIDER = os.environ.get('ARCHAITECT_AI_PROVIDER', 'ollama')


class AIError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------------------- transport
def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 240.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **(headers or {})}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read()[:400].decode('utf-8', 'replace')
        raise AIError(f'{url.split("/")[2]} antwortet {e.code}: {detail}') from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AIError(f'{url.split("/")[2]} nicht erreichbar: {e}') from e


def _get(url: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def ollama_host() -> str:
    return os.environ.get('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')


def status() -> dict:
    out: dict = {'default': DEFAULT_PROVIDER}
    try:
        tags = _get(f'{ollama_host()}/api/tags')
        names = [m['name'] for m in tags.get('models', [])]
        txt = os.environ.get('ARCHAITECT_OLLAMA_MODEL', 'qwen3:8b')
        vis = os.environ.get('ARCHAITECT_OLLAMA_VISION', 'qwen2.5vl:7b')
        out['ollama'] = {'ok': txt in names or vis in names, 'models': names, 'text_model': txt if txt in names else None, 'vision_model': vis if vis in names else None}
    except Exception as e:  # noqa: BLE001
        out['ollama'] = {'ok': False, 'error': str(e)[:160]}
    key = bool(os.environ.get('META_API_KEY'))
    out['meta'] = {'ok': key, 'model': os.environ.get('ARCHAITECT_META_MODEL', 'muse-spark-1.3'), 'image_model': 'muse-image-1.0', 'note': None if key else 'META_API_KEY nicht gesetzt'}
    out['render'] = {'photoreal': key, 'via': 'meta /v1/images/edits' if key else None}
    return out


def complete_json(provider: str, system: str, user: str, schema: dict, images: list[bytes] | None = None) -> tuple[dict, dict]:
    t0 = time.perf_counter()
    images = images or []
    if provider == 'ollama':
        model = os.environ.get('ARCHAITECT_OLLAMA_VISION', 'qwen2.5vl:7b') if images else os.environ.get('ARCHAITECT_OLLAMA_MODEL', 'qwen3:8b')
        msg = {'role': 'user', 'content': user}
        if images:
            msg['images'] = [base64.b64encode(b).decode() for b in images]
        body = {'model': model, 'stream': False, 'format': schema, 'options': {'temperature': 0.3, 'num_ctx': 8192}, 'messages': [{'role': 'system', 'content': system}, msg]}
        if not images:
            body['think'] = False
        j = _post(f'{ollama_host()}/api/chat', body)
        text = j.get('message', {}).get('content', '')
    elif provider == 'meta':
        key = os.environ.get('META_API_KEY')
        if not key:
            raise AIError('Meta-API nicht konfiguriert: META_API_KEY in der Umgebung des Backends setzen.')
        model = os.environ.get('ARCHAITECT_META_MODEL', 'muse-spark-1.3')
        content: list | str = user
        if images:
            content = [{'type': 'text', 'text': user}] + [{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(b).decode()}} for b in images]
        j = _post('https://api.meta.ai/v1/chat/completions', {'model': model, 'temperature': 0.3, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                                                              'response_format': {'type': 'json_schema', 'json_schema': {'name': 'massing', 'schema': schema}}},
                  {'Authorization': f'Bearer {key}'})
        text = j['choices'][0]['message']['content']
    else:
        raise AIError(f'Unbekannter Anbieter: {provider}')
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        s, t = text.find('{'), text.rfind('}')
        if s < 0 or t <= s:
            raise AIError('Modellantwort war kein JSON.') from e
        data = json.loads(text[s:t + 1])
    return data, {'provider': provider, 'model': model, 'ms': round((time.perf_counter() - t0) * 1000)}


# ------------------------------------------------------------------------------------------------------------- images
def prepare_image(data: bytes, media_type: str, max_px: int = 1280) -> bytes | None:
    """Image for a vision model: PDFs -> first page PNG, everything downscaled (macOS sips, else pdftoppm, else as-is if small)."""
    if media_type == 'application/pdf':
        tool = shutil.which('sips') or shutil.which('pdftoppm')
        if not tool:
            return None
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'in.pdf')
            open(src, 'wb').write(data)
            out = os.path.join(d, 'out.png')
            if tool.endswith('sips'):
                subprocess.run([tool, '-s', 'format', 'png', src, '--out', out, '-Z', str(max_px)], capture_output=True, timeout=60)
            else:
                subprocess.run([tool, '-png', '-singlefile', '-scale-to', str(max_px), src, out[:-4]], capture_output=True, timeout=60)
            return open(out, 'rb').read() if os.path.exists(out) else None
    sips = shutil.which('sips')
    if sips and len(data) > 400_000:
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'in.img')
            out = os.path.join(d, 'out.jpg')
            open(src, 'wb').write(data)
            subprocess.run([sips, '-s', 'format', 'jpeg', '-Z', str(max_px), src, '--out', out], capture_output=True, timeout=60)
            if os.path.exists(out):
                return open(out, 'rb').read()
    return data if len(data) <= 6_000_000 else None


# ------------------------------------------------------------------------------------------------------------- plot frame


