# Obecný rámec v3: Sekvenční multi-agentní vývojová pipeline (Claude Code)

> **Jak používat:** Celý dokument (sekce 1–8) je obecný a projektově neutrální. Pro nový projekt vezmi tento dokument jako prompt/kontext a v samostatné session/promptu ho nech "nasroubovat" na konkrétní problematiku. Výstupem je vždy samostatný, projektově specifický scaffold — ne úprava tohoto dokumentu.
>
> **Status: v1.0.** Sekce 7 (CLI/hooks) je **living detail** — re-verifikuj před implementací.

## 1. Základní principy

1. Agenti si nepředávají paměť, ale verziované artefakty.
2. Sekvenční, ne paralelní.
3. Specializace + omezený kontext.
4. Automatizované brány jsou skript, ne LLM.
5. Role needituje vlastní práci.
6. Verzování je striktní. Branch `agent/<task-id>/<run-id>`.
7. Human checkpointy jsou typované: `HUMAN:APPROVE_DESIGN`, `HUMAN:APPROVE_SCOPE_CHANGE`, `HUMAN:ACCEPT_FINDINGS`, `HUMAN:APPROVE_RELEASE`.
8. Cena za hotový feature, ne jen tokeny za volání.

## 2. Risk tier

```
L — explicitně riziková oblast
S — bezpečná izolovaná změna
M — default
```

## 3. Artefakty

```
TASK.md / ACCEPTANCE.md / research.md / design.md /
qa-report.json / domain-review.json / release-report.md /
.pipeline/config.yaml / .pipeline/state.json
```

## 4. Sekvence

**S:** implementer → gate → done

**M:** planner → HUMAN:APPROVE_DESIGN → implementer → gate → qa → domain_review → HUMAN:ACCEPT_FINDINGS → release → HUMAN:APPROVE_RELEASE → done

**L:** researcher → planner → HUMAN:APPROVE_DESIGN → implementer → gate → qa → domain_review → HUMAN:ACCEPT_FINDINGS → release → HUMAN:APPROVE_RELEASE → done

## 7. Claude Code mechanismy (verifikováno 2026-09-01 na tomto VPS)

- `claude -p "prompt" --agent <name>` načítá `.claude/agents/<name>.md` z CWD. **Ověřeno funkční.**
- `tools:` v frontmatteru souboru agenta = tvrdé omezení nástrojů. **Ověřeno funkční.**
- `--output-format json` vrací `{result, usage: {input_tokens, output_tokens, cache_read_input_tokens}}`. **Ověřeno.**
- `--system-prompt-file <path>` — alternativa k `--agent`, ignoruje frontmatter. **Ověřeno.**
- `--add-dir <path>` — přidá adresář do povolených cest pro nástroje. **Ověřeno.**
- Hooks (`PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`) — přítomny v CLI help, nebyly testovány v pipeline kontextu. Nepoužívány v pipeline.py (nahrazeny deterministickým gate skriptem).
- `--max-turns` — v help uveden, nepotřebný při použití `--agent` (agenti jsou task-bounded).
- Rozpočtové flagy — neověřeny, pipeline používá vlastní token tracking.
