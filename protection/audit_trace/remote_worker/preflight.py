"""Bounded, read-only SSH inventory; no installation, model load or inference."""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import shlex
import time
from pathlib import Path


def fingerprint(key: object) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def connect(host: str, port: int, username: str, password: str):
    import paramiko

    trust: dict[str, str] = {}

    class RecordFirstUse(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            trust.update(
                mode="SESSION_FIRST_USE_NOT_OUT_OF_BAND_VERIFIED", fingerprint=fingerprint(key)
            )
            client.get_host_keys().add(hostname, key.get_name(), key)

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(RecordFirstUse())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        password=password,
        look_for_keys=False,
        allow_agent=False,
        timeout=15,
        banner_timeout=20,
        auth_timeout=20,
    )
    if not trust:
        key = client.get_transport().get_remote_server_key()
        trust.update(mode="EXISTING_KNOWN_HOST_MATCH", fingerprint=fingerprint(key))
    return client, trust


def inventory_commands() -> dict[str, str]:
    python = r"""
import importlib.metadata as m, importlib.util as u, json, sys
names=['torch','torch-musa','torch_musa','transformers','vllm','vllm-musa','numpy','accelerate']
versions={}
for n in names:
 try: versions[n]=m.version(n)
 except m.PackageNotFoundError: versions[n]=None
print(json.dumps({'python':sys.version,'executable':sys.executable,'packages':versions}))
"""
    devices = r"""
import json
try:
 import torch
 import torch_musa
 api=getattr(torch,'musa',None)
 print(json.dumps({'torch':torch.__version__,'musa_available':bool(api and api.is_available()),'musa_device_count':api.device_count() if api else 0,'devices':[api.get_device_name(i) for i in range(api.device_count())] if api else []}))
except Exception as e:
 print(json.dumps({'device_query_error_type':type(e).__name__,'message':str(e)[:1500]}))
"""
    models = r"""
from pathlib import Path
import json
roots=[Path('/root/autodl-tmp'),Path('/root/.cache/huggingface/hub'),Path('/data/models'),Path('/models'),Path('/workspace')]
out=[]
for root in roots:
 if not root.is_dir(): continue
 for p in list(root.iterdir())[:150]:
  if 'qwen' in p.name.lower():
   out.append({'path':str(p),'directory':p.is_dir(),'config_exists':(p/'config.json').is_file(),'gguf':p.suffix=='.gguf'})
print(json.dumps({'bounded_top_level_model_inventory':out,'not_recursive_weight_scan':True}))
"""
    network = r"""
import socket,json
result={}
for name in ['huggingface.co','github.com','registry.mthreads.com']:
 try:
  socket.getaddrinfo(name,443)
  with socket.create_connection((name,443),timeout=4):pass
  result[name]='DNS_AND_TCP443_OK_NO_DOWNLOAD'
 except Exception as e:result[name]=type(e).__name__
print(json.dumps(result))
"""
    sdk = r"""
from pathlib import Path
import json,re
out={}
for name in ['/usr/local/musa/version.txt','/usr/local/musa/version.json','/usr/local/musa/include/musa.h','/usr/local/musa/include/musa_runtime_api.h']:
 p=Path(name)
 if p.is_file():
  text=p.read_text(errors='replace')[:1000000]
  out[name]=text[:2000] if 'version.' in name else [x for x in text.splitlines() if re.search(r'#define\s+MUSA(_VERSION|_MAJOR|_MINOR)',x)][:12]
print(json.dumps(out))
"""
    return {
        "os": "uname -srmo; id -u",
        "gpu": "command -v mthreads-gmi && mthreads-gmi",
        "musa_sdk": "command -v musaInfo && musaInfo",
        "compiler": "command -v mcc && mcc --version",
        "disk": "df -h / /root /tmp; free -m",
        "python_packages": "PYTHONDONTWRITEBYTECODE=1 python3 -c " + shlex.quote(python),
        "devices": "PYTHONDONTWRITEBYTECODE=1 python3 -c " + shlex.quote(devices),
        "model_inventory": "PYTHONDONTWRITEBYTECODE=1 python3 -c " + shlex.quote(models),
        "network": "PYTHONDONTWRITEBYTECODE=1 python3 -c " + shlex.quote(network),
        "sdk_version_files": "PYTHONDONTWRITEBYTECODE=1 python3 -c " + shlex.quote(sdk),
        "data_disks": "df -hT /root/autodl-tmp /data /workspace 2>/dev/null",
    }


def run_inventory(client, password: str, only: list[str] | None = None) -> dict:
    records = []
    for label, command in inventory_commands().items():
        if only and label not in only:
            continue
        row = {"check": label, "command": command, "started_epoch": time.time()}
        try:
            _, out, err = client.exec_command(command, timeout=35)
            row.update(
                stdout=out.read(65536)
                .decode("utf-8", errors="replace")
                .replace(password, "<REDACTED>"),
                stderr=err.read(8192)
                .decode("utf-8", errors="replace")
                .replace(password, "<REDACTED>"),
                exit_status=out.channel.recv_exit_status(),
            )
        except Exception as exc:
            row.update(error_type=type(exc).__name__)
        records.append(row)
    return {"records": records, "model_generations": 0, "remote_file_writes": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--username", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="+", choices=list(inventory_commands()))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preflight evidence must not be overwritten")
    password = getpass.getpass("SSH password (memory only, no echo): ")
    client = None
    report = {"classification": "READ_ONLY_PREFLIGHT", "started_epoch": time.time()}
    try:
        client, trust = connect(args.host, args.port, args.username, password)
        report.update(ssh="PASS", host_key=trust, **run_inventory(client, password, args.only))
    except Exception as exc:
        report.update(ssh="FAILED", error_type=type(exc).__name__)
    finally:
        if client:
            client.close()
        password = ""
    report["finished_epoch"] = time.time()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ssh": report["ssh"], "output": str(args.output), "model_generations": 0}))
    return 0 if report["ssh"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
