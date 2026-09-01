# Red-lines — zakázaný obsah (Pozitivní pes)

> Tento soubor slouží jako základ pro deterministický scan (`scripts/redline-scan.sh`) i pro LLM domain reviewer. Každá položka má kategorii a příklady. Aktualizuje `domain-knowledge-curator`.
>
> Poslední aktualizace: 2026-09-01

---

## Kategorie 1: Zakázané pomůcky

Skript hledá tyto výrazy v diff. Jakákoli POZITIVNÍ zmínka (doporučení, "funguje", "zkuste") = BLOCKER. Odmítnutí nebo varování = OK.

### Elektrické obojky / e-collary
```
elektrický obojek
elektronický obojek
e-collar
shock collar
záškrtový obojek
anti-bark collar
protištekovací obojek
vibracni obojek doporučuj
```

### Stahovací / škrtící obojky
```
stahovací obojek
strangulační obojek
škrtící obojek
choke collar
slip collar doporučuj
smyčkový obojek doporučuj
```

### Bodákové / ostnaté obojky
```
bodákový obojek
ostnatý obojek
prong collar
pinch collar
kovový bodákový
```

### Citronella / sprejové obojky (averzivní)
```
citronella obojek
sprejový obojek
anti-bark spray collar
```

---

## Kategorie 2: Zakázané metody

Tyto výrazy jsou red-line pokud jsou prezentovány jako DOPORUČENÍ, ne jako odmítnuté techniky.

### Fyzické tresty
```
fyzický trest
praštit
kopnout psa
udeřit psa
plácnout psa
bít psa
šlápnout
```

### Dominanční teorie (jako pozitivní doporučení)
```
alfa samec
alfa pes
alf\w+ postavení doporučuj
dominantní pes zkrotit
smečková hierarchie uplatni
smečkový vůdce musíš být
ukáž mu kdo je šéf
kdo je tady pánem
dominance over dog
cesar millan metod
```

### Flooding / nucené vystavení
```
nucené vystavení strachu
flooding technika
systematic flooding
drž ho dokud se neuklidní
donuť ho přivyknout
```

### Alpha rollover
```
alpha roll
alfa přehoz
přehoz na záda
dominance roll
přitlač na zem
```

### Aversivní trénink obecně
```
averzivní metoda doporučuj
punishment based
trest jako výcvik
trestání funguje
negative punishment.*hlavní metod
```

---

## Kategorie 3: Kontraindikované rady (zdravotní)

Tyto rady jsou zdravotně nebezpečné pro psy.

```
syrové vepřové doporučuj
čokoláda.*bezpečná
hrozny.*bezpečné
cibule.*malé množství.*bezpečn
xylitol.*bezpečn
kostičky.*z kosti.*bezpečn
kosti z drůbeže.*bezpečn
```

---

## Kategorie 4: Věkově nevhodná doporučení

```
štěně.*očkovat.*dříve.*6 týdn
odstavit.*dříve.*6 týdn
kastrovat.*dříve.*6 měsíc
venku.*před očkováním.*bezpečn
```

---

## Poznámky pro domain reviewer (LLM vrstva)

Deterministický scan zachytí doslovné shody. LLM reviewer kontroluje navíc:

1. **Opis bez klíčových slov**: "metoda, kdy pes pocítí nepříjemný podnět" = averzivní metoda i bez klíčového slova
2. **Produkty s averzivním principem**: obojky se "zápornou stimulací", "korekčním impulsem" apod.
3. **Dominanční teorie přes metafory**: "musíš být vůdce smečky", "respekt si musíš vybojovat"
4. **Selektivní citování**: citát z force-free zdroje vytržený z kontextu, aby podporoval trest
5. **False balance**: "někteří tréninkové odborníci doporučují elektrické obojky" bez jasného odmítnutí z naší strany
