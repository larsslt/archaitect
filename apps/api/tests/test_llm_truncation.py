import json
import pytest
from archaitect.bim import interpret


def setup(monkeypatch, responses):
    monkeypatch.setenv('BIMRENDER_LLM_URL', 'https://example.invalid')
    monkeypatch.setenv('BIMRENDER_LLM_MAX_TOKENS', '12000')
    monkeypatch.setenv('BIMRENDER_LLM_RETRIES', '0')
    monkeypatch.setenv('BIMRENDER_LLM_REASONING', 'high')
    requests = []
    class Response:
        def __init__(self, result): self.result = result
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps({'choices': [self.result]}).encode()
    def call(req, **kwargs):
        requests.append(json.loads(req.data))
        return Response(responses.pop(0))
    monkeypatch.setattr(interpret.urllib.request, 'urlopen', call)
    return requests


@pytest.mark.parametrize('partial', ['', '{"volumes": ['])
def test_truncation_retries_once_with_more_room(monkeypatch, partial):
    calls = setup(monkeypatch, [{'finish_reason': 'length', 'message': {'content': partial}}, {'finish_reason': 'stop', 'message': {'content': '{}'}}])
    assert interpret._openai_compatible([]) == '{}'
    assert len(calls) == 2
    assert calls[1]['max_completion_tokens'] == 24000
    assert calls[1]['reasoning_effort'] == 'low'


def test_repeated_truncation_stops_without_accepting_partial_spec(monkeypatch):
    calls = setup(monkeypatch, [{'finish_reason': 'length', 'message': {'content': '{'}}] * 2)
    with pytest.raises(RuntimeError, match='Antwortbudgets'):
        interpret._openai_compatible([])
    assert len(calls) == 2


def test_read_timeout_does_not_start_duplicate_generation(monkeypatch):
    monkeypatch.setenv('BIMRENDER_LLM_URL', 'https://example.invalid')
    monkeypatch.setenv('BIMRENDER_LLM_RETRIES', '3')
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise TimeoutError('read operation timed out')
    monkeypatch.setattr(interpret.urllib.request, 'urlopen', timeout)
    with pytest.raises(TimeoutError):
        interpret._openai_compatible([])
    assert len(calls) == 1
