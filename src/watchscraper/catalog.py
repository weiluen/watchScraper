"""Curated per-reference metadata: production windows, nicknames, variants.

This is the knowledge base the matching rules engine runs on. Three rules
govern the data:

  1. One reference number = one watch. Variant attributes (dial, material,
     bezel, bracelet) belong to the reference.
  2. Nicknames are many-to-many: "Batman" is 116710BLNR (2013-2019) AND
     126710BLNR (2019+). The matcher disambiguates by production window
     against the listing's stated year.
  3. Production windows are inclusive years; end=None means still in
     production. Windows are the primary consistency check: a "2023"
     listing cannot be a reference discontinued in 2010.

Windows are approximate at the ±1-year level (transition years overlap in
the wild: dealer stock, late serials), which is why the matcher applies
tolerance rather than knife-edge cutoffs.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RefMeta:
    family: str | None = None
    start: int | None = None
    end: int | None = None  # None = current production
    nicknames: tuple[str, ...] = ()
    bezel: str | None = None
    bracelet: str | None = None
    has_date: bool | None = None


@dataclass(frozen=True)
class DialVariant:
    """A dial variant of a reference — its own watch with its own value.

    match_terms are additional dial words in listings that mean this dial
    ("gold dial" on a yellow-gold Daytona means champagne). aliases are
    full reference strings that pin the variant exactly (Patek encodes the
    dial in the dash suffix: 5711/1A-014 IS the green dial).
    """

    dial: str
    nicknames: tuple[str, ...] = ()
    match_terms: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


# Keyed by (brand_slug, reference_number)
REF_METADATA: dict[tuple[str, str], RefMeta] = {
    # ══ ROLEX — Submariner ══
    ("rolex", "124060"): RefMeta("Submariner", 2020, None, (), "Black", "Oyster", False),
    ("rolex", "126610LN"): RefMeta("Submariner", 2020, None, (), "Black", "Oyster", True),
    ("rolex", "126610LV"): RefMeta("Submariner", 2020, None, ("Starbucks", "Cermit"), "Green", "Oyster", True),
    ("rolex", "126613LB"): RefMeta("Submariner", 2020, None, ("Bluesy",), "Blue", "Oyster", True),
    ("rolex", "126613LN"): RefMeta("Submariner", 2020, None, (), "Black", "Oyster", True),
    ("rolex", "126619LB"): RefMeta("Submariner", 2020, None, ("Cookie Monster",), "Blue", "Oyster", True),
    ("rolex", "116610LN"): RefMeta("Submariner", 2010, 2020, (), "Black", "Oyster", True),
    ("rolex", "116610LV"): RefMeta("Submariner", 2010, 2020, ("Hulk",), "Green", "Oyster", True),
    ("rolex", "116613LB"): RefMeta("Submariner", 2009, 2020, ("Bluesy",), "Blue", "Oyster", True),
    ("rolex", "16610"): RefMeta("Submariner", 1988, 2010, (), "Black", "Oyster", True),
    ("rolex", "16610LV"): RefMeta("Submariner", 2003, 2010, ("Kermit",), "Green", "Oyster", True),
    ("rolex", "16613"): RefMeta("Submariner", 1988, 2009, ("Bluesy",), None, "Oyster", True),
    ("rolex", "16613LB"): RefMeta("Submariner", 1988, 2009, ("Bluesy",), "Blue", "Oyster", True),
    ("rolex", "16800"): RefMeta("Submariner", 1979, 1988, (), "Black", "Oyster", True),
    ("rolex", "14060"): RefMeta("Submariner", 1990, 2001, (), "Black", "Oyster", False),
    ("rolex", "14060M"): RefMeta("Submariner", 2001, 2012, (), "Black", "Oyster", False),
    ("rolex", "114060"): RefMeta("Submariner", 2012, 2020, (), "Black", "Oyster", False),

    # ══ ROLEX — Daytona ══
    ("rolex", "116500LN"): RefMeta("Daytona", 2016, 2023, (), "Black", "Oyster", False),
    ("rolex", "126500LN"): RefMeta("Daytona", 2023, None, (), "Black", "Oyster", False),
    ("rolex", "116520"): RefMeta("Daytona", 2000, 2016, (), "Steel", "Oyster", False),
    ("rolex", "16520"): RefMeta("Daytona", 1988, 2000, ("Zenith Daytona",), "Steel", "Oyster", False),
    ("rolex", "116523"): RefMeta("Daytona", 2000, 2016, (), None, "Oyster", False),
    ("rolex", "16523"): RefMeta("Daytona", 1988, 2000, ("Zenith Daytona",), None, "Oyster", False),
    ("rolex", "116503"): RefMeta("Daytona", 2016, 2023, (), None, "Oyster", False),
    ("rolex", "126503"): RefMeta("Daytona", 2023, None, (), None, "Oyster", False),
    ("rolex", "116508"): RefMeta("Daytona", 2016, 2023, (), None, "Oyster", False),
    ("rolex", "116509"): RefMeta("Daytona", 2004, 2023, (), None, "Oyster", False),
    ("rolex", "116505"): RefMeta("Daytona", 2008, 2023, (), None, "Oyster", False),
    ("rolex", "116515LN"): RefMeta("Daytona", 2011, 2023, (), "Black", "Oysterflex", False),
    ("rolex", "116518"): RefMeta("Daytona", 1999, 2016, (), None, None, False),
    ("rolex", "126506"): RefMeta("Daytona", 2023, None, ("Le Mans" ,), "Brown", "Oyster", False),
    ("rolex", "126515LN"): RefMeta("Daytona", 2023, None, (), "Black", "Oysterflex", False),
    ("rolex", "126518LN"): RefMeta("Daytona", 2023, None, (), "Black", "Oysterflex", False),
    ("rolex", "126519LN"): RefMeta("Daytona", 2023, None, (), "Black", "Oysterflex", False),
    ("rolex", "126509"): RefMeta("Daytona", 2023, None, (), "Black", "Oyster", False),

    # ══ ROLEX — GMT-Master (II) ══
    ("rolex", "126710BLNR"): RefMeta("GMT-Master II", 2019, None, ("Batman", "Batgirl"), "Blue/Black", "Jubilee/Oyster", True),
    ("rolex", "126710BLRO"): RefMeta("GMT-Master II", 2018, None, ("Pepsi",), "Red/Blue", "Jubilee/Oyster", True),
    ("rolex", "126720VTNR"): RefMeta("GMT-Master II", 2022, None, ("Sprite", "Lefty"), "Green/Black", "Oyster/Jubilee", True),
    ("rolex", "126710GRNR"): RefMeta("GMT-Master II", 2024, None, ("Bruce Wayne",), "Grey/Black", "Oyster/Jubilee", True),
    ("rolex", "126711CHNR"): RefMeta("GMT-Master II", 2018, None, ("Root Beer",), "Brown/Black", "Oyster", True),
    ("rolex", "126713GRNR"): RefMeta("GMT-Master II", 2023, None, (), "Grey/Black", "Jubilee", True),
    ("rolex", "116710LN"): RefMeta("GMT-Master II", 2007, 2019, (), "Black", "Oyster", True),
    ("rolex", "116710BLNR"): RefMeta("GMT-Master II", 2013, 2019, ("Batman",), "Blue/Black", "Oyster", True),
    ("rolex", "116713LN"): RefMeta("GMT-Master II", 2007, 2019, (), "Black", "Oyster", True),
    ("rolex", "16710"): RefMeta("GMT-Master II", 1989, 2007, ("Pepsi", "Coke"), None, "Oyster/Jubilee", True),
    ("rolex", "16700"): RefMeta("GMT-Master", 1988, 1999, ("Pepsi",), None, "Oyster/Jubilee", True),
    ("rolex", "16750"): RefMeta("GMT-Master", 1981, 1988, ("Pepsi",), None, "Oyster/Jubilee", True),
    ("rolex", "1675"): RefMeta("GMT-Master", 1959, 1980, ("Pepsi",), None, "Oyster/Jubilee", True),
    ("rolex", "16753"): RefMeta("GMT-Master", 1981, 1988, ("Root Beer",), "Brown/Gold", "Oyster/Jubilee", True),
    ("rolex", "16713"): RefMeta("GMT-Master II", 1989, 2007, ("Root Beer",), "Brown/Gold", "Oyster/Jubilee", True),
    ("rolex", "116710"): RefMeta("GMT-Master II", 2007, 2019, (), None, "Oyster", True),
    ("rolex", "126710"): RefMeta("GMT-Master II", 2018, None, (), None, None, True),

    # ══ ROLEX — Datejust ══
    ("rolex", "126334"): RefMeta("Datejust", 2017, None, (), "Fluted", "Jubilee/Oyster", True),
    ("rolex", "126300"): RefMeta("Datejust", 2017, None, (), "Smooth", "Jubilee/Oyster", True),
    ("rolex", "126303"): RefMeta("Datejust", 2017, None, (), "Smooth", "Jubilee/Oyster", True),
    ("rolex", "126333"): RefMeta("Datejust", 2017, None, (), "Fluted", "Jubilee/Oyster", True),
    ("rolex", "126331"): RefMeta("Datejust", 2017, None, (), "Fluted", "Jubilee/Oyster", True),
    ("rolex", "126234"): RefMeta("Datejust", 2018, None, (), "Fluted", "Jubilee/Oyster", True),
    ("rolex", "126200"): RefMeta("Datejust", 2018, None, (), "Smooth", "Jubilee/Oyster", True),
    ("rolex", "116334"): RefMeta("Datejust", 2009, 2017, (), "Fluted", "Oyster", True),
    ("rolex", "116333"): RefMeta("Datejust", 2009, 2017, (), "Fluted", "Oyster", True),
    ("rolex", "116300"): RefMeta("Datejust", 2009, 2017, (), "Smooth", "Oyster", True),

    # ══ ROLEX — Explorer / others ══
    ("rolex", "124270"): RefMeta("Explorer", 2021, None, (), None, "Oyster", False),
    ("rolex", "226570"): RefMeta("Explorer", 2021, None, ("Polar",), None, "Oyster", True),
    ("rolex", "114270"): RefMeta("Explorer", 2001, 2010, (), None, "Oyster", False),
    ("rolex", "14270"): RefMeta("Explorer", 1990, 2001, (), None, "Oyster", False),
    ("rolex", "16570"): RefMeta("Explorer", 1991, 2011, ("Polar",), None, "Oyster", True),
    ("rolex", "228235"): RefMeta("Day-Date", 2015, None, (), "Fluted", "President", True),
    ("rolex", "228238"): RefMeta("Day-Date", 2015, None, (), "Fluted", "President", True),
    ("rolex", "228206"): RefMeta("Day-Date", 2015, None, (), "Smooth", "President", True),
    ("rolex", "326934"): RefMeta("Sky-Dweller", 2017, 2021, (), "Fluted", "Oyster/Jubilee", True),
    ("rolex", "336934"): RefMeta("Sky-Dweller", 2021, None, (), "Fluted", "Oyster/Jubilee", True),
    ("rolex", "126600"): RefMeta("Sea-Dweller", 2017, None, (), "Black", "Oyster", True),
    ("rolex", "136660"): RefMeta("Deepsea", 2022, None, (), "Black", "Oyster", True),
    ("rolex", "226659"): RefMeta("Yacht-Master", 2019, None, (), "Black", "Oysterflex", True),
    ("rolex", "126900"): RefMeta("Air-King", 2022, None, (), None, "Oyster", False),
    ("rolex", "124300"): RefMeta("Oyster Perpetual", 2020, None, (), "Smooth", "Oyster", False),

    # ══ AUDEMARS PIGUET ══
    ("audemars-piguet", "15202ST"): RefMeta("Royal Oak", 2012, 2021, ("Jumbo",), None, "Integrated", True),
    ("audemars-piguet", "16202ST"): RefMeta("Royal Oak", 2022, None, ("Jumbo",), None, "Integrated", True),
    ("audemars-piguet", "16202OR"): RefMeta("Royal Oak", 2022, None, ("Jumbo",), None, "Integrated", True),
    ("audemars-piguet", "15500ST"): RefMeta("Royal Oak", 2019, 2022, (), None, "Integrated", True),
    ("audemars-piguet", "15510ST"): RefMeta("Royal Oak", 2022, None, (), None, "Integrated", True),
    ("audemars-piguet", "15400ST"): RefMeta("Royal Oak", 2012, 2019, (), None, "Integrated", True),
    ("audemars-piguet", "15300ST"): RefMeta("Royal Oak", 2005, 2012, (), None, "Integrated", True),
    ("audemars-piguet", "26470ST"): RefMeta("Royal Oak Offshore", 2014, 2021, (), None, "Integrated", True),
    ("audemars-piguet", "15710ST"): RefMeta("Royal Oak Offshore", 2010, 2021, (), None, "Integrated", True),
    ("audemars-piguet", "26331ST"): RefMeta("Royal Oak", 2017, None, (), None, "Integrated", False),
    ("audemars-piguet", "26240ST"): RefMeta("Royal Oak", 2021, None, (), None, "Integrated", True),

    # ══ PATEK PHILIPPE ══
    ("patek-philippe", "5711/1A"): RefMeta("Nautilus", 2006, 2021, (), None, "Integrated", True),
    ("patek-philippe", "5711/1A-018"): RefMeta("Nautilus", 2021, 2021, ("Tiffany",), None, "Integrated", True),
    ("patek-philippe", "5811/1G"): RefMeta("Nautilus", 2022, None, (), None, "Integrated", True),
    ("patek-philippe", "5712/1A"): RefMeta("Nautilus", 2006, 2022, (), None, "Integrated", True),
    ("patek-philippe", "5726/1A"): RefMeta("Nautilus", 2010, 2022, (), None, "Integrated", True),
    ("patek-philippe", "5980/1A"): RefMeta("Nautilus", 2006, 2014, (), None, "Integrated", True),
    ("patek-philippe", "5990/1A"): RefMeta("Nautilus", 2014, 2021, (), None, "Integrated", True),
    ("patek-philippe", "5167A"): RefMeta("Aquanaut", 2007, 2022, (), None, "Rubber", True),
    ("patek-philippe", "5168G"): RefMeta("Aquanaut", 2017, None, (), None, "Rubber", True),
    ("patek-philippe", "5164A"): RefMeta("Aquanaut", 2011, None, (), None, "Rubber", True),
    ("patek-philippe", "5968A"): RefMeta("Aquanaut", 2018, None, (), None, "Rubber", False),

    # ══ OMEGA ══
    ("omega", "310.30.42.50.01.001"): RefMeta("Speedmaster", 2021, None, (), None, "Bracelet", False),
    ("omega", "310.30.42.50.01.002"): RefMeta("Speedmaster", 2021, None, (), None, "Bracelet", False),
    ("omega", "310.32.42.50.01.002"): RefMeta("Speedmaster", 2021, None, (), None, "Strap", False),
    ("omega", "310.32.42.50.02.001"): RefMeta("Speedmaster", 2020, None, ("Snoopy", "Silver Snoopy"), None, "Strap", False),
    ("omega", "304.30.44.52.01.001"): RefMeta("Speedmaster", 2013, None, ("Dark Side of the Moon", "DSOTM"), None, "Strap", True),
    ("omega", "145.022"): RefMeta("Speedmaster", 1968, 1988, (), None, "Bracelet", False),
    ("omega", "210.30.42.20.01.001"): RefMeta("Seamaster 300M", 2018, None, (), "Black", "Bracelet", True),
    ("omega", "210.30.42.20.03.001"): RefMeta("Seamaster 300M", 2018, None, (), "Blue", "Bracelet", True),
    ("omega", "210.30.42.20.06.001"): RefMeta("Seamaster 300M", 2018, None, (), "Grey", "Bracelet", True),
    ("omega", "210.90.42.20.01.001"): RefMeta("Seamaster 300M", 2019, None, ("No Time To Die", "NTTD"), None, "Mesh", False),
    ("omega", "212.30.41.20.03.001"): RefMeta("Seamaster 300M", 2005, 2018, (), "Blue", "Bracelet", True),
    ("omega", "212.30.41.20.01.003"): RefMeta("Seamaster 300M", 2005, 2018, (), "Black", "Bracelet", True),
    ("omega", "215.30.44.21.01.001"): RefMeta("Planet Ocean", 2016, None, (), "Black", "Bracelet", True),
    ("omega", "232.30.42.21.01.001"): RefMeta("Planet Ocean", 2011, 2016, (), "Black", "Bracelet", True),
    ("omega", "220.10.41.21.01.001"): RefMeta("Aqua Terra", 2017, None, (), None, "Bracelet", True),
    ("omega", "220.10.41.21.03.001"): RefMeta("Aqua Terra", 2017, None, (), None, "Bracelet", True),
    ("omega", "231.10.42.21.03.003"): RefMeta("Aqua Terra", 2011, 2017, (), None, "Bracelet", True),

    # ══ CARTIER ══
    ("cartier", "WSSA0018"): RefMeta("Santos", 2018, None, (), None, "Bracelet", True),
    ("cartier", "WSSA0029"): RefMeta("Santos", 2018, None, (), None, "Bracelet", True),
    ("cartier", "WSSA0030"): RefMeta("Santos", 2021, None, (), None, "Bracelet", True),
    ("cartier", "WSSA0009"): RefMeta("Santos", 2018, None, (), None, "Bracelet", True),
    ("cartier", "WSTA0065"): RefMeta("Tank", 2021, None, (), None, "Strap", False),
    ("cartier", "WSPA0013"): RefMeta("Pasha", 2020, None, (), None, "Bracelet", True),

    # ══ IWC ══
    ("iwc", "IW328201"): RefMeta("Pilot Mark", 2022, None, ("Mark XX",), None, None, True),
    ("iwc", "IW328202"): RefMeta("Pilot Mark", 2022, None, ("Mark XX",), None, None, True),
    ("iwc", "IW327006"): RefMeta("Pilot Mark", 2016, 2022, ("Mark XVIII",), None, None, True),
    ("iwc", "IW327004"): RefMeta("Pilot Mark", 2016, 2022, ("Mark XVIII", "Le Petit Prince"), None, None, True),
    ("iwc", "IW325501"): RefMeta("Pilot Mark", 2006, 2016, ("Mark XVI",), None, None, True),
    ("iwc", "IW329303"): RefMeta("Big Pilot", 2021, None, (), None, None, False),
    ("iwc", "IW329301"): RefMeta("Big Pilot", 2021, None, (), None, None, False),
    ("iwc", "IW501001"): RefMeta("Big Pilot", 2016, 2021, (), None, None, True),
    ("iwc", "IW500710"): RefMeta("Portugieser", 2015, None, (), None, None, True),
    ("iwc", "IW371605"): RefMeta("Portugieser", 2020, None, (), None, None, False),
    ("iwc", "IW371615"): RefMeta("Portugieser", 2020, None, (), None, None, False),

    # ══ JAEGER-LECOULTRE ══
    ("jaeger-lecoultre", "Q3858520"): RefMeta("Reverso", 2016, None, (), None, "Strap", False),
    ("jaeger-lecoultre", "Q3848420"): RefMeta("Reverso", 2021, None, (), None, "Strap", False),
    ("jaeger-lecoultre", "Q1548420"): RefMeta("Master Ultra Thin", 2019, None, ("MUT Moon",), None, "Strap", True),
    ("jaeger-lecoultre", "Q9068670"): RefMeta("Polaris", 2021, None, (), None, None, False),

    # ══ A. LANGE & SÖHNE ══
    ("a-lange-sohne", "191.032"): RefMeta("Lange 1", 2015, None, (), None, "Strap", True),
    ("a-lange-sohne", "191.039"): RefMeta("Lange 1", 2015, None, (), None, "Strap", True),
    ("a-lange-sohne", "363.179"): RefMeta("Odysseus", 2019, None, (), None, "Bracelet", True),

    # ══ VACHERON CONSTANTIN ══
    ("vacheron-constantin", "4500V/110A-B128"): RefMeta("Overseas", 2016, 2024, (), None, "Integrated", True),
    ("vacheron-constantin", "4500V/110A-B483"): RefMeta("Overseas", 2016, 2024, (), None, "Integrated", True),
    ("vacheron-constantin", "4520V/110A-B128"): RefMeta("Overseas", 2024, None, (), None, "Integrated", True),
    ("vacheron-constantin", "5520V/110A-B148"): RefMeta("Overseas", 2024, None, (), None, "Integrated", True),
    ("vacheron-constantin", "47040/000A-9008"): RefMeta("Overseas", 2004, 2016, (), None, "Integrated", True),
}

# New references introduced by the reference-centric model (nickname anchors
# that were missing from the original seed).
# (brand_slug, ref, model_name, case_mm, material, dial, movement, retail_cents)
ADDITIONAL_WATCHES: list[tuple] = [
    ("rolex", "16610LV", "Submariner Date Kermit (2003-2010)", 40, "Stainless Steel", "Black", "3135", 715000),
    ("rolex", "116619LB", "Submariner Date Smurf (2008-2020)", 40, "White Gold", "Blue", "3135", 3935000),
    ("rolex", "1675", "GMT-Master (1959-1980)", 40, "Stainless Steel", "Black", "1575", None),
    ("omega", "311.30.42.30.01.005", "Speedmaster Moonwatch Professional (2014-2021)", 42, "Stainless Steel", "Black", "1861", 532500),
]

ADDITIONAL_METADATA: dict[tuple[str, str], RefMeta] = {
    ("rolex", "16610LV"): RefMeta("Submariner", 2003, 2010, ("Kermit",), "Green", "Oyster", True),
    ("rolex", "116619LB"): RefMeta("Submariner", 2008, 2020, ("Smurf",), "Blue", "Oyster", True),
    ("omega", "311.30.42.30.01.005"): RefMeta("Speedmaster", 2014, 2021, (), None, "Bracelet", False),
}


# ── Dial variants ─────────────────────────────────────────────────────────
# Only for references where the short ref hides dial variety AND the dial
# moves the price materially. Omega, Cartier, IWC, JLC, and VC encode the
# dial in the full reference already, so they need no variant children.
REF_VARIANTS: dict[tuple[str, str], tuple[DialVariant, ...]] = {
    # Yellow-gold Daytona: the green dial ("John Mayer") trades ~60% above
    # champagne — averaging them is meaningless.
    ("rolex", "116508"): (
        DialVariant("Green", nicknames=("John Mayer",)),
        DialVariant("Champagne", match_terms=("gold",)),
        DialVariant("Black"),
        DialVariant("White"),
        DialVariant("MOP", match_terms=("mother of pearl",)),
    ),
    ("rolex", "116509"): (
        DialVariant("Silver"),
        DialVariant("Blue"),
        DialVariant("Black"),
        DialVariant("Meteorite"),
    ),
    ("rolex", "116505"): (
        DialVariant("Pink", match_terms=("rose",)),
        DialVariant("Chocolate", match_terms=("brown",)),
        DialVariant("Black"),
    ),
    ("rolex", "116515LN"): (
        DialVariant("Pink", match_terms=("rose",)),
        DialVariant("Chocolate", match_terms=("brown",)),
        DialVariant("Black"),
        DialVariant("Ivory"),
    ),
    ("rolex", "126515LN"): (
        DialVariant("Sundust", match_terms=("pink", "rose")),
        DialVariant("Chocolate", match_terms=("brown",)),
        DialVariant("Black"),
    ),
    ("rolex", "126518LN"): (
        DialVariant("Golden", match_terms=("gold", "champagne")),
        DialVariant("Green"),
        DialVariant("Black"),
    ),
    ("rolex", "126519LN"): (
        DialVariant("Grey", match_terms=("steel", "slate")),
        DialVariant("Black"),
    ),
    # Steel Daytona: white ("Panda") carries a persistent premium over black
    ("rolex", "116500LN"): (
        DialVariant("White", nicknames=("Panda",)),
        DialVariant("Black"),
    ),
    ("rolex", "126500LN"): (
        DialVariant("White", nicknames=("Panda",)),
        DialVariant("Black"),
    ),
    ("rolex", "116520"): (
        DialVariant("White"),
        DialVariant("Black"),
    ),
    ("rolex", "16520"): (
        DialVariant("White"),
        DialVariant("Black"),
    ),
    ("rolex", "116523"): (
        DialVariant("White"),
        DialVariant("Champagne", match_terms=("gold",)),
        DialVariant("Black"),
        DialVariant("Blue"),
    ),
    ("rolex", "116503"): (
        DialVariant("White"),
        DialVariant("Champagne", match_terms=("gold",)),
        DialVariant("Black"),
    ),
    ("rolex", "126503"): (
        DialVariant("White"),
        DialVariant("Champagne", match_terms=("gold",)),
        DialVariant("Black"),
    ),
    # Patek encodes the dial in the dash suffix — the alias pins it exactly
    ("patek-philippe", "5711/1A"): (
        DialVariant("Blue", aliases=("5711/1A-010",)),
        DialVariant("Green", aliases=("5711/1A-014",)),
    ),
    ("audemars-piguet", "15500ST"): (
        DialVariant("Blue"),
        DialVariant("Black"),
        DialVariant("Silver", match_terms=("white", "grey")),
    ),
    ("audemars-piguet", "15400ST"): (
        DialVariant("Blue"),
        DialVariant("Black"),
        DialVariant("Silver", match_terms=("white", "grey")),
    ),
}


def all_metadata() -> dict[tuple[str, str], RefMeta]:
    return {**REF_METADATA, **ADDITIONAL_METADATA}
