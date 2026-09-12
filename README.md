# HEL-1 — Boeing 737-300 Classic

Minimalni paket za uporabo in ponovno generiranje modela s popravljenimi pilotskimi okni.

Končni model: **models/Boeing_737-300.blend**. Datoteka je samostojna; za odpiranje ne potrebuje referenčnih fotografij ali zunanjih tekstur.

## Zahteve

- Python 3.10 ali novejši.
- Blender; model in preverjanje sta bila izvedena z Blenderjem 5.2.1 LTS.
- Dodatni Python paketi niso potrebni. `bpy` se uporablja znotraj Blenderja.

## Generiranje

Ukaza zaženi zaporedoma v tej mapi:

```powershell
python run_all.py --skip-render
python run_all.py --correct-cockpit --skip-render
```

Prvi ukaz ustvari osnovni model `models/HEL-1_Boeing_737-300.blend`, vključno z notranjima scenama, in ga preveri. Drugi popravi pilotska okna, shrani `models/Boeing_737-300.blend` in preveri ohranitev ostalih objektov. Drugi ukaz prepiše priloženi končni model z regeneriranim rezultatom. Binaren zapis datoteke se lahko med zagoni razlikuje.

Za izrise izpusti `--skip-render`. Po potrebi vsakemu ukazu dodaj `--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"` ali nastavi okoljsko spremenljivko `BLENDER_EXE`.

Mape `logs`, `reports` in `renders` nastanejo samodejno. Referenčne fotografije niso vhodna odvisnost skript; kontrolne točke oken so zapisane v `scripts/correct_cockpit_windows.py`, mere letala pa v `config/aircraft.json`.

## Vsebina za GitHub

- `run_all.py`: skupna vstopna skripta za oba koraka in preverjanje.
- `config/aircraft.json`: konfiguracija letala.
- `scripts/`: sedem skript za geometrijo, notranjost, korekcijo in preverjanje.
- `models/Boeing_737-300.blend`: končni popravljeni model.
- `README.md` in `.gitignore`: navodila in izločitev začasnih rezultatov.

## Reference za pilotska okna

Geometrija je vizualno prilagojena referencam, ne izdelana iz tovarniških mer zasteklitve. Šipe so površinski vložki na ohranjeni mreži nosu.

- [Norwegian B737-300 LN-KKN — Alasdair McLellan](https://commons.wikimedia.org/wiki/File:Nose_view_of_Norwegian_B737-300_LN-KKN_at_V%C3%A6rnes.jpg), CC BY-SA 3.0.
- [KLM B737-300 PH-BDO — Pieter van Marion](https://commons.wikimedia.org/wiki/File:KLM_Boeing_737-300_PH-BDO_nose_section_(3247986866).jpg), CC BY-SA 2.0.
- [Boeing 737-300 front view — NASA/Dryden](https://commons.wikimedia.org/wiki/File:Boeing_737-300_front_view.svg), public domain.

Fotografije niso vključene v paket ali uporabljene kot teksture.
