from __future__ import annotations


CATEGORY_BY_SHEET = {
    "Аксессуары Apple": "Accessory",
    "AirPods": "AirPods",
    "Apple Watch": "Apple Watch",
    "iPhone": "iPhone",
    "iPad": "iPad",
    "MacBook": "MacBook",
    "iMac": "iMac",
}


CATEGORY_KEYWORDS = {
    "iPhone": ["iphone", "айфон"],
    "iPad": ["ipad", "айпад"],
    "MacBook": ["macbook"],
    "iMac": ["imac"],
    "Apple Watch": ["apple watch", "watch", "series", "ultra", "se"],
    "AirPods": ["airpods"],
    "Accessory": [
        "magic keyboard",
        "keyboard",
        "pencil",
        "mouse",
        "trackpad",
        "adapter",
        "airtag",
        "magsafe",
        "case",
        "folio",
        "smart keyboard",
    ],
}


COLOR_ALIASES = {
    "black": ["space black", "black titanium", "black", "midnight", "черный", "чёрный"],
    "white": ["white titanium", "white", "starlight", "белый"],
    "silver": ["silver", "space gray", "space grey", "серебро", "серый"],
    "gold": ["gold", "золотой"],
    "pink": ["pink", "розовый"],
    "blue": ["blue titanium", "sky blue", "blue", "синий"],
    "green": ["green", "зеленый", "зелёный"],
    "purple": ["purple", "фиолетовый"],
    "yellow": ["yellow", "желтый", "жёлтый"],
    "red": ["red", "красный"],
    "orange": ["orange", "оранжевый"],
    "natural titanium": ["natural titanium", "natural"],
    "desert titanium": ["desert titanium"],
}


CONNECTIVITY_ALIASES = {
    "wifi": ["wi-fi", "wifi", "wi fi", "w-fi", "wireless"],
    "cellular": [
        "lte",
        "cellular",
        "sim",
        "5g",
        "4g",
        "wifi + cellular",
        "wi-fi + cellular",
        "wi-fi+cellular",
        "wifi+cellular",
    ],
    "gps": ["gps"],
    "gps+cellular": ["gps+cellular", "gps + cellular"],
}


ACCESSORY_KEYWORDS = {
    "magic keyboard": "Magic Keyboard",
    "apple pencil": "Apple Pencil",
    "pencil": "Apple Pencil",
    "magic mouse": "Magic Mouse",
    "mouse": "Magic Mouse",
    "magic trackpad": "Magic Trackpad",
    "trackpad": "Magic Trackpad",
    "airtag": "AirTag",
    "magsafe": "MagSafe",
}


STOPWORDS = {
    "apple",
    "new",
    "gb",
    "tb",
    "wifi",
    "cellular",
    "lte",
}
