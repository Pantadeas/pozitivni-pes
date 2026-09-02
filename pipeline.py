#!/usr/bin/env python3
"""
Pozitivní pes — vývojová pipeline orchestrátor.
Sekvenční multi-agentní pipeline (multi-agent-framework-v3).

Použití:
  python3 pipeline.py run              # Spustit/pokračovat v tasku z TASK.md
  python3 pipeline.py approve          # Schválit aktuální human checkpoint
  python3 pipeline.py status           # Zobrazit stav
  python3 pipeline.py gate             # Spustit jen scripts/gate.sh
  python3 pipeline.py curator          # Spustit domain-knowledge-curator (periodicky)
  python3 pipeline.py reset            # Resetovat stav (nový task)
"""

import json
import os
import re
import subprocess
import sys
import time
import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent
PIPELINE_DIR = REPO / ".pipeline"
STATE_FILE = PIPELINE_DIR / "state.json"
APPROVALS_DIR = PIPELINE_DIR / "approvals"
LOGS_DIR = PIPELINE_DIR / "logs"
TOKEN_LOG = LOGS_DIR / "token_log.jsonl"
PROGRESS_FILE = REPO / "PROGRESS.md"

TASK_FILE = REPO / "TASK.md"
ACCEPTANCE_FILE = REPO / "ACCEPTANCE.md"
RESEARCH_FILE = REPO / "research.md"
DESIGN_FILE = REPO / "design.md"
QA_REPORT = REPO / "qa-report.json"
DOMAIN_REVIEW = REPO / "domain-review.json"
RELEASE_REPORT = REPO / "release-report.md"

GATE_SCRIPT = REPO / "scripts" / "gate.sh"

# ── Risk tier sekvence ────────────────────────────────────────────────────────

SEQUENCES = {
    "S": [
        "implementer",
        "gate",
        "done",
    ],
    "M": [
        "planner",
        "HUMAN:APPROVE_DESIGN",
        "implementer",
        "coherence",
        "gate",
        "qa",
        "domain_review",
        "HUMAN:ACCEPT_FINDINGS",
        "release",
        "HUMAN:APPROVE_RELEASE",
        "done",
    ],
    "L": [
        "researcher",
        "planner",
        "HUMAN:APPROVE_DESIGN",
        "implementer",
        "coherence",
        "gate",
        "qa",
        "domain_review",
        "HUMAN:ACCEPT_FINDINGS",
        "release",
        "HUMAN:APPROVE_RELEASE",
        "done",
    ],
}

COHERENCE_REPORT = REPO / "coherence-report.json"

AGENT_MAP = {
    "researcher": "researcher",
    "planner": "content-planner",
    "implementer": "web-developer",
    "qa": "qa-agent",
    "domain_review": "domain-reviewer",
    "release": "release-manager",
}

# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    _write_progress(state)


def _write_progress(state: dict):
    if not state:
        return
    lines = [
        f"# Pipeline progress — {state.get('task_id', '?')}",
        "",
        f"**Run ID:** {state.get('run_id', '?')}",
        f"**Risk tier:** {state.get('risk_tier', '?')}",
        f"**Phase:** {state.get('phase', '?')}",
        f"**Attempt:** {state.get('attempt', 1)}",
        f"**Branch:** {state.get('branch', 'main')}",
        f"**Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Sekvence",
    ]
    seq = SEQUENCES.get(state.get("risk_tier", "M"), [])
    current = state.get("phase", "")
    for step in seq:
        if step == current:
            marker = "→ **" + step + "** ← (aktuální)"
        elif seq.index(step) < seq.index(current) if current in seq else False:
            marker = "✓ " + step
        else:
            marker = "  " + step
        lines.append(marker)
    PROGRESS_FILE.write_text("\n".join(lines) + "\n")


def new_run_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

# ── Token logging ─────────────────────────────────────────────────────────────

def log_tokens(state: dict, agent: str, phase: str, result: str,
               tokens_in: int, tokens_out: int, duration_s: float,
               gate_pass=None, files_changed=None):
    cost = (tokens_in * 3 + tokens_out * 15) / 1_000_000
    record = {
        "ts": datetime.datetime.now().isoformat(),
        "run_id": state.get("run_id"),
        "task_id": state.get("task_id"),
        "agent": agent,
        "phase": phase,
        "attempt": state.get("attempt", 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost, 5),
        "duration_s": round(duration_s, 1),
        "result": result,
        "gate_pass": gate_pass,
        "files_changed": files_changed,
    }
    LOGS_DIR.mkdir(exist_ok=True)
    with TOKEN_LOG.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# ── Claude runner ─────────────────────────────────────────────────────────────

LIVE_STATUS_FILE = PIPELINE_DIR / "live_status.json"


def _write_live_status(agent: str, phase: str, elapsed: float, tokens_out: int = 0):
    try:
        LIVE_STATUS_FILE.write_text(json.dumps({
            "agent": agent, "phase": phase,
            "elapsed_s": round(elapsed),
            "tokens_out_so_far": tokens_out,
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def run_agent(agent_name: str, prompt: str, timeout: int = 300, add_dir: bool = False) -> tuple[str, int, int, float]:
    """Spustí claude -p --agent <name>, streamuje výstup, vrátí (text, tokens_in, tokens_out, duration)."""
    cmd = [
        "claude", "-p", prompt,
        "--agent", agent_name,
        "--output-format", "stream-json",
        "--verbose",
    ]
    if add_dir:
        cmd += ["--add-dir", str(REPO)]
    t0 = time.time()
    _write_live_status(agent_name, agent_name, 0)

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=str(REPO)
    )

    stdout_lines = []
    tokens_out_live = 0
    deadline = t0 + timeout

    while True:
        elapsed = time.time() - t0
        if time.time() > deadline:
            proc.kill()
            LIVE_STATUS_FILE.unlink(missing_ok=True)
            raise subprocess.TimeoutExpired(cmd, timeout)

        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            _write_live_status(agent_name, agent_name, elapsed, tokens_out_live)
            continue

        line = line.strip()
        if not line:
            continue
        stdout_lines.append(line)

        # Parse streaming JSON for live token count
        try:
            ev = json.loads(line)
            if ev.get("type") == "assistant" and "message" in ev:
                usage = ev["message"].get("usage", {})
                tokens_out_live = usage.get("output_tokens", tokens_out_live)
            elif ev.get("type") == "result":
                pass  # final result — exit loop naturally
        except Exception:
            pass

        _write_live_status(agent_name, agent_name, elapsed, tokens_out_live)

    proc.wait()
    duration = time.time() - t0
    LIVE_STATUS_FILE.unlink(missing_ok=True)

    if proc.returncode != 0:
        stderr = proc.stderr.read()
        raise RuntimeError(f"claude exited {proc.returncode}: {stderr[:500]}")

    # Najdi finální result event
    text = ""
    tokens_in = tokens_out = 0
    for line in reversed(stdout_lines):
        try:
            ev = json.loads(line)
            if ev.get("type") == "result":
                text = ev.get("result", "")
                usage = ev.get("usage", {})
                tokens_in = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                tokens_out = usage.get("output_tokens", 0)
                break
        except Exception:
            continue

    return text, tokens_in, tokens_out, duration

# ── Git helpers ───────────────────────────────────────────────────────────────

def git(args: list[str], check=True) -> str:
    result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(REPO))
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def ensure_branch(state: dict):
    branch = state["branch"]
    current = git(["branch", "--show-current"])
    if current != branch:
        # Branch existuje?
        branches = git(["branch", "--list", branch])
        if branches:
            git(["checkout", branch])
        else:
            git(["checkout", "-b", branch])
        print(f"  → Branch: {branch}")

# ── Human checkpoint ──────────────────────────────────────────────────────────

def human_checkpoint(state: dict, phase: str):
    """Zastaví pipeline a čeká na schválení. Ukončí proces."""
    approval_file = APPROVALS_DIR / f"{state['run_id']}_{phase}.approved"
    needed_file = APPROVALS_DIR / f"{state['run_id']}_{phase}.needed"

    APPROVALS_DIR.mkdir(exist_ok=True)
    needed_file.write_text(json.dumps({
        "phase": phase,
        "run_id": state["run_id"],
        "task_id": state["task_id"],
        "timestamp": datetime.datetime.now().isoformat(),
    }, indent=2))

    state["phase"] = phase
    state["waiting_approval"] = str(approval_file)
    save_state(state)

    print()
    print("=" * 60)
    print(f"⏸  HUMAN CHECKPOINT: {phase}")
    print("=" * 60)

    if phase == "HUMAN:APPROVE_DESIGN":
        print("  Přečti design.md, pak:")
    elif phase == "HUMAN:ACCEPT_FINDINGS":
        print("  Přečti qa-report.json a domain-review.json, pak:")
    elif phase == "HUMAN:APPROVE_RELEASE":
        print("  Přečti release-report.md, pak:")

    print()
    print("  python3 pipeline.py approve    ← schválení, pokračovat")
    print("  python3 pipeline.py status     ← zobrazit stav")
    print()
    sys.exit(0)


def is_approved(state: dict, phase: str) -> bool:
    approval_file = APPROVALS_DIR / f"{state['run_id']}_{phase}.approved"
    return approval_file.exists()

# ── Phase handlers ────────────────────────────────────────────────────────────

def phase_researcher(state: dict):
    print("  🔍 RESEARCHER — prohledává oblast tasku...")
    task = TASK_FILE.read_text()
    prompt = (
        f"Přečti TASK.md a CLAUDE.md. Prozkoumej oblast tasku na webu a v repo. "
        f"Napiš research.md.\n\nTASK.md:\n{task}"
    )
    text, tin, tout, dur = run_agent("researcher", prompt, timeout=600, add_dir=True)
    RESEARCH_FILE.write_text(text)
    log_tokens(state, "researcher", "researcher", "PASS", tin, tout, dur)
    print(f"  → research.md vytvořen ({tin+tout:,} tokenů)")


def phase_planner(state: dict):
    print("  📐 PLANNER — navrhuje implementaci...")
    task = TASK_FILE.read_text()
    research = RESEARCH_FILE.read_text() if RESEARCH_FILE.exists() else ""
    prompt = (
        f"Přečti CLAUDE.md, TASK.md{', research.md' if research else ''} a napiš design.md.\n\n"
        f"TASK.md:\n{task}\n"
        + (f"\nresearch.md:\n{research}\n" if research else "")
        + "\nPiš design.md přesně podle formátu v CLAUDE.md."
    )
    t0 = time.time()
    text, tin, tout, dur = run_agent("content-planner", prompt, timeout=300, add_dir=True)
    DESIGN_FILE.write_text(text)
    log_tokens(state, "content-planner", "planner", "PASS", tin, tout, dur)
    print(f"  → design.md vytvořen ({tin+tout:,} tokenů)")


def _extract_article_spec(design_text: str, fname: str) -> str:
    """Vytáhne z design.md část relevantní pro daný soubor."""
    # Zkus najít sekci podle názvu souboru (bez .dc.html)
    base = fname.replace(".dc.html", "").replace("Clanek-", "")
    lines = design_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if base.lower() in line.lower() and line.startswith(("####", "###", "##")):
            start = i
            break
    if start is None:
        # Fallback — celá sekce Obsah článků
        for i, line in enumerate(lines):
            if "Obsah článků" in line or "### 3." in line:
                start = i
                break
    if start is None:
        return design_text[:3000]  # krajní fallback

    # Čti do další sekce stejné nebo vyšší úrovně
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    result = []
    for line in lines[start:]:
        if result and line.startswith("#"):
            cur_level = len(line) - len(line.lstrip("#"))
            if cur_level <= level:
                break
        result.append(line)
    return "\n".join(result)


def _parse_files_from_design(design_text: str) -> list[str]:
    """Parsuje seznam souborů ke změně z design.md (sekce '## Soubory ke změně')."""
    files = []
    in_section = False
    for line in design_text.splitlines():
        if "## Soubory ke změně" in line or "## Soubory ke" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("##"):
                break
            # Řádky jako "- `Vychova.dc.html` — ..." nebo "- `Clanek-X.dc.html` — ..."
            m = re.search(r'`([^`]+\.(?:dc\.html|html|js|css))`', line)
            if m:
                files.append(m.group(1))
    return files


def phase_implementer(state: dict):
    print(f"  🛠  IMPLEMENTER — implementuje na branchi {state['branch']}...")
    ensure_branch(state)
    design = DESIGN_FILE.read_text() if DESIGN_FILE.exists() else TASK_FILE.read_text()

    # Per-file split: každý soubor dostane vlastní volání agenta
    files = _parse_files_from_design(design)
    if not files:
        # Fallback: jediné volání (starý chování)
        files = ["(všechny soubory z design.md)"]

    # Zjisti co už bylo hotovo z předchozích attempts
    already_done = set()
    if TOKEN_LOG.exists():
        with TOKEN_LOG.open() as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("run_id") == state["run_id"] and rec.get("phase", "").startswith("implementer:") and rec.get("result") == "PASS":
                        already_done.add(rec["phase"].replace("implementer:", ""))
                except Exception:
                    pass

    remaining = [f for f in files if f not in already_done]
    if already_done:
        print(f"  → přeskakuji {len(already_done)} hotových: {', '.join(already_done)}")
    print(f"  → {len(remaining)}/{len(files)} soubor(ů) zbývá: {', '.join(remaining)}")

    total_in = total_out = 0
    # Přečti šablonu jednou — Python ji předá v promptu, agent nemusí číst repo
    template_file = REPO / "Clanek-Pelisek.dc.html"
    template = template_file.read_text() if template_file.exists() else ""
    vychova_file = REPO / "Vychova.dc.html"

    for i, fname in enumerate(remaining, len(already_done) + 1):
        print(f"  [{i}/{len(files)}] {fname}...")
        state["current_file"] = fname
        state["current_file_idx"] = i
        state["total_files"] = len(files)
        save_state(state)

        is_new_article = fname.startswith("Clanek-")
        is_vychova = fname == "Vychova.dc.html"

        if is_new_article:
            article_spec = _extract_article_spec(design, fname)
            prompt = (
                f"Napiš HTML soubor `{fname}`.\n\n"
                f"ŠABLONA — zkopíruj strukturu přesně:\n```html\n{template}\n```\n\n"
                f"OBSAH PRO TENTO ČLÁNEK:\n{article_spec}\n\n"
                f"Kicker: 'Kooperativní péče'. Zpětný odkaz: Vychova.dc.html. "
                f"Zdroje: prázdné, jen komentář. Žádné vymyšlené URL.\n"
                f"Write do `{fname}`, pak: git add {fname} && git commit -m 'feat: {fname}'"
            )
            text, tin, tout, dur = run_agent("article-writer", prompt, timeout=180, add_dir=False)
            agent_name = "article-writer"
        elif is_vychova:
            vychova_current = vychova_file.read_text() if vychova_file.exists() else ""
            prompt = (
                f"Uprav soubor `Vychova.dc.html` — přidej sekci Kooperativní péče.\n\n"
                f"AKTUÁLNÍ OBSAH:\n```html\n{vychova_current}\n```\n\n"
                f"CO PŘIDAT (z design.md):\n{_extract_article_spec(design, 'Vychova.dc.html')}\n\n"
                f"Vlož novou sekci Kapitola 3 mezi konec Kapitoly 2 a blok Filozofie. Zbytek NEMEŇ.\n"
                f"Použij Write pro zápis celého souboru. Pak git add + commit 'feat: Vychova.dc.html'. Hotovo."
            )
            text, tin, tout, dur = run_agent("web-developer", prompt, timeout=720, add_dir=False)
            agent_name = "web-developer"
        else:
            prompt = (
                f"Implementuj soubor `{fname}` dle design.md.\n\n"
                f"design.md:\n{design}\n\n"
                f"Jsi na branchi {state['branch']}. Git add + commit 'feat: {fname}'. Hotovo."
            )
            text, tin, tout, dur = run_agent("web-developer", prompt, timeout=720, add_dir=False)
            agent_name = "web-developer"

        total_in += tin
        total_out += tout
        log_tokens(state, agent_name, f"implementer:{fname}", "PASS", tin, tout, dur,
                   files_changed=_count_changed_files())
        state.pop("current_file", None)
        save_state(state)
        print(f"    → hotovo ({tin+tout:,} tok)")

    state.pop("current_file", None)
    state.pop("current_file_idx", None)
    state.pop("total_files", None)
    save_state(state)
    print(f"  → implementace celkem ({total_in+total_out:,} tokenů)")


def phase_coherence(state: dict):
    print("  🔗 COHERENCE REVIEW — kontrola konzistence terminologie a tónu...")
    # Sbírám změněné soubory z branchi (oproti main)
    diff = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True, text=True, cwd=str(REPO)
    )
    changed = [f for f in diff.stdout.strip().splitlines() if f.endswith(".html")]
    if not changed:
        # Fallback: všechny html soubory v repozitáři
        changed = [p.name for p in REPO.glob("*.dc.html")]

    prompt = (
        f"Proveď coherence review pro task '{state['task_id']}'.\n\n"
        f"Zkontroluj tyto soubory: {', '.join(changed)}\n\n"
        f"Přečti každý soubor a zkontroluj konzistenci terminologie, tónu a struktury "
        f"napříč všemi soubory. Vrať výsledek jako JSON do souboru coherence-report.json."
    )
    text, tin, tout, dur = run_agent("coherence-reviewer", prompt, timeout=600, add_dir=False)
    report = _extract_json(text) or {"status": "PASS", "issues": [], "raw": text}
    COHERENCE_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    status = report.get("status", "PASS")
    log_tokens(state, "coherence-reviewer", "coherence", status, tin, tout, dur)
    issues = report.get("issues", [])
    highs = [i for i in issues if i.get("severity") == "HIGH"]
    print(f"  → {status} | {len(issues)} issues ({len(highs)} HIGH)")
    if highs:
        for h in highs:
            print(f"    ⚠ [{h['type']}] {h['file']}: {h['description'][:80]}")


def phase_coherence_periodic():
    """Periodická kontrola celého webu — jen návrhy, nikdy neupravuje soubory."""
    print("  🔗 COHERENCE PERIODIC — prochází celý web...")
    all_html = sorted(REPO.glob("*.dc.html"))
    prompt = (
        f"Proveď periodickou coherence kontrolu celého webu Pozitivní pes.\n\n"
        f"Projdi VŠECHNY soubory: {', '.join(p.name for p in all_html)}\n\n"
        f"Hledej: nekonzistentní terminologii napříč stránkami, rozdíly v tónu, "
        f"strukturální nesrovnalosti. Výstup ulož do coherence-proposals.md jako "
        f"markdown seznam návrhů (bez JSON). Nikdy neupravuj html soubory."
    )
    text, tin, tout, dur = run_agent("coherence-reviewer", prompt, timeout=600, add_dir=True)
    proposals_file = REPO / "coherence-proposals.md"
    proposals_file.write_text(text)
    print(f"  → návrhy uloženy do coherence-proposals.md ({tin+tout:,} tok)")


def phase_gate(state: dict) -> bool:
    print("  🚦 AUTOMATED GATE — scripts/gate.sh...")
    result = subprocess.run(["bash", str(GATE_SCRIPT)], capture_output=True, text=True, cwd=str(REPO))
    print(result.stdout)
    passed = result.returncode == 0
    log_tokens(state, "gate-script", "gate", "PASS" if passed else "FAIL",
               0, 0, 0, gate_pass=passed)
    return passed


def phase_qa(state: dict):
    print("  🔬 QA AGENT — exploratory testing...")
    design = DESIGN_FILE.read_text() if DESIGN_FILE.exists() else ""
    acceptance = ACCEPTANCE_FILE.read_text() if ACCEPTANCE_FILE.exists() else ""
    run_id = state["run_id"]
    task_id = state["task_id"]
    prompt = (
        f"Proveď QA pro task '{task_id}' (run_id: {run_id}).\n\n"
        + (f"design.md:\n{design}\n\n" if design else "")
        + (f"ACCEPTANCE.md:\n{acceptance}\n\n" if acceptance else "")
        + "Přečti změněné soubory a napiš qa-report.json podle formátu z CLAUDE.md."
    )
    text, tin, tout, dur = run_agent("qa-agent", prompt, timeout=300, add_dir=True)
    # Extrahuj JSON z odpovědi
    qa_json = _extract_json(text) or {"status": "PASS", "findings": [], "raw": text}
    QA_REPORT.write_text(json.dumps(qa_json, indent=2, ensure_ascii=False))
    log_tokens(state, "qa-agent", "qa", qa_json.get("status", "PASS"), tin, tout, dur)
    print(f"  → qa-report.json ({len(qa_json.get('findings', []))} nálezů, {tin+tout:,} tokenů)")
    return qa_json


def phase_domain_review(state: dict):
    print("  🐾 DOMAIN REVIEWER — kontrola force-free souladu...")
    run_id = state["run_id"]
    task_id = state["task_id"]
    prompt = (
        f"Proveď domain review pro task '{task_id}' (run_id: {run_id}).\n"
        f"Přečti knowledge/red-lines.md, knowledge/domain-knowledge.md a změněné .dc.html soubory. "
        f"Napiš domain-review.json."
    )
    text, tin, tout, dur = run_agent("domain-reviewer", prompt, timeout=300, add_dir=True)
    dr_json = _extract_json(text) or {"status": "PASS", "red_line_triggered": False, "findings": [], "raw": text}
    DOMAIN_REVIEW.write_text(json.dumps(dr_json, indent=2, ensure_ascii=False))
    log_tokens(state, "domain-reviewer", "domain_review", dr_json.get("status", "PASS"), tin, tout, dur)
    print(f"  → domain-review.json ({len(dr_json.get('findings', []))} nálezů, {tin+tout:,} tokenů)")
    return dr_json


def phase_release(state: dict):
    print("  📋 RELEASE MANAGER — připravuje release report...")
    run_id = state["run_id"]
    task_id = state["task_id"]
    prompt = (
        f"Připrav release-report.md pro task '{task_id}' (run_id: {run_id}).\n"
        f"Přečti TASK.md, design.md, qa-report.json, domain-review.json. "
        f"Spusť git log a git diff pro přehled. "
        f"Napiš release-report.md — nemerge, nepush."
    )
    text, tin, tout, dur = run_agent("release-manager", prompt, timeout=180, add_dir=True)
    RELEASE_REPORT.write_text(text)
    log_tokens(state, "release-manager", "release", "PASS", tin, tout, dur)
    print(f"  → release-report.md ({tin+tout:,} tokenů)")

# ── Severity routing ──────────────────────────────────────────────────────────

def _max_severity(findings: list) -> str:
    order = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]
    for sev in order:
        if any(f.get("severity") == sev for f in findings):
            return sev
    return "INFO"


def _needs_human_after_review(qa_json: dict, dr_json: dict) -> bool:
    """HIGH nebo MEDIUM v jakémkoli reportu → human checkpoint."""
    all_findings = qa_json.get("findings", []) + dr_json.get("findings", [])
    sev = _max_severity(all_findings)
    return sev in ("BLOCKER", "HIGH", "MEDIUM")


def _is_blocker(qa_json: dict, dr_json: dict) -> bool:
    all_findings = qa_json.get("findings", []) + dr_json.get("findings", [])
    return any(f.get("severity") == "BLOCKER" for f in all_findings) or \
           dr_json.get("red_line_triggered", False)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    # Zkus najít JSON blok v textu
    match = re.search(r'\{[\s\S]+\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _count_changed_files() -> int:
    try:
        base = git(["merge-base", "HEAD", "main"], check=False) or "HEAD~1"
        out = git(["diff", base + "..HEAD", "--name-only", "--", "*.dc.html"])
        return len([l for l in out.splitlines() if l.strip()])
    except Exception:
        return 0


def _detect_risk_tier(task_text: str) -> str:
    """Heuristika pro detekci risk tieru z TASK.md. Human může přepsat."""
    import re
    # Explicitní override v TASK.md: řádek "RISK: M" / "RISK: L" / "RISK: S"
    explicit = re.search(r'^RISK:\s*([SML])', task_text, re.MULTILINE | re.IGNORECASE)
    if explicit:
        return explicit.group(1).upper()
    # L: explicitně riziková oblast
    l_triggers = ["support.js", "image-slot.js", "O-nas.dc.html",
                  "design systém", "architektur", "přejmenovat soubor"]
    # nav triggernuje L jen pokud jde o změnu nav (ne "nav zůstává", "nav se nemění")
    nav_change = re.search(r'nav.{0,20}(přidat|odebrat|změn|upravit|update)', task_text, re.I)
    if nav_change:
        l_triggers.append("_nav_change_detected")

    s_patterns = ["překlep", "typo", "broken link", "nefunkční odkaz",
                  "spacing", "drobná", "jeden odstavec", "oprav"]

    text_lower = task_text.lower()
    if any(p.lower() in text_lower for p in l_triggers) or nav_change:
        return "L"
    if any(p.lower() in text_lower for p in s_patterns):
        return "S"
    return "M"

# ── Commands ──────────────────────────────────────────────────────────────────

LOCK_FILE = PIPELINE_DIR / "pipeline.lock"


def _acquire_lock() -> bool:
    """Vrátí True pokud se podařilo získat lock (žádný jiný run neběží)."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            import os as _os
            _os.kill(pid, 0)  # process exists?
            return False  # stále běží
        except (ProcessLookupError, ValueError):
            LOCK_FILE.unlink(missing_ok=True)  # stale lock
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def _hourly_tokens_used() -> int:
    """Tokeny spotřebované za poslední hodinu (z token_log.jsonl)."""
    if not TOKEN_LOG.exists():
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - 3600
    total = 0
    with TOKEN_LOG.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
                ts = datetime.datetime.fromisoformat(rec.get("ts", "")).timestamp()
                if ts >= cutoff:
                    total += rec.get("tokens_in", 0) + rec.get("tokens_out", 0)
            except Exception:
                pass
    return total


HOURLY_TOKEN_CAP = int(os.environ.get("PIPELINE_HOURLY_CAP", "450000"))


def cmd_run():
    """Spustí nebo pokračuje v pipeline."""
    if not _acquire_lock():
        print("Pipeline již běží (lock existuje), přeskakuji.")
        sys.exit(0)

    try:
        _cmd_run_inner()
    finally:
        _release_lock()


def _cmd_run_inner():
    if not TASK_FILE.exists():
        print("ERROR: TASK.md nenalezen. Vytvoř ho nejdřív.")
        sys.exit(1)

    # Hodinový cap
    used = _hourly_tokens_used()
    if used >= HOURLY_TOKEN_CAP:
        print(f"⏳ Hodinový cap dosažen ({used:,}/{HOURLY_TOKEN_CAP:,} tok) — cron to zkusí znovu.")
        sys.exit(0)

    state = load_state()

    # Nový run?
    if not state or state.get("phase") == "done":
        task_text = TASK_FILE.read_text()
        run_id = new_run_id()
        # Task ID z prvního řádku TASK.md nebo timestamp
        first_line = task_text.strip().splitlines()[0].lstrip("#").strip()
        task_id = re.sub(r'[^a-z0-9-]', '-', first_line[:40].lower()).strip('-')

        risk_tier = _detect_risk_tier(task_text)
        branch = f"agent/{task_id}/{run_id}"

        state = {
            "run_id": run_id,
            "task_id": task_id,
            "risk_tier": risk_tier,
            "phase": SEQUENCES[risk_tier][0],
            "attempt": 1,
            "branch": branch,
        }
        print(f"Nový run: {run_id} | task: {task_id} | risk: RISK:{risk_tier}")
        print(f"Branch: {branch}")
        save_state(state)
    else:
        # Pokračujeme v existujícím runu
        phase = state.get("phase", "done")
        print(f"Pokračuji: run={state['run_id']} | phase={phase} | risk=RISK:{state['risk_tier']}")

        # Jsme na human checkpointu?
        if phase.startswith("HUMAN:"):
            if is_approved(state, phase):
                # Přejít na další fázi
                seq = SEQUENCES[state["risk_tier"]]
                idx = seq.index(phase)
                state["phase"] = seq[idx + 1]
                save_state(state)
                print(f"  → Schváleno, pokračuji na: {state['phase']}")
            else:
                print(f"  Čeká na schválení: python3 pipeline.py approve")
                return

    _run_sequence(state)


def _run_sequence(state: dict):
    """Spouští fáze od aktuální phase dokud nenarazí na checkpoint nebo done."""
    seq = SEQUENCES[state["risk_tier"]]
    max_gate_attempts = 3

    while True:
        phase = state["phase"]
        print(f"\n[{phase}]")

        if phase == "done":
            print("\n✅ Pipeline dokončena!")
            print(f"  Branch: {state['branch']}")
            print(f"  Přečti release-report.md a merguj ručně.")
            break

        if phase.startswith("HUMAN:"):
            if is_approved(state, phase):
                idx = seq.index(phase)
                state["phase"] = seq[idx + 1]
                save_state(state)
                continue
            else:
                human_checkpoint(state, phase)
                return  # human_checkpoint ukončí proces

        try:
            if phase == "researcher":
                phase_researcher(state)
            elif phase == "planner":
                phase_planner(state)
            elif phase == "implementer":
                phase_implementer(state)
            elif phase == "coherence":
                phase_coherence(state)
            elif phase == "gate":
                gate_ok = phase_gate(state)
                if not gate_ok:
                    state["attempt"] = state.get("attempt", 1) + 1
                    if state["attempt"] > max_gate_attempts:
                        print(f"\n🛑 Gate fail po {max_gate_attempts} pokusech → needs_human")
                        print("  Zkontroluj scripts/gate.sh výstup a oprav ručně.")
                        state["phase"] = "GATE_FAIL"
                        save_state(state)
                        sys.exit(1)
                    print(f"  Gate fail (pokus {state['attempt']}/{max_gate_attempts}), vracím implementera...")
                    state["phase"] = "implementer"
                    save_state(state)
                    continue
                state["attempt"] = 1
            elif phase == "qa":
                qa_json = phase_qa(state)
                state["_qa_json"] = qa_json
                if _is_blocker(qa_json, {}):
                    print("🛑 QA BLOCKER — pipeline zastavena. Oprav ručně, pak approve.")
                    human_checkpoint(state, "HUMAN:ACCEPT_FINDINGS")
                    return
            elif phase == "domain_review":
                dr_json = phase_domain_review(state)
                qa_json = state.get("_qa_json", {})
                state["_dr_json"] = dr_json
                if _is_blocker(qa_json, dr_json):
                    print("🛑 DOMAIN BLOCKER — pipeline zastavena.")
                    human_checkpoint(state, "HUMAN:ACCEPT_FINDINGS")
                    return
            elif phase == "release":
                phase_release(state)

        except subprocess.TimeoutExpired:
            print(f"  ⏱ Timeout pro fázi {phase}")
            state["attempt"] = state.get("attempt", 1) + 1
            save_state(state)
            sys.exit(1)
        except Exception as e:
            print(f"  ❌ Chyba ve fázi {phase}: {e}")
            save_state(state)
            sys.exit(1)

        # Přejít na další fázi
        idx = seq.index(phase)
        state["phase"] = seq[idx + 1]
        save_state(state)


def cmd_approve():
    """Schválí aktuální human checkpoint."""
    state = load_state()
    if not state:
        print("Žádný aktivní run.")
        sys.exit(1)

    phase = state.get("phase", "")
    if not phase.startswith("HUMAN:"):
        print(f"Aktuální fáze '{phase}' není human checkpoint.")
        sys.exit(1)

    approval_file = APPROVALS_DIR / f"{state['run_id']}_{phase}.approved"
    approval_file.write_text(json.dumps({
        "decision": "APPROVED",
        "phase": phase,
        "timestamp": datetime.datetime.now().isoformat(),
        "by": "human",
    }, indent=2))

    print(f"✓ Schváleno: {phase}")
    print("  Pokračuj s: python3 pipeline.py run")


def cmd_status():
    """Zobrazí aktuální stav pipeline."""
    state = load_state()
    if not state:
        print("Žádný aktivní run. Vytvoř TASK.md a spusť: python3 pipeline.py run")
        return

    print(f"Run ID:     {state.get('run_id')}")
    print(f"Task ID:    {state.get('task_id')}")
    print(f"Risk tier:  RISK:{state.get('risk_tier')}")
    print(f"Phase:      {state.get('phase')}")
    print(f"Branch:     {state.get('branch')}")
    print(f"Attempt:    {state.get('attempt', 1)}")

    # Token souhrn
    if TOKEN_LOG.exists():
        total_cost = 0.0
        total_tokens = 0
        run_id = state.get("run_id")
        with TOKEN_LOG.open() as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("run_id") == run_id:
                    total_cost += rec.get("cost_usd", 0)
                    total_tokens += rec.get("tokens_in", 0) + rec.get("tokens_out", 0)
        print(f"Tokeny:     {total_tokens:,} (${total_cost:.4f})")

    if PROGRESS_FILE.exists():
        print()
        print(PROGRESS_FILE.read_text())


def cmd_gate():
    """Spustí jen gate.sh."""
    result = subprocess.run(["bash", str(GATE_SCRIPT)], cwd=str(REPO))
    sys.exit(result.returncode)


def cmd_curator():
    """Spustí domain-knowledge-curator."""
    print("🌿 Domain Knowledge Curator — aktualizace knowledge/...")
    prompt = (
        "Aktualizuj knowledge/red-lines.md a knowledge/domain-knowledge.md. "
        "Přečti aktuální soubory, vyhledej nové poznatky z ověřených zdrojů, "
        "doplň nebo uprav záznamy s datem a zdrojem. Neupravuj nic jiného."
    )
    text, tin, tout, dur = run_agent("domain-knowledge-curator", prompt, timeout=600, add_dir=True)
    print(text[:500])
    print(f"\n→ Hotovo ({tin+tout:,} tokenů, ${(tin*3+tout*15)/1e6:.4f})")


def cmd_reset():
    """Resetuje stav pipeline (připraví na nový task)."""
    if STATE_FILE.exists():
        backup = STATE_FILE.with_suffix(".json.bak")
        STATE_FILE.rename(backup)
        print(f"Stav archivován do {backup}")
    # Smaž pracovní soubory
    for f in [RESEARCH_FILE, DESIGN_FILE, QA_REPORT, DOMAIN_REVIEW, RELEASE_REPORT]:
        if f.exists():
            f.unlink()
            print(f"Smazán: {f.name}")
    print("Reset hotov. Vytvoř nový TASK.md a spusť: python3 pipeline.py run")

# ── Main ──────────────────────────────────────────────────────────────────────

COMMANDS = {
    "run": cmd_run,
    "approve": cmd_approve,
    "status": cmd_status,
    "gate": cmd_gate,
    "curator": cmd_curator,
    "coherence": lambda: phase_coherence_periodic(),
    "reset": cmd_reset,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in COMMANDS:
        print(__doc__)
        print(f"Neznámý příkaz: {cmd}")
        sys.exit(1)
    COMMANDS[cmd]()
