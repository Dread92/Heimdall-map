# -*- coding: utf-8 -*-
"""
Offline Ukrainian → English translator for air-alert / monitoring posts.

Deterministic and domain-specific: phrase glossary (longest match first) + place-name
transliteration (gazetteer-aware) + fallback transliteration for anything left in Cyrillic,
so the result never contains Ukrainian script. Not a general translator — it is tuned on the
vocabulary of the Air Force, monitoring and administration channels.
"""
import re

try:
    import geo
except Exception:  # pragma: no cover
    geo = None

# Ukrainian national transliteration (2010 standard, simplified)
_TR = {"а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i",
       "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
       "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "iu", "я": "ia", "'": "", "’": "", "ʼ": "",
       # russian letters occasionally present
       "ы": "y", "э": "e", "ё": "io", "ъ": ""}
_TR_FIRST = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}


def translit(word):
    out = []
    for i, ch in enumerate(word):
        low = ch.lower()
        if i == 0 and low in _TR_FIRST:
            t = _TR_FIRST[low]
        else:
            t = _TR.get(low, ch)
        if ch != low and t:
            t = t[0].upper() + t[1:]
        out.append(t)
    return "".join(out)


# Oblast adjective stems → English region name
OBLAST_EN = {
    "вінничч": "Vinnytsia", "вінницьк": "Vinnytsia", "житомирщ": "Zhytomyr", "житомирськ": "Zhytomyr", "чернігівщ": "Chernihiv", "чернігівськ": "Chernihiv",
    "харківщ": "Kharkiv", "харківськ": "Kharkiv", "полтавщ": "Poltava", "полтавськ": "Poltava", "київщ": "Kyiv", "київськ": "Kyiv",
    "сумщ": "Sumy", "сумськ": "Sumy", "дніпропетровщ": "Dnipropetrovsk", "дніпропетровськ": "Dnipropetrovsk", "донечч": "Donetsk", "донецьк": "Donetsk",
    "запоріжж": "Zaporizhzhia", "запорізьк": "Zaporizhzhia", "херсонщ": "Kherson", "херсонськ": "Kherson", "миколаївщ": "Mykolaiv", "миколаївськ": "Mykolaiv",
    "одещ": "Odesa", "одеськ": "Odesa", "черкащ": "Cherkasy", "черкаськ": "Cherkasy", "кіровоградщ": "Kirovohrad", "кіровоградськ": "Kirovohrad",
    "хмельничч": "Khmelnytskyi", "хмельницьк": "Khmelnytskyi", "тернопільщ": "Ternopil", "тернопільськ": "Ternopil", "рівненщ": "Rivne", "рівненськ": "Rivne",
    "волин": "Volyn", "львівщ": "Lviv", "львівськ": "Lviv", "івано-франківщ": "Ivano-Frankivsk", "прикарпатт": "Prykarpattia", "закарпатт": "Zakarpattia",
    "чернівеччин": "Chernivtsi", "чернівецьк": "Chernivtsi", "буковин": "Bukovyna", "луганщ": "Luhansk", "луганськ": "Luhansk", "крим": "Crimea",
}
PLACE_EN = {"Кременчуцьке водосховище": "Kremenchuk Reservoir", "Київське водосховище": "Kyiv Reservoir", "Канівське водосховище": "Kaniv Reservoir",
            "Каховське водосховище": "Kakhovka Reservoir", "Дністровське водосховище": "Dniester Reservoir", "Черкаське водосховище": "Cherkasy Reservoir",
            "Чорне море": "Black Sea", "Азовське море": "Sea of Azov", "Запорізька АЕС": "Zaporizhzhia NPP", "Рівненська АЕС": "Rivne NPP",
            "Хмельницька АЕС": "Khmelnytskyi NPP", "Дніпровська ГЕС": "Dnipro HPP", "Кінбурнська коса": "Kinburn Spit", "Столиця": "the capital",
            "Лівий берег": "Left Bank", "Правий берег": "Right Bank", "Харківський масив": "Kharkivskyi district", "Лісовий масив": "Lisovyi district",
            "Мінський масив": "Minskyi district", "Іванківська громада": "Ivankiv hromada", "Ржищівська громада": "Rzhyshchiv hromada",
            "Ставищенська громада": "Stavyshche hromada", "Кагарлицька громада": "Kaharlyk hromada", "Білоцерківська громада": "Bila Tserkva hromada",
            "Тетіївська громада": "Tetiiv hromada", "Новоград-Волинський": "Zviahel", "Кривий Ріг": "Kryvyi Rih", "Біла Церква": "Bila Tserkva"}
PREP = {"до": "to", "від": "from", "з": "from", "зі": "from", "із": "from", "біля": "near", "поблизу": "near", "повз": "past", "над": "over",
        "через": "via", "в": "in", "у": "in", "довкола": "around", "навколо": "around", "поряд": "near"}
_PREP_RX = re.compile(r"(на|в|у|до|від|з|зі|із|біля|поблизу|повз|над|через|довкола|навколо|поряд)\s+$", re.I)


def _prep_for(prefix, token, name):
    """Choose the English preposition for '<prep> <place>' using Ukrainian case endings."""
    m = _PREP_RX.search(prefix)
    if not m:
        return None, 0
    p = m.group(1).lower()
    # 1.45.1: "на півночі від Миколаєва" is "north of Mykolaiv" — the side words and "від" together
    sm = re.search(r"на\s+(півночі|півдні|сході|заході)\s+від\s+$", prefix, re.I)
    if sm:
        return {"півночі": "north of", "півдні": "south of", "сході": "east of", "заході": "west of"}[sm.group(1).lower()], len(sm.group(0))
    if p != "на":
        return PREP[p], len(m.group(0))
    tok = token.lower()
    base = name.split(" (")[0].lower()
    fem = base.endswith(("а", "я"))
    if fem:
        en = "to" if tok.endswith(("у", "ю")) else ("in" if tok.endswith(("і", "ї")) else "to")
    else:
        en = "to" if tok == base or tok.endswith(base[-1]) and not tok.endswith(("у", "ові", "і", "ї")) else "in"
    return en, len(m.group(0))


RAION_EN = {"білоцерківськ": "Bila Tserkva", "бориспільськ": "Boryspil", "броварськ": "Brovary", "бучанськ": "Bucha", "вишгородськ": "Vyshhorod",
            "обухівськ": "Obukhiv", "фастівськ": "Fastiv", "київськ": "Kyiv", "чернігівськ": "Chernihiv", "ніжинськ": "Nizhyn", "козелецьк": "Kozelets",
            "черкаськ": "Cherkasy", "уманськ": "Uman", "звенигородськ": "Zvenyhorodka", "золотоніськ": "Zolotonosha", "житомирськ": "Zhytomyr",
            "коростенськ": "Korosten", "бердичівськ": "Berdychiv", "новоград-волинськ": "Zviahel", "звягельськ": "Zviahel", "полтавськ": "Poltava",
            "кременчуцьк": "Kremenchuk", "лубенськ": "Lubny", "миргородськ": "Myrhorod"}

# Phrase glossary. Patterns are matched case-insensitively on apostrophe-normalised text; order = longest first.
# Endings are made flexible with [а-яіїє]* where declension matters.
G = [
    # --- єРадар summaries / monitor slang ---
    (r"ударн[а-яіїє]*\s+бп(ла)?\b", "strike UAV"), (r"реактивн[а-яіїє]*\s+бп(ла)?\b", "jet UAV"), (r"реактивн[а-яіїє]*", "jet UAV"),
    (r"(\d+)\s*грп\.?", r"\1 grp"), (r"\bбп\b", "UAV"), (r"жовтий рівень (тривоги|небезпеки)", "yellow level"), (r"червоний рівень (тривоги|небезпеки)", "red level"),
    (r"прямуйте в укриття", "go to shelter"), (r"перейдіть в укриття", "go to shelter"), (r"загроза застосування", "threat of"), (r"монітор[а-яіїє]*", "monitors"),
    (r"[ву]\s+напрямк[а-яіїє]*", "toward"), (r"напрямк[а-яіїє]*", "toward"), (r"над столицею", "over Kyiv"), (r"\bчисто\b", "clear"),
    (r"region\s+област[а-яіїє]*", "region"), (r"toward\s*(in|to|at)\b", "toward"), (r"тривог[а-яіїє]*", "alert"), (r"небезпек[а-яіїє]*", "danger"),
    # --- alerts (administrations) ---
    (r"відбій повітряної тривоги", "air raid alert lifted"),
    (r"відбій тривоги", "alert lifted"),
    (r"відбій загрози[а-яіїє]*", "threat over"),
    (r"відбій", "all clear"),
    (r"повітряна тривога", "air raid alert"), (r"повітряної тривоги", "air raid alert"), (r"повітряну тривогу", "air raid alert"),
    (r"повітряних тривог", "air raid alerts"),
    (r"оголошен[аоі] дронова небезпека", "drone danger declared"), (r"дронова небезпека", "drone danger"),
    (r"дронова загроза", "drone threat"), (r"оголошен[аоі]", "declared"),
    (r"жовтий рівень", "yellow level"), (r"червоний рівень", "red level"), (r"\(жовтий рівень\)", "(yellow level)"),
    (r"зверніть увагу,? повітряна тривога досі триває у:?", "note: the air raid alert continues in:"),
    (r"досі триває", "still ongoing"), (r"триває", "ongoing"),
    (r"просимо всіх терміново прослідувати в укриття цивільного захисту", "everyone please proceed to a civil-defence shelter immediately"),
    (r"просимо уважно слідкувати за повідомленнями і, у разі оголошення тривоги, повернутися до укриття", "please follow the announcements and return to shelter if an alert is declared"),
    (r"мапа укриттів", "shelter map"), (r"укриття цивільного захисту", "civil-defence shelter"), (r"укритт[а-яіїє]*", "shelter"),
    (r"перебувайте в укриттях", "stay in shelters"), (r"перебувайте в укритті", "stay in shelter"),
    (r"у столиці працюють сили ппо", "air defence is engaging over the capital"),
    (r"працюють сили ппо", "air defence is engaging"), (r"працює ппо", "air defence engaging"), (r"робота ппо", "air-defence activity"),
    (r"сили ппо", "air defence"), (r"\bппо\b", "air defence"),
    (r"загроза застосування балістичного озброєння", "threat of ballistic missile use"),
    (r"загроза застосування ударних бпла", "threat of strike-UAV use"),
    (r"загроза застосування", "threat of use of"), (r"балістична загроза", "ballistic threat"), (r"загроза балістики", "ballistic threat"),
    (r"загроза ударних бпла", "strike-UAV threat"), (r"загроз[аиу]", "threat"),
    (r"небезпек[аиу]", "danger"),
    (r"увага!?", "attention!"),
    (r"у києві", "in Kyiv"), (r"в києві", "in Kyiv"), (r"києва", "Kyiv"), (r"києві", "Kyiv"), (r"столиц[яіюі]", "the capital"),
    # --- monitoring vocabulary ---
    (r"ударн[а-яіїє]* бпла", "strike UAVs"), (r"ударний бпла", "strike UAV"), (r"ударні бпла", "strike UAVs"),
    (r"реактивн[а-яіїє]* бпла", "jet UAV"), (r"реактивний бпла", "jet UAV"), (r"реактивні бпла", "jet UAVs"),
    (r"звичайн[а-яіїє]* бпла", "regular (propeller) UAVs"),
    (r"розвідувальн[а-яіїє]* бпла", "reconnaissance UAV"),
    (r"по реактивам", "regarding the jet UAVs"), (r"реактив[иі]", "jet UAVs"), (r"реактив", "jet UAV"),
    (r"бпла", "UAV"), (r"бпл", "UAV"), (r"шахед[а-яіїє]*", "Shahed"), (r"мопед[а-яіїє]*", "Shahed"), (r"герань", "Geran"),
    (r"дрон[а-яіїє]*", "drone"), (r"безпілотник[а-яіїє]*", "drone"),
    (r"крилат[а-яіїє]* ракет[а-яіїє]*", "cruise missiles"), (r"балістичн[а-яіїє]* ракет[а-яіїє]*", "ballistic missiles"),
    (r"балістик[аиу]", "ballistic missiles"), (r"балістичн[а-яіїє]*", "ballistic"), (r"ракет[а-яіїє]*", "missile(s)"),
    (r"швидкісн[а-яіїє]* ціл[а-яіїє]*", "high-speed target"), (r"ціл[а-яіїє]*", "target"),
    (r"пуски керованих авіаційних бомб ворожою тактичною авіацією", "guided aerial bomb launches by enemy tactical aviation"),
    (r"керован[а-яіїє]* авіаційн[а-яіїє]* бомб[а-яіїє]*", "guided aerial bombs"), (r"каб[иі]?\b", "KAB guided bombs"),
    (r"тактичн[а-яіїє]* авіаці[а-яіїє]*", "tactical aviation"), (r"стратегічн[а-яіїє]* авіаці[а-яіїє]*", "strategic aviation"),
    (r"ворож[а-яіїє]*", "enemy"), (r"пуск[иу]?\b", "launches"), (r"зліт", "take-off"),
    (r"міг-?31к?", "MiG-31K"), (r"ту-?95", "Tu-95"), (r"ту-?160", "Tu-160"), (r"ту-?22", "Tu-22"),
    (r"аеродром[а-яіїє]*", "airfield"),
    (r"змішан[а-яіїє]* груп[а-яіїє]*", "mixed groups"), (r"груп[аиу]?\b", "group"),
    (r"дорозвідка по бпла", "UAV reconnaissance update"), (r"дорозвідка", "reconnaissance update"),
    (r"загальна оцінка загроз для україни на ніч", "overall threat assessment for Ukraine for the night of"),
    (r"загально:?", "overall:"), (r"оцінка загроз", "threat assessment"),
    (r"не активна", "not active"), (r"активна", "active"), (r"низька", "low"), (r"висока", "high"), (r"середня", "moderate"),
    (r"мінімальна кількість", "minimal number"), (r"кількість", "number"),
    (r"у повітрі", "in the air"), (r"в повітрі", "in the air"),
    (r"обережно!?", "caution!"), (r"може бути гучно", "it may be loud"),
    # --- movement ---
    (r"[ув] південно-західному напрямку", "heading south-west"), (r"[ув] південно-східному напрямку", "heading south-east"),
    (r"[ув] північно-західному напрямку", "heading north-west"), (r"[ув] північно-східному напрямку", "heading north-east"),
    (r"[ув] західному напрямку", "heading west"), (r"[ув] східному напрямку", "heading east"), (r"[ув] північному напрямку", "heading north"), (r"[ув] південному напрямку", "heading south"),
    (r"з північного-сходу", "from the north-east"), (r"з північного-заходу", "from the north-west"), (r"з південного-сходу", "from the south-east"), (r"з південного-заходу", "from the south-west"),
    (r"тримають курс", "holding course"), (r"тримає курс", "holding course"), (r"\bкурс\b", "heading"),
    (r"в акваторії", "over the waters of"), (r"акваторі[а-яіїє]*", "waters"),
    (r"(\d+)\s*х\b", r"\1×"), (r"\br-н\b", "raion"), (r"\bр-н\b", "raion"),
    (r"курсом на", "heading to"), (r"курс на", "heading to"), (r"курс -", "heading:"), (r"курсом", "heading"),
    (r"курс північно-західний", "heading north-west"), (r"курс північно-східний", "heading north-east"),
    (r"курс південно-західний", "heading south-west"), (r"курс південно-східний", "heading south-east"),
    (r"курс північний", "heading north"), (r"курс південний", "heading south"), (r"курс західний", "heading west"), (r"курс східний", "heading east"),
    (r"північно-західн[а-яіїє]*", "north-west"), (r"північно-східн[а-яіїє]*", "north-east"), (r"південно-західн[а-яіїє]*", "south-west"), (r"південно-східн[а-яіїє]*", "south-east"),
    (r"північно західн[а-яіїє]*", "north-west"), (r"північно східн[а-яіїє]*", "north-east"), (r"південно західн[а-яіїє]*", "south-west"), (r"південно східн[а-яіїє]*", "south-east"),
    (r"з північного сходу", "from the north-east"), (r"з північного заходу", "from the north-west"), (r"з південного сходу", "from the south-east"), (r"з південного заходу", "from the south-west"),
    (r"з півночі", "from the north"), (r"з півдня", "from the south"), (r"із заходу", "from the west"), (r"з заходу", "from the west"), (r"зі сходу", "from the east"), (r"з сходу", "from the east"),
    (r"на північ від", "north of"), (r"на південь від", "south of"), (r"на захід від", "west of"), (r"на схід від", "east of"),
    (r"на півночі", "in the north of"), (r"на півдні", "in the south of"), (r"на заході", "in the west of"), (r"на сході", "in the east of"),
    (r"на північ", "north"), (r"на південь", "south"), (r"на захід", "west"), (r"на схід", "east"),
    (r"північн[а-яіїє]*", "north"), (r"південн[а-яіїє]*", "south"), (r"західн[а-яіїє]*", "west"), (r"східн[а-яіїє]*", "east"),
    (r"у напрямку", "toward"), (r"в напрямку", "toward"), (r"напрямку", "toward"), (r"у бік", "toward"), (r"в бік", "toward"), (r"в сторону", "toward"), (r"зі сторони", "from the direction of"), (r"з боку", "from the direction of"),
    (r"вздовж", "along"), (r"уздовж", "along"), (r"вектор[а-яіїє]*", "vector"),
    (r"в районі", "near"), (r"в р-ні\.?", "near"), (r"у районі", "near"), (r"р-ні\.?", "near"), (r"в р-н\.?", "near"),
    (r"поблизу", "near"), (r"біля", "near"), (r"поряд з", "next to"), (r"поряд", "near"), (r"довкола", "around"), (r"навколо", "around"),
    (r"н\.п\.\s*", ""), (r"н\.п\s+", ""),
    (r"на/повз", "over/past"), (r"повз", "past"), (r"через", "via"), (r"над", "over"),
    (r"перелітає з", "crossing from"), (r"перелітають з", "crossing from"), (r"перелітає", "crossing"), (r"перелітають", "crossing"), (r"заходить на", "entering"), (r"заходять на", "entering"),
    (r"летить на", "flying to"), (r"летять на", "flying to"), (r"летить", "flying"), (r"летять", "flying"),
    (r"рухається", "moving"), (r"рухаються", "moving"), (r"прямує", "heading"), (r"прямують", "heading"),
    (r"змінив курс на", "changed course to"), (r"змінив курс", "changed course"),
    (r"або ж полетить на", "or may turn to"), (r"або", "or"),
    (r"водосховищ[а-яіїє]*", "reservoir"), (r"чорн[а-яіїє]* мор[а-яіїє]*", "Black Sea"), (r"азовськ[а-яіїє]* мор[а-яіїє]*", "Sea of Azov"),
    (r"з орла", "from Oryol"), (r"з курська", "from Kursk"), (r"з брянська", "from Bryansk"), (r"з міллерово", "from Millerovo"), (r"з приморсько-ахтарська", "from Primorsko-Akhtarsk"),
    (r"з шаталово", "from Shatalovo"), (r"з саваслейки", "from Savasleyka"), (r"саваслейка", "Savasleyka"), (r"з енгельса", "from Engels"), (r"з олен[ьі][а-яіїє]*", "from Olenya"),
    # --- outcomes ---
    (r"збит[а-яіїє]*", "shot down"), (r"знищен[а-яіїє]*", "destroyed"), (r"ліквідован[а-яіїє]*", "eliminated"),
    (r"мінус[а-яіїє]*", "minus (downed)"), (r"зниженн[а-яіїє]*", "descent (going down)"), (r"падінн[а-яіїє]*", "fall"), (r"впав", "fell"), (r"впали", "fell"),
    (r"втрачен[а-яіїє]*", "lost"), (r"зник[а-яіїє]*", "disappeared"), (r"не спостерігається", "no longer observed"),
    (r"чисто", "clear"), (r"залишок", "remaining"), (r"за ним йде полювання", "it is being hunted"),
    (r"вибух[а-яіїє]*", "explosion"), (r"приліт", "impact"), (r"прильот", "impact"),
    (r"уламк[а-яіїє]*", "debris"), (r"постраждал[а-яіїє]*", "injured"),
    # --- generic ---
    (r"екстрені служби прямують на місце", "emergency services are on their way"),
    (r"на відкритій території", "in an open area"), (r"в зеленій зоні", "in a green zone"),
    (r"район[уі]?", "raion"), (r"області", "oblast"), (r"область", "oblast"), (r"обл\.", "oblast"), (r"громад[аиу]", "hromada"), (r"міста", "the city"), (r"місто", "city"), (r"міст[оа]м", "the city"),
    (r"карта повітряних тривог", "air raid alert map"), (r"карта", "map"),
    (r"попередньо", "preliminarily"), (r"ймовірно", "probably"), (r"можливо", "possibly"), (r"очікувано", "as expected"), (r"оновлення", "update"), (r"upd", "UPD"),
    (r"також", "also"), (r"ще", "another"), (r"нов[а-яіїє]*", "new"), (r"додатково", "additionally"),
    (r"вересня", "September"), (r"жовтня", "October"), (r"листопада", "November"), (r"грудня", "December"), (r"січня", "January"), (r"лютого", "February"), (r"березня", "March"), (r"квітня", "April"), (r"травня", "May"), (r"червня", "June"), (r"липня", "July"), (r"серпня", "August"),
    (r"година", "hour"), (r"хвилин[а-яіїє]*", "minutes"), (r"протягом", "within"), (r"підліт", "arrival"),
    (r"\bта\b", "and"), (r"\bі\b", "and"), (r"\bй\b", "and"), (r"\bна\b", "on"), (r"\bв\b", "in"), (r"\bу\b", "in"), (r"\bз\b", "from"), (r"\bзі\b", "from"), (r"\bіз\b", "from"),
    (r"\bдо\b", "to"), (r"\bвід\b", "from"), (r"\bпо\b", "along"), (r"\bпід\b", "under"), (r"\bпро\b", "about"), (r"\bдля\b", "for"), (r"\bне\b", "not"), (r"\bце\b", "this"),
(r"\bще (од[на][ао]?|один)\b", "one more"), (r"\bще (два|дві|три)\b", lambda m: {"два": "two", "дві": "two", "три": "three"}[m.group(1).lower()] + " more"), (r"\bще\b", "still"), (r"\bвже\b", "already"), (r"\bзараз\b", "now"), (r"\bтам\b", "there"), (r"\bтут\b", "here"),
]
_G = [(re.compile(p, re.I), r) for p, r in sorted(G, key=lambda t: -len(t[0]))]
_RAION = re.compile(r"([а-яіїє'-]+ськ)(?:ий|ого|ому|им|ім)\s+район[а-яіїє]*", re.I)
_OBL = re.compile("(" + "|".join(sorted(map(re.escape, OBLAST_EN), key=len, reverse=True)) + r")[а-яіїє]*", re.I)
_CYR = re.compile(r"[А-ЯІЇЄҐа-яіїєґЁёЫыЭэЪъ][а-яіїєґ'’ʼЁёыэъ-]*")


def _norm(s):
    return s.replace("’", "'").replace("ʼ", "'").replace("`", "'")


# ---------------------------------------------------------------------------
# Online mode: Google Translate (free gtx endpoint) with the domain glossary protecting the military
# vocabulary it gets wrong. Falls back to the offline glossary on any error. Selected by
# TRANSLATOR=google (default) / glossary.
# ---------------------------------------------------------------------------
import json as _json
import os as _os
import ssl as _ssl
import urllib.error as _ue
import urllib.parse as _up
import urllib.request as _ur

PRE = [  # Ukrainian phrase → English inserted before the call (Google leaves English untouched)
    (r"відбій повітряної тривоги", "all clear — air raid alert lifted"), (r"відбій тривоги", "all clear — alert lifted"),
    (r"відбій загрози[а-яіїє]*", "threat over"), (r"\bвідбій\b", "all clear"),
    (r"повітряна тривога", "air raid alert"), (r"повітряної тривоги", "air raid alert"), (r"повітряну тривогу", "air raid alert"),
    (r"дронова небезпека", "drone danger"), (r"дронова загроза", "drone threat"),
    (r"реактивн[а-яіїє]* бпла", "jet drones"), (r"реактивн[а-яіїє]* мопед[а-яіїє]*", "jet drones"), (r"реактив[а-яіїє]*", "jet drone"),
    (r"мопед[а-яіїє]*", "Shahed"), (r"ударн[а-яіїє]*\s+бпла\b", "strike drones (UAV)"), (r"ударн[а-яіїє]*", "strike drones"), (r"\bбпла\b", "strike drones (UAV)"), (r"шахед[а-яіїє]*", "Shahed"), (r"герань", "Geran"),
    (r"\bкаб(и|і|ів|ами|ах)?\b", "KAB guided bombs"), (r"звичайн[а-яіїє]*", "regular Shahed (not jet)"), (r"\bппо\b", "air defence"), (r"сили ппо", "air defence"),
    (r"балістик[аиу]", "ballistic missiles"), (r"швидкісн[а-яіїє]* ціл[а-яіїє]*", "high-speed target"),
    (r"\(\s*(київськ|житомирськ|чернігівськ|сумськ|полтавськ|черкаськ|вінницьк|харківськ|дніпропетровськ|кіровоградськ|рівненськ|хмельницьк|миколаївськ|одеськ|запорізьк|херсонськ|донецьк|луганськ|волинськ|львівськ|тернопільськ|івано-франківськ|чернівецьк|закарпатськ)а\s+обл\.?\s*\)", lambda m: "(" + {"київськ":"Kyiv","житомирськ":"Zhytomyr","чернігівськ":"Chernihiv","сумськ":"Sumy","полтавськ":"Poltava","черкаськ":"Cherkasy","вінницьк":"Vinnytsia","харківськ":"Kharkiv","дніпропетровськ":"Dnipropetrovsk","кіровоградськ":"Kirovohrad","рівненськ":"Rivne","хмельницьк":"Khmelnytskyi","миколаївськ":"Mykolaiv","одеськ":"Odesa","запорізьк":"Zaporizhzhia","херсонськ":"Kherson","донецьк":"Donetsk","луганськ":"Luhansk","волинськ":"Volyn","львівськ":"Lviv","тернопільськ":"Ternopil","івано-франківськ":"Ivano-Frankivsk","чернівецьк":"Chernivtsi","закарпатськ":"Zakarpattia"}[m.group(1).lower()] + " oblast)"),
    (r"жовтий рівень тривоги", "yellow alert level"), (r"червоний рівень тривоги", "red alert level"), (r"прямуйте в укриття", "go to shelter"),
    (r"київщин[а-яіїє]*", "Kyiv region"), (r"черкащин[а-яіїє]*", "Cherkasy region"), (r"полтавщин[а-яіїє]*", "Poltava region"), (r"харківщин[а-яіїє]*", "Kharkiv region"),
    (r"кіровоградщин[а-яіїє]*", "Kirovohrad region"), (r"дніпропетровщин[а-яіїє]*", "Dnipropetrovsk region"), (r"сумщин[а-яіїє]*", "Sumy region"), (r"чернігівщин[а-яіїє]*", "Chernihiv region"),
    (r"житомирщин[а-яіїє]*", "Zhytomyr region"), (r"вінниччин[а-яіїє]*", "Vinnytsia region"), (r"миколаївщин[а-яіїє]*", "Mykolaiv region"), (r"одещин[а-яіїє]*", "Odesa region"),
    (r"херсонщин[а-яіїє]*", "Kherson region"), (r"донеччин[а-яіїє]*", "Donetsk region"), (r"луганщин[а-яіїє]*", "Luhansk region"), (r"хмельниччин[а-яіїє]*", "Khmelnytskyi region"),
    (r"рівненщин[а-яіїє]*", "Rivne region"), (r"львівщин[а-яіїє]*", "Lviv region"), (r"тернопільщин[а-яіїє]*", "Ternopil region"), (r"франківщин[а-яіїє]*", "Ivano-Frankivsk region"),
    (r"буковин[а-яіїє]*", "Chernivtsi region"), (r"закарпатт[а-яіїє]*", "Zakarpattia region"), (r"волин[іь][а-яіїє]*", "Volyn region"), (r"запоріжж[а-яіїє]*", "Zaporizhzhia region"),
    (r"жовт[іи]х? вод[а-яіїє]*", "Zhovti Vody"),
    (r"н\.п\.\s*", ""), (r"\bр-н\b", "raion"), (r"\bрайон\b", "raion"), (r"(\d+)\s*х\b", r"\1×"),
    (r"мінус[а-яіїє]*", "minus (downed)"), (r"зниженн[а-яіїє]*", "descent (going down)"), (r"знижується", "descending (going down)"),
    (r"дорозвідка", "reconnaissance update"), (r"\bйде\b", "is heading"), (r"\bчисто\b", "clear (no targets)"), (r"\bуважно\b", "— caution"), (r"зліт", "take-off"), (r"міг-?31к?", "MiG-31K"),
]
_PRE = [(re.compile(p, re.I), r) for p, r in PRE]
POST = [  # Google artefacts → domain wording
    (r"\bshock (?:guns?|drones?)\b", "strike drones"), (r"\bshock\b", "strike"), (r"\bair (?:raid )?alarm\b", "air raid alert"), (r"\bair anxiety\b", "air raid alert"), (r"\banxiety\b", "alert"),
    (r"\brepulse\b", "all clear"), (r"\bhang up\b", "all clear"), (r"\bmopeds?\b", "Shahed"), (r"\breactive\b", "jet"),
    (r"\bUAVs?\b", "UAV"), (r"\bCABs?\b", "KAB guided bombs"), (r"\bOblast\b", "region"), (r"\bdistrict\b", "raion"), (r"\bcourse\b", "heading"),
    (r"\bin the direction of\b", "toward"), (r"\bthe capital\b", "Kyiv (the capital)"), (r"\bshelters? of civil protection\b", "civil-defence shelter"),
    (r"\bhits?\b", "impact"), (r"\barrival\b", "impact"), (r"\bis clean\b", "is clear"), (r"\bclean\b", "clear"), (r"\bHe is\b", "It is"), (r"\bhe is\b", "it is"),
]
_POST = [(re.compile(p, re.I), r) for p, r in POST]
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


PRE_FR = [  # the same domain words, for French: the slang a general translator gets wrong
    (r"відбій повітряної тривоги", "fin d'alerte — alerte aérienne levée"), (r"відбій тривоги", "fin d'alerte"),
    (r"відбій загрози[а-яіїє]*", "menace terminée"), (r"\bвідбій\b", "fin d'alerte"),
    (r"повітряна тривога", "alerte aérienne"), (r"повітряної тривоги", "alerte aérienne"), (r"повітряну тривогу", "alerte aérienne"),
    (r"дронова небезпека", "danger drones"), (r"дронова загроза", "menace de drones"),
    (r"реактивн[а-яіїє]* бпла", "drones à réaction"), (r"реактивн[а-яіїє]* мопед[а-яіїє]*", "drones à réaction"), (r"реактив[а-яіїє]*", "drone à réaction"),
    (r"мопед[а-яіїє]*", "Shahed"), (r"ударн[а-яіїє]*\s+бпла\b", "drones d'attaque"), (r"ударн[а-яіїє]*", "drones d'attaque"), (r"\bбпла\b", "drones d'attaque"), (r"шахед[а-яіїє]*", "Shahed"), (r"герань", "Geran"),
    (r"\bкаб(и|і|ів|ами|ах)?\b", "bombes guidées KAB"), (r"\bппо\b", "défense antiaérienne"), (r"сили ппо", "défense antiaérienne"),
    (r"балістик[аиу]", "missiles balistiques"), (r"швидкісн[а-яіїє]* ціл[а-яіїє]*", "cible rapide"),
    (r"прямуйте в укриття", "allez aux abris"), (r"н\.п\.\s*", ""), (r"\bр-н\b", "raion"), (r"(\d+)\s*х\b", r"\1×"),
    (r"мінус[а-яіїє]*", "abattu"), (r"зниженн[а-яіїє]*", "descente"), (r"знижується", "descend"),
    (r"\bчисто\b", "dégagé (aucune cible)"), (r"зліт", "décollage"), (r"міг-?31к?", "MiG-31K"),
]
_PRE_FR = [(re.compile(p, re.I), r) for p, r in PRE_FR]
POST_FR = [
    (r"\bde choc\b", "d'attaque"), (r"\bcyclomoteurs?\b", "Shahed"), (r"\bmobylettes?\b", "Shahed"), (r"\bréactifs?\b", "à réaction"), (r"\bdistrict\b", "raion"),
    (r"\banxiété\b", "alerte"), (r"\bsirène aérienne\b", "alerte aérienne"), (r"\bla capitale\b", "Kyiv (la capitale)"),
]
_POST_FR = [(re.compile(p, re.I), r) for p, r in POST_FR]


# ---- machine translators ---------------------------------------------------------------------------------
# In order: DeepL (key), Google Cloud Translation (key), then the free Google endpoint. The free endpoint
# answers from a home connection but refuses a data-centre address ("Sorry…", HTTP 429) — which is where the
# server lives. A key is what makes translation work on the server; without one the offline glossary is used.
KEYS = {"deepl": _os.environ.get("DEEPL_KEY") or "", "google_cloud": _os.environ.get("GOOGLE_TRANSLATE_KEY") or ""}
_DOWN = {}          # backend → until when it is not tried again
_TARGET = {"en": ("EN-GB", "en"), "fr": ("FR", "fr")}


# 1.46: one TLS context for every call — urlopen() without one loads the system's root certificates again each time
_CTX = _ssl.create_default_context()


def configure(deepl=None, google_cloud=None):
    if deepl:
        KEYS["deepl"] = deepl
    if google_cloud:
        KEYS["google_cloud"] = google_cloud


def _google(text, target="en"):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=uk&tl={target}&dt=t&q=" + _up.quote(text)
    with _ur.urlopen(_ur.Request(url, headers={"User-Agent": _UA}), timeout=6, context=_CTX) as r:
        d = _json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in d[0] if seg and seg[0])


def _deepl(text, target="en"):
    key = KEYS["deepl"]
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    body = _json.dumps({"text": [text], "source_lang": "UK", "target_lang": _TARGET[target][0], "preserve_formatting": True}).encode()
    req = _ur.Request(f"https://{host}/v2/translate", data=body, method="POST",
                      headers={"Authorization": "DeepL-Auth-Key " + key, "Content-Type": "application/json", "User-Agent": "heimdall"})
    with _ur.urlopen(req, timeout=10, context=_CTX) as r:
        return _json.loads(r.read().decode("utf-8"))["translations"][0]["text"]


def _google_cloud(text, target="en"):
    body = _json.dumps({"q": text, "source": "uk", "target": _TARGET[target][1], "format": "text"}).encode()
    # 1.58.46, the audit (I9): the key in a header Google takes (X-Goog-Api-Key), not in the address an error could quote
    req = _ur.Request("https://translation.googleapis.com/language/translate/v2", data=body, method="POST",
                      headers={"Content-Type": "application/json", "User-Agent": "heimdall", "X-Goog-Api-Key": KEYS["google_cloud"]})
    with _ur.urlopen(req, timeout=10, context=_CTX) as r:
        return _json.loads(r.read().decode("utf-8"))["data"]["translations"][0]["translatedText"]


def backends():
    """The machine translators that may be tried right now, in order."""
    now = _time.time()
    out = []
    if KEYS["deepl"]:
        out.append(("deepl", _deepl))
    if KEYS["google_cloud"]:
        out.append(("google_cloud", _google_cloud))
    if MODE == "google":
        out.append(("google", _google))
    return [(n, f) for n, f in out if _DOWN.get(n, 0) <= now]


def machine(text, target="en"):
    """(translation, backend) from the first machine translator that answers, or (None, None).

    A backend that fails is left alone for a while — 30 min after a refusal (429, quota, bad key), 5 min after
    anything else — so a blocked one never costs a second per post again."""
    t = _norm(text)
    for rx, rep in (_PRE if target == "en" else _PRE_FR):
        t = rx.sub(rep, t)
    for name, fn in backends():
        try:
            wait = 0.35 - (_time.time() - _last_call[0])
            if wait > 0:
                _time.sleep(wait)
            _last_call[0] = _time.time()
            out = fn(t, target)
        except _ue.HTTPError as e:
            _DOWN[name] = _time.time() + (1800 if e.code in (401, 403, 429, 456) else 300)
            continue
        except Exception:
            _DOWN[name] = _time.time() + 300
            continue
        for rx, rep in (_POST if target == "en" else _POST_FR):
            out = rx.sub(rep, out)
        out = _CYR.sub(lambda m: translit(m.group(0)), out)
        return out.strip(), name
    return None, None


def translate_online(text):
    out, _ = machine(text, "en")
    if out is None:
        raise RuntimeError("no machine translator answered")
    return out


MODE = (_os.environ.get("TRANSLATOR") or "google").lower()


import time as _time

_last_call = [0.0]
LAST_OK = [True]   # whether the most recent translate() used the online translator


_BOILER = re.compile(r"^\s*(#\S+(\s+#\S+)*|підписат[а-яіїє]*.*|поширюємо інформацію.*|детальніше читайте тут.*|читати більше.*|київ \| times.*|купуємо контент.*|➡️\s*оперативно про .*|реклама:.*|надіслати новину.*|зворотн[іи]й зв.язок.*|\(переглянути\)|⚡️перегляньте, що летить.*)\s*$", re.I | re.M)


# Channel promos, ads and attributions glued to the END of a real warning:
#   "…на Лівобережний масив, — монітори. Київ | Times Купуємо контент | ❤️"
# They are not information, they take the space a warning needs, and they make the app look like an ad board.
# Everything from the first marker to the end of the post is dropped.
_PROMO = re.compile(
    r"\s*(?:[—–-]\s*монітори\b[.,]?|"
    r"купуємо\s+контент|київ\s*\|\s*times|"
    r"➡️?\s*оперативно\s+про|новини\s*:\s*[А-ЯІЇЄа-яіїє]|"
    r"підписат[а-яіїє]*|підписуйт[а-яіїє]*|"
    r"надісл(?:ати|ать)\s+новину|присла(?:ти|ть)\s+новину|запропонувати\s+новину|"
    r"наш\s+бот\b|бот\s+для\s+зв|зворотн[іи]й\s+зв|"
    r"реклама\s*:|співпраця\s*:|"
    r"підтримати\s+канал|донат|банка\s*:|monobank|приватбанк|"
    r"поширюємо\s+інформацію|детальніше\s+читайте|читати\s+більше|"
    r"⚡️?\s*перегляньте,?\s+що\s+летить|"
    # the Odesa live channels sign every post with a promo line; one of them is profane, and none of it
    # belongs in a warning read by somebody deciding whether to go to a shelter
    r"[\u2693\ufe0f\s]*х[уy]\w*\s+одесса\s*\||\blive\s+афиша\b|присла(?:ть|ти)\s+новость|надіслати\s+новость"
    r").*$", re.I | re.S)
_TAIL_JUNK = re.compile(r"(?:\s*[|·•/]\s*)?(?:[\u2190-\u27bf\U0001f000-\U0001faff\ufe0f\u2600-\u26ff\s]|@[\w_]+)+$")


# 1.44: a channel's signature line — "Вінниця Радар | Підписатись", "🔄 Моніторинг Миколаїв | Підписатись", "💪 Телеграм
# канал ППО Вінниця". Cut from the "Підписатись" alone, the channel's name stayed, and the parser drew a target at
# Vinnytsia under every post of @vinnytsiappo. The whole line goes (never the first: that is the warning).
_SIGN_LINE = re.compile(r"\n[^\n]{0,80}\|\s*п[іо]дпи[сш]\w*[^\n]*|\n[^\n\w]{0,6}телеграм[\s-]+канал\b[^\n]*", re.I)


def strip_promo(text):
    """Cut the channel's advertising tail off a post, keeping the warning itself."""
    if not text:
        return text
    t = _SIGN_LINE.sub("", text)
    t = _PROMO.sub("", t)
    t = _TAIL_JUNK.sub("", t)          # trailing "| ❤️", "⚠️ @monitor_ukr", stray separators
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"\s*[|·•,;:—–-]\s*$", "", t.strip())
    return t.strip() or (text or "").strip()


def clean(text):
    """Drop channel boilerplate before translation: hashtags (#без_бар'єрів), 'subscribe', 'read more', ads."""
    t = re.sub(r"[\u3164\u200b\u2800\u00a0]+", " ", text or "")
    t = strip_promo(t)
    t = _BOILER.sub("", t)
    t = re.sub(r"(?<!\w)#[\w'’\-]+", "", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def translate(text):
    """English: a machine translator if one answers, else the offline glossary. LAST_OK says which."""
    text = clean(text)
    if text and re.search(r"[А-ЯІЇЄа-яіїє]", text) and backends():
        out, _ = machine(text, "en")
        if out is not None:
            LAST_OK[0] = True
            return out
    LAST_OK[0] = not re.search(r"[А-ЯІЇЄа-яіїє]", text or "")
    return translate_offline(text)


def translate_to(text, lang):
    """(text, machine) for 'en' or 'fr'. French has no offline fallback: (None, False) — the page then shows English."""
    text = clean(text)
    if not re.search(r"[А-ЯІЇЄа-яіїє]", text or ""):
        return text, True
    out, _ = machine(text, lang)
    if out is not None:
        return out, True
    return (translate_offline(text), False) if lang == "en" else (None, False)


# Everyday words of these channels that the phrase glossary above does not cover. Without them the fallback
# printed "oblast zahalom clear, poky dykhaiemo" — a transliteration, which reads as noise to anyone who needs
# the translation. Collected from ~1,000 posts of the six channels the app reads (Sep 2026): each is a word the
# glossary used to leave in Cyrillic, most frequent first. Rough grammar, right words.
WORDS = {
    # whole phrases first (the longest key wins)
    "поки дихаємо": "breathing easy for now", "поки що": "for now", "баражуючих боєприпасів": "loitering munitions",
    "в повітряному просторі": "in the airspace", "у повітряному просторі": "in the airspace", "повітряному просторі": "airspace",
    "повітряного простору": "airspace", "зона відчуження": "exclusion zone", "зоні відчуження": "exclusion zone",
    "силайте в анонімний бот": "send it to the anonymous bot", "анонімний бот": "anonymous bot", "робота ппо": "air defence at work",
    "на даний момент": "at the moment", "в даний момент": "at the moment", "тим часом": "meanwhile", "з боку": "from the side of",
    "ще один": "one more", "ще одна": "one more", "ще одне": "one more", "ще два": "two more", "ще дві": "two more",
    "нас атакують": "we are under attack", "атакують": "attacking", "пролунав": "was heard", "пролунали": "were heard",
    "чути": "heard", "квартирі": "an apartment", "квартира": "an apartment", "жк": "residential complex",
    "в бік": "toward", "у бік": "toward", "в сторону": "toward", "у напрямку": "toward", "так само": "likewise",
    # movement
    "йде": "heading", "іде": "heading", "йдуть": "heading", "ідуть": "heading", "далі": "further", "назад": "back",
    "кружляє": "circling", "кружляють": "circling", "маневрує": "manoeuvring", "довернув": "turned", "розвернувся": "turned back",
    "вилітають": "taking off", "вилітає": "taking off", "залітають": "entering", "залітає": "entering", "відлітає": "leaving",
    "виходить": "leaving", "виходять": "leaving", "заходить": "coming in", "заходять": "coming in", "летить": "flying", "летять": "flying",
    "транзит": "transit", "транзитом": "in transit", "руху": "movement", "рух": "movement", "напрямок": "direction", "напрям": "direction",
    "готується": "preparing", "готуються": "preparing", "повертає": "turning", "змінив": "changed", "змінили": "changed",
    # what
    "ударний": "strike drone", "ударних": "strike drones", "ударні": "strike drones", "ударна": "strike", "керований": "guided", "керовані": "guided",
    "керованих": "guided", "звичайний": "regular", "звичайних": "regular", "звичайні": "regular", "типу": "type", "типів": "types",
    "бандероль": "Banderol (jet drone)", "бандеролі": "Banderol (jet drones)", "бандеролей": "Banderol (jet drones)",
    "циркон": "Zircon", "іскандер": "Iskander", "гербера": "Gerbera (decoy)", "гербер": "Gerbera (decoy)", "малогабаритних": "small",
    "гіперзвукових": "hypersonic", "швидкісна": "high-speed", "масована": "massed", "атака": "attack", "атаки": "attacks", "атак": "attacks",
    "влучання": "impact", "влучив": "hit", "уламок": "debris", "уламки": "debris", "пошкоджено": "damaged", "пошкоджені": "damaged",
    "висота": "altitude", "пара": "a pair", "табун": "a swarm", "пачка": "a pack", "суміш": "a mix", "ворог": "the enemy", "противник": "the enemy",
    # how many
    "один": "one", "одна": "one", "одне": "one", "одного": "one", "два": "two", "дві": "two", "три": "three", "троє": "three",
    "декілька": "several", "кілька": "several", "десяток": "about ten", "десятка": "about ten", "щонайменше": "at least",
    "більше": "more", "менше": "fewer", "близько": "about", "приблизно": "about", "приблизна": "approximate", "всі": "all", "всіх": "all",
    "одиниць": "units", "од": "units", "шт": "pcs", "перший": "first", "другий": "second", "наступний": "next", "наступна": "next",
    "наступні": "next", "наступних": "next", "останній": "last",
    # where
    "захід": "west", "заході": "west", "заходу": "west", "схід": "east", "сході": "east", "сходу": "east", "північ": "north",
    "півночі": "north", "південь": "south", "півдні": "south", "межі": "border", "межа": "border", "кордону": "the border",
    "околиці": "outskirts", "передмісті": "suburbs", "передмістя": "suburbs", "центрі": "centre", "частині": "part",
    "частина": "part", "частини": "part", "території": "territory", "територію": "territory", "зону": "zone", "зоні": "zone",
    "зона": "zone", "десь": "somewhere", "поруч": "nearby", "між": "between", "моря": "sea", "десну": "the Desna", "десни": "the Desna",
    "десна": "the Desna", "бучу": "Bucha", "бучі": "Bucha", "трою": "Troieshchyna", "трої": "Troieshchyna", "рф": "Russia",
    "україни": "Ukraine", "білорусі": "Belarus", "білорусь": "Belarus", "орел": "Oryol", "орла": "Oryol", "курськ": "Kursk",
    "курської": "Kursk oblast", "брянщини": "Bryansk oblast", "брянської": "Bryansk oblast", "ростовської": "Rostov oblast",
    "шаталово": "Shatalovo", "шаталове": "Shatalovo",
    # when / state
    "поки": "for now", "загалом": "overall", "після": "after", "ніч": "night", "доби": "day", "час": "time", "момент": "moment",
    "тиша": "quiet", "відмічено": "spotted", "зафіксовано": "recorded", "виявлено": "detected", "застосовано": "used",
    "очікуємо": "we expect", "підтвердиться": "is confirmed", "інформація": "information", "окремо": "separately",
    # small words
    "він": "it", "вони": "they", "його": "it", "йому": "it", "нас": "us", "вами": "you", "цей": "this", "ті": "those", "тим": "that",
    "є": "there is", "не": "not", "ні": "no", "так": "yes", "як": "as", "якщо": "if", "що": "that", "та": "and", "і": "and", "й": "and",
    "а": "and", "о": "at", "чи": "or", "де": "where", "все": "all", "ще": "still", "вже": "already", "також": "also", "трішки": "a little",
    "трошки": "a little", "варто": "worth", "робота": "work", "роботи": "work", "перемогу": "victory", "ймовірний": "probable",
    "потенційно": "potentially", "чітко": "clearly", "повністю": "completely", "головне": "the main thing", "будинки": "houses",
}
_WORD = re.compile(r"(?<![а-яіїєґ'’ʼa-z])(" + "|".join(sorted(map(re.escape, WORDS), key=len, reverse=True)) + r")(?![а-яіїєґ'’ʼa-z])", re.I)


def _words(t):
    def rep(m):
        w = m.group(0)
        en = WORDS[re.sub(r"\s+", " ", w.lower())]
        return en[0].upper() + en[1:] if w[0].isupper() and m.start() in (0,) else en
    t = re.sub(r"\b[мс]\.\s*(?=[А-ЯІЇЄҐ])", "", t)     # "м. Бровари", "с. Гора": the name says it
    return _WORD.sub(rep, t)


def translate_offline(text):
    t = _norm(clean(text))
    # 1. raions
    def raion(m):
        stem = m.group(1).lower()
        return (RAION_EN.get(stem) or translit(stem[:-3].capitalize())) + " raion"
    t = _RAION.sub(raion, t)
    # 2. gazetteer places → transliterated names (handles declension)
    if geo:
        spans = geo._find_places(t.lower())
        if spans:
            out, last = [], 0
            for s, e, name in spans:
                chunk = t[last:s]
                en, cut = _prep_for(chunk, t[s:e], name)
                if en:
                    chunk = chunk[:-cut] + en + " "
                out.append(chunk)
                out.append(PLACE_EN.get(name) or translit(name.split(" (")[0]))
                last = e
            out.append(t[last:])
            t = "".join(out)
    # 3. oblast adjectives → "X region" (with case-aware preposition)
    def obl(m):
        tok = m.group(0).lower()
        prefix = t[:m.start()]
        pm = _PREP_RX.search(prefix)
        en = OBLAST_EN[m.group(1).lower()] + " region"
        if pm:
            p = pm.group(1).lower()
            prep = PREP.get(p) if p != "на" else ("to" if tok.endswith(("у", "ю")) else "in")
            return "\x00" * len(pm.group(0)) + prep + " " + en
        return en
    t = _OBL.sub(obl, t)
    t = re.sub(r"(на|в|у|до|від|з|зі|із|біля|поблизу|повз|над|через|довкола|навколо|поряд)\s+\x00+", "", t, flags=re.I)
    t = t.replace("\x00", "")
    # 4. glossary
    for rx, rep in _G:
        t = rx.sub(rep, t)
    # 4b. everyday words of these channels
    t = _words(t)
    # 5. leftovers: transliterate any remaining Cyrillic
    t = _CYR.sub(lambda m: translit(m.group(0)), t)
    # tidy
    t = re.sub(r"(^|\n)([^\w\n]*)([a-z])", lambda m: m.group(1) + m.group(2) + m.group(3).upper(), t)   # a line starts with a capital
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" ([,.;:!?)])", r"\1", t)
    t = re.sub(r"\(\s+", "(", t)
    return t.strip()


if __name__ == "__main__":
    tests = ["🛵 Ударні БпЛА на півночі Чернігівщини на/повз Ріпки ➡️ у південно-західному напрямку.",
             "🟡 Броварський район — повітряна тривога, жовтий рівень: Дронова загроза (жовтий рівень)",
             "1х зниження Троєщина.", "По реактивам довкола Києва та Житомира чисто.\n\nЗалишок 1х реактив на Вінниччині. За ним йде полювання.",
             "✈️Харківщина:\n→Богодухів/р-н;\n→Білий Колодязь/Шевченкове (5х).", "🟡 УВАГА! У Києві оголошена дронова небезпека!\n\nПросимо всіх терміново прослідувати в укриття цивільного захисту!",
             "🅿️1х реактив від Білої Церкви на Фастів.", "Пуски змішаних груп БпЛА з Орла.", "💣Пуски керованих авіаційних бомб ворожою тактичною авіацією на Дніпропетровщину та Запоріжжя"]
    for s in tests:
        print(s.replace("\n", " | "), "\n   →", translate(s).replace("\n", " | "))
