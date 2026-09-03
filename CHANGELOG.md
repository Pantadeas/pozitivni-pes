
## 2026-09-02 — fix: article-writer double-call

**Problém:** `phase_implementer` volal `article-writer` pro nové Clanek-* soubory, ale pak padl skrz na sdílenou `run_agent("web-developer")` — každý nový článek spotřeboval 2× agenty.

**Příčina:** Sdílený `run_agent` call byl mimo if/elif/else blok — vždy se zavolal.

**Fix:** Každá větev (`is_new_article` / `is_vychova` / else) teď vlastní svůj `run_agent` + `agent_name`. Log_tokens používá proměnnou `agent_name`.

---

## 2026-09-03 — fix: EOF bug v run_agent (coherence/qa/domain/release timeouty)

**Problém:** Coherence, QA, domain review a release manager opakovaně timeoutovaly i po dokončení agenta.

**Příčina:** `select()` loop v `run_agent` — když agent skončí a stdout dosáhne EOF, `select()` vrací `ready=True` pořád, `readline()` vrací `""` pořád, ale blok `if not line` neexistoval → smyčka nikdy nedosáhla větve `proc.poll()` a běžela až do deadlinu (300s nebo 600s).

**Fix:** Přidán `if not line: break` v `ready` větvi — EOF okamžitě ukončí smyčku.

---

## 2026-09-03 — fix: coherence — zkrácení promptu + zvýšení timeoutu

**Problém:** Coherence agent dostával 8KB na soubor × 5 souborů = 40KB prompt → i po EOF fixu příliš pomalé.

**Fix:** Zkráceno na 3KB/soubor (kicker, H1, H2 stačí pro terminologii), timeout 300s → 600s.

---

## 2026-09-03 — fix: QA a domain review — agenti čtou soubory sami

**Problém:** QA a domain review dostávaly soubory zkrácené na 8KB v promptu → agenti viděli HTML oříznuté uprostřed a hlásili "soubor zkrácen" jako BLOCKER.

**Příčina:** Soubory jsou 11–30 KB, truncate na 8000 bytů vytvářel falešné nálezy.

**Fix:** Agenti dostávají jen seznam souborů + kontext; čtou je celé sami přes Read tool (`add_dir=True`). Tokeny vzrostly (~55k pro QA), ale nálezy jsou teď správné.

---

## 2026-09-03 — fix: release-manager — odstraněn Bash tool

**Problém:** Release manager měl `tools: Read, Bash`, snažil se spouštět git příkazy a zapisovat soubor shellem → permission prompt bez TTY → 180s timeout každý pokus.

**Fix:** `tools: Bash` odstraněn. Agent vrací report jako text v odpovědi, pipeline ho uloží do `release-report.md`. Git přehled sestavuje z PROGRESS.md a design.md.

---

## 2026-09-03 — feat: release report jako management dokument

**Problém:** Release report byl plný AI žargonu (run_id, BLOCKER, gate, agent) — nečitelný pro lidi mimo projekt.

**Fix:** Nový formát: lidsky psaný pro management — co je nového, nové stránky v tabulce, prošlo kontrolou (✅/⚠️/❌), co zbývá doplnit, jak zveřejnit.

---

## 2026-09-03 — feat: QA se učí z reálných incidentů (knowledge/qa-learnings.md)

**Problém:** QA agent opakoval stejné typy chyb — nevěděl o vzorech z předchozích tasků.

**Fix:** Vytvořen `knowledge/qa-learnings.md` — living document reálných incidentů s přesným popisem chyby a jak správně vypadá oprava. QA agent ho čte jako první krok. Checklist qa-agent.md rozšířen o konkrétní pravidla (plný footer, H1 vs karty, neprázdné Zdroje).

**Incident 001 (sept 2026):** 6 vzorů — zjednodušený footer, H1/karta mismatch, prázdné Zdroje, gender typo (Chirag Patel), adjektivní typo (kovo→kovový), compound typo (férovéhokomunikace).

---

## 2026-09-03 — feat: dashboard — strukturované zobrazení reportů

**Problém:** Dashboard ukazoval coherence report jen jako jednořádkový summary, QA a domain review vůbec ne.

**Fix:** Nová sekce `dev-reports-wrap` — tři karty (🔗 Coherence / 🔬 QA / 🐾 Domain review) se všemi nálezy v přehledné tabulce (závažnost, soubor, řádek, popis). Načítá JSON soubory z branchi.

