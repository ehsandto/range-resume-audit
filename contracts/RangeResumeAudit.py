# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import hashlib
import json
import re

from genlayer import TreeMap, gl

LIMIT = 32768
SCHEMA = "range-resume/v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(body):
    return hashlib.sha256(body).hexdigest()


def allowed(url):
    if len(url) > 256:
        return False
    github = re.fullmatch(
        r"https://raw\.githubusercontent\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+/"
        r"[0-9a-f]{40}/([A-Za-z0-9_./-]+)", url
    )
    if github:
        return all(piece not in ("", ".", "..") for piece in github[1].split("/"))
    return bool(re.fullmatch(r"https://www\.rfc-editor\.org/rfc/rfc[1-9][0-9]{0,4}\.txt", url))


def header(headers, name):
    values = [v for k, v in headers.items() if k.lower() == name]
    if not values:
        return ""
    if len(values) != 1 or not isinstance(values[0], (str, bytes)) or len(values[0]) > 160:
        return None
    try:
        return (values[0].decode("ascii") if isinstance(values[0], bytes) else values[0]).strip(" \t")
    except UnicodeError:
        return None


def strong_tag(tag):
    return tag if tag and re.fullmatch(r'"[!#-~]{0,126}"', tag) else ""


def content_range(value):
    if value == "":
        return []
    if value is None:
        return None
    part = re.fullmatch(r"bytes ([0-9]{1,5})-([0-9]{1,5})/([0-9]{1,5})", value, re.IGNORECASE)
    if part:
        start, end, size = map(int, part.groups())
        return [start, end, size] if start <= end < size else None
    unsat = re.fullmatch(r"bytes \*/([0-9]{1,5})", value, re.IGNORECASE)
    return [int(unsat[1])] if unsat else None


def observe(fetch, url, range_field="", guard=""):
    headers = {"Accept-Encoding": "identity"}
    if range_field:
        headers["Range"] = range_field
    if guard:
        headers["If-Range"] = guard
    try:
        response = fetch(url, headers=headers)
    except Exception:
        return {"http": 0}, None
    status = response.status
    doc = {"http": status}
    if status not in (200, 206, 416):
        return doc, None
    doc["range"] = content_range(header(response.headers, "content-range"))
    if status == 416:
        return doc, None
    encoding = header(response.headers, "content-encoding")
    body = response.body
    bounded = isinstance(body, bytes) and len(body) <= LIMIT
    doc.update({
        "size": len(body) if bounded else None,
        "sha256": sha(body) if bounded else None,
        "identity": encoding is not None and encoding.lower() in ("", "identity"),
        "etag": strong_tag(header(response.headers, "etag")),
    })
    return doc, body if bounded and doc["identity"] else None


def is_full(doc, body):
    return doc["http"] == 200 and doc["range"] == [] and body is not None


def is_part(doc, body, reference, start, end):
    return (
        doc["http"] == 206
        and doc["range"] == [start, end, len(reference)]
        and body == reference[start:end + 1]
    )


def evaluate(fetch, url, expected):
    baseline, full = observe(fetch, url)
    out = {
        "schema": SCHEMA, "url": url, "expected_sha256": expected,
        "decision": "INCONCLUSIVE", "observations": {"full": baseline},
        "windows": [], "assembled_sha256": None, "checks": {},
    }
    if not is_full(baseline, full) or not 16 <= len(full) <= LIMIT:
        return out
    if baseline["sha256"] != expected:
        out["decision"] = "ARTIFACT_MISMATCH"
        return out

    size = len(full)
    seam = size // 2
    # Fetch in reverse assembly order; overlap detects inconsistent middle bytes.
    windows = [[0, seam + 3], [seam - 4, size - 1]]
    out["windows"] = windows
    front_start, front_end = windows[0]
    tail_start, tail_end = windows[1]
    tail_range = f"bytes={tail_start}-{tail_end}"
    tail, tail_body = observe(fetch, url, tail_range)
    front, front_body = observe(fetch, url, f"bytes={front_start}-{front_end}")
    outside, _ = observe(fetch, url, f"bytes={size}-")
    out["observations"].update({"tail": tail, "front": front, "outside": outside})
    front_ok = is_part(front, front_body, full, front_start, front_end)
    tail_ok = is_part(tail, tail_body, full, tail_start, tail_end)
    overlap = front_ok and tail_ok and front_body[tail_start:] == tail_body[:8]
    if overlap:
        out["assembled_sha256"] = sha(front_body + tail_body[8:])

    tag = baseline["etag"]
    fresh = stale = "UNTESTED"
    if tag:
        mismatch = '"rra-stale-' + expected + '"'
        if mismatch == tag:
            mismatch = '"rra-other-' + expected + '"'
        current, cb = observe(fetch, url, tail_range, tag)
        invalid, ib = observe(fetch, url, tail_range, mismatch)
        out["observations"].update({"fresh": current, "stale": invalid})
        fresh = ("PARTIAL_MATCH" if is_part(current, cb, full, tail_start, tail_end)
                 and current["etag"] == tag else "NOT_PROVEN")
        if invalid["http"] == 206:
            stale = "STALE_PARTIAL"
        elif is_full(invalid, ib) and ib == full and invalid["etag"] == tag:
            stale = "SAFE_FALLBACK"
        else:
            stale = "NOT_PROVEN"

    out["checks"] = {
        "front_matches": front_ok, "tail_matches": tail_ok, "overlap_matches": overlap,
        "outside_416": outside["http"] == 416 and outside["range"] == [size],
        "fresh_guard": fresh, "stale_guard": stale,
    }
    out["decision"] = "FULL_DOWNLOAD"
    if out["assembled_sha256"] == expected:
        out["decision"] = ("CONDITIONAL_RESUME" if fresh == "PARTIAL_MATCH" and stale == "SAFE_FALLBACK"
                           else "PINNED_RESUME")
    return out


def key(publisher, run):
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", publisher):
        raise gl.vm.UserError("Invalid publisher address")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", run):
        raise gl.vm.UserError("Invalid run ID")
    return publisher.lower() + ":" + run


class RangeResumeAudit(gl.Contract):
    audits: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def audit(self, run: str, url: str, expected_sha256: str) -> str:
        slot = key(str(gl.message.sender_address), run)
        if slot in self.audits:
            raise gl.vm.UserError("Run already recorded")
        if not allowed(url) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise gl.vm.UserError("Unsupported artifact URL or SHA-256")

        def acquire():
            return canonical(evaluate(gl.nondet.web.get, url, expected_sha256))

        def validate(leader):
            return isinstance(leader, gl.vm.Return) and acquire() == leader.calldata

        agreed = gl.vm.run_nondet_unsafe(acquire, validate)
        self.audits[slot] = agreed
        return sha(agreed.encode("utf-8"))

    @gl.public.view
    def get_audit(self, publisher: str, run: str) -> dict:
        slot = key(publisher, run)
        if slot not in self.audits:
            raise gl.vm.UserError("Unknown run")
        agreed = self.audits[slot]
        return {"id": sha(agreed.encode("utf-8")), "report": json.loads(agreed)}
