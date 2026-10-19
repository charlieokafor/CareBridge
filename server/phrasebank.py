"""Languages, pre-checked phrases, consent text and the medical glossary.

All non-English text here is a DRAFT written for the hackathon prototype. It is marked
"pending interpreter review" in the app and must be checked by TUH's professional interpreters
before clinical use (rung 0 of the Safety Ladder)."""
import difflib
import json
import os
import re

# code: (English name, native name, NLLB code, Whisper code or None, device-voice tag, right-to-left)
_CATALOGUE = {
    "en": ("English", "English", "eng_Latn", "en", "en-IE", False),
    # Pilot languages: TUH's five most-booked, with team-drafted consent text and pre-checked phrases
    "uk": ("Ukrainian", "Українська", "ukr_Cyrl", "uk", "uk-UA", False),
    "ru": ("Russian", "Русский", "rus_Cyrl", "ru", "ru-RU", False),
    "pl": ("Polish", "Polski", "pol_Latn", "pl", "pl-PL", False),
    "ro": ("Romanian", "Română", "ron_Latn", "ro", "ro-RO", False),
    "ar": ("Arabic", "العربية", "arb_Arab", "ar", "ar-SA", True),
    # Also drafted by the team
    "ga": ("Irish", "Gaeilge", "gle_Latn", None, "ga-IE", False),
    "fr": ("French", "Français", "fra_Latn", "fr", "fr-FR", False),
    "es": ("Spanish", "Español", "spa_Latn", "es", "es-ES", False),
    "ur": ("Urdu", "اردو", "urd_Arab", "ur", "ur-PK", True),
    "ko": ("Korean", "한국어", "kor_Hang", "ko", "ko-KR", False),
    # Machine-translated interface (pending interpreter review)
    "pt": ("Portuguese", "Português", "por_Latn", "pt", "pt-BR", False),
    "zh": ("Chinese (Mandarin)", "中文", "zho_Hans", "zh", "zh-CN", False),
    "lt": ("Lithuanian", "Lietuvių", "lit_Latn", "lt", "lt-LT", False),
    "lv": ("Latvian", "Latviešu", "lvs_Latn", "lv", "lv-LV", False),
    "ka": ("Georgian", "ქართული", "kat_Geor", "ka", "ka-GE", False),
    "sq": ("Albanian", "Shqip", "als_Latn", "sq", "sq-AL", False),
    "tr": ("Turkish", "Türkçe", "tur_Latn", "tr", "tr-TR", False),
    "prs": ("Dari", "دری", "prs_Arab", "fa", "fa-AF", True),
    "ps": ("Pashto", "پښتو", "pbt_Arab", "ps", "ps-AF", True),
    "ckb": ("Kurdish (Sorani)", "کوردی", "ckb_Arab", None, "ckb-IQ", True),
    "so": ("Somali", "Soomaali", "som_Latn", "so", "so-SO", False),
    "ti": ("Tigrinya", "ትግርኛ", "tir_Ethi", None, "ti-ER", False),
    "am": ("Amharic", "አማርኛ", "amh_Ethi", "am", "am-ET", False),
    "sw": ("Swahili", "Kiswahili", "swh_Latn", "sw", "sw-KE", False),
    "yo": ("Yoruba", "Yorùbá", "yor_Latn", "yo", "yo-NG", False),
    "ha": ("Hausa", "Hausa", "hau_Latn", "ha", "ha-NG", False),
    "ig": ("Igbo", "Igbo", "ibo_Latn", None, "ig-NG", False),
    "hi": ("Hindi", "हिन्दी", "hin_Deva", "hi", "hi-IN", False),
    "bn": ("Bengali", "বাংলা", "ben_Beng", "bn", "bn-BD", False),
    "pa": ("Punjabi", "ਪੰਜਾਬੀ", "pan_Guru", "pa", "pa-IN", False),
    "it": ("Italian", "Italiano", "ita_Latn", "it", "it-IT", False),
    "de": ("German", "Deutsch", "deu_Latn", "de", "de-DE", False),
    "hu": ("Hungarian", "Magyar", "hun_Latn", "hu", "hu-HU", False),
    "sk": ("Slovak", "Slovenčina", "slk_Latn", "sk", "sk-SK", False),
    "bg": ("Bulgarian", "Български", "bul_Cyrl", "bg", "bg-BG", False),
    "vi": ("Vietnamese", "Tiếng Việt", "vie_Latn", "vi", "vi-VN", False),
    "tl": ("Filipino", "Filipino", "tgl_Latn", "tl", "fil-PH", False),
    "id": ("Indonesian", "Bahasa Indonesia", "ind_Latn", "id", "id-ID", False),
    "ja": ("Japanese", "日本語", "jpn_Jpan", "ja", "ja-JP", False),
    "cs": ("Czech", "Čeština", "ces_Latn", "cs", "cs-CZ", False),
    "el": ("Greek", "Ελληνικά", "ell_Grek", "el", "el-GR", False),
    # Cantonese: recognised by Amazon Transcribe (zh-HK); the server's Whisper-small has no Cantonese of its own and
    # hears it as Chinese, so for Whisper it is "zh" (WHISPER_MODEL_LANG) and Transcribe tells the two apart.
    "yue": ("Cantonese", "廣東話", "yue_Hant", "yue", "zh-HK", False),
}
# Languages the server's Whisper model has no token for: the code it uses instead
WHISPER_MODEL_LANG = {"yue": "zh"}
PILOT_LANGS = ["uk", "ru", "pl", "ro", "ar"]
DRAFTED_LANGS = PILOT_LANGS + ["ga", "fr", "es", "ur", "ko"]
SERVER_VOICES = {"en", "uk", "ru", "pl", "ro", "ar"}


def _tier(code, whisper):
    if code in PILOT_LANGS:
        return "pilot"
    return "speech" if whisper else "text"


LANGUAGES = {
    code: {"name": n, "native": nat, "nllb": nllb, "whisper": wh, "bcp47": tag, "dir": "rtl" if rtl else "ltr",
           "tier": _tier(code, wh), "serverVoice": code in SERVER_VOICES, "drafted": code in DRAFTED_LANGS}
    for code, (n, nat, nllb, wh, tag, rtl) in _CATALOGUE.items()
}
# Language licences from our overnight evaluation (eval/lang_eval_server.py + eval/speech_eval.py):
# which translation model each language uses, whether speech is allowed, and which languages failed.
LICENCE = {}
_LICENCE_PATH = os.path.join(os.path.dirname(__file__), "lang_licence.json")
if os.path.exists(_LICENCE_PATH):
    with open(_LICENCE_PATH, encoding="utf-8") as _f:
        LICENCE = json.load(_f)
for _code, _lic in LICENCE.items():
    if _code not in LANGUAGES or _code == "en":
        continue
    if _lic.get("model") == "remove":
        del LANGUAGES[_code]
        continue
    LANGUAGES[_code]["model"] = _lic.get("model", "600m")
    if _lic.get("speech") is False:   # failed the speech test (None = not tested yet: speech stays on)
        LANGUAGES[_code]["whisper"] = None
    LANGUAGES[_code]["licence"] = {k: _lic[k] for k in ("mtScore", "okRate", "asrCer", "detection") if k in _lic}
    LANGUAGES[_code]["tier"] = _tier(_code, LANGUAGES[_code]["whisper"])
PILOT_LANGS = [c for c in PILOT_LANGS if c in LANGUAGES]
PATIENT_LANGS = PILOT_LANGS + sorted((c for c in LANGUAGES if c != "en" and c not in PILOT_LANGS),
                                     key=lambda c: LANGUAGES[c]["name"])
WHISPER_TO_CODE = {v["whisper"]: k for k, v in LANGUAGES.items() if v["whisper"] and k not in WHISPER_MODEL_LANG}

# Interface text the patient sees, in their own language.
PATIENT_UI = {
    "uk": {"choose": "Оберіть свою мову", "consent_title": "Перекладач CareBridge",
           "consent": "Це комп'ютерний перекладач, яким користується медичний персонал. Він може помилятися. Ви будь-коли можете попросити живого перекладача.",
           "consent_q": "Ви згодні ним користуватися?", "yes": "Так", "no": "Ні",
           "human": "Я хочу живого перекладача", "speak": "Натисніть і говоріть", "listening": "Слухаю…",
           "waiting": "Медпрацівник говорить…", "pain": "Наскільки сильний біль?", "replies": "Швидкі відповіді",
           "interpreter_coming": "Професійний перекладач уже в дорозі."},
    "ru": {"choose": "Выберите свой язык", "consent_title": "Переводчик CareBridge",
           "consent": "Это компьютерный переводчик, которым пользуется медицинский персонал. Он может ошибаться. Вы в любой момент можете попросить живого переводчика.",
           "consent_q": "Вы согласны им пользоваться?", "yes": "Да", "no": "Нет",
           "human": "Я хочу живого переводчика", "speak": "Нажмите и говорите", "listening": "Слушаю…",
           "waiting": "Медработник говорит…", "pain": "Насколько сильная боль?", "replies": "Быстрые ответы",
           "interpreter_coming": "Профессиональный переводчик уже в пути."},
    "pl": {"choose": "Wybierz swój język", "consent_title": "Tłumacz CareBridge",
           "consent": "To jest komputerowy tłumacz używany przez personel szpitala. Może popełniać błędy. W każdej chwili można poprosić o tłumacza.",
           "consent_q": "Czy zgadza się Pan/Pani na jego użycie?", "yes": "Tak", "no": "Nie",
           "human": "Chcę rozmawiać przez tłumacza", "speak": "Naciśnij i mów", "listening": "Słucham…",
           "waiting": "Personel mówi…", "pain": "Jak silny jest ból?", "replies": "Szybkie odpowiedzi",
           "interpreter_coming": "Profesjonalny tłumacz jest w drodze."},
    "ro": {"choose": "Alegeți limba dumneavoastră", "consent_title": "Traducătorul CareBridge",
           "consent": "Acesta este un traducător pe calculator folosit de personalul spitalului. Poate greși. Puteți cere oricând un interpret uman.",
           "consent_q": "Sunteți de acord să îl folosim?", "yes": "Da", "no": "Nu",
           "human": "Vreau un interpret uman", "speak": "Apăsați și vorbiți", "listening": "Ascult…",
           "waiting": "Personalul vorbește…", "pain": "Cât de puternică este durerea?", "replies": "Răspunsuri rapide",
           "interpreter_coming": "Un interpret profesionist este pe drum."},
    "ar": {"choose": "اختر لغتك", "consent_title": "مترجم CareBridge",
           "consent": "هذا مترجم آلي يستخدمه طاقم المستشفى. قد يخطئ. يمكنك طلب مترجم بشري في أي وقت.",
           "consent_q": "هل توافق على استخدامه؟", "yes": "نعم", "no": "لا",
           "human": "أريد مترجمًا بشريًا", "speak": "اضغط وتحدث", "listening": "أستمع…",
           "waiting": "الطاقم الطبي يتحدث…", "pain": "ما مدى شدة الألم؟", "replies": "ردود سريعة",
           "interpreter_coming": "مترجم محترف في الطريق."},
}

# Pre-checked phrases. If a clinician says one of these, the checked translation is used instead of
# machine translation. Patient quick replies use the same mechanism.
PHRASES = {
    "hello": {"en": "Hello, I am here to help you.", "uk": "Добрий день, я тут, щоб вам допомогти.",
              "ru": "Здравствуйте, я здесь, чтобы вам помочь.", "pl": "Dzień dobry, jestem tu, żeby pomóc.",
              "ro": "Bună ziua, sunt aici să vă ajut.", "ar": "مرحبًا، أنا هنا لمساعدتك."},
    "in_pain": {"en": "Are you in pain?", "uk": "У вас щось болить?", "ru": "У вас что-нибудь болит?",
                "pl": "Czy coś boli?", "ro": "Vă doare ceva?", "ar": "هل تشعر بألم؟"},
    "where_hurt": {"en": "Where does it hurt?", "uk": "Де у вас болить?", "ru": "Где у вас болит?",
                   "pl": "Gdzie boli?", "ro": "Unde vă doare?", "ar": "أين تشعر بالألم؟"},
    "pain_scale": {"en": "On a scale of 0 to 10, how bad is the pain?", "uk": "Оцініть свій біль від 0 до 10.",
                   "ru": "Оцените свою боль от 0 до 10.", "pl": "Proszę ocenić ból w skali od 0 do 10.",
                   "ro": "Vă rog să evaluați durerea pe o scară de la 0 la 10.", "ar": "قيّم ألمك من 0 إلى 10."},
    "allergies": {"en": "Do you have any allergies?", "uk": "У вас є алергія на щось?",
                  "ru": "У вас есть аллергия на что-нибудь?", "pl": "Czy ma Pan/Pani jakieś alergie?",
                  "ro": "Aveți vreo alergie?", "ar": "هل لديك أي حساسية؟"},
    "since_midnight": {"en": "Have you eaten or drunk anything since midnight?",
                       "uk": "Ви щось їли або пили після опівночі?", "ru": "Вы что-нибудь ели или пили после полуночи?",
                       "pl": "Czy od północy coś Pan/Pani jadł(a) lub pił(a)?",
                       "ro": "Ați mâncat sau ați băut ceva după miezul nopții?",
                       "ar": "هل أكلت أو شربت أي شيء منذ منتصف الليل؟"},
    "nothing_by_mouth": {"en": "Please do not eat or drink anything.", "uk": "Будь ласка, нічого не їжте і не пийте.",
                         "ru": "Пожалуйста, ничего не ешьте и не пейте.", "pl": "Proszę nic nie jeść ani nie pić.",
                         "ro": "Vă rog să nu mâncați și să nu beți nimic.", "ar": "من فضلك لا تأكل ولا تشرب أي شيء."},
    "blood_test": {"en": "We need to take a blood test.", "uk": "Нам потрібно взяти аналіз крові.",
                   "ru": "Нам нужно взять анализ крови.", "pl": "Musimy pobrać krew do badania.",
                   "ro": "Trebuie să vă recoltăm o probă de sânge.", "ar": "نحتاج إلى أخذ عينة دم."},
    "pregnant": {"en": "Are you pregnant?", "uk": "Ви вагітні?", "ru": "Вы беременны?",
                 "pl": "Czy jest Pani w ciąży?", "ro": "Sunteți însărcinată?", "ar": "هل أنتِ حامل؟"},
    "medicines": {"en": "Do you take any medicines?", "uk": "Ви приймаєте якісь ліки?",
                  "ru": "Вы принимаете какие-нибудь лекарства?", "pl": "Czy przyjmuje Pan/Pani jakieś leki?",
                  "ro": "Luați vreun medicament?", "ar": "هل تتناول أي أدوية؟"},
    "wait_here": {"en": "Please wait here.", "uk": "Будь ласка, зачекайте тут.", "ru": "Пожалуйста, подождите здесь.",
                  "pl": "Proszę tu zaczekać.", "ro": "Vă rog să așteptați aici.", "ar": "من فضلك انتظر هنا."},
    "interpreter_coming": {"en": "A professional interpreter is on the way.", "uk": "Професійний перекладач уже в дорозі.",
                           "ru": "Профессиональный переводчик уже в пути.", "pl": "Profesjonalny tłumacz jest w drodze.",
                           "ro": "Un interpret profesionist este pe drum.", "ar": "مترجم محترف في الطريق."},
    "understand": {"en": "Do you understand?", "uk": "Вам зрозуміло?", "ru": "Вам понятно?",
                   "pl": "Czy to jest zrozumiałe?", "ro": "Ați înțeles?", "ar": "هل فهمت؟"},
    # Patient quick replies
    "r_yes": {"en": "Yes.", "uk": "Так.", "ru": "Да.", "pl": "Tak.", "ro": "Da.", "ar": "نعم."},
    "r_no": {"en": "No.", "uk": "Ні.", "ru": "Нет.", "pl": "Nie.", "ro": "Nu.", "ar": "لا."},
    "r_not_understand": {"en": "I don't understand.", "uk": "Я не розумію.", "ru": "Я не понимаю.",
                         "pl": "Nie rozumiem.", "ro": "Nu înțeleg.", "ar": "لا أفهم."},
    "r_repeat": {"en": "Please repeat that.", "uk": "Повторіть, будь ласка.", "ru": "Повторите, пожалуйста.",
                 "pl": "Proszę powtórzyć.", "ro": "Vă rog să repetați.", "ar": "أعد من فضلك."},
    "r_interpreter": {"en": "I need a human interpreter.", "uk": "Мені потрібен живий перекладач.",
                      "ru": "Мне нужен живой переводчик.", "pl": "Potrzebuję tłumacza.",
                      "ro": "Am nevoie de un interpret uman.", "ar": "أحتاج إلى مترجم بشري."},
    "r_pain": {"en": "I am in pain.", "uk": "Мені боляче.", "ru": "Мне больно.", "pl": "Boli mnie.",
               "ro": "Mă doare.", "ar": "أشعر بألم."},
    "r_toilet": {"en": "I need the toilet.", "uk": "Мені потрібно в туалет.", "ru": "Мне нужно в туалет.",
                 "pl": "Muszę iść do toalety.", "ro": "Trebuie să merg la toaletă.", "ar": "أحتاج إلى الحمام."},
    "r_water": {"en": "Can I have some water?", "uk": "Можна мені води?", "ru": "Можно мне воды?",
                "pl": "Czy mogę dostać wodę?", "ro": "Pot să primesc puțină apă?", "ar": "هل يمكنني الحصول على بعض الماء؟"},
}
PAIN_TEMPLATE = {"en": "My pain is {n} out of 10.", "uk": "Мій біль — {n} з 10.", "ru": "Моя боль — {n} из 10.",
                 "pl": "Mój ból to {n} na 10.", "ro": "Durerea mea este {n} din 10.", "ar": "ألمي {n} من 10."}
QUICK_REPLIES = ["r_yes", "r_no", "r_pain", "r_not_understand", "r_repeat", "r_water", "r_toilet", "r_interpreter"]
CLINICIAN_PHRASES = ["hello", "in_pain", "where_hurt", "pain_scale", "allergies", "since_midnight",
                     "nothing_by_mouth", "medicines", "pregnant", "blood_test", "understand", "wait_here"]

# Team-drafted text for Irish, French, Spanish, Urdu and Korean (pending interpreter review)
_DRAFTED = {
    "ga": {
        "ui": {"choose": "Roghnaigh do theanga", "consent_title": "Aistritheoir CareBridge",
               "consent": "Is aistritheoir ríomhaire é seo a úsáideann foireann an ospidéil. D'fhéadfadh botúin a bheith ann. Is féidir leat ateangaire daonna a iarraidh am ar bith.",
               "consent_q": "An aontaíonn tú é a úsáid?", "yes": "Tá", "no": "Níl",
               "human": "Teastaíonn ateangaire daonna uaim", "speak": "Brúigh agus labhair", "listening": "Ag éisteacht…",
               "waiting": "Tá an fhoireann ag caint…", "pain": "Cé chomh dona is atá an phian?", "replies": "Freagraí tapa",
               "interpreter_coming": "Tá ateangaire gairmiúil ar an mbealach."},
        "phrases": {"hello": "Dia duit, táim anseo chun cabhrú leat.", "in_pain": "An bhfuil pian ort?",
                    "where_hurt": "Cá bhfuil an phian?", "pain_scale": "Ar scála ó 0 go 10, cé chomh dona is atá an phian?",
                    "allergies": "An bhfuil aon ailléirge ort?", "since_midnight": "Ar ith nó ar ól tú aon rud ó mheán oíche?",
                    "nothing_by_mouth": "Ná hith agus ná hól aon rud, le do thoil.", "blood_test": "Caithfimid tástáil fola a dhéanamh.",
                    "pregnant": "An bhfuil tú ag iompar clainne?", "medicines": "An dtógann tú aon chógas?",
                    "wait_here": "Fan anseo, le do thoil.", "interpreter_coming": "Tá ateangaire gairmiúil ar an mbealach.",
                    "understand": "An dtuigeann tú?", "r_yes": "Tá.", "r_no": "Níl.", "r_not_understand": "Ní thuigim.",
                    "r_repeat": "Abair arís é, le do thoil.", "r_interpreter": "Teastaíonn ateangaire daonna uaim.",
                    "r_pain": "Tá pian orm.", "r_toilet": "Caithfidh mé dul go dtí an leithreas.", "r_water": "An féidir liom uisce a fháil?"},
        "pain": "Tá mo phian {n} as 10."},
    "fr": {
        "ui": {"choose": "Choisissez votre langue", "consent_title": "Traducteur CareBridge",
               "consent": "Ceci est un traducteur informatique utilisé par le personnel de l'hôpital. Il peut faire des erreurs. Vous pouvez demander un interprète humain à tout moment.",
               "consent_q": "Acceptez-vous de l'utiliser ?", "yes": "Oui", "no": "Non",
               "human": "Je veux un interprète humain", "speak": "Appuyez et parlez", "listening": "J'écoute…",
               "waiting": "Le soignant parle…", "pain": "Quelle est l'intensité de la douleur ?", "replies": "Réponses rapides",
               "interpreter_coming": "Un interprète professionnel arrive."},
        "phrases": {"hello": "Bonjour, je suis là pour vous aider.", "in_pain": "Avez-vous mal ?", "where_hurt": "Où avez-vous mal ?",
                    "pain_scale": "Sur une échelle de 0 à 10, quelle est l'intensité de la douleur ?",
                    "allergies": "Avez-vous des allergies ?", "since_midnight": "Avez-vous mangé ou bu quelque chose depuis minuit ?",
                    "nothing_by_mouth": "Veuillez ne rien manger ni boire.", "blood_test": "Nous devons faire une prise de sang.",
                    "pregnant": "Êtes-vous enceinte ?", "medicines": "Prenez-vous des médicaments ?", "wait_here": "Veuillez attendre ici.",
                    "interpreter_coming": "Un interprète professionnel arrive.", "understand": "Avez-vous compris ?",
                    "r_yes": "Oui.", "r_no": "Non.", "r_not_understand": "Je ne comprends pas.",
                    "r_repeat": "Pouvez-vous répéter, s'il vous plaît ?", "r_interpreter": "J'ai besoin d'un interprète humain.",
                    "r_pain": "J'ai mal.", "r_toilet": "J'ai besoin d'aller aux toilettes.", "r_water": "Puis-je avoir de l'eau ?"},
        "pain": "Ma douleur est à {n} sur 10."},
    "es": {
        "ui": {"choose": "Elija su idioma", "consent_title": "Traductor CareBridge",
               "consent": "Este es un traductor informático que usa el personal del hospital. Puede cometer errores. Puede pedir un intérprete humano en cualquier momento.",
               "consent_q": "¿Está de acuerdo en usarlo?", "yes": "Sí", "no": "No",
               "human": "Quiero un intérprete humano", "speak": "Pulse y hable", "listening": "Escuchando…",
               "waiting": "El personal está hablando…", "pain": "¿Cuánto le duele?", "replies": "Respuestas rápidas",
               "interpreter_coming": "Un intérprete profesional está en camino."},
        "phrases": {"hello": "Hola, estoy aquí para ayudarle.", "in_pain": "¿Tiene dolor?", "where_hurt": "¿Dónde le duele?",
                    "pain_scale": "En una escala del 0 al 10, ¿cuánto le duele?", "allergies": "¿Tiene alguna alergia?",
                    "since_midnight": "¿Ha comido o bebido algo desde la medianoche?", "nothing_by_mouth": "Por favor, no coma ni beba nada.",
                    "blood_test": "Necesitamos hacerle un análisis de sangre.", "pregnant": "¿Está embarazada?",
                    "medicines": "¿Toma algún medicamento?", "wait_here": "Por favor, espere aquí.",
                    "interpreter_coming": "Un intérprete profesional está en camino.", "understand": "¿Lo ha entendido?",
                    "r_yes": "Sí.", "r_no": "No.", "r_not_understand": "No entiendo.", "r_repeat": "¿Puede repetirlo, por favor?",
                    "r_interpreter": "Necesito un intérprete humano.", "r_pain": "Me duele.", "r_toilet": "Necesito ir al baño.",
                    "r_water": "¿Me puede dar agua?"},
        "pain": "Mi dolor es {n} de 10."},
    "ur": {
        "ui": {"choose": "اپنی زبان منتخب کریں", "consent_title": "CareBridge مترجم",
               "consent": "یہ ایک کمپیوٹر مترجم ہے جسے ہسپتال کا عملہ استعمال کرتا ہے۔ اس سے غلطی ہو سکتی ہے۔ آپ کسی بھی وقت انسانی ترجمان طلب کر سکتے ہیں۔",
               "consent_q": "کیا آپ اس کے استعمال سے متفق ہیں؟", "yes": "جی ہاں", "no": "نہیں",
               "human": "مجھے انسانی ترجمان چاہیے", "speak": "دبائیں اور بولیں", "listening": "سن رہا ہے…",
               "waiting": "عملہ بات کر رہا ہے…", "pain": "درد کتنا شدید ہے؟", "replies": "فوری جوابات",
               "interpreter_coming": "ایک پیشہ ور ترجمان آ رہا ہے۔"},
        "phrases": {"hello": "السلام علیکم، میں آپ کی مدد کے لیے یہاں ہوں۔", "in_pain": "کیا آپ کو درد ہے؟",
                    "where_hurt": "آپ کو کہاں درد ہو رہا ہے؟", "pain_scale": "0 سے 10 تک کے پیمانے پر، درد کتنا شدید ہے؟",
                    "allergies": "کیا آپ کو کسی چیز سے الرجی ہے؟", "since_midnight": "کیا آپ نے آدھی رات کے بعد کچھ کھایا یا پیا ہے؟",
                    "nothing_by_mouth": "براہ کرم کچھ نہ کھائیں اور نہ پئیں۔", "blood_test": "ہمیں آپ کے خون کا ٹیسٹ کرنا ہے۔",
                    "pregnant": "کیا آپ حاملہ ہیں؟", "medicines": "کیا آپ کوئی دوائی لیتے ہیں؟", "wait_here": "براہ کرم یہاں انتظار کریں۔",
                    "interpreter_coming": "ایک پیشہ ور ترجمان آ رہا ہے۔", "understand": "کیا آپ سمجھ گئے؟",
                    "r_yes": "جی ہاں۔", "r_no": "نہیں۔", "r_not_understand": "مجھے سمجھ نہیں آیا۔", "r_repeat": "براہ کرم دوبارہ کہیں۔",
                    "r_interpreter": "مجھے انسانی ترجمان چاہیے۔", "r_pain": "مجھے درد ہو رہا ہے۔", "r_toilet": "مجھے بیت الخلا جانا ہے۔",
                    "r_water": "کیا مجھے پانی مل سکتا ہے؟"},
        "pain": "میرا درد 10 میں سے {n} ہے۔"},
    "ko": {
        "ui": {"choose": "언어를 선택하세요", "consent_title": "CareBridge 통역기",
               "consent": "이것은 병원 직원이 사용하는 컴퓨터 통역기입니다. 오류가 있을 수 있습니다. 언제든지 사람 통역사를 요청할 수 있습니다.",
               "consent_q": "사용에 동의하십니까?", "yes": "예", "no": "아니요", "human": "사람 통역사를 원합니다",
               "speak": "누르고 말씀하세요", "listening": "듣고 있습니다…", "waiting": "의료진이 말하고 있습니다…",
               "pain": "통증이 얼마나 심한가요?", "replies": "빠른 답변", "interpreter_coming": "전문 통역사가 오고 있습니다."},
        "phrases": {"hello": "안녕하세요, 도와드리러 왔습니다.", "in_pain": "아프신 곳이 있나요?", "where_hurt": "어디가 아프세요?",
                    "pain_scale": "0부터 10까지 중에서 통증이 얼마나 심한가요?", "allergies": "알레르기가 있으신가요?",
                    "since_midnight": "자정 이후에 음식이나 음료를 드셨나요?", "nothing_by_mouth": "아무것도 드시거나 마시지 마세요.",
                    "blood_test": "혈액 검사를 해야 합니다.", "pregnant": "임신 중이신가요?", "medicines": "복용하시는 약이 있나요?",
                    "wait_here": "여기서 기다려 주세요.", "interpreter_coming": "전문 통역사가 오고 있습니다.", "understand": "이해하셨나요?",
                    "r_yes": "예.", "r_no": "아니요.", "r_not_understand": "이해가 안 됩니다.", "r_repeat": "다시 말씀해 주세요.",
                    "r_interpreter": "사람 통역사가 필요합니다.", "r_pain": "아파요.", "r_toilet": "화장실에 가야 해요.",
                    "r_water": "물 좀 주시겠어요?"},
        "pain": "제 통증은 10점 중 {n}점입니다."},
}
EN_UI = {"choose": "Choose your language", "consent_title": "CareBridge translator",
         "consent": "This is a computer translator used by hospital staff. It can make mistakes. You can ask for a human interpreter at any time.",
         "consent_q": "Do you agree to use it?", "yes": "Yes", "no": "No", "human": "I want a human interpreter",
         "speak": "Press and speak", "listening": "Listening…", "waiting": "The staff member is speaking…",
         "pain": "How bad is the pain?", "replies": "Quick answers",
         "interpreter_coming": "A professional interpreter is on the way.", "type": "Type your answer"}
_TYPE = {"uk": "Напишіть відповідь", "ru": "Напишите ответ", "pl": "Napisz odpowiedź", "ro": "Scrieți răspunsul",
         "ar": "اكتب إجابتك", "ga": "Scríobh do fhreagra", "fr": "Écrivez votre réponse", "es": "Escriba su respuesta",
         "ur": "اپنا جواب لکھیں", "ko": "답변을 입력하세요"}
for _code, _d in _DRAFTED.items():
    PATIENT_UI[_code] = _d["ui"]
    PAIN_TEMPLATE[_code] = _d["pain"]
    for _pid, _txt in _d["phrases"].items():
        PHRASES[_pid][_code] = _txt
for _code, _t in _TYPE.items():
    PATIENT_UI[_code]["type"] = _t

# Machine-translated interface text for the remaining languages (generated once with NLLB-200 by
# eval/build_auto_phrasebank.py; shown to patients but never treated as "pre-checked").
AUTO = {}
_AUTO_PATH = os.path.join(os.path.dirname(__file__), "phrasebank_auto.json")
if os.path.exists(_AUTO_PATH):
    with open(_AUTO_PATH, encoding="utf-8") as _f:
        AUTO = json.load(_f)
for _code, _d in AUTO.items():
    if _code in DRAFTED_LANGS or _code not in LANGUAGES:
        continue
    PATIENT_UI[_code] = {**EN_UI, **_d.get("ui", {})}   # any string not generated falls back to English
    if _d.get("pain"):
        PAIN_TEMPLATE[_code] = _d["pain"]


def phrase(pid, lang):
    """Patient-facing text for a phrase: drafted if we have it, else machine-translated, else None."""
    if lang in PHRASES.get(pid, {}):
        return PHRASES[pid][lang]
    return AUTO.get(lang, {}).get("phrases", {}).get(pid)


def is_checked(pid, lang):
    """True only for team-drafted phrases (the ones prepared for interpreter review)."""
    return lang in PHRASES.get(pid, {})

# Medical glossary: each English term has accepted stems per language. Used to check that a
# translation kept the right medical word (NLLB has no forced-terminology option).
GLOSSARY = {
    "paracetamol": {"uk": ["парацетамол"], "ru": ["парацетамол"], "pl": ["paracetamol"], "ro": ["paracetamol"], "ar": ["باراسيتامول", "الباراسيتامول"]},
    "ibuprofen": {"uk": ["ібупрофен"], "ru": ["ибупрофен"], "pl": ["ibuprofen"], "ro": ["ibuprofen"], "ar": ["إيبوبروفين", "ايبوبروفين"]},
    "penicillin": {"uk": ["пеніцилін"], "ru": ["пенициллин", "пенецилин"], "pl": ["penicylin"], "ro": ["penicilin"], "ar": ["بنسلين", "البنسلين"]},
    "amoxicillin": {"uk": ["амоксицилін"], "ru": ["амоксициллин"], "pl": ["amoksycylin"], "ro": ["amoxicilin"], "ar": ["أموكسيسيلين"]},
    "insulin": {"uk": ["інсулін"], "ru": ["инсулин"], "pl": ["insulin"], "ro": ["insulin"], "ar": ["أنسولين", "الأنسولين", "انسولين"]},
    "antibiotic": {"uk": ["антибіотик"], "ru": ["антибиотик"], "pl": ["antybiotyk"], "ro": ["antibiotic"], "ar": ["مضاد حيوي", "مضادات حيوية", "المضاد الحيوي"]},
    "allergy": {"uk": ["алерг"], "ru": ["аллерг"], "pl": ["alerg", "uczulen"], "ro": ["alergi", "alergic"], "ar": ["حساسية", "الحساسية"]},
    "allergic": {"uk": ["алерг"], "ru": ["аллерг"], "pl": ["alerg", "uczulon"], "ro": ["alergic"], "ar": ["حساسية"]},
    "blood test": {"uk": ["аналіз крові", "кров"], "ru": ["анализ крови", "кров"], "pl": ["krw", "krew"], "ro": ["sânge", "sange"], "ar": ["دم"]},
    "blood pressure": {"uk": ["тиск"], "ru": ["давлен"], "pl": ["ciśnieni"], "ro": ["tensiun"], "ar": ["ضغط الدم"]},
    "operation": {"uk": ["операці"], "ru": ["операци"], "pl": ["operacj", "zabieg"], "ro": ["operați", "operati", "intervenți"], "ar": ["عملية", "جراحة"]},
    "surgery": {"uk": ["операці", "хірург"], "ru": ["операци", "хирург"], "pl": ["operacj", "chirurg"], "ro": ["operați", "chirurg"], "ar": ["جراح", "عملية"]},
    "anaesthetic": {"uk": ["наркоз", "анестез", "знеболен"], "ru": ["наркоз", "анестез", "обезболи"], "pl": ["znieczul"], "ro": ["anestez"], "ar": ["تخدير", "مخدر"]},
    "x-ray": {"uk": ["рентген"], "ru": ["рентген"], "pl": ["rentgen", "prześwietl"], "ro": ["radiografi", "raze"], "ar": ["أشعة", "الأشعة"]},
    "pregnant": {"uk": ["вагітн"], "ru": ["беременн"], "pl": ["ciąż", "ciaz"], "ro": ["însărcinat", "insarcinat", "gravid"], "ar": ["حامل"]},
    "diabetes": {"uk": ["діабет"], "ru": ["диабет"], "pl": ["cukrzyc"], "ro": ["diabet"], "ar": ["السكري", "سكري"]},
    "asthma": {"uk": ["астм"], "ru": ["астм"], "pl": ["astm"], "ro": ["astm"], "ar": ["الربو", "ربو"]},
    "chest pain": {"uk": ["груд"], "ru": ["груд"], "pl": ["klatk", "piers"], "ro": ["piept"], "ar": ["الصدر", "صدر"]},
    "headache": {"uk": ["голов"], "ru": ["голов"], "pl": ["głow", "glow"], "ro": ["cap"], "ar": ["صداع", "الرأس"]},
    "vomit": {"uk": ["блю", "блював", "нудот"], "ru": ["рвот", "рвал", "тошн"], "pl": ["wymiot"], "ro": ["vărs", "vars", "vomit"], "ar": ["تقيؤ", "قيء", "تقيأ"]},
    "urinate": {"uk": ["сеч", "мочи"], "ru": ["моч"], "pl": ["mocz", "oddawa"], "ro": ["urin"], "ar": ["تبول", "البول"]},
    "fever": {"uk": ["температур", "гарячк"], "ru": ["температур", "жар", "лихорад"], "pl": ["gorącz", "temperatur"], "ro": ["febr"], "ar": ["حمى", "حرارة"]},
    "consent": {"uk": ["згод"], "ru": ["соглас"], "pl": ["zgod", "zgód"], "ro": ["consimț", "consimt", "acord"], "ar": ["موافقة", "الموافقة"]},
}
# Speech recognition sometimes misspells a medicine name or glues a preposition onto it ("напеніцелін",
# "паніцилін"). A near-miss of a known medicine is corrected before translation, so it cannot turn into an
# unrelated word (NLLB once rendered "паніцилін" as "pancakes").
MEDICINE_WORDS = {
    "uk": ["парацетамол", "ібупрофен", "пеніцилін", "амоксицилін", "інсулін", "аспірин"],
    "ru": ["парацетамол", "ибупрофен", "пенициллин", "амоксициллин", "инсулин", "аспирин"],
}
_GLUED = ("на", "від", "до", "от")


def _medicine_for(core: str, lang: str):
    """The medicine `core` is a misspelling of; '' when it is already correct (or inflected); None if no match."""
    for w in MEDICINE_WORDS[lang]:
        if core.startswith(w[:-1]):
            return ""
    best, score = None, 0.0
    for w in MEDICINE_WORDS[lang]:
        if abs(len(core) - len(w)) <= 3:
            r = difflib.SequenceMatcher(None, core, w).ratio()
            if r > score:
                best, score = w, r
    return best if score >= 0.75 else None


_ALLERGY_TO = {"uk": re.compile(r"(алергі\w*\s+на\s+)(\w+)", re.I), "ru": re.compile(r"(аллерги\w*\s+на\s+)(\w+)", re.I)}


def fix_medicine_words(text: str, lang: str):
    """Returns (text, fixes): near-misses of known medicine names replaced by the correct word."""
    if lang not in MEDICINE_WORDS or not text:
        return text, []
    fixes = []

    def allergen(m):   # right after "allergic to", a looser match is safe: "алергія на паніція" -> пеніцилін
        word = m.group(2)
        if _medicine_for(word.lower(), lang) == "":
            return m.group(0)
        best = max(MEDICINE_WORDS[lang], key=lambda w: difflib.SequenceMatcher(None, word.lower(), w).ratio())
        if difflib.SequenceMatcher(None, word.lower(), best).ratio() >= 0.6:
            fixes.append({"from": word, "to": best})
            return m.group(1) + best
        return m.group(0)

    text = _ALLERGY_TO[lang].sub(allergen, text)

    def repl(m):
        tok = m.group(0)
        low = tok.lower()
        if len(low) < 6:
            return tok
        hit = _medicine_for(low, lang)
        if hit == "":
            return tok
        for prep in _GLUED:   # a preposition glued on: "напеніцелін" -> "на пеніцилін"
            if low.startswith(prep) and len(low) - len(prep) >= 6:
                core = _medicine_for(low[len(prep):], lang)
                if core is not None:
                    new = f"{tok[:len(prep)]} {core or low[len(prep):]}"
                    fixes.append({"from": tok, "to": new})
                    return new
        if hit:
            fixes.append({"from": tok, "to": hit})
            return hit
        return tok

    return re.sub(r"\w+", repl, text), fixes


_GLOSSARY_RX = {term: re.compile(r"\b" + re.escape(term) + r"\w*", re.I) for term in GLOSSARY}


def glossary_checks(english: str, translation: str, lang: str):
    low = translation.lower()
    out = []
    for term, rx in _GLOSSARY_RX.items():
        if lang in GLOSSARY[term] and rx.search(english):
            ok = any(stem.lower() in low for stem in GLOSSARY[term][lang])
            out.append({"term": term, "ok": ok, "expected": GLOSSARY[term][lang][0]})
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


_EN_INDEX = {_norm(p["en"]): pid for pid, p in PHRASES.items()}


def match_phrase(english: str):
    return _EN_INDEX.get(_norm(english))


# Demo clips: a native Ukrainian voice saying the patient's lines (nobody on the team speaks
# Ukrainian; in the hospital the patient simply talks).
DEMO_CLIPS = [   # neural Ukrainian voice (Microsoft Polina); each clip checked end to end on the live server
    {"id": "uk2_help", "lang": "uk", "text": "Допоможіть, будь ласка. У мене дуже болить у грудях. У мене алергія на пеніцилін.",
     "en": "Help me, please. My chest hurts a lot. I'm allergic to penicillin."},
    {"id": "uk2_chest", "lang": "uk", "text": "У мене з ранку болить у грудях, і біль віддає в ліву руку.",
     "en": "My chest has hurt since this morning, and the pain goes into my left arm."},
    {"id": "uk2_stomach", "lang": "uk", "text": "Так, у мене болить живіт праворуч. Також у мене алергія на пеніцилін.",
     "en": "Yes, my stomach hurts on the right. I'm also allergic to penicillin."},
    {"id": "uk2_since", "lang": "uk", "text": "Біль почався вчора ввечері, приблизно о десятій.",
     "en": "The pain started last night, at about ten."},
    {"id": "uk2_breath", "lang": "uk", "text": "Мені дуже погано, мені важко дихати.",
     "en": "I feel very bad, it's hard for me to breathe."},
    {"id": "uk2_food", "lang": "uk", "text": "Ні, я нічого не їла і не пила з вечора.",
     "en": "No, I haven't eaten or drunk anything since the evening."},
]
