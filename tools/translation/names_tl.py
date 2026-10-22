# Shop names and star names (CSH tables). Keys are r{row}:c{col}.
_SHOPS = [
    "Store", "Store 0000", None, "Honoka Futaba Fan", "Man on the 8th Floor",
    "Man on the 8th Floor", "Calm Man", "Hinageshidai Station Kiosk", "Cafe Iberis",
    "Miyato Sky Tower Deck 1F Shop", "Clover - Northeast Sumire Store", None,
    "Clover - West Hananira Store", None,
]
STORE_TEXT = {f"r{i}:c0": s for i, s in enumerate(_SHOPS) if s}
STORE_TEXT.update({"r2:c0": "Clover - Aokiba Store",
                   "r11:c0": "Buyer: Choose What to Sell",
                   "r13:c0": "As the Savior, I Bestow My Belongings"})
STORE_DATA = {f"r{i}:c3": s for i, s in enumerate(_SHOPS) if s}
STORE_DATA.update({"r2:c3": "Clover - Azami Store",
                   "r11:c3": "Buyer: Choose What to Sell",
                   "r13:c3": "As the Savior..."})
# BrightStars: column 0 gets the English name already stored in column 1.
STARS_HEADER = {"r0:c0": "Name", "r0:c1": "English Name"}
