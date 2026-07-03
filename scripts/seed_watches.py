"""Seed the database with key watch references across Rolex, AP, Patek, Omega, and VC."""

import logging

from sqlalchemy import select

from watchscraper.analysis import _match_family
from watchscraper.catalog import ADDITIONAL_WATCHES, all_metadata
from watchscraper.database import get_session
from watchscraper.models import Brand, Source, Watch, WatchAlias, WatchNickname

logger = logging.getLogger(__name__)

BRANDS = [
    {"name": "Rolex", "slug": "rolex"},
    {"name": "Audemars Piguet", "slug": "audemars-piguet"},
    {"name": "Patek Philippe", "slug": "patek-philippe"},
    {"name": "Omega", "slug": "omega"},
    {"name": "Vacheron Constantin", "slug": "vacheron-constantin"},
    {"name": "IWC", "slug": "iwc"},
    {"name": "Jaeger-LeCoultre", "slug": "jaeger-lecoultre"},
    {"name": "A. Lange & Söhne", "slug": "a-lange-sohne"},
    {"name": "Cartier", "slug": "cartier"},
]

SOURCES = [
    {
        "name": "ebay",
        "base_url": "https://www.ebay.com",
        "scraper_type": "EbayScraper",
    },
    {
        "name": "chrono24",
        "base_url": "https://www.chrono24.com",
        "scraper_type": "Chrono24Scraper",
    },
    {
        "name": "watchcharts",
        "base_url": "https://watchcharts.com",
        "scraper_type": "WatchChartsScraper",
    },
    {
        "name": "hodinkee",
        "base_url": "https://shop.hodinkee.com",
        "scraper_type": "HodinkeeScraper",
    },
]

# ~60 key references: (brand_slug, ref, model_name, case_mm, material, dial, movement, retail_usd_cents)
WATCHES = [
    # === ROLEX ===
    # Submariner
    ("rolex", "124060", "Submariner No Date", 41, "Oystersteel", "Black", "3230", 890000),
    ("rolex", "126610LN", "Submariner Date", 41, "Oystersteel", "Black", "3235", 1015000),
    ("rolex", "126610LV", "Submariner Date Starbucks", 41, "Oystersteel", "Green", "3235", 1065000),
    ("rolex", "126613LB", "Submariner Date Two-Tone", 41, "Rolesor", "Blue", "3235", 1578000),
    ("rolex", "126619LB", "Submariner Date White Gold", 41, "White Gold", "Blue", "3235", 4145000),
    # Daytona
    ("rolex", "116500LN", "Cosmograph Daytona", 40, "Oystersteel", "White", "4130", 1515000),
    ("rolex", "126500LN", "Cosmograph Daytona", 40, "Oystersteel", "Black", "4131", 1560000),
    # GMT-Master II
    ("rolex", "126710BLNR", "GMT-Master II Batman", 40, "Oystersteel", "Black", "3285", 1105000),
    ("rolex", "126710BLRO", "GMT-Master II Pepsi", 40, "Oystersteel", "Black", "3285", 1105000),
    ("rolex", "126720VTNR", "GMT-Master II Sprite", 40, "Oystersteel", "Black", "3285", 1105000),
    # Datejust
    ("rolex", "126334", "Datejust 41 Fluted", 41, "Oystersteel/White Gold", "Blue", "3235", 1065000),
    ("rolex", "126300", "Datejust 41 Smooth", 41, "Oystersteel", "Blue", "3235", 835000),
    ("rolex", "126234", "Datejust 36 Fluted", 36, "Oystersteel/White Gold", "Blue", "3235", 1005000),
    # Explorer
    ("rolex", "124270", "Explorer", 36, "Oystersteel", "Black", "3230", 725000),
    ("rolex", "226570", "Explorer II", 42, "Oystersteel", "White", "3285", 965000),
    # Day-Date
    ("rolex", "228235", "Day-Date 40 Everose", 40, "Everose Gold", "Olive", "3255", 3875000),
    ("rolex", "228238", "Day-Date 40 Yellow Gold", 40, "Yellow Gold", "Champagne", "3255", 3855000),
    # Sky-Dweller
    ("rolex", "326934", "Sky-Dweller Steel/Gold", 42, "Oystersteel/White Gold", "Blue", "9001", 1660000),
    # Sea-Dweller
    ("rolex", "126600", "Sea-Dweller", 43, "Oystersteel", "Black", "3235", 1280000),
    ("rolex", "136660", "Deepsea", 44, "Oystersteel", "Black", "3235", 1390000),
    # Yacht-Master
    ("rolex", "226659", "Yacht-Master 42 White Gold", 42, "White Gold", "Black", "3235", 3155000),
    # Air-King
    ("rolex", "126900", "Air-King", 40, "Oystersteel", "Black", "3230", 810000),
    # OP
    ("rolex", "124300", "Oyster Perpetual 41", 41, "Oystersteel", "Green", "3230", 640000),
    # --- Older/Discontinued Rolex (high-volume in scraped data) ---
    # Old Submariner
    ("rolex", "116610LN", "Submariner Date (2010-2020)", 40, "Oystersteel", "Black", "3135", 925000),
    ("rolex", "116610LV", "Submariner Date Hulk (2010-2020)", 40, "Oystersteel", "Green", "3135", 925000),
    ("rolex", "16610", "Submariner Date (1988-2010)", 40, "Stainless Steel", "Black", "3135", 640000),
    ("rolex", "16613LB", "Submariner Date Two-Tone (1988-2009)", 40, "Rolesor", "Blue", "3135", 800000),
    ("rolex", "14060", "Submariner No Date (1989-2012)", 40, "Stainless Steel", "Black", "3130", 540000),
    # Old Daytona
    ("rolex", "116520", "Cosmograph Daytona (2000-2016)", 40, "Stainless Steel", "White", "4130", 1050000),
    ("rolex", "116523", "Cosmograph Daytona Two-Tone (2000-2016)", 40, "Rolesor", "White", "4130", 1350000),
    ("rolex", "116509", "Cosmograph Daytona White Gold", 40, "White Gold", "Silver", "4130", 3665000),
    ("rolex", "116515LN", "Cosmograph Daytona Everose", 40, "Everose Gold", "Pink", "4130", 3240000),
    ("rolex", "116508", "Cosmograph Daytona Yellow Gold", 40, "Yellow Gold", "Green", "4130", 3450000),
    ("rolex", "116505", "Cosmograph Daytona Everose Bracelet", 40, "Everose Gold", "Pink", "4130", 4250000),
    ("rolex", "116503", "Cosmograph Daytona Two-Tone (2016+)", 40, "Rolesor", "White", "4130", 1700000),
    # Old GMT-Master
    ("rolex", "116710LN", "GMT-Master II (2007-2019)", 40, "Oystersteel", "Black", "3186", 925000),
    ("rolex", "116710BLNR", "GMT-Master II Batman (2013-2019)", 40, "Oystersteel", "Black", "3186", 1005000),
    ("rolex", "126710GRNR", "GMT-Master II Sprite Grey/Black", 40, "Oystersteel", "Black", "3285", 1105000),
    ("rolex", "126710", "GMT-Master II", 40, "Oystersteel", "Black", "3285", 1105000),
    ("rolex", "126711CHNR", "GMT-Master II Root Beer", 40, "Everose/Steel", "Brown", "3285", 1650000),
    ("rolex", "126713GRNR", "GMT-Master II Two-Tone", 40, "Rolesor", "Black", "3285", 1560000),
    # Old Explorer
    ("rolex", "114270", "Explorer (2001-2010)", 36, "Stainless Steel", "Black", "3130", 540000),
    # Datejust variants
    ("rolex", "126333", "Datejust 41 Two-Tone Fluted", 41, "Rolesor", "Champagne", "3235", 1430000),
    ("rolex", "126331", "Datejust 41 Everose Fluted", 41, "Everose/Steel", "Chocolate", "3235", 1430000),
    ("rolex", "126200", "Datejust 36 Smooth", 36, "Oystersteel", "Blue", "3235", 735000),
    ("rolex", "126303", "Datejust 41 Two-Tone Smooth", 41, "Rolesor", "Silver", "3235", 1170000),
    ("rolex", "124273", "Datejust 36 Two-Tone", 36, "Rolesor", "Gold", "3235", 1355000),
    ("rolex", "116334", "Datejust II (2009-2017)", 41, "Oystersteel", "Blue", "3136", 870000),
    ("rolex", "116333", "Datejust II Two-Tone (2009-2017)", 41, "Rolesor", "Champagne", "3136", 1230000),
    ("rolex", "116300", "Datejust II Smooth (2009-2017)", 41, "Oystersteel", "Blue", "3136", 770000),
    ("rolex", "116613LB", "Submariner Date Two-Tone (2009-2020)", 40, "Rolesor", "Blue", "3135", 1405000),
    # Vintage/older Rolex 5-digit (high-volume in scraped data)
    ("rolex", "16570", "Explorer II (1991-2011)", 40, "Stainless Steel", "White", "3185", 570000),
    ("rolex", "16710", "GMT-Master II (1989-2007)", 40, "Stainless Steel", "Black", "3185", 570000),
    ("rolex", "16613", "Submariner Date Two-Tone (1988-2009)", 40, "Rolesor", "Blue", "3135", 800000),
    ("rolex", "14270", "Explorer (1991-2001)", 36, "Stainless Steel", "Black", "3000", 430000),
    ("rolex", "14060M", "Submariner No Date (2001-2012)", 40, "Stainless Steel", "Black", "3130", 580000),
    ("rolex", "16520", "Cosmograph Daytona (1988-2000)", 40, "Stainless Steel", "White", "4030", 850000),
    ("rolex", "16713", "GMT-Master II Two-Tone (1989-2007)", 40, "Rolesor", "Black", "3185", 750000),
    ("rolex", "16523", "Cosmograph Daytona Two-Tone (1988-2000)", 40, "Rolesor", "White", "4030", 1050000),
    ("rolex", "16700", "GMT-Master (1988-1999)", 40, "Stainless Steel", "Black", "3175", 500000),
    ("rolex", "16800", "Submariner Date (1979-1988)", 40, "Stainless Steel", "Black", "3035", 550000),
    ("rolex", "16750", "GMT-Master (1981-1988)", 40, "Stainless Steel", "Black", "3075", 500000),
    ("rolex", "16753", "GMT-Master Two-Tone (1981-1988)", 40, "Rolesor", "Black", "3075", 700000),
    ("rolex", "114060", "Submariner No Date (2012-2020)", 40, "Oystersteel", "Black", "3130", 765000),
    ("rolex", "126610", "Submariner Date", 41, "Oystersteel", "Black", "3235", 1015000),
    ("rolex", "126613LN", "Submariner Date Two-Tone", 41, "Rolesor", "Black", "3235", 1578000),
    ("rolex", "116518", "Cosmograph Daytona Yellow Gold Strap", 40, "Yellow Gold", "Champagne", "4130", 2760000),
    # Other older
    ("rolex", "116710", "GMT-Master II (2007-2019)", 40, "Oystersteel", "Black", "3186", 925000),
    ("rolex", "116713LN", "GMT-Master II Two-Tone (2007-2019)", 40, "Rolesor", "Black", "3186", 1370000),
    ("rolex", "126503", "Cosmograph Daytona Two-Tone (2023+)", 40, "Rolesor", "White", "4131", 1700000),
    ("rolex", "126509", "Cosmograph Daytona White Gold (2023+)", 40, "White Gold", "Black", "4131", 3910000),

    # === AUDEMARS PIGUET ===
    # Royal Oak
    ("audemars-piguet", "15500ST", "Royal Oak Selfwinding", 41, "Stainless Steel", "Blue", "4302", 2730000),
    ("audemars-piguet", "15202ST", "Royal Oak Jumbo Extra-Thin", 39, "Stainless Steel", "Blue", "2121", 3100000),  # Discontinued — last MSRP
    ("audemars-piguet", "15510ST", "Royal Oak Selfwinding", 41, "Stainless Steel", "Blue", "4302", 2730000),
    ("audemars-piguet", "15550ST", "Royal Oak Jumbo Extra-Thin", 39, "Stainless Steel", "Blue", "7121", 3400000),
    ("audemars-piguet", "15400ST", "Royal Oak Selfwinding", 41, "Stainless Steel", "Blue", "3120", 2190000),  # Discontinued 2019 — last MSRP
    ("audemars-piguet", "15300ST", "Royal Oak Selfwinding", 39, "Stainless Steel", "Blue", "3120", 1740000),  # Discontinued ~2012 — last MSRP
    ("audemars-piguet", "15202IP", "Royal Oak Jumbo Extra-Thin", 39, "Titanium/Platinum", "Blue", "2121", 4660000),  # Limited edition
    # Royal Oak Chronograph
    ("audemars-piguet", "26331ST", "Royal Oak Chronograph", 41, "Stainless Steel", "Blue", "2385", 3360000),
    ("audemars-piguet", "26240ST", "Royal Oak Chronograph", 41, "Stainless Steel", "Blue", "4401", 4100000),
    # Royal Oak Offshore
    ("audemars-piguet", "26470ST", "Royal Oak Offshore Chronograph", 42, "Stainless Steel", "Black", "3126/3840", 2950000),  # Discontinued ~2020 — last MSRP
    ("audemars-piguet", "26238ST", "Royal Oak Offshore Chronograph", 42, "Stainless Steel", "Black", "4404", 4400000),
    ("audemars-piguet", "15710ST", "Royal Oak Offshore Diver", 42, "Stainless Steel", "Blue", "3120", 2910000),
    # Code 11.59
    ("audemars-piguet", "15210CR", "Code 11.59 Selfwinding", 41, "Pink Gold/Ceramic", "Blue", "4302", 3180000),

    # === PATEK PHILIPPE ===
    # Nautilus
    ("patek-philippe", "5711/1A", "Nautilus", 40, "Stainless Steel", "Blue", "26‑330 S C", 3041000),  # Discontinued 2021 — last MSRP
    ("patek-philippe", "5811/1G", "Nautilus", 41, "White Gold", "Blue", "26‑330 S C", 5240000),
    ("patek-philippe", "5712/1A", "Nautilus Power Reserve", 40, "Stainless Steel", "Blue", "240 PS IRM C LU", 3535000),  # Discontinued ~2021 — last MSRP
    ("patek-philippe", "5726/1A", "Nautilus Annual Calendar", 40.5, "Stainless Steel", "Blue", "324 S QA LU 24H", 4407000),  # Last MSRP
    ("patek-philippe", "5980/1A", "Nautilus Chronograph", 40.5, "Stainless Steel", "Blue", "CH 28‑520 C", 5760000),  # Discontinued — last MSRP
    ("patek-philippe", "5990/1A", "Nautilus Travel Time Chronograph", 40.5, "Stainless Steel", "Blue", "CH 28‑520 C FUS", 7269000),  # Last MSRP
    # Aquanaut
    ("patek-philippe", "5167A", "Aquanaut", 40, "Stainless Steel", "Black", "324 S C", 2143000),  # Discontinued ~2021 — last MSRP
    ("patek-philippe", "5168G", "Aquanaut", 42.2, "White Gold", "Blue", "324 S C", 5190000),
    ("patek-philippe", "5267/200A", "Aquanaut Luce", 35.6, "Stainless Steel", "Green", "324 S C", 2910000),
    # Calatrava
    ("patek-philippe", "5196G", "Calatrava", 37, "White Gold", "Silver", "215 PS", 2670000),
    ("patek-philippe", "5227G", "Calatrava", 39, "White Gold", "White", "324 S C", 3650000),
    # Complications
    ("patek-philippe", "5205G", "Annual Calendar", 40, "White Gold", "Blue", "324 S QA LU 24H", 5060000),
    ("patek-philippe", "5230G", "World Time", 38.5, "White Gold", "Blue", "240 HU", 5520000),
    ("patek-philippe", "5270P", "Perpetual Calendar Chronograph", 41, "Platinum", "Blue", "CH 29‑535 PS Q", 17590000),
    # Tiffany
    ("patek-philippe", "5711/1A-018", "Nautilus Tiffany Blue", 40, "Stainless Steel", "Tiffany Blue", "26‑330 S C", 5271000),  # Special edition — Tiffany & Co.
    # Grand Complications
    ("patek-philippe", "5320G", "Perpetual Calendar", 40, "White Gold", "Cream", "324 S Q", 9660000),
    ("patek-philippe", "5236P", "In-Line Perpetual Calendar", 41.3, "Platinum", "Blue", "31‑260 PS QL", 10020000),
    # Chronograph
    ("patek-philippe", "5172G", "Chronograph", 41, "White Gold", "Blue", "CH 29‑535 PS", 6810000),

    # === OMEGA ===
    # Speedmaster
    ("omega", "310.30.42.50.01.001", "Speedmaster Moonwatch Professional", 42, "Stainless Steel", "Black", "3861", 695000),
    ("omega", "310.30.42.50.01.002", "Speedmaster Moonwatch Professional Sapphire", 42, "Stainless Steel", "Black", "3861", 735000),
    ("omega", "310.32.42.50.01.002", "Speedmaster Moonwatch Professional Hesalite", 42, "Stainless Steel", "Black", "3861", 695000),
    ("omega", "310.60.42.50.01.001", "Speedmaster Moonwatch Canopus Gold", 42, "Canopus Gold", "Black", "3861", 3600000),
    ("omega", "329.30.44.51.01.001", "Speedmaster Racing Chronograph", 44.25, "Stainless Steel", "Black", "9900", 805000),
    ("omega", "304.30.44.52.01.001", "Speedmaster Dark Side of the Moon", 44.25, "Black Ceramic", "Black", "9300", 1250000),
    # Seamaster 300M
    ("omega", "210.30.42.20.01.001", "Seamaster Diver 300M", 42, "Stainless Steel", "Black", "8800", 575000),
    ("omega", "210.30.42.20.03.001", "Seamaster Diver 300M", 42, "Stainless Steel", "Blue", "8800", 575000),
    ("omega", "210.30.42.20.06.001", "Seamaster Diver 300M", 42, "Stainless Steel", "Grey", "8800", 575000),
    ("omega", "210.22.42.20.01.004", "Seamaster Diver 300M Two-Tone", 42, "Steel/Sedna Gold", "Black", "8800", 1020000),
    ("omega", "210.90.42.20.01.001", "Seamaster Diver 300M Titanium", 42, "Titanium", "Black", "8806", 775000),
    # Seamaster Planet Ocean
    ("omega", "215.30.44.21.01.001", "Seamaster Planet Ocean 600M", 43.5, "Stainless Steel", "Black", "8900", 735000),
    # Seamaster Aqua Terra
    ("omega", "220.10.41.21.01.001", "Seamaster Aqua Terra 150M", 41, "Stainless Steel", "Black", "8900", 600000),
    ("omega", "220.10.41.21.03.001", "Seamaster Aqua Terra 150M", 41, "Stainless Steel", "Blue", "8900", 600000),
    ("omega", "220.10.41.21.06.001", "Seamaster Aqua Terra 150M", 41, "Stainless Steel", "Grey", "8900", 600000),
    # Constellation
    ("omega", "131.10.41.21.01.001", "Constellation Co-Axial Master", 41, "Stainless Steel", "Black", "8900", 625000),
    # De Ville
    ("omega", "434.13.41.21.03.001", "De Ville Prestige Co-Axial", 41, "Stainless Steel", "Blue", "8900", 475000),
    # Moonwatch Snoopy
    ("omega", "310.32.42.50.02.001", "Speedmaster Silver Snoopy Award 50th Anniversary", 42, "Stainless Steel", "Silver/Blue", "3861", 1110000),
    # Ultra Deep
    ("omega", "215.30.46.21.01.001", "Seamaster Planet Ocean Ultra Deep", 45.5, "Stainless Steel", "Black", "8912", 1310000),
    # --- Older/additional Omega refs from scraped data ---
    ("omega", "145.022", "Speedmaster Professional (Vintage 1969-1997)", 42, "Stainless Steel", "Black", "861", 205000),  # Last MSRP ~$2,050 in late 1990s
    ("omega", "212.30.41.20.03.001", "Seamaster Diver 300M (Previous Gen)", 41, "Stainless Steel", "Blue", "2500", 475000),
    ("omega", "212.30.41.20.01.003", "Seamaster Diver 300M (Previous Gen)", 41, "Stainless Steel", "Black", "2500", 475000),
    ("omega", "215.30.44.21.03.001", "Seamaster Planet Ocean 600M Blue", 43.5, "Stainless Steel", "Blue", "8900", 735000),
    ("omega", "215.30.44.21.01.002", "Seamaster Planet Ocean 600M GMT", 43.5, "Stainless Steel", "Black", "8906", 785000),
    ("omega", "215.92.40.20.01.001", "Seamaster Planet Ocean Ultra Deep", 39.5, "Titanium", "Black", "8912", 1050000),
    ("omega", "210.32.42.20.01.001", "Seamaster Diver 300M Rubber", 42, "Stainless Steel", "Black", "8800", 575000),
    ("omega", "210.32.42.20.04.001", "Seamaster Diver 300M White Rubber", 42, "Stainless Steel", "White", "8800", 575000),
    ("omega", "210.30.42.20.04.001", "Seamaster Diver 300M White", 42, "Stainless Steel", "White", "8800", 575000),
    ("omega", "210.30.42.20.10.001", "Seamaster Diver 300M Green", 42, "Stainless Steel", "Green", "8800", 575000),
    ("omega", "232.30.42.21.01.001", "Seamaster Planet Ocean 600M (Previous Gen)", 42, "Stainless Steel", "Black", "8500", 630000),
    ("omega", "232.30.42.21.01.002", "Seamaster Planet Ocean 600M (Previous Gen)", 42, "Stainless Steel", "Black", "8500", 630000),
    ("omega", "326.30.40.50.01.002", "Speedmaster Racing Chronograph", 40, "Stainless Steel", "Black", "3330", 540000),
    ("omega", "310.30.42.50.04.001", "Speedmaster Moonwatch White Dial", 42, "Stainless Steel", "White", "3861", 735000),
    ("omega", "310.30.42.50.01.004", "Speedmaster Moonwatch Green", 42, "Stainless Steel", "Green", "3861", 735000),

    # === VACHERON CONSTANTIN ===
    # Overseas
    ("vacheron-constantin", "4500V/110A-B128", "Overseas Automatic", 41, "Stainless Steel", "Blue", "5100", 2850000),
    ("vacheron-constantin", "4500V/110A-B483", "Overseas Automatic", 41, "Stainless Steel", "Black", "5100", 2850000),
    ("vacheron-constantin", "4500V/110A-B126", "Overseas Automatic", 41, "Stainless Steel", "Silver", "5100", 2850000),
    ("vacheron-constantin", "47040/000A-9008", "Overseas Chronograph", 42.5, "Stainless Steel", "Blue", "5200", 3550000),
    ("vacheron-constantin", "2300V/100A-B170", "Overseas Dual Time", 41, "Stainless Steel", "Blue", "5110 DT", 3600000),
    ("vacheron-constantin", "4000E/000A-B548", "Overseas Ultra-Thin Perpetual Calendar", 41.5, "Stainless Steel", "Blue", "1120 QP", 8400000),  # Last MSRP
    # Patrimony
    ("vacheron-constantin", "81180/000G-9117", "Patrimony Contemporaine", 40, "White Gold", "Silver", "2450 Q6", 2200000),
    ("vacheron-constantin", "85180/000G-9230", "Patrimony Manual-Winding", 40, "White Gold", "Silver", "1400", 2040000),
    ("vacheron-constantin", "43175/000R-9687", "Patrimony Retrograde Day-Date", 42.5, "Rose Gold", "Silver", "2460 R31R7", 4380000),
    # Traditionnelle
    ("vacheron-constantin", "82172/000G-9383", "Traditionnelle Manual-Winding", 38, "White Gold", "Silver", "4400 AS", 2300000),
    ("vacheron-constantin", "87172/000G-9301", "Traditionnelle Complete Calendar", 41, "White Gold", "Blue", "2460 QCL", 5590000),
    ("vacheron-constantin", "57260/000G-B046", "Traditionnelle Tourbillon", 41, "White Gold", "Silver", "2160", 14850000),  # Last MSRP
    # Fiftysix
    ("vacheron-constantin", "4600E/000A-B487", "Fiftysix Automatic", 40, "Stainless Steel", "Blue", "1326", 1350000),
    ("vacheron-constantin", "4000E/000A-B439", "Fiftysix Complete Calendar", 40, "Stainless Steel", "Blue", "2460 QCL", 2500000),
    # Historiques
    ("vacheron-constantin", "1110S/000A-B075", "Historiques American 1921", 40, "Stainless Steel", "White", "4400 AS", 2900000),
    ("vacheron-constantin", "86020/000G-9508", "Historiques Triple Calendrier 1948", 40, "White Gold", "Silver", "2460 QCL", 4550000),

    # === IWC ===
    # Portugieser
    ("iwc", "IW371605", "Portugieser Chronograph", 41, "Stainless Steel", "Blue", "69355", 945000),
    ("iwc", "IW371615", "Portugieser Chronograph", 41, "Stainless Steel", "Silver", "69355", 945000),
    ("iwc", "IW500710", "Portugieser Automatic", 42.3, "Stainless Steel", "Blue", "52010", 1240000),
    ("iwc", "IW344205", "Portugieser Perpetual Calendar", 44.2, "Stainless Steel", "Blue", "52615", 2650000),
    # Pilot
    ("iwc", "IW388101", "Pilot's Watch Chronograph 41", 41, "Stainless Steel", "Blue", "69385", 710000),
    ("iwc", "IW388103", "Pilot's Watch Chronograph 41", 41, "Stainless Steel", "Green", "69385", 710000),
    ("iwc", "IW329303", "Big Pilot's Watch 43", 43, "Stainless Steel", "Blue", "82100", 1100000),
    ("iwc", "IW501001", "Big Pilot's Watch", 46.2, "Stainless Steel", "Black", "52110", 1595000),
    ("iwc", "IW328201", "Pilot's Mark XX", 40, "Stainless Steel", "Blue", "32111", 550000),
    ("iwc", "IW377709", "Pilot's Chronograph Spitfire", 41, "Stainless Steel", "Green", "69380", 565000),  # Discontinued — last MSRP
    # Aquatimer
    ("iwc", "IW329005", "Aquatimer Automatic", 42, "Stainless Steel", "Blue", "32111", 680000),
    # --- Additional IWC refs from scraped data ---
    ("iwc", "IW377714", "Pilot's Chronograph Le Petit Prince", 43, "Stainless Steel", "Blue", "79320", 645000),
    ("iwc", "IW325501", "Pilot's Mark XVI", 39, "Stainless Steel", "Black", "30110", 430000),
    ("iwc", "IW376705", "Portugieser Chronograph Classic", 42, "Rose Gold", "Silver", "79350", 1490000),
    ("iwc", "IW328202", "Pilot's Mark XX", 40, "Stainless Steel", "Green", "32111", 550000),
    ("iwc", "IW327010", "Pilot's Automatic 36", 36, "Stainless Steel", "Blue", "32111", 480000),
    ("iwc", "IW327006", "Pilot's Mark XVIII", 40, "Stainless Steel", "Blue", "35111", 510000),
    ("iwc", "IW500401", "Big Pilot's Watch (Previous Gen)", 46.2, "Stainless Steel", "Black", "51111", 1350000),
    ("iwc", "IW329301", "Big Pilot's Watch 43", 43, "Stainless Steel", "Black", "82100", 1100000),
    ("iwc", "IW326501", "Pilot's Watch Automatic 36", 36, "Stainless Steel", "Blue", "35111", 480000),
    ("iwc", "IW371445", "Portugieser Chronograph", 40.9, "Stainless Steel", "White", "79350", 870000),
    ("iwc", "IW327004", "Pilot's Mark XVIII Le Petit Prince", 40, "Stainless Steel", "Blue", "35111", 510000),

    # === JAEGER-LECOULTRE ===
    # Reverso
    ("jaeger-lecoultre", "Q3858520", "Reverso Classic Medium Thin", 40.1, "Stainless Steel", "Silver", "822/2", 720000),
    ("jaeger-lecoultre", "Q2438520", "Reverso Classic Large", 45.6, "Stainless Steel", "Silver", "822/2", 755000),
    ("jaeger-lecoultre", "Q3848420", "Reverso Tribute Monoface", 45.6, "Stainless Steel", "Blue", "822/2", 900000),
    ("jaeger-lecoultre", "Q3918420", "Reverso Tribute Duoface", 47, "Stainless Steel", "Blue/Silver", "854A/2", 1250000),
    ("jaeger-lecoultre", "Q7168431", "Reverso Tribute Calendar", 49.4, "Rose Gold", "Silver", "853A/2", 2200000),
    # Master
    ("jaeger-lecoultre", "Q1548420", "Master Ultra Thin Moon", 39, "Stainless Steel", "Blue", "925/1", 1050000),
    ("jaeger-lecoultre", "Q1368420", "Master Control Calendar", 40, "Stainless Steel", "Blue", "866AA/2", 1100000),
    ("jaeger-lecoultre", "Q1358480", "Master Control Chronograph", 40, "Stainless Steel", "Blue", "759AA/2", 1300000),
    # Polaris
    ("jaeger-lecoultre", "Q9068670", "Polaris Automatic", 41, "Stainless Steel", "Blue", "899AC/1", 950000),
    ("jaeger-lecoultre", "Q9028480", "Polaris Chronograph", 42, "Stainless Steel", "Blue", "751H/2", 1390000),
    # Atmos
    ("jaeger-lecoultre", "Q5102208", "Atmos Classique", None, "Glass/Brass", "White", "Atmos", 1050000),
    # --- Additional JLC refs ---
    ("jaeger-lecoultre", "Q3752520", "Reverso Classic Large Duoface", 47, "Stainless Steel", "Silver/Black", "854A/2", 1100000),
    ("jaeger-lecoultre", "Q1558420", "Master Ultra Thin Perpetual", 39, "Stainless Steel", "Blue", "868/2", 1850000),

    # === A. LANGE & SÖHNE ===
    # Lange 1
    ("a-lange-sohne", "191.032", "Lange 1", 38.5, "Rose Gold", "Silver", "L121.1", 3680000),
    ("a-lange-sohne", "191.039", "Lange 1", 38.5, "White Gold", "Blue", "L121.1", 4350000),
    ("a-lange-sohne", "192.032", "Lange 1 Daymatic", 39.5, "Rose Gold", "Silver", "L021.1", 4040000),
    ("a-lange-sohne", "720.025", "Lange 1 Moon Phase", 38.5, "Rose Gold", "Silver", "L121.3", 5050000),
    # Saxonia
    ("a-lange-sohne", "380.032", "Saxonia Thin", 40, "Rose Gold", "Silver", "L093.1", 2020000),
    ("a-lange-sohne", "381.031", "Saxonia", 38.5, "Rose Gold", "Silver", "L941.1", 1860000),
    ("a-lange-sohne", "386.032", "Saxonia Moon Phase", 40, "Rose Gold", "Silver", "L086.5", 3120000),
    # 1815
    ("a-lange-sohne", "235.032", "1815 Up/Down", 39, "Rose Gold", "Silver", "L051.3", 2960000),
    ("a-lange-sohne", "414.028", "1815 Chronograph", 39.5, "Rose Gold", "Silver", "L951.5", 5100000),
    # Datograph
    ("a-lange-sohne", "403.035", "Datograph Up/Down", 41, "Rose Gold", "Silver", "L951.6", 8600000),
    ("a-lange-sohne", "405.031", "Datograph Perpetual", 41, "Rose Gold", "Silver", "L952.1", 13050000),
    # Odysseus
    ("a-lange-sohne", "363.179", "Odysseus", 40.5, "Stainless Steel", "Grey", "L155.1", 3560000),
    # Zeitwerk
    ("a-lange-sohne", "140.029", "Zeitwerk", 41.9, "White Gold", "Silver", "L043.1", 9600000),

    # === CARTIER ===
    # Santos
    ("cartier", "WSSA0018", "Santos de Cartier Medium", 35.1, "Stainless Steel", "Silver", "1847 MC", 760000),
    ("cartier", "WSSA0029", "Santos de Cartier Large", 39.8, "Stainless Steel", "Silver", "1847 MC", 825000),
    ("cartier", "WSSA0030", "Santos de Cartier Large Blue", 39.8, "Stainless Steel", "Blue", "1847 MC", 825000),
    ("cartier", "W2SA0016", "Santos de Cartier Two-Tone Large", 39.8, "Steel/Yellow Gold", "Silver", "1847 MC", 1220000),
    # Tank
    ("cartier", "WSTA0065", "Tank Must Large", 33.7, "Stainless Steel", "Silver", "1847 MC", 390000),
    ("cartier", "WSTA0041", "Tank Française Medium", 32, "Stainless Steel", "Silver", "1847 MC", 460000),
    ("cartier", "WGTA0108", "Tank Louis Cartier Large", 33.7, "Rose Gold", "Silver", "1917 MC", 1430000),
    ("cartier", "CRWSTA0016", "Tank Américaine Medium", 34.8, "Stainless Steel", "Silver", "1847 MC", 650000),
    # Ballon Bleu
    ("cartier", "WSBB0046", "Ballon Bleu 40mm", 40, "Stainless Steel", "Silver", "1847 MC", 740000),
    ("cartier", "WSBB0025", "Ballon Bleu 36mm", 36, "Stainless Steel", "Silver", "076", 590000),
    # Pasha
    ("cartier", "WSPA0013", "Pasha de Cartier 41mm", 41, "Stainless Steel", "Blue", "1847 MC", 865000),
    # Panthère
    ("cartier", "WSPN0007", "Panthère de Cartier Medium", 27, "Stainless Steel", "Silver", "Quartz", 440000),
    # Drive
    ("cartier", "CRWSNM0015", "Drive de Cartier", 40, "Stainless Steel", "Silver", "1847 MC", 680000),
    # --- Additional Cartier refs ---
    ("cartier", "WSSA0062", "Santos de Cartier Large Green", 39.8, "Stainless Steel", "Green", "1847 MC", 825000),
    ("cartier", "WSSA0039", "Santos de Cartier Large Grey", 39.8, "Stainless Steel", "Grey", "1847 MC", 825000),
    ("cartier", "WSSA0009", "Santos de Cartier Large", 39.8, "Stainless Steel", "White", "1847 MC", 825000),

    # --- Additional Omega refs (unmatched in scraped data) ---
    ("omega", "210.32.42.20.10.001", "Seamaster Diver 300M Green Rubber", 42, "Stainless Steel", "Green", "8800", 575000),
    ("omega", "210.30.42.20.03.002", "Seamaster Diver 300M Blue (Summer)", 42, "Stainless Steel", "Blue", "8800", 575000),
    ("omega", "232.30.46.21.01.003", "Seamaster Planet Ocean 600M 45.5mm", 45.5, "Stainless Steel", "Black", "8500", 680000),
    ("omega", "310.30.40.50.06.001", "Speedmaster Moonwatch 38.6mm Grey", 38.6, "Stainless Steel", "Grey", "3861", 695000),
    ("omega", "233.30.41.21.01.001", "Seamaster 300 Master Co-Axial", 41, "Stainless Steel", "Black", "8400", 630000),
    ("omega", "231.10.42.21.03.003", "Seamaster Aqua Terra 150M (Previous Gen)", 41.5, "Stainless Steel", "Blue", "8500", 570000),

    # --- Additional AP refs ---
    ("audemars-piguet", "15710ST", "Royal Oak Offshore Diver (Previous)", 42, "Stainless Steel", "Blue", "3120", 2910000),
    ("audemars-piguet", "26420SO", "Royal Oak Offshore Chronograph (Camo)", 43, "Steel/Ceramic", "Green", "4401", 4750000),

    # --- Additional Cartier refs (unmatched) ---
    ("cartier", "WSSA0037", "Santos de Cartier Large Skeleton", 39.8, "Stainless Steel", "Skeleton", "1847 MC", 965000),
    ("cartier", "WSSA0061", "Santos de Cartier Large Black", 39.8, "Stainless Steel", "Black", "1847 MC", 825000),
    ("cartier", "WSPA0026", "Pasha de Cartier 41mm Skeleton", 41, "Stainless Steel", "Skeleton", "9624 MC", 1040000),

    # --- Additional Vacheron refs ---
    ("vacheron-constantin", "4600E/000A-B442", "Fiftysix Automatic", 40, "Stainless Steel", "Grey", "1326", 1350000),
    ("vacheron-constantin", "4600E/110A-B487", "Fiftysix Automatic Bracelet", 40, "Stainless Steel", "Blue", "1326", 1350000),
    ("vacheron-constantin", "4400E/000A-B437", "Fiftysix Complete Calendar", 40, "Stainless Steel", "Grey", "2460 QCL", 2500000),

    # --- Additional Lange refs ---
    ("a-lange-sohne", "234.032", "1815 Manual-Winding", 38.5, "Rose Gold", "Silver", "L051.1", 2310000),
    ("a-lange-sohne", "403.032", "Datograph Up/Down", 41, "Rose Gold", "Grey", "L951.6", 8600000),
    ("a-lange-sohne", "405.035", "Datograph Perpetual", 41, "Rose Gold", "Grey", "L952.1", 13050000),

    # === GEMINI CURATED ADDITIONS ===

    # --- Rolex: Daytona Oysterflex + Platinum, Day-Date Platinum, Sky-Dweller new gen ---
    ("rolex", "126515LN", "Cosmograph Daytona Everose Oysterflex", 40, "Everose Gold", "Sundust", "4131", 3700000),
    ("rolex", "126519LN", "Cosmograph Daytona White Gold Oysterflex", 40, "White Gold", "Grey", "4131", 3910000),
    ("rolex", "126518LN", "Cosmograph Daytona Yellow Gold Oysterflex", 40, "Yellow Gold", "Golden", "4131", 3520000),
    ("rolex", "126506", "Cosmograph Daytona Platinum", 40, "Platinum", "Ice Blue", "4131", 8215000),
    ("rolex", "228206", "Day-Date 40 Platinum", 40, "Platinum", "Ice Blue", "3255", 6120000),
    ("rolex", "336934", "Sky-Dweller Steel/White Gold", 42, "Oystersteel/White Gold", "Blue", "9002", 1755000),

    # --- Audemars Piguet: Jumbo 16202, Rose Gold variants, Complications ---
    ("audemars-piguet", "16202ST", "Royal Oak Jumbo Extra-Thin", 39, "Stainless Steel", "Blue", "7121", 3700000),
    ("audemars-piguet", "16202OR", "Royal Oak Jumbo Extra-Thin", 39, "Rose Gold", "Smoke Grey", "7121", 5700000),
    ("audemars-piguet", "15510OR", "Royal Oak Selfwinding", 41, "Rose Gold", "Black", "4302", 4520000),
    ("audemars-piguet", "26240OR", "Royal Oak Chronograph", 41, "Rose Gold", "Black", "4401", 5950000),
    ("audemars-piguet", "26574ST", "Royal Oak Perpetual Calendar", 41, "Stainless Steel", "Blue", "5134", 8950000),
    ("audemars-piguet", "26579CE", "Royal Oak Perpetual Calendar", 41, "Black Ceramic", "Blue", "5134", 11000000),
    ("audemars-piguet", "26585CE", "Royal Oak Perpetual Calendar Openworked", 41, "Black Ceramic", "Skeleton", "5135", 13500000),
    ("audemars-piguet", "15407ST", "Royal Oak Double Balance Wheel Openworked", 41, "Stainless Steel", "Skeleton", "3132", 5550000),
    ("audemars-piguet", "15407OR", "Royal Oak Double Balance Wheel Openworked", 41, "Rose Gold", "Skeleton", "3132", 7300000),

    # --- Patek Philippe: Nautilus complications, Aquanaut variants, World Time, Grand Complications ---
    ("patek-philippe", "5712R", "Nautilus Power Reserve", 40, "Rose Gold", "Brown", "240 PS IRM C LU", 5530000),
    ("patek-philippe", "5980/1R", "Nautilus Chronograph", 40.5, "Rose Gold", "Blue", "CH 28‑520 C", 8830000),
    ("patek-philippe", "5740/1G", "Nautilus Perpetual Calendar", 40, "White Gold", "Blue", "240 Q", 10200000),
    ("patek-philippe", "5167R", "Aquanaut", 40, "Rose Gold", "Brown", "324 S C", 3640000),
    ("patek-philippe", "5164A", "Aquanaut Travel Time", 40.8, "Stainless Steel", "Black", "324 S C FUS", 4700000),
    ("patek-philippe", "5968A", "Aquanaut Chronograph", 42.2, "Stainless Steel", "Blue", "CH 28‑520 C", 6950000),
    ("patek-philippe", "5261R", "Aquanaut Luce Annual Calendar", 38.8, "Rose Gold", "Brown", "324 S QA LU", 7310000),
    ("patek-philippe", "5327G", "Perpetual Calendar", 39, "White Gold", "Blue", "324 S Q", 8800000),
    ("patek-philippe", "5230P", "World Time", 38.5, "Platinum", "Blue", "240 HU", 6250000),
    ("patek-philippe", "5231J", "World Time Cloisonné", 38.5, "Yellow Gold", "Enamel", "240 HU", 7590000),
    ("patek-philippe", "5231G", "World Time Cloisonné", 38.5, "White Gold", "Enamel", "240 HU", 7590000),
    ("patek-philippe", "5930P", "World Time Chronograph", 39.5, "Platinum", "Green", "CH 28‑520 HU", 9250000),
    ("patek-philippe", "5531R", "World Time Minute Repeater", 40.2, "Rose Gold", "Enamel", "R 27 HU", 56100000),
    ("patek-philippe", "5326G", "Annual Calendar Travel Time", 41, "White Gold", "Grey", "31‑260 PS QA LU", 6520000),

    # --- A. Lange & Söhne: Zeitwerk variants, Lange 1 complications ---
    ("a-lange-sohne", "148.038", "Zeitwerk Date", 44.2, "White Gold", "Grey", "L043.8", 11500000),
    ("a-lange-sohne", "142.031", "Zeitwerk Luminous", 41.9, "White Gold", "Phantom", "L043.2", 10200000),
    ("a-lange-sohne", "116.032", "Lange 1 Time Zone", 41.9, "Rose Gold", "Silver", "L031.1", 5200000),
    ("a-lange-sohne", "139.032", "Lange 1 Moon Phase", 38.5, "Rose Gold", "Silver", "L121.3", 5050000),

    # --- Vacheron Constantin: new Overseas refs ---
    ("vacheron-constantin", "4520V/110A-B128", "Overseas Self-Winding", 41, "Stainless Steel", "Blue", "5100/1", 3100000),
    ("vacheron-constantin", "4520V/110R-B705", "Overseas Self-Winding", 41, "Rose Gold", "Green", "5100/1", 5400000),
    ("vacheron-constantin", "7920V/110A-B334", "Overseas Dual Time", 41, "Stainless Steel", "Blue", "5110 DT/2", 4100000),
    ("vacheron-constantin", "5520V/110A-B148", "Overseas Chronograph", 42.5, "Stainless Steel", "Blue", "5200/2", 3950000),
    ("vacheron-constantin", "4300V/120G-B945", "Overseas Perpetual Calendar Ultra-Thin", 41.5, "White Gold", "Skeleton", "1120 QPSQ", 13500000),
    ("vacheron-constantin", "6000V/110A-B544", "Overseas Tourbillon", 42.5, "Stainless Steel", "Blue", "2160", 14500000),
]

ALIASES = {
    "126610LN": ["126610 LN", "Sub Date Black"],
    "126610LV": ["126610 LV", "Sub Date Green", "Starbucks"],
    "126710BLNR": ["126710 BLNR", "Batman", "GMT Batman"],
    "126710BLRO": ["126710 BLRO", "Pepsi", "GMT Pepsi"],
    "116500LN": ["116500 LN", "Daytona Ceramic White", "Panda Daytona"],
    "126500LN": ["126500 LN", "Daytona Ceramic 2023"],
    "5711/1A": ["5711/1A-010", "5711/1A-014", "Nautilus Steel Blue"],
    "5811/1G": ["5811/1G-001"],
    "5167A": ["5167A-001"],
    "15500ST": ["15500ST.OO.1220ST.01", "RO 41mm Blue"],
    "15202ST": ["15202ST.OO.1240ST.01", "Jumbo"],
    "15510ST": ["15510ST.OO.1320ST.01"],
    # Omega
    "310.30.42.50.01.001": ["Speedmaster Professional", "Moonwatch Hesalite"],
    "310.32.42.50.02.001": ["Snoopy", "Silver Snoopy", "Speedmaster Snoopy"],
    "210.30.42.20.03.001": ["Seamaster 300M Blue", "SMP Blue"],
    "210.30.42.20.01.001": ["Seamaster 300M Black", "SMP Black"],
    # Vacheron Constantin
    "4500V/110A-B128": ["Overseas Blue", "VC Overseas 4500V"],
    "4500V/110A-B483": ["Overseas Black"],
    # IWC
    "IW371605": ["Portugieser Chrono Blue"],
    "IW329303": ["Big Pilot 43"],
    "IW328201": ["Mark XX", "Pilot Mark 20"],
    # JLC
    "Q3848420": ["Reverso Tribute Blue"],
    "Q1548420": ["Master Ultra Thin Moon Blue", "MUT Moon"],
    # A. Lange & Söhne
    "191.032": ["Lange 1 Rose Gold"],
    "403.035": ["Datograph Up/Down Rose Gold"],
    "363.179": ["Odysseus Steel"],
    # Cartier
    "WSSA0029": ["Santos Large Steel"],
    "WSSA0030": ["Santos Large Blue"],
    "WSTA0065": ["Tank Must Large"],
    # Gemini curated — AP long-form aliases
    "16202ST": ["16202ST.OO.1240ST.02"],
    "16202OR": ["16202OR.OO.1240OR.02"],
    "15510OR": ["15510OR.OO.1320OR.04"],
    "26240OR": ["26240OR.OO.1320OR.02"],
    "26574ST": ["26574ST.OO.1220ST.03"],
    "26579CE": ["26579CE.OO.1225CE.01"],
    "26585CE": ["26585CE.OO.1225CE.01"],
    "15407ST": ["15407ST.OO.1220ST.01"],
    "15407OR": ["15407OR.OO.1220OR.01"],
    # Gemini curated — Patek suffix aliases
    "5712R": ["5712R-001"],
    "5980/1R": ["5980/1R-001"],
    "5740/1G": ["5740/1G-001"],
    "5167R": ["5167R-001"],
    "5164A": ["5164A-001"],
    "5968A": ["5968A-001"],
    "5261R": ["5261R-001"],
    "5327G": ["5327G-001"],
    "5230P": ["5230P-001"],
    "5231J": ["5231J-001"],
    "5231G": ["5231G-001"],
    "5930P": ["5930P-001"],
    "5531R": ["5531R-012"],
    "5326G": ["5326G-001"],
}


def run_seed() -> None:
    session = get_session()
    try:
        # Brands
        brand_map: dict[str, int] = {}
        for b in BRANDS:
            existing = session.execute(
                select(Brand).where(Brand.slug == b["slug"])
            ).scalar_one_or_none()
            if existing:
                brand_map[b["slug"]] = existing.id
            else:
                brand = Brand(**b)
                session.add(brand)
                session.flush()
                brand_map[b["slug"]] = brand.id
                logger.info("Added brand: %s", b["name"])

        # Sources
        for s in SOURCES:
            existing = session.execute(
                select(Source).where(Source.name == s["name"])
            ).scalar_one_or_none()
            if not existing:
                session.add(Source(**s, is_active=True))
                logger.info("Added source: %s", s["name"])

        # Watches
        watch_map: dict[str, int] = {}
        for brand_slug, ref, model, size, material, dial, mvmt, retail in WATCHES:
            brand_id = brand_map[brand_slug]
            existing = session.execute(
                select(Watch).where(
                    Watch.brand_id == brand_id,
                    Watch.reference_number == ref,
                )
            ).scalar_one_or_none()

            if existing:
                watch_map[ref] = existing.id
                # Update retail price if it was previously NULL
                if existing.retail_price_usd is None and retail is not None:
                    existing.retail_price_usd = retail
                    logger.info("Updated retail price for %s %s: $%.2f", brand_slug, ref, retail / 100)
            else:
                watch = Watch(
                    brand_id=brand_id,
                    reference_number=ref,
                    model_name=model,
                    case_size_mm=size,
                    case_material=material,
                    dial_color=dial,
                    movement=mvmt,
                    retail_price_usd=retail,
                )
                session.add(watch)
                session.flush()
                watch_map[ref] = watch.id
                logger.info("Added watch: %s %s", brand_slug, ref)

        # Additional references introduced by the reference-centric catalog
        for brand_slug, ref, model, size, material, dial, mvmt, retail in ADDITIONAL_WATCHES:
            brand_id = brand_map[brand_slug]
            existing = session.execute(
                select(Watch).where(
                    Watch.brand_id == brand_id,
                    Watch.reference_number == ref,
                )
            ).scalar_one_or_none()
            if existing:
                watch_map[ref] = existing.id
            else:
                watch = Watch(
                    brand_id=brand_id,
                    reference_number=ref,
                    model_name=model,
                    case_size_mm=size,
                    case_material=material,
                    dial_color=dial,
                    movement=mvmt,
                    retail_price_usd=retail,
                )
                session.add(watch)
                session.flush()
                watch_map[ref] = watch.id
                logger.info("Added watch: %s %s", brand_slug, ref)

        # Reference-centric metadata: production windows, families, variants
        metadata = all_metadata()
        slug_by_brand_id = {v: k for k, v in brand_map.items()}
        all_watches = session.execute(select(Watch)).scalars().all()
        curated = derived = 0
        for w in all_watches:
            brand_slug = slug_by_brand_id.get(w.brand_id)
            meta = metadata.get((brand_slug, w.reference_number))
            if meta:
                w.family = meta.family
                w.production_start_year = meta.start
                w.production_end_year = meta.end
                if meta.bezel:
                    w.bezel = meta.bezel
                if meta.bracelet:
                    w.bracelet = meta.bracelet
                if meta.has_date is not None:
                    w.has_date = meta.has_date
                curated += 1
            if not w.family:
                # Derive the collection name from the model name
                _, family = _match_family(w.model_name or "")
                if family:
                    w.family = family
                    derived += 1
        logger.info("Metadata applied: %d curated, %d families derived", curated, derived)

        # Nicknames (many references may share one nickname)
        nickname_count = 0
        for w in all_watches:
            brand_slug = slug_by_brand_id.get(w.brand_id)
            meta = metadata.get((brand_slug, w.reference_number))
            if not meta or not meta.nicknames:
                continue
            for nick in meta.nicknames:
                existing = session.execute(
                    select(WatchNickname).where(
                        WatchNickname.watch_id == w.id,
                        WatchNickname.nickname == nick,
                    )
                ).scalar_one_or_none()
                if not existing:
                    session.add(WatchNickname(watch_id=w.id, nickname=nick))
                    nickname_count += 1
        logger.info("Nicknames added: %d", nickname_count)

        # Aliases
        for canonical_ref, alias_list in ALIASES.items():
            watch_id = watch_map.get(canonical_ref)
            if not watch_id:
                continue
            for alias_str in alias_list:
                existing = session.execute(
                    select(WatchAlias).where(WatchAlias.alias == alias_str)
                ).scalar_one_or_none()
                if not existing:
                    session.add(WatchAlias(watch_id=watch_id, alias=alias_str))

        session.commit()
        logger.info(
            "Seed complete: %d brands, %d watches",
            len(brand_map),
            len(watch_map),
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()
