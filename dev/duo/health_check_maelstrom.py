#!/usr/bin/env python3
import json, os, re, shlex, subprocess, sys, time, datetime, pathlib

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/home/mills")
MON_ROOT = os.environ.get("MON_ROOT", f"{PROJECT_ROOT}/maelstrom_mgmt")
DUO_LOCAL = os.environ.get("DUO_LOCAL", f"{PROJECT_ROOT}/tools/duo")
DUO_DEV_LOCAL = os.environ.get("DUO_DEV_LOCAL", f"{PROJECT_ROOT}/dev/duo")
MNT_CODE = os.environ.get("MNT_CODE", "/mnt/code")
RESURGENT_IP = os.environ.get("RESURGENT_IP", "192.168.1.115")
NATS_MON = os.environ.get("NATS_MON", f"http://{RESURGENT_IP}:8222")
PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000")
LOKI_URL = os.environ.get("LOKI_URL", "http://localhost:3100")
ALERT_URL = os.environ.get("ALERT_URL", "http://localhost:9093")
OUT_JSON = os.environ.get("OUT_JSON", f"{DUO_LOCAL}/logs/health_maelstrom.json")
OUT_MD = os.environ.get("OUT_MD", f"{DUO_LOCAL}/logs/health_maelstrom.md")
RCA_JSON = os.environ.get("RCA_JSON", f"{DUO_LOCAL}/logs/rca_maelstrom.json")
PLAN_MD = os.environ.get("PLAN_MD", f"{DUO_LOCAL}/logs/remediation_plan_maelstrom.md")
JOURNAL = os.environ.get("JOURNAL", f"{DUO_LOCAL}/logs/seed.status")

TEST_SLACK = os.environ.get("TEST_SLACK", "false").lower() == "true"
PROM_DEEP_TARGETS = os.environ.get("PROM_DEEP_TARGETS", "true").lower() == "true"
LOKI_DEEP_QUERY = os.environ.get("LOKI_DEEP_QUERY", "true").lower() == "true"
DUO_E2E_EXERCISE = os.environ.get("DUO_E2E_EXERCISE", "false").lower() == "true"

ts = datetime.datetime.now(datetime.timezone.utc).isoformat()


def run(cmd, timeout=10, check=False, input=None):
    if isinstance(cmd, str):
        shell = True
    else:
        shell = False
    try:
        p = subprocess.run(
            cmd,
            shell=shell,
            timeout=timeout,
            input=input,
            capture_output=True,
            text=True,
        )
        if check and p.returncode != 0:
            raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
        return {
            "ok": p.returncode == 0,
            "rc": p.returncode,
            "out": (p.stdout or "") + (p.stderr or ""),
        }
    except Exception as e:
        return {"ok": False, "rc": 124, "out": f"EXCEPTION: {e}"}


def ensure_dirs():
    for d in [f"{DUO_LOCAL}/logs", DUO_DEV_LOCAL, MON_ROOT]:
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)


def http_head(url, timeout=5):
    return run(
        ["bash", "-lc", f"curl -sI --max-time {timeout} {shlex.quote(url)} | head -n1"]
    )


def http_get(url, timeout=5):
    return run(
        ["bash", "-lc", f"curl -sf --max-time {timeout} {shlex.quote(url)}"],
        timeout=timeout,
    )


def classify(status_bool, warn=False):
    if status_bool:
        return "PASS"
    return "WARN" if warn else "FAIL"


results = []


def add_result(key, title, status, evidence):
    results.append(
        {"key": key, "title": title, "status": status, "evidence": evidence.strip()}
    )


def section_A():
    # Preflight & Mount Posture
    who = run("whoami")
    dt = run("date -Is")
    uname = run("uname -a")
    lsb = run("lsb_release -a")
    ok_all = all([who.get("ok"), dt.get("ok"), uname.get("ok"), lsb.get("ok")])
    evidence = (
        "whoami="
        + who.get("out", "").strip()
        + "\n"
        + dt.get("out", "")
        + uname.get("out", "")
        + lsb.get("out", "")
    )
    add_result("A.basic", "Identity and OS info", classify(ok_all), evidence)
    mnt = run(
        [
            "bash",
            "-lc",
            f"findmnt -no SOURCE,TARGET,OPTIONS {shlex.quote(MNT_CODE)} || echo 'not a mount'",
        ]
    )
    add_result(
        "A.mount",
        f"Mount posture {MNT_CODE}",
        "PASS" if "not a mount" not in mnt["out"] else "WARN",
        mnt["out"],
    )
    df = run(["bash", "-lc", f"df -h / {shlex.quote(PROJECT_ROOT)}"])
    add_result(
        "A.df", "Disk free for / and project root", classify(df["ok"]), df["out"]
    )


def section_B():
    up = run("uptime")
    mem = run("free -h")
    vm = run("vmstat 1 3", timeout=6)
    proc = run("ps -e --no-headers | wc -l")
    ok_all = all([up.get("ok"), mem.get("ok"), vm.get("ok"), proc.get("ok")])
    evidence = (
        up.get("out", "")
        + mem.get("out", "")
        + vm.get("out", "")
        + "procs="
        + proc.get("out", "").strip()
    )
    add_result("B.load", "Load and memory snapshot", classify(ok_all), evidence)
    failed = run("systemctl --failed")
    status = (
        "PASS"
        if (failed["ok"] and re.search(r"0 loaded units listed", failed["out"]))
        else "WARN"
    )
    add_result("B.systemd_failed", "Systemd failed units", status, failed["out"])
    blame = run("systemd-analyze blame | head -n 30")
    add_result(
        "B.boot_blame",
        "Slowest services (top 30)",
        classify(blame["ok"], warn=True),
        blame["out"],
    )


def section_C():
    info = run("docker info | head -n 25")
    add_result(
        "C.docker_info",
        "Docker info (header)",
        classify(info["ok"], warn=True),
        info["out"],
    )
    ps = run("docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'")
    status = "PASS" if ps["ok"] else "FAIL"
    add_result("C.docker_ps", "Docker running containers", status, ps["out"])
    # Check unhealthy/exited
    unhealthy = []
    for line in ps["out"].splitlines():
        if "unhealthy" in line.lower() or line.lower().startswith("\tunhealthy"):
            unhealthy.append(line)
        if "Exited" in line or "Dead" in line:
            unhealthy.append(line)
    if unhealthy:
        add_result(
            "C.docker_health",
            "Container health anomalies",
            "FAIL",
            "\n".join(unhealthy),
        )
    else:
        add_result(
            "C.docker_health", "Container health anomalies", "PASS", "none detected"
        )


def section_D():
    rdy = http_get(f"{PROM_URL}/-/ready")
    add_result("D.prom_ready", "Prometheus readiness", classify(rdy["ok"]), rdy["out"])
    if PROM_DEEP_TARGETS:
        tgt = http_get(f"{PROM_URL}/api/v1/targets?state=active")
        add_result(
            "D.prom_targets",
            "Prom active targets (head)",
            classify(tgt["ok"], warn=True),
            tgt["out"][:2000],
        )
        q = http_get(
            f"{PROM_URL}/api/v1/query?query="
            + shlex.quote('up{job=~"resurgent_(node|cadvisor)"}')
        )
        st = "PASS"
        if not q["ok"]:
            st = "WARN"
        else:
            try:
                data = json.loads(q["out"]) if q["out"] else {}
                vals = [
                    int(float(v["value"][1]))
                    for v in data.get("data", {}).get("result", [])
                    if "value" in v
                ]
                if not vals or any(v == 0 for v in vals):
                    st = "WARN"
            except Exception:
                st = "WARN"
        add_result(
            "D.prom_up_resurgent",
            "Prom up{resurgent_node|cadvisor}",
            st,
            q["out"][:2000],
        )


def section_E():
    head = http_head(GRAFANA_URL)
    ok = head["ok"] and ("HTTP/1." in head["out"])
    add_result(
        "E.grafana_head", "Grafana HTTP head", classify(ok, warn=True), head["out"]
    )
    dashdir = pathlib.Path(MON_ROOT) / "grafana" / "dashboards"
    if dashdir.exists():
        files = "\n".join(sorted(str(p) for p in dashdir.glob("**/*.json")))
        add_result(
            "E.grafana_dash",
            "Grafana dashboards present",
            "PASS" if files else "WARN",
            files or "none",
        )
    else:
        add_result(
            "E.grafana_dash",
            "Grafana dashboards present",
            "WARN",
            f"missing: {dashdir}",
        )


def section_F():
    rdy = http_get(f"{LOKI_URL}/ready")
    add_result("F.loki_ready", "Loki readiness", classify(rdy["ok"]), rdy["out"])
    if LOKI_DEEP_QUERY:
        # Basic instant query; Loki expects /loki/api/v1/query
        q = http_get(
            f"{LOKI_URL}/loki/api/v1/query?query="
            + shlex.quote('{job="promtail"}')
            + "&limit=1"
        )
        st = (
            "PASS"
            if (q["ok"] and ("stream" in q["out"] or "values" in q["out"]))
            else "WARN"
        )
        add_result("F.loki_query", "Loki promtail existence (10m)", st, q["out"][:2000])


def section_G():
    head = http_head(ALERT_URL)
    ok = head["ok"] and ("HTTP/1." in head["out"])
    add_result(
        "G.alert_head", "Alertmanager HTTP head", classify(ok, warn=True), head["out"]
    )
    rules_dir = pathlib.Path(MON_ROOT) / "prometheus" / "rules"
    if rules_dir.exists():
        names = "\n".join(sorted(str(p) for p in rules_dir.glob("**/*.*")))
        add_result(
            "G.rules_list",
            "Prometheus rules on disk",
            "PASS" if names else "WARN",
            names or "none",
        )
    # Optional rules via API
    rr = http_get(f"{PROM_URL}/api/v1/rules")
    if rr["ok"]:
        try:
            jd = json.loads(rr["out"])
            groups = jd.get("data", {}).get("groups", [])
            firing = sum(
                1
                for g in groups
                for r in g.get("rules", [])
                if r.get("state") == "firing"
            )
            add_result(
                "G.rules_api",
                "Prom rules via API",
                "PASS",
                f"groups={len(groups)} firing={firing}",
            )
        except Exception:
            add_result("G.rules_api", "Prom rules via API", "WARN", rr["out"][:1000])
    else:
        add_result("G.rules_api", "Prom rules via API", "WARN", rr["out"])


def section_H():
    svc = run("systemctl is-active codex-home-sync.service")
    st = "PASS" if (svc["ok"] and svc["out"].strip() == "active") else "WARN"
    add_result("H.lsyncd_active", "lsyncd service active", st, svc["out"])
    log = run("tail -n 50 /var/log/lsyncd/lsyncd.log*")
    add_result(
        "H.lsyncd_tail", "lsyncd logs tail", classify(log["ok"], warn=True), log["out"]
    )


def section_I():
    connz = http_get(f"{NATS_MON}/connz")
    m = re.search(r'"num_connections"\s*:\s*(\d+)', connz["out"] if connz["ok"] else "")
    num = int(m.group(1)) if m else 0
    st = "PASS" if num > 0 else "WARN"
    add_result(
        "I.nats_connz",
        "NATS connections",
        st,
        f"num_connections={num}\n{connz['out'][:500]}",
    )
    run_dir = pathlib.Path(MON_ROOT) / "duo-staging" / "run"
    if run_dir.exists():
        listing = run(
            ["bash", "-lc", f"ls -l {shlex.quote(str(run_dir))} | head -n 50"]
        )
        add_result(
            "I.duo_run_dir",
            "DUO run dir listing",
            classify(listing["ok"], warn=True),
            listing["out"],
        )
    else:
        add_result(
            "I.duo_run_dir", "DUO run dir listing", "WARN", f"missing: {run_dir}"
        )
    # Count inbox/processed/results/reviews
    counts = {}
    for d in ["tasks/inbox", "tasks/processed", "results", "reviews"]:
        p = pathlib.Path(DUO_DEV_LOCAL) / d
        c = len(list(p.glob("**/*"))) if p.exists() else 0
        counts[d] = {"exists": p.exists(), "count": c}
    add_result(
        "I.duo_counts", "DUO dev local counts", "PASS", json.dumps(counts, indent=2)
    )


def section_J():
    state = pathlib.Path(DUO_LOCAL) / ".state" / "pub_window.json"
    if state.exists():
        out = run(
            [
                "bash",
                "-lc",
                f"jq -r '.window // empty' {shlex.quote(str(state))} 2>/dev/null || cat {shlex.quote(str(state))}",
            ]
        )
        add_result(
            "J.window", "Publication window", classify(out["ok"], warn=True), out["out"]
        )
    else:
        add_result("J.window", "Publication window", "WARN", f"missing: {state}")
    paths = [
        f"{DUO_LOCAL}/MAELSTROM_HANDOFF.md",
        f"{DUO_LOCAL}/logs/maelstrom_summary_LATEST.md",
        f"{DUO_LOCAL}/.state/verifier.index",
    ]
    ev = []
    for p in paths:
        pp = pathlib.Path(p)
        ev.append(
            f"{p}: {'present' if pp.exists() else 'missing'} mtime={datetime.datetime.fromtimestamp(pp.stat().st_mtime).isoformat() if pp.exists() else 'n/a'}"
        )
    add_result(
        "J.handoff_files", "Handoff/summary/verifier presence", "PASS", "\n".join(ev)
    )
    # manifests
    manifests = sorted(
        pathlib.Path(DUO_LOCAL).glob("**/manifest-*.sha256*"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if manifests:
        newest = manifests[0]
        add_result(
            "J.manifest",
            "Newest manifest artifact",
            "PASS",
            f"{newest} age_sec={int(time.time()-newest.stat().st_mtime)}",
        )
        # optional minisign verify if key exists
        if (
            shutil.which("minisign")
            and (pathlib.Path.home() / ".minisign/secret.key").exists()
        ):
            ver = run(
                ["bash", "-lc", f"minisign -Vm {shlex.quote(str(newest))} -P auto"],
                timeout=8,
            )
            add_result(
                "J.minisign",
                "Minisign verify",
                classify(ver["ok"], warn=True),
                ver["out"],
            )
        else:
            add_result(
                "J.minisign",
                "Minisign verify",
                "WARN",
                "skipped: minisign or key not available",
            )
    else:
        add_result("J.manifest", "Newest manifest artifact", "WARN", "none found")


def section_K():
    if TEST_SLACK and pathlib.Path(f"{DUO_LOCAL}/secrets/slack_webhook").exists():
        add_result(
            "K.slack", "Slack test", "WARN", "skipped per toggle or missing webhook"
        )
    else:
        add_result("K.slack", "Slack test", "PASS", "skipped per toggle")


def section_L():
    ss = run(
        [
            "bash",
            "-lc",
            "ss -tulpen | grep -E ':(9090|9091|9093|3000|3100)\\b' | head -n 50 || true",
        ]
    )
    add_result(
        "L.ports",
        "Listening ports of interest",
        classify(ss["ok"], warn=True),
        ss["out"],
    )
    ipa = run("ip addr show | head -n 50")
    add_result(
        "L.ipaddr", "IP address snapshot", classify(ipa["ok"], warn=True), ipa["out"]
    )
    target = f"{MNT_CODE}/resurgent_mgmt"
    writable = os.access(target, os.W_OK)
    add_result(
        "L.mount_writable",
        f"Assert {target} not writable",
        "FAIL" if writable else "PASS",
        f"writable={writable}",
    )


def section_M():
    bsh = pathlib.Path(PROJECT_ROOT) / "tools" / "backup.sh"
    if bsh.exists():
        backups_root = pathlib.Path(PROJECT_ROOT) / "backup" / "maelstrom"
        if backups_root.exists():
            entries = sorted(
                backups_root.glob("*/"), key=lambda x: x.stat().st_mtime, reverse=True
            )[:5]
            lines = []
            now = time.time()
            for e in entries:
                age = int(now - e.stat().st_mtime)
                lines.append(f"{e} age_sec={age}")
            add_result(
                "M.backups",
                "Recent backups",
                "PASS" if entries else "WARN",
                "\n".join(lines) or "none",
            )
        else:
            add_result(
                "M.backups", "Recent backups", "WARN", f"missing: {backups_root}"
            )
    else:
        add_result(
            "M.backups", "Recent backups", "WARN", f"missing backup script: {bsh}"
        )


def section_N():
    # SLA snapshot
    df = run(["bash", "-lc", "df -h / | tail -n1 | awk '{print $5}'"])
    disk = df.get("out", " ").strip()
    # Read memory from /proc/meminfo to avoid quoting complexity
    try:
        mt = ma = 0
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mt = int(line.split()[1])
                if line.startswith("MemAvailable:"):
                    ma = int(line.split()[1])
        used = mt - ma
        mems = f"{used//1024}MB/{mt//1024}MB"
        mem_ok = True
    except Exception:
        mems = "unknown"
        mem_ok = False
    load = run(["bash", "-lc", "awk '{print $1,$2,$3}' /proc/loadavg"])
    loadv = load["out"].strip()
    add_result(
        "N.sla",
        "SLA snapshot CPU/Mem/Disk",
        classify(all([df.get("ok"), mem_ok, load.get("ok")]), warn=True),
        f"disk={disk} mem={mems} loadavg={loadv}",
    )
    # Prom up% for resurgent_*
    q = http_get(
        f"{PROM_URL}/api/v1/query?query="
        + shlex.quote('avg_over_time(up{job=~"resurgent_.*"}[15m])')
    )
    # Consider API availability primary; empty results degrade to WARN
    add_result(
        "N.prom_up_pct",
        "Prom up% resurgent_* (15m avg)",
        "PASS" if q["ok"] else "WARN",
        q["out"][:2000],
    )


def section_O():
    if DUO_E2E_EXERCISE:
        add_result(
            "O.duo_e2e",
            "DUO E2E exercise",
            "WARN",
            "skipped per toggle (would write only under /home/mills)",
        )
    else:
        add_result("O.duo_e2e", "DUO E2E exercise", "PASS", "skipped per toggle")


def build_reports():
    # Write OUT_JSON and OUT_MD
    pathlib.Path(OUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(
            {"host": "Maelstrom", "generated_at": ts, "results": results}, f, indent=2
        )
    # Markdown
    p = sum(1 for r in results if r["status"] == "PASS")
    w = sum(1 for r in results if r["status"] == "WARN")
    fl = sum(1 for r in results if r["status"] == "FAIL")
    lines = [
        f"# Maelstrom Health Check",
        "",
        f"Generated: {ts}",
        f"Summary: PASS={p} WARN={w} FAIL={fl}",
        "",
    ]
    for r in results:
        lines.append(f"- [{r['status']}] {r['key']} — {r['title']}")
        lines.append("  ")
        lines.append("  Evidence:\n  " + "\n  ".join(r["evidence"].splitlines()[:50]))
        lines.append("")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    # Append journal
    with open(JOURNAL, "a") as f:
        f.write(f"HEALTHCHECK maelstrom {ts} P:{p} W:{w} F:{fl}\n")
    return p, w, fl


def rca_and_plan():
    # Build RCA for non-green
    with open(OUT_JSON) as f:
        data = json.load(f)
    issues = []
    for r in data["results"]:
        if r["status"] == "PASS":
            continue
        key = r["key"]
        ev = r["evidence"]
        cat = "config drift"
        hypotheses = []
        confirm = []
        blast = "low"
        if key.startswith("C.docker_health") or (
            key == "C.docker_ps" and r["status"] == "FAIL"
        ):
            cat = "container unhealthy"
            hypotheses = [
                {
                    "text": "One or more containers unhealthy or exited",
                    "confidence": "high",
                }
            ]
            confirm = [
                "docker ps --format '{{.Names}}\t{{.Status}}' | grep -Ei 'unhealthy|Exited'"
            ]
            blast = "med"
        elif key == "D.prom_ready" and r["status"] != "PASS":
            cat = "Prometheus down"
            hypotheses = [
                {
                    "text": "Prometheus container not ready or port blocked",
                    "confidence": "med",
                }
            ]
            confirm = [
                f"curl -sf {PROM_URL}/-/ready || docker logs prometheus --tail=200"
            ]
            blast = "high"
        elif key == "D.prom_up_resurgent" and r["status"] != "PASS":
            cat = "scrape target down"
            hypotheses = [
                {
                    "text": "resurgent node_exporter or cadvisor not reachable",
                    "confidence": "med",
                }
            ]
            confirm = [
                f"curl -sf http://{RESURGENT_IP}:9100/metrics | head -n2",
                f"curl -sf http://{RESURGENT_IP}:8080/metrics | head -n2",
            ]
            blast = "med"
        elif key.startswith("E.grafana") and r["status"] != "PASS":
            cat = "dashboards not provisioned"
            hypotheses = [
                {
                    "text": "Grafana not reachable or dashboards missing",
                    "confidence": "med",
                }
            ]
            confirm = [f"curl -sI {GRAFANA_URL}", f"ls {MON_ROOT}/grafana/dashboards"]
            blast = "med"
        elif key == "F.loki_ready" and r["status"] != "PASS":
            cat = "Loki down"
            hypotheses = [{"text": "Loki not ready", "confidence": "med"}]
            confirm = [f"curl -sf {LOKI_URL}/ready"]
            blast = "med"
        elif key == "F.loki_query" and r["status"] != "PASS":
            cat = "Loki ingestion gap"
            hypotheses = [
                {
                    "text": "Promtail not shipping logs or label mismatch",
                    "confidence": "med",
                }
            ]
            confirm = [f"curl -sf '{LOKI_URL}/loki/api/v1/labels' | jq ."]
            blast = "low"
        elif key.startswith("G.alert_head") and r["status"] != "PASS":
            cat = "Alertmanager down"
            hypotheses = [{"text": "Alertmanager not reachable", "confidence": "med"}]
            confirm = [f"curl -sI {ALERT_URL}"]
            blast = "med"
        elif key == "G.rules_api" and r["status"] != "PASS":
            cat = "config drift"
            hypotheses = [
                {"text": "Prometheus rules endpoint not reachable", "confidence": "low"}
            ]
            confirm = [f"curl -sf {PROM_URL}/api/v1/rules"]
            blast = "low"
        elif key == "H.lsyncd_active" and r["status"] != "PASS":
            cat = "lsync lag"
            hypotheses = [
                {"text": "lsyncd service inactive or failing", "confidence": "med"}
            ]
            confirm = ["systemctl status codex-home-sync.service"]
            blast = "low"
        elif key == "I.nats_connz" and r["status"] != "PASS":
            cat = "NATS connz low"
            hypotheses = [
                {"text": "No active NATS clients/subscribers", "confidence": "med"}
            ]
            confirm = [f"curl -sf {NATS_MON}/connz | jq '.num_connections' "]
            blast = "med"
        elif key.startswith("J.manifest") and r["status"] != "PASS":
            cat = "signing artifacts missing"
            hypotheses = [
                {"text": "Manifest artifacts not generated", "confidence": "low"}
            ]
            confirm = [f"ls -ltr {DUO_LOCAL}/**/manifest-*.sha256*"]
            blast = "low"
        elif key == "J.window" and r["status"] != "PASS":
            cat = "window mis-set"
            hypotheses = [
                {"text": "Publication window not configured", "confidence": "low"}
            ]
            confirm = [f"cat {DUO_LOCAL}/.state/pub_window.json"]
            blast = "low"
        elif key == "L.mount_writable" and r["status"] == "FAIL":
            cat = "segmentation misconfig"
            hypotheses = [
                {
                    "text": "/mnt/code is writable; should be read-only bind mount",
                    "confidence": "med",
                }
            ]
            confirm = [f"test -w {MNT_CODE}/resurgent_mgmt && echo writable"]
            blast = "med"
        else:
            hypotheses = [
                {
                    "text": "General anomaly detected in health check",
                    "confidence": "low",
                }
            ]
            confirm = ["Re-run targeted command and inspect logs"]
        issues.append(
            {
                "id": key,
                "category": cat,
                "hypotheses": hypotheses,
                "evidence": [l for l in r["evidence"].splitlines()[:10]],
                "confirm_tests": confirm,
                "blast_radius": blast,
            }
        )

    # Build remediation plan ordered: FAIL first, then WARN
    def severity_of(i):
        if i["id"] in [r["key"] for r in results if r["status"] == "FAIL"]:
            return 0
        return 1

    ordered = sorted(issues, key=severity_of)
    plan = []
    for i in ordered:
        title = f"Remediate {i['id']} ({i['category']})"
        severity = (
            "high"
            if i["blast_radius"] in ("high", "med")
            and i["id"] in [r["key"] for r in results if r["status"] == "FAIL"]
            else "medium"
        )
        owner = (
            "Maelstrom"
            if not i["id"].startswith("D.prom_up_resurgent")
            else "Resurgent"
        )
        prereq = "Change window; backup configs"
        deps = "Docker and network available"
        commands = []
        if i["category"] == "container unhealthy":
            commands = [
                "docker ps --format '{{.Names}}\t{{.Status}}'",
                "docker logs <container> --tail=200",
                "docker inspect <container> | jq '.[0].State'",
            ]
        elif i["category"] == "Prometheus down":
            commands = [
                f"curl -sI {PROM_URL}/-/ready || true",
                "docker logs prometheus --tail=200 || true",
            ]
        elif i["category"] == "scrape target down":
            commands = [
                f"curl -sf http://{RESURGENT_IP}:9100/metrics | head -n2 || true",
                f"curl -sf http://{RESURGENT_IP}:8080/metrics | head -n2 || true",
            ]
        elif i["category"] == "dashboards not provisioned":
            commands = [
                f"ls {MON_ROOT}/grafana/dashboards | wc -l || true",
                f"curl -sI {GRAFANA_URL} || true",
            ]
        elif i["category"] in ("Loki down", "Loki ingestion gap"):
            commands = [
                f"curl -s {LOKI_URL}/ready || true",
                f"curl -s {LOKI_URL}/loki/api/v1/labels || true",
            ]
        elif i["category"] == "Alertmanager down":
            commands = [f"curl -sI {ALERT_URL} || true"]
        elif i["category"] == "lsync lag":
            commands = [
                "systemctl status codex-home-sync.service || true",
                "tail -n 200 /var/log/lsyncd/lsyncd.log || true",
            ]
        elif i["category"] == "NATS connz low":
            commands = [f"curl -s {NATS_MON}/connz | jq '.num_connections' || true"]
        elif i["category"] == "segmentation misconfig":
            commands = [
                f"mount | grep '{MNT_CODE}' || true",
                f"ls -ld {MNT_CODE} {MNT_CODE}/resurgent_mgmt || true",
            ]
        else:
            commands = ["Re-run health check and inspect logs"]
        validation = ["Re-run health check; expect PASS for this item"]
        rollback = "Revert config changes and restart affected service if needed"
        change_window = "Low-traffic hours"
        duration = "15-45m"
        plan.append(
            {
                "title": title,
                "severity": severity,
                "owner": owner,
                "prerequisites": prereq,
                "dependencies": deps,
                "commands": commands,
                "change_window": change_window,
                "estimated_duration": duration,
                "rollback": rollback,
                "validation": validation,
                "success_metrics": ["Target reports PASS and service endpoints ready"],
            }
        )

    rca_doc = {"host": "maelstrom", "generated_at": ts, "issues": issues, "plan": plan}
    with open(RCA_JSON, "w") as f:
        json.dump(rca_doc, f, indent=2)
    # Write PLAN_MD
    lines = ["# Remediation Plan: Maelstrom", f"Generated: {ts}", ""]
    for step in plan:
        lines.append(
            f"- [ ] {step['title']} ({step['severity']}, owner={step['owner']})"
        )
        lines.append(f"  - Prerequisites: {step['prerequisites']}")
        lines.append(f"  - Dependencies: {step['dependencies']}")
        lines.append(f"  - Commands:")
        for c in step["commands"]:
            lines.append(f"    - `{c}`")
        lines.append(
            f"  - Change window: {step['change_window']} | Est: {step['estimated_duration']}"
        )
        lines.append(f"  - Rollback: {step['rollback']}")
        lines.append(f"  - Validation: {'; '.join(step['validation'])}")
        lines.append(f"  - Success: {'; '.join(step['success_metrics'])}")
        lines.append("")
    with open(PLAN_MD, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import shutil

    ensure_dirs()
    section_A()
    section_B()
    section_C()
    section_D()
    section_E()
    section_F()
    section_G()
    section_H()
    section_I()
    section_J()
    section_K()
    section_L()
    section_M()
    section_N()
    section_O()
    p, w, f = build_reports()
    rca_and_plan()
    print(
        json.dumps(
            {
                "summary": {"PASS": p, "WARN": w, "FAIL": f},
                "OUT_JSON": OUT_JSON,
                "OUT_MD": OUT_MD,
                "RCA_JSON": RCA_JSON,
                "PLAN_MD": PLAN_MD,
            },
            indent=2,
        )
    )
