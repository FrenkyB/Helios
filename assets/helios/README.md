# Helios Airways 5B-DBY Olympia — poslikava

Poslikava je vizualno rekonstruirana iz obeh slik v uporabniškem paketu `HELIOS_LIVERY_REFERENCE_PACK`: `Helios_Airways_Boeing_737-300_5B-DBY.jpg` in `caf5eab8-0bb8-47d8-bd5d-0b8bebe91132.webp`.

`helios_tail_reference.webp` je nespremenjena kopija druge slike. Na repu je s koordinatami UV uporabljen samo motiv zlate glave, slika pa je vgrajena v končni `.blend`. Podrobnost glave je omejena z ločljivostjo izvorne fotografije. Vir paketa ne navaja avtorja ali licence te fotografije.

Modra in bela barva ter zlati koncentrični krogi so proceduralni materiali. Napisi HELIOS, www.flyhelios.com, OLYMPIA in 5B-DBY so površinski vektorski vložki. Pisava glavnega napisa je vizualni približek logotipa s krepkimi pravokotnimi serifi; ne gre za izvirno vektorsko datoteko znamke.

`lettering_geometry.json` vsebuje pripravljeno geometrijo napisov. Za generiranje z vključeno datoteko niso potrebne nameščene pisave ali povezava z internetom.

Ponovitev: `python run_all.py --helios-livery` iz korenske mape projekta. Skripta uporabi shranjeni popravljeni model, doda samo poslikavo in po ponovnem odprtju preveri ohranitev izvirne geometrije ter vgrajeno teksturo. Podrobno poročilo nastane v `reports/helios_livery.json`.
