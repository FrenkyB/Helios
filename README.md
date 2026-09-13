# HEL-1 — Boeing 737-300 Classic / Helios Airways

Končni model: **models/Boeing_737-300_Helios_Livery.blend**. Vsebuje zunanjost s poslikavo 5B-DBY »Olympia«, obstoječi cockpit in vgrajeno potniško kabino. Tekstura repa je vgrajena; dodatne fotografije in Python paketi niso potrebni.

## Ena gradnja za celoten model

V tej mapi zaženi:

```powershell
python run_all.py
```

Ukaz zaporedoma zgradi osnovni model in kabino, uporabi obstoječo korekcijo pilotskih oken, nanese Helios poslikavo, ponovno odpre shranjene datoteke in preveri rezultat. Na koncu izriše zunanjost ter štiri poglede kabine. Koda geometrije cockpita in korekcije pilotskih oken je nespremenjena.

```powershell
python run_all.py --skip-render  # celoten model in vsa preverjanja brez izrisov
python run_all.py --draft        # celoten model s hitrejšimi izrisi
```

Zahteve: Python 3.10+ in Blender (preverjeno z 5.2.1 LTS). Po potrebi dodaj `--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"` ali nastavi `BLENDER_EXE`.

Pred prepisom obstoječih modelov se kopije shranijo v `reports/backups/<čas>/`. Ročno spremenjene modele ohrani tudi v svoji ločeni datoteki: polna gradnja vedno regenerira geometrijo iz skript.

## Potniška kabina

- 23 vrst / 138 sedežev v razporedu 3 + 3; oznake ABC na levi in DEF na desni strani, gledano proti nosu.
- Nominalni razmik vrst 0,79 m, čista širina prehoda 0,51 m in večji razmik pri izhodih nad krili.
- Oblazinjeni temnomodri sedeži z belimi prevlekami vzglavnikov, mizicami, zaponkami, žepi, varnostnimi karticami in pasovi.
- Skupni nasloni za roke, nosilci trojčkov, noge in talne tirnice.
- Obloge, okenski okvirji, strop, zaprti prtljažni predali, PSU z zračniki in bralnimi lučmi ter talna zasilna osvetlitev.
- Sprednji servisni omari, zadnji galley in poenostavljen WC z ločenimi stenami, vrati, školjko in umivalnikom.

Mere in razpored so v `config/aircraft.json` pod `cabin`. Osnova so uporabniške fotografije iz `B737-300_SEATS_REFERENCE_PACK`, zlasti Norwegian Classic kabina. To je vizualna rekonstrukcija, ne potrjen sedežni načrt Helios 5B-DBY. Fotografije niso vključene kot teksture in niso potrebne za gradnjo.

Kabina je v zbirki `B737_300_CABIN_STUDY`, ki je povezana tudi v glavno sceno letala. Sedeži delijo mreže za manjšo datoteko; posamezne objekte je mogoče premikati, za neodvisno urejanje mreže pa uporabi Make Single User.

V Blenderjevem izbirniku scen:

- `HEL-1 | Boeing 737-300`: celotno letalo s kabino v trupu.
- `02 | Cockpit study`: obstoječa nespremenjena študija cockpita.
- `03 | Passenger cabin - 138 seats`: notranji pogled po prehodu; dodatni kameri za pogled nazaj in detajl sedežev.
- `04 | Passenger cabin layout`: tloris s skupnimi objekti sedežev in tal, brez oblog in stropa.

Obstoječa zunanja lupina ostaja zaprta; potniška okna so notranji osvetljeni vložki in niso nove odprtine skozi trup. Za pregled notranjosti uporabi sceno 03 ali 04 oziroma skrij zunanje zbirke. Servisna oprema je vizualna in brez animacij ali delujočih sistemov.

Izrisi: `renders/helios/` in `renders/passenger/` (`aisle_forward`, `aisle_aft`, `seat_detail`, `layout`). Dnevniki in preverjanja: `logs/` in `reports/`.

## Posamezni koraki

```powershell
python run_all.py --passenger-cabin --skip-render
python run_all.py --base-only --skip-render
python run_all.py --correct-cockpit --skip-render
python run_all.py --helios-livery --skip-render
```

`--passenger-cabin` nadgradi samo potniški del obstoječega končnega Helios modela in po shranjevanju preveri ohranitev vseh drugih objektov ter njihovih materialov. `--source "pot/model.blend"` izbere drug vhod pri tem koraku, korekciji ali poslikavi. Izhod kabine in poslikave je vedno `models/Boeing_737-300_Helios_Livery.blend`.

`--base-only` izdela `models/HEL-1_Boeing_737-300.blend`; `--views` pri tem določa zunanje izrise. `--exterior-only` je izbirna regeneracija brez obeh notranjosti. Privzeta gradnja vključuje vse.

Preverjanje kabine po ponovnem odprtju vključuje število in oznake sedežev, razpored 3 + 3, širino prehoda, prost prehod ob nadkrilnem izhodu, pripadnost glavni sceni in prileganje ovrednotene geometrije trupu. Skripta `verify_passenger_cabin.py` podpira tudi `--baseline` za primerjavo cockpita in materialov z obstoječim modelom.

Vmesni modeli: `HEL-1_Boeing_737-300.blend` (osnova) in `Boeing_737-300.blend` (obstoječa korekcija zasteklitve). Poslikava potrebuje `assets/helios/lettering_geometry.json` in `assets/helios/helios_tail_reference.webp`; podrobnosti so v `assets/helios/README.md`.

## Reference za pilotska okna

Geometrija je vizualno prilagojena referencam, ne izdelana iz tovarniških mer zasteklitve. Šipe so površinski vložki na ohranjeni mreži nosu.

- [Norwegian B737-300 LN-KKN — Alasdair McLellan](https://commons.wikimedia.org/wiki/File:Nose_view_of_Norwegian_B737-300_LN-KKN_at_V%C3%A6rnes.jpg), CC BY-SA 3.0.
- [KLM B737-300 PH-BDO — Pieter van Marion](https://commons.wikimedia.org/wiki/File:KLM_Boeing_737-300_PH-BDO_nose_section_(3247986866).jpg), CC BY-SA 2.0.
- [Boeing 737-300 front view — NASA/Dryden](https://commons.wikimedia.org/wiki/File:Boeing_737-300_front_view.svg), public domain.

Fotografije niso vključene v paket ali uporabljene kot teksture.
