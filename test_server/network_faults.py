"""Deterministic transport errors, alongside real socket faults in main.py."""
import httpx


ERRORS={
    'dns':lambda request:httpx.ConnectError('simulated DNS resolution failed',request=request),
    'connect-timeout':lambda request:httpx.ConnectTimeout('simulated connect timeout',request=request),
    'read-timeout':lambda request:httpx.ReadTimeout('simulated read timeout',request=request),
    'reset':lambda request:httpx.ReadError('simulated TCP reset',request=request),
    'encoding':lambda request:httpx.DecodingError('simulated invalid Content-Encoding',request=request),
}


def transport(name,calls):
    def respond(request):
        calls.append(request.url.path)
        raise ERRORS[name](request)
    return httpx.MockTransport(respond)
