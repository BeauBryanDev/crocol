"""Validate the project secrets in .env without ever printing secret values.

Checks:
  - required keys present, non-empty, unquoted, no spaces, no '$' (docker compose interpolation)
  - formats: Chroma host/tenant/key prefix, Anthropic and OpenAI key prefixes
  - embedding providers: OpenAI key + model availability, Google key (optional)
  - PG_DSN consistent with POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_PORT
  - .env file permissions
  - Chroma Cloud: authentication, tenant, database, collection, count, index schema
  - PostgreSQL: host port availability, and connectivity + PostGIS if the server is up

Usage:
    magdalena/bin/python pipelines/check_env.py [--env .env] [--skip-chroma] [--skip-postgres] [--skip-providers]

Exit code 0 when every check passes, 1 otherwise.
"""

import argparse
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values

REQUIRED_KEYS = [
    "CHROMA_HOST", "CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE", "COLLECTION_NAME",
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "PG_DSN", "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]
OPTIONAL_KEYS = ["GOOGLE_API_KEY", "POSTGRES_PORT", "CROCO_MEMORY_KEY"]
MEMORY_KEY_MIN_BYTES = 32
OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_PG_PORT = 5445
CHROMA_HOSTS = {"api.trychroma.com"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
HTTP_TIMEOUT = 20


class Report:
    def __init__(self):
        self.failures = 0
        self.warnings = 0

    def ok(self, label, detail=""):
        print(f"  OK    {label}" + (f": {detail}" if detail else ""))

    def warn(self, label, detail=""):
        self.warnings += 1
        print(f"  WARN  {label}" + (f": {detail}" if detail else ""))

    def fail(self, label, detail=""):
        self.failures += 1
        print(f"  FAIL  {label}" + (f": {detail}" if detail else ""))

    def check(self, condition, label, detail_ok="", detail_fail=""):
        if condition:
            self.ok(label, detail_ok)
        else:
            self.fail(label, detail_fail)
        return condition


def raw_values(path):
    values = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = (number, value)
    return values


def check_file(path, report):
    print("File")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        report.warn(".env permissions", f"{oct(mode)[2:]}; run 'chmod 600 {path.name}'")
    else:
        report.ok(".env permissions", oct(mode)[2:])


def check_keys(path, env, report):
    print("Keys")
    raw = raw_values(path)
    for key in REQUIRED_KEYS + OPTIONAL_KEYS:
        if key not in raw:
            if key in REQUIRED_KEYS:
                report.fail(key, "missing")
            else:
                report.ok(key, "not set (optional)")
            continue
        number, value = raw[key]
        problems = []
        if value != value.strip():
            problems.append("leading/trailing whitespace")
        if value.strip()[:1] in {"'", '"'}:
            problems.append("quoted")
        if not (env.get(key) or "").strip():
            problems.append("empty")
        if "$" in value:
            problems.append("contains '$' (escape as '$$' for docker compose)")
        if " " in value.strip():
            problems.append("contains a space")
        if problems:
            report.fail(f"{key} (line {number})", ", ".join(problems))
        else:
            report.ok(key, f"set, length {len(env[key])}")


def check_formats(env, report):
    print("Formats")
    report.check(env.get("CHROMA_HOST") in CHROMA_HOSTS, "CHROMA_HOST",
                 "official Chroma Cloud endpoint", "unexpected host")
    report.check(bool(UUID_RE.fullmatch(env.get("CHROMA_TENANT") or "")), "CHROMA_TENANT",
                 "UUID", "not a UUID")
    report.check((env.get("CHROMA_API_KEY") or "").startswith("ck-"), "CHROMA_API_KEY",
                 "prefix ck-", "unexpected prefix")
    report.check((env.get("ANTHROPIC_API_KEY") or "").startswith("sk-ant-"), "ANTHROPIC_API_KEY",
                 "prefix sk-ant-", "unexpected prefix")
    report.check((env.get("OPENAI_API_KEY") or "").startswith("sk-"), "OPENAI_API_KEY",
                 "prefix sk-", "unexpected prefix")
    report.check(len((env.get("CROCO_MEMORY_KEY") or "").encode()) >= MEMORY_KEY_MIN_BYTES,
                 "CROCO_MEMORY_KEY", f">= {MEMORY_KEY_MIN_BYTES} bytes",
                 "missing or too short: follow-up memory is off")


def http_get_json(url, headers):
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return None, str(getattr(exc, "reason", exc))


def check_embedding_providers(env, report):
    print("Embedding providers")
    status, body = http_get_json(f"https://api.openai.com/v1/models/{OPENAI_EMBEDDING_MODEL}",
                                 {"Authorization": f"Bearer {env['OPENAI_API_KEY']}"})
    report.check(status == 200, "OpenAI", f"key accepted, {OPENAI_EMBEDDING_MODEL} available",
                 f"status {status}")
    if not env.get("GOOGLE_API_KEY"):
        return
    status, body = http_get_json(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
        {"x-goog-api-key": env["GOOGLE_API_KEY"]},
    )
    if status == 200:
        models = [m["name"].split("/")[-1] for m in body.get("models", [])
                  if "embedContent" in m.get("supportedGenerationMethods", [])]
        report.ok("Google", f"key accepted, embedding models: {', '.join(models) or 'none'}")
    else:
        report.fail("Google", f"status {status}")


def pg_port(env):
    return int(env.get("POSTGRES_PORT") or DEFAULT_PG_PORT)


def check_dsn(env, report):
    print("PostgreSQL DSN")
    try:
        dsn = urlsplit(env.get("PG_DSN") or "")
        port = dsn.port
    except ValueError as exc:
        report.fail("PG_DSN", f"cannot parse ({exc.__class__.__name__})")
        return
    report.check(dsn.scheme in {"postgresql", "postgres"}, "scheme", dsn.scheme, dsn.scheme or "none")
    report.check(dsn.hostname in {"127.0.0.1", "localhost"}, "host", dsn.hostname or "",
                 f"{dsn.hostname}; the container is bound to 127.0.0.1 only")
    expected = pg_port(env)
    report.check(port == expected, "port", str(port),
                 f"{port} but docker-compose publishes {expected}; set the PG_DSN port to {expected}")
    report.check(dsn.username == env.get("POSTGRES_USER"), "user matches POSTGRES_USER")
    report.check(dsn.path.lstrip("/") == env.get("POSTGRES_DB"), "database matches POSTGRES_DB")
    report.check(unquote(dsn.password or "") == env.get("POSTGRES_PASSWORD"),
                 "password matches POSTGRES_PASSWORD")


def chroma_get(env, path):
    url = f"https://{env['CHROMA_HOST']}/api/v2{path}"
    request = urllib.request.Request(url, headers={"x-chroma-token": env["CHROMA_API_KEY"]})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return None, str(getattr(exc, "reason", exc))


def describe_schema(collection):
    config = collection.get("configuration_json") or {}
    schema = collection.get("schema") or config.get("schema") or {}
    dense = ((schema.get("defaults") or {}).get("float_list") or {}).get("vector_index") or {}
    dense_cfg = dense.get("config") or {}
    keys = schema.get("keys") or {}
    sparse = []
    for name, spec in keys.items():
        index = (spec.get("sparse_vector") or {}).get("sparse_vector_index") or {}
        if index.get("enabled"):
            sparse.append(f"{name}{' (bm25)' if (index.get('config') or {}).get('bm25') else ''}")
    ef = (dense_cfg.get("embedding_function") or config.get("embedding_function") or {}).get("name")
    return ef, dense_cfg.get("space"), sparse


def check_chroma(env, report):
    print("Chroma Cloud")
    status, identity = chroma_get(env, "/auth/identity")
    if not report.check(status == 200, "authentication", "API key accepted", f"status {status}"):
        return
    report.check(identity.get("tenant") == env["CHROMA_TENANT"], "tenant matches CHROMA_TENANT")
    databases = identity.get("databases") or []
    report.check(env["CHROMA_DATABASE"] in databases, "database visible to key",
                 env["CHROMA_DATABASE"], f"key sees {databases}")
    base = f"/tenants/{env['CHROMA_TENANT']}/databases/{env['CHROMA_DATABASE']}/collections"
    status, collections = chroma_get(env, base)
    if not report.check(status == 200, "list collections", detail_fail=f"status {status}"):
        return
    match = [c for c in collections if c.get("name") == env["COLLECTION_NAME"]]
    if not match:
        report.warn("collection", f"{env['COLLECTION_NAME']} not created yet")
        return
    collection = match[0]
    _, count = chroma_get(env, f"{base}/{collection['id']}/count")
    report.ok("collection", f"{env['COLLECTION_NAME']} exists, {count} records")
    embedding_function, space, sparse = describe_schema(collection)
    if embedding_function == "default" or not sparse:
        report.warn("collection schema",
                    f"dense ef={embedding_function}, space={space}, sparse indexes={sparse or 'none'}; "
                    "the plan needs precomputed BGE-M3 (1024-d, cosine) plus bm25 and sparse keys")
    else:
        report.ok("collection schema", f"dense ef={embedding_function}, space={space}, sparse={sparse}")


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def container_running(name="vmm-postgis"):
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "ps", "-q", "--filter", f"name=^{name}$"],
                            capture_output=True, text=True, timeout=20, check=False)
    return bool(result.stdout.strip())


def check_postgres(env, report):
    print("PostgreSQL server")
    port = pg_port(env)
    running = container_running()
    if not running:
        if port_in_use(port):
            report.fail(f"host port {port}", "already used by another process; pick another POSTGRES_PORT")
        else:
            report.ok(f"host port {port}", "free; container not started yet (connectivity check skipped)")
        return
    if not shutil.which("psql"):
        report.warn("psql", "client not installed; connectivity check skipped")
        return
    child_env = {
        "PATH": os.environ.get("PATH", ""),
        "PGHOST": "127.0.0.1",
        "PGPORT": str(port),
        "PGUSER": env["POSTGRES_USER"],
        "PGPASSWORD": env["POSTGRES_PASSWORD"],
        "PGDATABASE": env["POSTGRES_DB"],
        "PGCONNECT_TIMEOUT": "5",
    }
    query = ("SELECT current_setting('server_version') || ' | ' || "
             "coalesce((SELECT extversion FROM pg_extension WHERE extname = 'postgis'), "
             "'postgis available: ' || (SELECT default_version FROM pg_available_extensions "
             "WHERE name = 'postgis'))")
    result = subprocess.run(["psql", "-X", "-At", "-c", query], env=child_env,
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode == 0:
        report.ok("connect", result.stdout.strip())
    else:
        report.fail("connect", (result.stderr.strip().splitlines() or ["unknown error"])[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", default=".env", type=Path)
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--skip-postgres", action="store_true")
    parser.add_argument("--skip-providers", action="store_true")
    args = parser.parse_args()

    if not args.env.is_file():
        sys.exit(f"not found: {args.env}")
    env = {k: (v or "") for k, v in dotenv_values(args.env).items()}
    report = Report()
    check_file(args.env, report)
    check_keys(args.env, env, report)
    if report.failures:
        print(f"\n{report.failures} failure(s); fix the keys above first")
        sys.exit(1)
    check_formats(env, report)
    check_dsn(env, report)
    if not args.skip_chroma:
        check_chroma(env, report)
    if not args.skip_providers:
        check_embedding_providers(env, report)
    if not args.skip_postgres:
        check_postgres(env, report)
    print(f"\n{report.failures} failure(s), {report.warnings} warning(s)")
    sys.exit(1 if report.failures else 0)


if __name__ == "__main__":
    main()
