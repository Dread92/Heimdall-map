"""Build data/regional_places.json — the villages and city districts of the oblasts that have a channel of their own.

    python scripts/build_places.py UA.txt alternatenames-UA.txt

The two files are GeoNames' Ukraine dumps (https://download.geonames.org/export/dump/UA.zip and
.../alternatenames/UA.zip, CC BY 4.0 — attribution in docs/TECHNICAL.md). Without arguments both are downloaded.

1.43 (1.44: and Sumy, Mykolaiv, Poltava, Vinnytsia, Zhytomyr; 1.45: Kherson, Kirovohrad, Khmelnytskyi, Ternopil, Rivne,
Lviv, Volyn). The gazetteer in app/geo.py holds the towns the Air Force and the Kyiv trackers name — a few hundred. A
regional tracker names villages: "2 реакти від Куликівки на Лихачів", "Стрюково", "Троицкое", "БпЛА на Лесное -
Пятихатки". This file holds every populated place of those oblasts with its Ukrainian name, its Russian name (the
Odesa and Kharkiv channels write in Russian) and the raion it is in. geo.py matches these names ONLY in a post from
that oblast's own channel, or a post that names that oblast — "Іванівка" alone, from a Kyiv channel, is nothing.

A name several villages of the same oblast share is kept with all of them; geo.py never picks one at random (see
REGIONAL in geo.py: the one nearest the channel's previous report, or a clear raion/hromada centre, or nothing).
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GeoNames admin1 code → the app's oblast uid. Only the oblasts that have a regional channel (1.43; 1.44: Sumy, Mykolaiv,
# Poltava, Vinnytsia, Zhytomyr).
ADMIN1 = {"02": "25", "01": "24", "17": "18", "07": "22", "04": "9",
          "21": "20", "16": "17", "18": "19", "23": "4", "27": "10",
          # 1.45: Kherson, Kirovohrad, Khmelnytskyi, Ternopil, Rivne, Lviv, Volyn
          "08": "23", "10": "15", "09": "3", "22": "21", "19": "5", "15": "27", "24": "8"}

# GeoNames admin2 (the raions of the 2020 reform) → the short Ukrainian label shown after a name several villages share
RAION = {
    ("02", "7402"): "Корюківський р-н", ("02", "7404"): "Ніжинський р-н", ("02", "7406"): "Новгород-Сіверський р-н",
    ("02", "7408"): "Прилуцький р-н", ("02", "7410"): "Чернігівський р-н",
    ("01", "7102"): "Звенигородський р-н", ("01", "7104"): "Золотоніський р-н", ("01", "7106"): "Уманський р-н",
    ("01", "7108"): "Черкаський р-н",
    ("17", "5102"): "Березівський р-н", ("17", "5104"): "Білгород-Дністровський р-н", ("17", "5106"): "Болградський р-н",
    ("17", "5108"): "Ізмаїльський р-н", ("17", "5110"): "Одеський р-н", ("17", "5112"): "Подільський р-н",
    ("17", "5114"): "Роздільнянський р-н",
    ("07", "6302"): "Богодухівський р-н", ("07", "6304"): "Ізюмський р-н", ("07", "6306"): "Берестинський р-н",
    ("07", "6308"): "Куп'янський р-н", ("07", "6310"): "Лозівський р-н", ("07", "6312"): "Харківський р-н",
    ("07", "6314"): "Чугуївський р-н",
    ("04", "1202"): "Дніпровський р-н", ("04", "1204"): "Кам'янський р-н", ("04", "1206"): "Криворізький р-н",
    ("04", "1208"): "Нікопольський р-н", ("04", "1210"): "Самарівський р-н", ("04", "1212"): "Павлоградський р-н",
    ("04", "1214"): "Синельниківський р-н",
    ("21", "5902"): "Конотопський р-н", ("21", "5904"): "Охтирський р-н", ("21", "5906"): "Роменський р-н",
    ("21", "5908"): "Сумський р-н", ("21", "5910"): "Шосткинський р-н",
    ("16", "4802"): "Баштанський р-н", ("16", "4804"): "Вознесенський р-н", ("16", "4806"): "Миколаївський р-н",
    ("16", "4808"): "Первомайський р-н",
    ("18", "5302"): "Кременчуцький р-н", ("18", "5304"): "Лубенський р-н", ("18", "5306"): "Миргородський р-н",
    ("18", "5308"): "Полтавський р-н",
    ("23", "0502"): "Вінницький р-н", ("23", "0504"): "Гайсинський р-н", ("23", "0506"): "Жмеринський р-н",
    ("23", "0508"): "Могилів-Подільський р-н", ("23", "0510"): "Тульчинський р-н", ("23", "0512"): "Хмільницький р-н",
    ("27", "1802"): "Бердичівський р-н", ("27", "1804"): "Житомирський р-н", ("27", "1806"): "Коростенський р-н",
    ("27", "1808"): "Звягельський р-н",
    ("08", "6502"): "Бериславський р-н", ("08", "6504"): "Генічеський р-н", ("08", "6506"): "Каховський р-н",
    ("08", "6508"): "Скадовський р-н", ("08", "6510"): "Херсонський р-н",
    ("10", "3502"): "Голованівський р-н", ("10", "3504"): "Кропивницький р-н", ("10", "3506"): "Новоукраїнський р-н",
    ("10", "3508"): "Олександрійський р-н",
    ("09", "6802"): "Кам'янець-Подільський р-н", ("09", "6804"): "Хмельницький р-н", ("09", "6806"): "Шепетівський р-н",
    ("22", "6102"): "Кременецький р-н", ("22", "6104"): "Тернопільський р-н", ("22", "6106"): "Чортківський р-н",
    ("19", "5602"): "Вараський р-н", ("19", "5604"): "Дубенський р-н", ("19", "5606"): "Рівненський р-н",
    ("19", "5608"): "Сарненський р-н",
    ("15", "4602"): "Дрогобицький р-н", ("15", "4604"): "Золочівський р-н", ("15", "4606"): "Львівський р-н",
    ("15", "4608"): "Самбірський р-н", ("15", "4610"): "Стрийський р-н", ("15", "4612"): "Шептицький р-н",
    ("15", "4614"): "Яворівський р-н",
    ("24", "0702"): "Володимирський р-н", ("24", "0704"): "Камінь-Каширський р-н", ("24", "0706"): "Ковельський р-н",
    ("24", "0708"): "Луцький р-н",
}

# Kharkiv city's districts and microdistricts, which @radar_kharkov names post after post. GeoNames has them as city
# sections (PPLX) under names that are half Russian, half transliterated ("Пивнична Салтивка"); the coordinates are
# GeoNames', the names are the Ukrainian ones with the Russian spelling the channel uses. geonameid → (name, aliases).
CURATED_BY_NAME = {
    # (oblast uid, GeoNames name) → (Ukrainian name, extra aliases)
    ("22", "Saltivka"): ("Салтівка", ["салтовка", "салтівський масив", "салтовский массив"]),
    ("22", "Pivnichna Saltivka"): ("Північна Салтівка", ["северная салтовка", "северную салтовку"]),
    ("22", "Pyatykhatka"): ("П'ятихатки", ["пятихатки", "пятихатка", "п'ятихатка"]),
    ("22", "Oleksiyivka"): ("Олексіївка", ["алексеевка"]),
    ("22", "Kholodna Hora"): ("Холодна Гора", ["холодная гора"]),
    ("22", "Rayon KhTZ"): ("ХТЗ", ["хтз"]),
    ("22", "Shyshkivka"): ("Шишківка", ["шишковка"]),
    ("22", "Pavlove Pole"): ("Павлове Поле", ["павлово поле"]),
    ("22", "Zhukovskoho"): ("Жуковського", ["жуковский", "жуковского", "посёлок жуковского", "поселок жуковского"]),
    ("22", "Lysa Hora"): ("Лиса Гора", ["лысая гора"]),
    ("22", "Nova Bavariya"): ("Нова Баварія", ["новая бавария"]),
    ("22", "Osnova"): ("Основа", []),
    ("22", "Zhuravlivka"): ("Журавлівка", ["журавлевка"]),
    ("22", "Nemyshlya"): ("Немишля", ["немышля"]),
    # 1.43.1: "БпЛА от Даниловки на 524 район", right after "на Большую Даниловку" — the channel's short name for it
    ("22", "Velyka Danylivka"): ("Велика Данилівка", ["большая даниловка", "даниловка", "данилівка"]),
    ("22", "Sokol’nyky"): ("Сокільники", ["сокольники"]),
    ("22", "Shatylivka"): ("Шатилівка", ["шатиловка"]),
    ("22", "Pomerki"): ("Померки", []),
    ("22", "Saltivskyi"): ("Салтівський район", ["салтовский район"]),
    ("22", "Shevchenkivskyi"): ("Шевченківський район", ["шевченковский район"]),
    ("22", "Industrialnyi"): ("Індустріальний район", ["индустриальный район"]),
    ("22", "Nemyshlyanskyi"): ("Немишлянський район", ["немышлянский район"]),
    ("22", "Novobavarskyi"): ("Новобаварський район", ["новобаварский район"]),
    ("22", "Osnovyanskyi"): ("Основ'янський район", ["основянский район"]),
    ("22", "Slobidskyi"): ("Слобідський район", ["слободской район"]),
    ("9", "Prydniprovsk"): ("Придніпровськ", ["приднепровск"]),
    # 1.44.1: "Великий Буялык", "Первый курс Буялык" (the Odesa trackers) — GeoNames gives the bare name only to Петрівка,
    # 6 km away; the hromada centre is the village they name
    ("18", "Velykyi Buialyk"): ("Великий Буялик", ["великий буялык", "буялык", "буялик"]),
    ("9", "Ihren"): ("Ігрень", ["игрень"]),
    ("9", "Chapli"): ("Чаплі", ["чапли"]),
}
# The Kharkiv city raion "Холодногірський" is a second GeoNames row with the same English name as the microdistrict.
CURATED_BY_ID = {"13680600": ("Холодногірський район", ["холодногорский район"])}

# Kinds of populated place kept: a village or town, a city section, an administrative centre. Abandoned (PPLQ),
# historical (PPLH) and destroyed (PPLW) places are not places anyone is reporting a drone over.
KEEP = {"PPL", "PPLX", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLL", "PPLS", "PPLF", "PPLR"}

# 1.45: a Soviet name GeoNames still lists first for a renamed village ("Куйбишеве" for Зимівник, Kherson) is not the
# name the channels write: when the village has another Ukrainian name, that one is shown
SOVIET = re.compile(r"куйбиш|комінтерн|ленін|кіров|жовтн|червоноарм|комсомол|радянськ|дзержин|орджонікідз|ворошилов|фрунзе|"
                    r"свердлов|калінін|артем|щорс|чапаєв|пролетар|більшовик|жданов|постишев|котовськ|чкалов|димитров|ілліч|"
                    r"октябр|піонер|петровськ|кірово|котовськ|леніно|красноарм|радгосп|колгосп|інтернаціонал|урицьк|жовтнев",
                    re.I)
CYR = re.compile(r"^[А-Яа-яІіЇїЄєҐґЁёЫыЭэЪъ'’ʼ\- ]+$")
RU_ONLY = re.compile(r"[ЁёЫыЭэЪъ]")
UK_ONLY = re.compile(r"[ІіЇїЄєҐґ]")


def norm(s):
    return re.sub(r"\s+", " ", s.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'")).strip()


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "heimdall-build"})
    with urllib.request.urlopen(req, timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    return z.read("UA.txt").decode("utf-8")


def rows(text):
    return csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)


def main():
    if len(sys.argv) >= 3:
        with open(sys.argv[1], encoding="utf-8") as f:
            main_txt = f.read()
        with open(sys.argv[2], encoding="utf-8") as f:
            alt_txt = f.read()
    else:
        main_txt = fetch("https://download.geonames.org/export/dump/UA.zip")
        alt_txt = fetch("https://download.geonames.org/export/dump/alternatenames/UA.zip")

    places = {}
    for r in rows(main_txt):
        if r[6] != "P" or r[7] not in KEEP or r[10] not in ADMIN1:
            continue
        places[r[0]] = {"en": r[1], "lat": float(r[4]), "lon": float(r[5]), "code": r[7], "a1": r[10], "a2": r[11],
                        "pop": int(r[14] or 0), "uk": [], "ru": []}
    for r in rows(alt_txt):
        p = places.get(r[1])
        if not p or r[2] not in ("uk", "ru") or r[7] == "1":      # isHistoric
            continue
        name = r[3].strip()
        if not CYR.match(name):
            continue
        (p["uk"] if r[2] == "uk" else p["ru"]).append((name, r[4] == "1"))

    out = {}
    for gid, p in places.items():
        uid = ADMIN1[p["a1"]]
        cur = CURATED_BY_ID.get(gid) or CURATED_BY_NAME.get((uid, p["en"]))
        uk = [n for n, pref in sorted(p["uk"], key=lambda x: not x[1]) if not RU_ONLY.search(n)]
        uk.sort(key=lambda n: bool(SOVIET.search(n)))          # stable: the preferred non-Soviet name first
        if cur:
            name, extra = cur
        elif uk:
            name, extra = uk[0], []
        else:
            continue            # no Ukrainian name: nobody can be sure what a post calls it
        aliases = {norm(name)} | {norm(n) for n, _ in p["uk"]} | {norm(n) for n, _ in p["ru"]} | {norm(a) for a in extra}
        aliases = sorted(a for a in aliases if len(a.replace(" ", "")) >= 3)
        kind = "X" if p["code"] == "PPLX" else "A" if p["code"].startswith("PPLA") else "P"
        out.setdefault(uid, []).append([name, round(p["lon"], 4), round(p["lat"], 4), kind, p["pop"],
                                        RAION.get((p["a1"], p["a2"]), ""), aliases])
    for uid in out:
        out[uid].sort(key=lambda e: (e[0], -e[4]))
    doc = {"_about": "built by scripts/build_places.py from GeoNames (CC BY 4.0, geonames.org): populated places of the "
                     "oblasts with a regional channel — [name, lon, lat, kind X=city section A=admin centre P=place, "
                     "population (0 = unknown), raion, aliases]",
           "oblasts": out}
    path = os.path.join(ROOT, "data", "regional_places.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(path, {k: len(v) for k, v in out.items()}, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    main()
