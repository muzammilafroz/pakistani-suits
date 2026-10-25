"""Colour names the seller wrote in titles, descriptions or image alt text.

Detecting colour from the photos was tried and dropped: studio backgrounds and heavy
embroidery made it wrong too often (a white suit read as brown, a black one as beige).
"""
import re

SWATCH = {
    "Black": "#151515", "Grey": "#8c8c8c", "Silver": "#c4c4c8", "White": "#f7f7f4",
    "Cream": "#efe4cc", "Beige": "#d6c1a1", "Brown": "#6e4529", "Mustard": "#d1a118",
    "Yellow": "#f1d33a", "Lemon": "#f3ec7a", "Gold": "#c39b3a", "Orange": "#ee8424",
    "Rust": "#b0461c", "Peach": "#f5b89a", "Coral": "#ee7468", "Red": "#c51f2e",
    "Maroon": "#7a1d2a", "Wine": "#56192c", "Baby Pink": "#f6c6d6", "Pink": "#ee93b5",
    "Rani Pink": "#d2276f", "Onion Pink": "#c98a95", "Lavender": "#b6a4d6", "Purple": "#6b2f8f",
    "Navy Blue": "#1f2a56", "Blue": "#2c4fb0", "Sky Blue": "#8ec3e8", "Firozi": "#2fb8bd",
    "Teal": "#11777c", "Mint Green": "#a9dcc1", "Pista Green": "#b5cd7b", "Olive": "#6c7a2c",
    "Green": "#2f8a3f", "Bottle Green": "#124d33", "Multi": "conic-gradient(#c51f2e,#f1d33a,#2f8a3f,#2c4fb0,#c51f2e)",
}

WORDS = {
    "black": "Black", "white": "White", "off white": "Cream", "off-white": "Cream", "cream": "Cream",
    "beige": "Beige", "grey": "Grey", "gray": "Grey", "silver": "Silver", "brown": "Brown",
    "coffee": "Brown", "mustard": "Mustard", "yellow": "Yellow", "lemon": "Lemon",
    "orange": "Orange", "rust": "Rust", "peach": "Peach", "coral": "Coral",
    "red": "Red", "maroon": "Maroon", "wine": "Wine", "baby pink": "Baby Pink", "pink": "Pink",
    "rani": "Rani Pink", "magenta": "Rani Pink", "onion": "Onion Pink", "lavender": "Lavender",
    "lilac": "Lavender", "purple": "Purple", "navy": "Navy Blue", "navy blue": "Navy Blue",
    "royal blue": "Blue", "blue": "Blue", "sky blue": "Sky Blue", "firozi": "Firozi",
    "turquoise": "Firozi", "teal": "Teal", "mint": "Mint Green", "mint green": "Mint Green",
    "pista": "Pista Green", "pista green": "Pista Green", "olive": "Olive", "mehndi": "Olive",
    "bottle green": "Bottle Green", "green": "Green", "multicolor": "Multi", "multicolour": "Multi",
    "multi color": "Multi", "multi colour": "Multi",
}
_WORD_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, WORDS), key=len, reverse=True)) + r")\b", re.I)


def text_colours(*texts):
    """Ordered unique colour names mentioned in the given texts."""
    found = []
    for t in texts:
        for m in _WORD_RE.finditer(t or ""):
            name = WORDS[m.group(1).lower()]
            if name not in found:
                found.append(name)
    return found


def swatches(names):
    return [{"name": n, "css": SWATCH[n]} for n in names]
