# QA Learnings — reálné incidenty

Tento soubor slouží jako živá paměť QA agenta. Každý incident je zdokumentován s přesným popisem chyby a jak vypadala oprava, aby příští kontrola věděla, na co se zaměřit.

---

## Incident 001 — 2026-09-03 — task: nov--podrubrika--kooperativn--p--e

### 1. Zjednodušený footer místo site-wide footeru

**Co se stalo:** Dva nové články (Clanek-DrapkyBezBoje.dc.html, Clanek-VetTrenink.dc.html) měly minimalistický 2-linkový footer uvnitř `<article>` elementu místo plného site-wide footeru.

**Jak chyba vypadala:**
```html
<footer style="margin-top:64px; padding-top:24px; border-top:1px solid ...">
  <a href="Homepage.dc.html">Domů</a>
  <a href="Checklist.dc.html">Checklist</a>
</footer>
```

**Jak správný footer vypadá:**
```html
<footer style="background:#2B241C; padding:clamp(32px,5vw,56px) ...">
  <!-- logo + 4 navigační odkazy + copyright -->
</footer>
```

**Jak kontrolovat:** Každý `.dc.html` musí mít `<footer style="background:#2B241C">` jako sibling `</article>`, nikoli uvnitř article. Musí obsahovat 4 navigační linky (Výchova, Vybavení a recenze, Checklist, O nás).

---

### 2. Neshoda H1 článku s textem karty na Vychova.dc.html

**Co se stalo:** H1 v článcích se lišilo od textu `<h3>` v kartách na Vychova.dc.html.

**Příklady:**
- BucketGame: H1 „...jak ho naučit" vs karta „...proč ho naučit první"
- ChinRest: H1 „...uší, očí a tlamy" vs karta „...uší a očí"
- DrapkyBezBoje: H1 „...od nulté tolerance" vs karta „...od nuly"

**Jak kontrolovat:** Pro každý nový článek zkontroluj kartu na Vychova.dc.html — `<h3>` karta musí přesně odpovídat H1 z článku (nebo být záměrně kratší, ale nesmí se věcně lišit).

---

### 3. Prázdná sekce Zdroje

**Co se stalo:** Všechny 4 nové články měly sekci `<h2>Zdroje</h2>` s prázdným `<ul>` a komentářem `<!-- ZDROJE: doplní researcher -->`. QA musí tuto situaci hlásit jako FAIL.

**Pravidlo:** Sekce Zdroje MUSÍ obsahovat alespoň 2 reálné zdroje s URL nebo bibliografickou citací. Prázdná sekce nebo samotný placeholder komentář = FAIL HIGH.

---

### 4. Faktická chyba — pohlaví osoby

**Co se stalo:** Text v Clanek-BucketGame.dc.html uváděl „Vymyslela ji **trenérka** Chirag Patel" — Chirag Patel je muž.

**Jak kontrolovat:** Jména vlastní osob kontroluj ve spojení s přívlastky rodu. Pokud si nejsi jistý pohlavím, použij neutrální formulaci nebo flag jako MEDIUM.

---

### 5. Typo z rychlého psaní

**Co se stalo:** Clanek-VetTrenink.dc.html: „kovo zvuk" místo „kovový zvuk" (chybějící přípona adjektiva).

**Jak kontrolovat:** Při čtení článků hledej sekvence slov, kde přídavné jméno zdánlivě schází příponu (-ý, -á, -é). Obzvlášť u technického popisu materiálů a procedur.

---

### 6. Typo — mezera v compound slově

**Co se stalo:** Vychova.dc.html: „férovéhokomunikace" místo „férové komunikace" — chybějící mezera uvnitř přivlastňovacího spojení.

**Jak kontrolovat:** Hledej neobvykle dlouhá slova (>15 znaků) v plynném textu — mohou být dvě slova slepená bez mezery.

---

## Jak přidat nový incident

Po každém task kde QA nebo domain review odhalí a opraví chybu:
1. Přidej nový `## Incident NNN` s datem a task ID
2. Stručně popiš: Co se stalo / Jak chyba vypadala / Jak správně vypadá / Jak kontrolovat
3. Commit spolu s ostatními změnami tasku
