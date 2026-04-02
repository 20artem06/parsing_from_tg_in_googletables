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
    "Mac": ["mac mini"],
    "MacBook": ["macbook"],
    "iMac": ["imac"],
    "Apple Watch": ["apple watch", "watch", "series", "ultra", "se"],
    "AirPods": ["airpods"],
    "Accessory": [
        "apple tv",
        "magic keyboard",
        "usb-c cable",
        "keyboard",
        "pencil",
        "mouse",
        "trackpad",
        "power adapter",
        "adapter",
        "airtag",
        "magsafe",
        "case",
        "folio",
        "smart keyboard",
    ],
}


COLOR_ALIASES = {
    "black titanium": ["black titanium", "black ti"],
    "white titanium": ["white titanium"],
    "blue titanium": ["blue titanium"],
    "natural titanium": ["natural titanium", "natural ti", "natural"],
    "desert titanium": ["desert titanium", "desert"],
    "space black": ["space black"],
    "space gray": ["space gray", "space grey"],
    "midnight": ["midnight"],
    "starlight": ["starlight"],
    "rose gold": ["rose gold"],
    "black": ["black", "черный", "чёрный"],
    "white": ["white", "белый"],
    "silver": ["silver", "серебро", "серый"],
    "gold": ["gold", "золотой"],
    "pink": ["pink", "розовый"],
    "blue": ["sky blue", "blue", "синий"],
    "green": ["green", "зеленый", "зелёный"],
    "purple": ["purple", "фиолетовый"],
    "purple fog": ["purple fog"],
    "yellow": ["yellow", "желтый", "жёлтый"],
    "red": ["red", "красный"],
    "orange": ["orange", "оранжевый"],
    "slate": ["slate"],
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
    "apple tv": "Apple TV",
    "magic keyboard": "Magic Keyboard",
    "apple pencil": "Apple Pencil",
    "pencil": "Apple Pencil",
    "magic mouse": "Magic Mouse",
    "mouse": "Magic Mouse",
    "magic trackpad": "Magic Trackpad",
    "trackpad": "Magic Trackpad",
    "power adapter": "Power Adapter",
    "usb-c cable": "USB-C Cable",
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
