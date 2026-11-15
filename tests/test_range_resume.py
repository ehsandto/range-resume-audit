import ast
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "contracts/RangeResumeAudit.py"
URL = "https://www.rfc-editor.org/rfc/rfc20.txt"
BODY = bytes(range(63))
TAG = '"artifact-tag"'
PIN = hashlib.sha256(BODY).hexdigest()


@pytest.fixture
def core():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, ast.ClassDef)
                 and not (isinstance(node, ast.ImportFrom) and node.module == "genlayer")]
    ns = {}
    exec(compile(tree, str(SOURCE), "exec"), ns)
    return ns


def response(status, body=b"", **headers):
    return SimpleNamespace(status=status, body=body, headers=headers)


def server(mode, body=BODY):
    calls = []
    def fetch(url, *, headers):
        assert url == URL and headers["Accept-Encoding"] == "identity"
        field, guard = headers.get("Range"), headers.get("If-Range")
        calls.append((field, guard))
        tag = 'W/"weak"' if mode == "weak" else TAG
        if not field or mode == "ignore" or (guard and guard != TAG and mode != "stale_partial"):
            if mode == "down":
                raise TimeoutError()
            return response(200, body, Etag=tag.encode())
        if field == f"bytes={len(body)}-":
            return response(416, **{"Content-Range": f"bytes */{len(body)}".encode()})
        start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", field).groups())
        chunk = body[start:end + 1]
        cr = f"Bytes {start}-{end}/{len(body)}"
        if field.startswith("bytes=0-"):
            if mode == "mutated":
                chunk = chunk[:-1] + b"\xff"
            if mode == "wrong_extent":
                cr = f"bytes {start}-{end}/{len(body) + 1}"
            if mode == "encoded":
                return response(206, chunk, **{"Content-Range": cr, "Content-Encoding": "gzip"})
            if mode == "duplicate":
                return response(206, chunk, **{"Content-Range": cr, "content-range": cr})
        return response(206, chunk, ETag=tag, **{"Content-Range": cr})
    return fetch, calls


@pytest.mark.parametrize("mode,decision,checks,requests", [
    ("normal", "CONDITIONAL_RESUME", (True, "SAFE_FALLBACK"), 6),
    ("stale_partial", "PINNED_RESUME", (True, "STALE_PARTIAL"), 6),
    ("weak", "PINNED_RESUME", (True, "UNTESTED"), 4),
    ("ignore", "FULL_DOWNLOAD", (False, "SAFE_FALLBACK"), 6),
    ("mutated", "FULL_DOWNLOAD", (False, "SAFE_FALLBACK"), 6),
    ("wrong_extent", "FULL_DOWNLOAD", (False, "SAFE_FALLBACK"), 6),
    ("encoded", "FULL_DOWNLOAD", (False, "SAFE_FALLBACK"), 6),
    ("duplicate", "FULL_DOWNLOAD", (False, "SAFE_FALLBACK"), 6),
    ("down", "INCONCLUSIVE", None, 1),
])
def test_delivery_matrix(core, mode, decision, checks, requests):
    fetch, calls = server(mode)
    result = core["evaluate"](fetch, URL, PIN)
    assert result["decision"] == decision
    assert len(calls) == requests
    if requests > 1:
        assert result["windows"] == [[0, 34], [27, 62]]
        assert calls[:4] == [(None, None), ("bytes=27-62", None),
                            ("bytes=0-34", None), ("bytes=63-", None)]
        found = result["checks"]
        assert (found["overlap_matches"], found["stale_guard"]) == checks
        assert result["assembled_sha256"] == (PIN if checks[0] else None)
        assert found["outside_416"] is (mode != "ignore")


@pytest.mark.parametrize("size", [16, 17, 32, 101, 32768])
def test_overlap_covers_every_byte_at_bounds(core, size):
    body = bytes(i % 251 for i in range(size))
    fetch, _ = server("normal", body)
    report = core["evaluate"](fetch, URL, hashlib.sha256(body).hexdigest())
    a, b = report["windows"]
    assert a[1] - b[0] + 1 == 8
    assert a[0] == 0 and b[1] == size - 1
    assert report["decision"] == "CONDITIONAL_RESUME"


@pytest.mark.parametrize("url", [
    "http://www.rfc-editor.org/rfc/rfc20.txt", URL + "?x=1", URL + "#x",
    "https://www.rfc-editor.org@127.0.0.1/rfc/rfc20.txt",
    "https://raw.githubusercontent.com/org/repo/main/file",
    "https://raw.githubusercontent.com/org/repo/" + "1" * 40 + "/a/../file",
    "https://raw.githubusercontent.com/org/repo/" + "1" * 40 + "/a%2ffile",
])
def test_endpoint_restrictions(core, url):
    assert not core["allowed"](url)


def test_wrong_pin_is_not_an_endpoint_failure(core):
    fetch, calls = server("normal")
    record = core["evaluate"](fetch, URL, "0" * 64)
    assert record["decision"] == "ARTIFACT_MISMATCH"
    assert record["observations"]["full"]["sha256"] == PIN
    assert record["windows"] == [] and len(calls) == 1


def test_direct_namespace_consensus_and_replay(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(str(SOURCE))
    direct_vm.sender = direct_alice
    first = "0x" + bytes(direct_alice).hex()
    reply = {"method": "GET", "response": {"status": 200, "headers": {}, "body": BODY}}
    direct_vm.mock_web(re.escape(URL) + "$", reply)
    report_id = contract.audit("rfc", URL, PIN)
    result = contract.get_audit(first, "rfc")
    assert result["id"] == report_id
    assert result["report"]["decision"] == "FULL_DOWNLOAD"
    assert direct_vm.run_validator()
    forged = {**result["report"], "decision": "CONDITIONAL_RESUME"}
    assert not direct_vm.run_validator(leader_result=json.dumps(forged, sort_keys=True, separators=(",", ":")))
    direct_vm.clear_mocks()
    direct_vm.mock_web(re.escape(URL) + "$", {"method": "GET", "response": {
        "status": 200, "headers": {}, "body": BODY + b"x"}})
    assert not direct_vm.run_validator()
    with direct_vm.expect_revert("Run already recorded"):
        contract.audit("rfc", URL, "0" * 64)
    with direct_vm.expect_revert("Unknown run"):
        contract.get_audit("0x" + "fe" * 20, "rfc")
    with direct_vm.expect_revert("Unsupported artifact URL or SHA-256"):
        contract.audit("bad-url", "https://example.com/file", PIN)
