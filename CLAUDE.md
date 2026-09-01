# Pozitivní pes — CLAUDE.md

## Projekt

Web o pozitivním výcviku psů pro české majitele. Výhradně force-free metody — bez elektrických obojků, stahovacích obojků, přinucení nebo trestání. Cílová skupina: nový majitel štěněte nebo adoptovaného psa.

Autoři: Kuba (obsah, výcvik) + Simona (organizace). Jedna 2letá dcerka.

## Tech stack

- **Framework:** dc-runtime (vlastní). Soubory `.dc.html` — obaleny `<x-dc>`, head se injektuje přes `<helmet>`. Žádný build krok, žádný bundler, žádný package.json.
- **Rendering:** `support.js` (dc-runtime engine, 60 KB) + `image-slot.js` (lazy image helper). Oba soubory v root adresáři — **nemazat, neupravovat bez RISK:L tasku**.
- **Hosting:** VPS, statické soubory servírované přímo. Server log: `server.log` (nearchivovat, necommitovat).
- **Test runner:** žádný. Automatizovaná brána = `scripts/gate.sh` (HTML parse + red-line scan + interní linky).
- **Git remote:** `https://github.com/Pantadeas/pozitivni-pes.git`, branch `main`.

## Kde co je

```
/opt/pozitivni-pes/
├── Homepage.dc.html          # Hlavní stránka (SVG ilustrace, nav, hero)
├── Checklist.dc.html         # Interaktivní checklist (main product)
├── Vychova.dc.html           # Hub: sekce 4+5 (první dny + napořád)
├── Vybaveni-a-recenze.dc.html # Hub: vybavení + zabezpečení
├── O-nas.dc.html             # O nás (Kubův příběh — citlivé, RISK:M)
├── Clanek-*.dc.html          # Články (35+ souborů)
├── support.js                # dc-runtime engine — NEUPRAVOVAT bez L tasku
├── image-slot.js             # lazy image — NEUPRAVOVAT bez L tasku
├── knowledge/                # Doménová znalostní báze (jen knowledge-curator)
│   ├── red-lines.md          # Zakázaná klíčová slova a metody
│   └── domain-knowledge.md   # Aktuální doménové znalosti s datumem
├── scripts/
│   ├── gate.sh               # Automatizovaná brána (PASS/FAIL)
│   └── redline-scan.sh       # Deterministický scan na zakázaný obsah
├── .claude/agents/           # Agent definice pro pipeline
├── .pipeline/                # Stav, logy, approvals pipeline
├── docs/                     # Framework dokumentace
└── pipeline.py               # Orchestrátor vývojové pipeline
```

## Design systém

**Barvy:**
- `#F6F1E4` — krémové pozadí (bg)
- `#2B241C` — tmavý text (primary)
- `#2D5F4C` — tmavá zelená (akcent, nav, klikatelné prvky)
- `#C96A4E` — terakota (linky, CTA)
- `#E0A83E` — zlatá (selection, zvýraznění)
- `#C7D3B6` — světle zelená (borders, table lines)

**Fonty (Google Fonts):**
- `Fraunces` — nadpisy, logo (serif, variable: `opsz,wght`)
- `Karla` — tělo textu (sans-serif)
- `Space Mono` — monosace akcenty (tabulky, kikkery, labels)

**Struktura článku** (`.dc.html` vzor z `Clanek-Pelisek.dc.html`):
1. `<helmet>` — fonts, globální CSS
2. Nav (stejný na všech stránkách — Výchova / Vybavení a recenze / Checklist / O nás)
3. Kicker (sekce: "Vybavení" / "Výcvik" / "První dny doma" / "Napořád" / "Administrativa")
4. Titulek H1 + perex
5. Tělo článku (H2 sekce, tabulky, blockquotes pro citace/tipy)
6. Sekce "Zdroje" (jen ověřené URL z výzkumu — žádné vymyšlené)
7. Footer s odkazem na Homepage + Checklist

## Risk tier pravidla (pro tento projekt)

**RISK:L — Vyžaduje RESEARCHER + PLANNER + 3× human checkpoint:**
- Změny v `support.js` nebo `image-slot.js`
- Změny nav struktury (přidání/odebrání položky nav na všech stránkách)
- Změny barvy/fontu na úrovni design systému (affects all pages)
- Stránka `O-nas.dc.html` (osobní příběh, citlivé)
- Architektonická změna (nový typ stránky, nový hub)
- Změna URL struktury (přejmenování souborů, které jsou linkované ze Checklistu)

**RISK:M — Vyžaduje PLANNER + 2× human checkpoint (default):**
- Nový článek (`Clanek-*.dc.html`)
- Aktualizace existujícího článku (přidání sekce, oprava faktů)
- Nová hub stránka
- Změna obsahu hub stránek (Homepage, Vychova, Vybaveni-a-recenze)
- Změna Checklist.dc.html (komplexní stránka)

**RISK:S — Přímá implementace bez plánování:**
- Oprava překlepu (1–3 slova)
- Oprava nefunkčního odkazu
- Drobná CSS úprava na jedné stránce (spacing, color jednotlivého prvku)
- Přidání jednoho odstavce do existujícího článku

## Invarianty (nikdy neporušit)

1. **Force-free only** — žádné averzivní metody, žádné trestání. Viz `knowledge/red-lines.md`.
2. **Žádné vymyšlené URL** — každý odkaz v článku musí pocházet z ověřených zdrojů.
3. **Nav konzistence** — všechny `.dc.html` stránky musí mít stejné 4 nav položky.
4. **Žádný přímý push do `main`** — agenti commitují na branch `agent/<task-id>/<run-id>`, human merguje.
5. **`support.js` a `image-slot.js`** — nepsat nad ně bez explicitního L tasku.
