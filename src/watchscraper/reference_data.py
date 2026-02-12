"""
Investment-grade reference data for key Rolex Daytona, Audemars Piguet, and
Patek Philippe watches.

Each tuple:
    (reference_number, release_year, discontinuation_year_or_None,
     production_status, notable_facts)

production_status is one of: "current", "discontinued", "limited"
"""

WATCH_REFERENCE_DATA: list[tuple[str, int, int | None, str, str]] = [
    # -------------------------------------------------------------------------
    # ROLEX COSMOGRAPH DAYTONA
    # -------------------------------------------------------------------------
    (
        "116500LN",
        2016,
        2023,
        "discontinued",
        "Steel/ceramic Daytona. First Daytona with Cerachrom bezel. Cal. 4130. "
        "40 mm Oystersteel. Iconic 'Panda' and 'Reverse Panda' dial configs. "
        "Replaced by 126500LN. Multi-year AD waiting lists when in production. "
        "Prices surged above 2x retail on secondary market.",
    ),
    (
        "126500LN",
        2023,
        None,
        "current",
        "Steel/ceramic successor to 116500LN. Cal. 4131 with 72-hr power reserve. "
        "40 mm. Sapphire display caseback (first for steel Daytona). Refined "
        "lugs and thinner subdial frames. Released for Daytona's 60th anniversary. "
        "Extreme waitlists at ADs; trades well above retail on grey market.",
    ),
    (
        "126515LN",
        2023,
        None,
        "current",
        "18K Everose gold with black Cerachrom bezel and Oysterflex strap. "
        "Cal. 4131, 72-hr reserve, sapphire caseback. Successor to 116515LN. "
        "40 mm. High demand, strong grey-market premium.",
    ),
    (
        "126519LN",
        2023,
        None,
        "current",
        "18K white gold with black Cerachrom bezel and Oysterflex strap. "
        "Cal. 4131. 40 mm. 'Baby Le Mans' panda dial variant is among the "
        "most coveted modern Daytonas. Sapphire caseback.",
    ),
    (
        "126518LN",
        2023,
        None,
        "current",
        "18K yellow gold with black Cerachrom bezel and Oysterflex strap. "
        "Cal. 4131, 72-hr reserve, sapphire caseback. 40 mm. Successor to "
        "116518LN. Multiple dial options including turquoise (2025 release).",
    ),
    (
        "126506",
        2023,
        None,
        "current",
        "950 Platinum with Cerachrom bezel. Cal. 4131. 40 mm. Ice-blue dial "
        "exclusive to platinum Rolex. Sapphire caseback. Diamond baguette dial "
        "variant available. Successor to 116506. Top-tier Daytona; six-figure "
        "retail and secondary prices.",
    ),
    (
        "116520",
        2000,
        2016,
        "discontinued",
        "Steel Daytona with metal bezel. Cal. 4130 -- the first in-house Rolex "
        "chronograph caliber. 40 mm. Produced 16 years. Black and white dials. "
        "Highly collectible; prices rising steadily since discontinuation. "
        "Considered a modern classic and 'future vintage'.",
    ),
    (
        "116523",
        2000,
        2016,
        "discontinued",
        "Two-tone Rolesor (steel + 18K yellow gold) Daytona. Cal. 4130. 40 mm. "
        "Metal bezel. Replaced by 116503 in 2016. Less demand than steel "
        "counterpart but appreciating on secondary market.",
    ),
    (
        "116509",
        2000,
        2023,
        "discontinued",
        "18K white gold Daytona on Oyster bracelet. Cal. 4130. 40 mm. Metal "
        "bezel. Numerous dial variants over 23-year run including meteorite "
        "and blue. Replaced by 126509. Strong collector following.",
    ),
    (
        "116515LN",
        2011,
        2023,
        "discontinued",
        "18K Everose gold with black Cerachrom bezel. Cal. 4130. 40 mm. "
        "Originally on leather strap; updated to Oysterflex rubber in 2017. "
        "Replaced by 126515LN. First Cerachrom-bezel gold Daytona.",
    ),
    (
        "116508",
        2016,
        2023,
        "discontinued",
        "18K yellow gold on Oyster bracelet. Cal. 4130. 40 mm. Metal bezel. "
        "Green dial variant became the famous 'John Mayer' Daytona after the "
        "musician showcased it on Hodinkee's Talking Watches. Prices surged "
        "dramatically. Replaced by 126508.",
    ),
    (
        "116505",
        2008,
        2023,
        "discontinued",
        "18K Everose gold on Oyster bracelet. Cal. 4130. 40 mm. Metal bezel. "
        "First-ever rose gold Daytona on bracelet. Multiple dial options "
        "including chocolate and sundust. Replaced by 126505.",
    ),
    (
        "116503",
        2016,
        2023,
        "discontinued",
        "Two-tone Rolesor (steel + 18K yellow gold) Daytona. Cal. 4130. 40 mm. "
        "Metal bezel. Replaced the 116523. Itself replaced by 126503 in 2023.",
    ),
    (
        "126503",
        2023,
        None,
        "current",
        "Two-tone Rolesor (Oystersteel + 18K yellow gold) on Oyster bracelet. "
        "Cal. 4131, 72-hr reserve, sapphire caseback. 40 mm. Successor to "
        "116503. Part of the 2023 Daytona refresh.",
    ),
    (
        "126509",
        2023,
        None,
        "current",
        "18K white gold on Oyster bracelet. Cal. 4131, sapphire caseback. "
        "40 mm. Successor to 116509. Part of 2023 Daytona generation refresh.",
    ),
    (
        "16520",
        1988,
        2000,
        "discontinued",
        "Steel 'Zenith Daytona'. First automatic Daytona, powered by modified "
        "Zenith El Primero (Rolex Cal. 4030). 40 mm. Produced 12 years. "
        "Highly collectible vintage reference. Patrizzi dials command huge "
        "premiums. Prices range from $25K to $100K+ depending on dial variant "
        "and condition.",
    ),
    (
        "16523",
        1988,
        2000,
        "discontinued",
        "Two-tone (steel + 18K yellow gold) 'Zenith Daytona'. Cal. 4030 "
        "(modified Zenith El Primero). 40 mm. Same production era as 16520. "
        "Less collected than steel version but appreciating.",
    ),
    (
        "116518",
        2000,
        2016,
        "discontinued",
        "18K yellow gold on leather strap. Cal. 4130. 40 mm. Metal bezel. "
        "Available in numerous dial configurations. Replaced by 116518LN "
        "(ceramic bezel / Oysterflex) in 2016.",
    ),

    # -------------------------------------------------------------------------
    # AUDEMARS PIGUET ROYAL OAK & ROYAL OAK OFFSHORE
    # -------------------------------------------------------------------------
    (
        "15500ST",
        2019,
        None,
        "current",
        "Royal Oak Selfwinding 41 mm in stainless steel. Cal. 4302 with 70-hr "
        "power reserve. Replaced the 15400ST. Date at 3 o'clock. Grande "
        "Tapisserie dial. Strong secondary market premiums; multi-year AD "
        "waitlists.",
    ),
    (
        "15510ST",
        2022,
        None,
        "current",
        "Royal Oak Selfwinding 41 mm steel. Cal. 4302. Launched for the 50th "
        "anniversary with '50 Years' engraved rotor. Updated ergonomic design "
        "with slimmer integrated bracelet. Multiple dial colors. Successor "
        "generation to 15500ST.",
    ),
    (
        "15550ST",
        2022,
        None,
        "current",
        "Royal Oak Selfwinding 37 mm steel. Cal. 5900 with 60-hr reserve. "
        "Part of the 50th anniversary redesign. Mid-size option bridging the "
        "gap between 34 mm and 41 mm. Grande Tapisserie dial.",
    ),
    (
        "26331ST",
        2017,
        None,
        "current",
        "Royal Oak Chronograph 41 mm in stainless steel. Cal. 2385. Released "
        "at SIHH 2017 for the 20th anniversary of the Royal Oak Chronograph. "
        "Blue, black, and 'Panda' (silver) dial variants. High demand.",
    ),
    (
        "26240ST",
        2022,
        None,
        "current",
        "Royal Oak Selfwinding Chronograph 41 mm steel. Cal. 4401 with flyback "
        "function and 70-hr reserve. 50th anniversary launch with special rotor. "
        "Blue, black, green, white dial variants. Successor to 26331ST's design "
        "generation. Sapphire caseback.",
    ),
    (
        "26238ST",
        2021,
        None,
        "current",
        "Royal Oak Offshore Selfwinding Chronograph 42 mm steel. Modern "
        "re-edition evoking the original 1993 'Beast'. Cal. 4401 flyback "
        "chronograph. Multiple colorways including 'Tiffany' blue/green. "
        "Strong collector demand.",
    ),
    (
        "15710ST",
        2015,
        None,
        "current",
        "Royal Oak Offshore Diver 42 mm stainless steel. Cal. 3120. 300 m "
        "water resistance. Inner rotating bezel. Replaced 15703ST. Multiple "
        "dial colors. Popular entry to Offshore line.",
    ),
    (
        "15210CR",
        2019,
        None,
        "current",
        "Code 11.59 Selfwinding 41 mm. Two-tone case: 18K pink gold with "
        "white gold bezel, lugs, and caseback. Cal. 4302. Lacquered dials "
        "with exceptional finishing. Initially polarizing design, now gaining "
        "collector appreciation.",
    ),
    (
        "15202ST",
        2000,
        2021,
        "discontinued",
        "Royal Oak 'Jumbo' Extra-Thin 39 mm steel. Cal. 2121 (legendary "
        "ultra-thin movement). The definitive modern Jumbo reference. "
        "Petite Tapisserie dial. Discontinued after 21-year run. Replaced "
        "by 16202ST. Secondary prices surged post-discontinuation to "
        "$70K-$100K+. Closest modern equivalent to the original 5402 from 1972.",
    ),
    (
        "15400ST",
        2012,
        2019,
        "discontinued",
        "Royal Oak Selfwinding 41 mm steel. Cal. 3120. First 41 mm Royal Oak "
        "(succeeded the 39 mm 15300ST). Grande Tapisserie dial. Replaced by "
        "15500ST. Appreciating on secondary market.",
    ),
    (
        "15300ST",
        2005,
        2012,
        "discontinued",
        "Royal Oak Selfwinding 39 mm steel. Cal. 3120 -- first in-house "
        "automatic movement for the Royal Oak. Grande Tapisserie dial. "
        "Replaced by 15400ST. Vintage-proportioned; increasingly collectible.",
    ),
    (
        "15202IP",
        2018,
        2021,
        "limited",
        "Royal Oak 'Jumbo' Extra-Thin 39 mm. Titanium case with platinum "
        "accents (IP = iridescent platinum). Smoked blue gradient dial. "
        "Boutique exclusive, limited to 250 pieces. Cal. 2121. Extremely "
        "rare; strong collector premiums.",
    ),
    (
        "26470ST",
        2014,
        2020,
        "discontinued",
        "Royal Oak Offshore Chronograph 42 mm steel. Cal. 3126/3840 with "
        "50-hr reserve. Multiple dial colors: brown, navy 'Navy', black "
        "'Vampire', and indigo. Leather/rubber straps. Replaced by 26420SO "
        "generation. Very popular on secondary market.",
    ),
    (
        "26420SO",
        2021,
        None,
        "current",
        "Royal Oak Offshore Chronograph 43 mm. Steel case with black ceramic "
        "bezel, crown, and pushers. Cal. 4401 flyback chronograph. Mega "
        "Tapisserie dial. Interchangeable rubber strap. Black, taupe, and "
        "blue variants.",
    ),
    (
        "16202ST",
        2022,
        None,
        "current",
        "Royal Oak 'Jumbo' Extra-Thin 39 mm steel. Cal. 7121 (new ultra-thin "
        "movement replacing the 2121 after 55+ years). 50th anniversary debut "
        "with special rotor. Petite Tapisserie dial. Successor to 15202ST. "
        "Extreme demand; very hard to acquire at retail.",
    ),
    (
        "16202OR",
        2022,
        None,
        "current",
        "Royal Oak 'Jumbo' Extra-Thin 39 mm in 18K pink/rose gold. Cal. 7121. "
        "50th anniversary launch. Smoked grey Petite Tapisserie dial. "
        "Retail ~$70,500 USD. Highly coveted.",
    ),
    (
        "15510OR",
        2022,
        None,
        "current",
        "Royal Oak Selfwinding 41 mm in 18K pink/rose gold. Cal. 4302 with "
        "70-hr reserve. 50th anniversary design updates. Blue and black dial "
        "variants. Leather strap or gold bracelet options.",
    ),
    (
        "26240OR",
        2022,
        None,
        "current",
        "Royal Oak Selfwinding Chronograph 41 mm in 18K pink/rose gold. "
        "Cal. 4401 flyback chronograph, 70-hr reserve. Sapphire caseback. "
        "Silver and green Grande Tapisserie dial variants.",
    ),
    (
        "26574ST",
        2015,
        None,
        "current",
        "Royal Oak Perpetual Calendar 41 mm steel. Cal. 5134 (ultra-thin "
        "automatic perpetual calendar based on Cal. 2120). Day, date, month, "
        "astronomical moon phase, leap year, week number. Blue dial with "
        "Grande Tapisserie. One of the most desirable AP complications in "
        "steel.",
    ),
    (
        "26579CE",
        2017,
        None,
        "current",
        "Royal Oak Perpetual Calendar 41 mm in black ceramic (case AND "
        "bracelet). Cal. 5134. Full ceramic construction including bracelet "
        "-- technical achievement. Grey Grande Tapisserie dial. Aventurine "
        "moon phase. Lightweight at ~127 g. SIHH 2017 debut.",
    ),
    (
        "26585CE",
        2019,
        None,
        "current",
        "Royal Oak Perpetual Calendar Openworked 41 mm black ceramic. "
        "Cal. 5135 (skeletonized 5134). Full ceramic case and bracelet. "
        "Sapphire openworked dial revealing the perpetual calendar mechanism. "
        "Boutique exclusive. Extremely complex manufacture.",
    ),
    (
        "15407ST",
        2016,
        None,
        "current",
        "Royal Oak Double Balance Wheel Openworked 41 mm steel. Cal. 3132 "
        "with patented double balance wheel for enhanced accuracy. Skeleton "
        "dial showcasing movement architecture. Technical showpiece in "
        "stainless steel.",
    ),
    (
        "15407OR",
        2016,
        None,
        "current",
        "Royal Oak Double Balance Wheel Openworked 41 mm in 18K pink/rose "
        "gold. Cal. 3132. Same technical innovation as steel version. "
        "Pink gold applied hour markers on openworked dial.",
    ),

    # -------------------------------------------------------------------------
    # PATEK PHILIPPE
    # -------------------------------------------------------------------------
    (
        "5811/1G",
        2022,
        None,
        "current",
        "Nautilus Selfwinding 41 mm in 18K white gold. Cal. 26-330 S C. "
        "Successor to the legendary 5711. Blue sunburst dial with black "
        "gradation. 1 mm larger than 5711. Retail ~$69,785. Extremely long "
        "waitlists; trades at massive premiums. THE most sought-after "
        "production Patek.",
    ),
    (
        "5168G",
        2017,
        None,
        "current",
        "Aquanaut Selfwinding 42.2 mm white gold. Cal. 324 S C. Launched for "
        "the Aquanaut's 20th anniversary. First men's Aquanaut in white gold. "
        "Night blue and khaki green dial variants. Composite rubber strap.",
    ),
    (
        "5267/200A",
        2021,
        None,
        "current",
        "Aquanaut Luce 38.8 mm stainless steel. Quartz movement. Diamond-set "
        "bezel. Ladies' model. Black, white, and khaki green dial options. "
        "Rare Patek in steel; collectible for that reason.",
    ),
    (
        "5196G",
        2004,
        None,
        "current",
        "Calatrava 37 mm white gold. Cal. 215 PS (manual wind). Subsidiary "
        "seconds. Two-piece case design. Classic Calatrava dress watch. "
        "One of the most honest expressions of Patek's traditional "
        "watchmaking. Long-running production.",
    ),
    (
        "5227G",
        2013,
        None,
        "current",
        "Calatrava 39 mm white gold. Cal. 324 S C (automatic). Officer's-style "
        "hinged caseback. Date function. Multiple dial variants including "
        "black and charcoal grey. Quintessential Patek dress watch.",
    ),
    (
        "5205G",
        2010,
        None,
        "current",
        "Complications Annual Calendar 40 mm white gold. Cal. 324 S QA LU. "
        "Day/date/month in apertures. Moon phase and 24-hr subdial at 6. "
        "PP's signature annual calendar (patented 1996). Multiple dial colors "
        "including blue sunburst.",
    ),
    (
        "5230G",
        2016,
        None,
        "current",
        "Complications World Time 38.5 mm white gold. Cal. 240 HU. Pusher at "
        "10 o'clock for city disc rotation. Guilloched center. Limited edition "
        "'New York 2017' variant (300 pcs). Standard production continues.",
    ),
    (
        "5270P",
        2018,
        None,
        "current",
        "Grand Complications Perpetual Calendar Chronograph 41 mm platinum. "
        "Cal. CH 29-535 PS Q (manual wind). Salmon dial debut created enormous "
        "collector excitement. Concave bezel. Combines two of PP's signature "
        "complications. Six-figure retail.",
    ),
    (
        "5320G",
        2017,
        None,
        "current",
        "Grand Complications Perpetual Calendar 40 mm white gold. Cal. 324 S Q. "
        "Retro-styled with three-tier lugs and vintage-inspired dial. Day, "
        "date, month, leap year, moon phase. Lacquered cream and salmon "
        "dial variants.",
    ),
    (
        "5236P",
        2021,
        None,
        "current",
        "Grand Complications In-Line Perpetual Calendar 41.3 mm platinum. "
        "Cal. 31-260 PS QL. Revolutionary single-aperture display showing "
        "day, date, month in one window at 12 o'clock -- a first for Patek. "
        "Blue dial with black gradient. Inspired by 1970s pocket watch design "
        "and ref. 3448. Micro-rotor movement.",
    ),
    (
        "5172G",
        2019,
        None,
        "current",
        "Complications Chronograph 41 mm white gold. Cal. CH 29-535 PS "
        "(manual wind). Column wheel, horizontal clutch. Blue dial. "
        "Round guilloched pushers with vintage styling. Successor to ref. "
        "5170. 65-hr power reserve.",
    ),
    (
        "5711/1A",
        2006,
        2021,
        "discontinued",
        "Nautilus Selfwinding 40 mm stainless steel on bracelet. Cal. 324 S C "
        "(later 26-330 S C). THE grail steel sports watch. Blue gradient dial. "
        "Discontinued Jan 2021 after 15-year run. Traded at $100K-$150K+ on "
        "secondary market at peak. Succeeded by 5811/1G in white gold. "
        "Arguably the most famous modern luxury sports watch.",
    ),
    (
        "5712/1A",
        2006,
        2025,
        "discontinued",
        "Nautilus Moon Phase Power Reserve Date 40 mm stainless steel on "
        "bracelet. Cal. 240 PS IRM C LU. Sub-dials for moon phase, power "
        "reserve, and date. Discontinued Feb 2025 after ~19-year run. "
        "Beloved for its 'quiet complication' approach. Now a grail piece.",
    ),
    (
        "5726/1A",
        2012,
        None,
        "current",
        "Nautilus Annual Calendar Moon Phase 40.5 mm stainless steel on "
        "bracelet. Cal. 324 S QA LU. Annual calendar, 24-hr indication, "
        "and moon phase. Blue dial variant (5726/1A-014) released 2019. "
        "Popular complication piece in Nautilus line.",
    ),
    (
        "5980/1A",
        2006,
        2013,
        "discontinued",
        "Nautilus Chronograph 40.5 mm stainless steel on bracelet. Cal. CH "
        "28-520 C. First-ever Nautilus chronograph. Blue-black gradient dial. "
        "Discontinued ~2013, replaced by 5990/1A. Now trades at strong "
        "premiums as the original Nautilus chrono.",
    ),
    (
        "5990/1A",
        2014,
        None,
        "current",
        "Nautilus Travel Time Chronograph 40.5 mm stainless steel on bracelet. "
        "Cal. CH 28-520 C FUS. Flyback chronograph + dual time zone + date. "
        "Original black dial (5990/1A-001) discontinued 2022; replaced by "
        "blue dial (5990/1A-011). Triple complication in a sports case.",
    ),
    (
        "5167A",
        2007,
        None,
        "current",
        "Aquanaut Selfwinding 40 mm stainless steel. Cal. 324 S C. Black "
        "embossed dial on composite rubber strap. Entry-level Patek sports "
        "watch. Bracelet variant (5167/1A) discontinued 2025, but rubber "
        "strap version (5167A-001) remains current. Long waitlists.",
    ),
    (
        "5711/1A-018",
        2021,
        2021,
        "limited",
        "Nautilus 'Tiffany Blue' 40 mm steel. Cal. 26-330 S C. LIMITED TO "
        "170 PIECES for Tiffany & Co. 170th anniversary. Sold exclusively at "
        "3 US Tiffany boutiques. Unique Tiffany-blue dial with double stamp "
        "(Patek + Tiffany). One example sold for $6.5M at Phillips auction. "
        "Ultimate modern grail watch. Created to celebrate the end of 5711 "
        "production.",
    ),
    (
        "5712R",
        2006,
        None,
        "current",
        "Nautilus Moon Phase Power Reserve Date 40 mm 18K rose gold on leather "
        "strap. Cal. 240 PS IRM C LU. Same complications as 5712/1A (moon "
        "phase, power reserve, date pointer). Charcoal brown dial. Continues "
        "in production as the gold variant.",
    ),
    (
        "5980/1R",
        2006,
        2024,
        "discontinued",
        "Nautilus Chronograph 40.5 mm 18K rose gold on bracelet. Cal. CH "
        "28-520 C. Black dial with rose gold markers. Discontinued ~2024 "
        "alongside 5980 line refresh. Succeeded by new Nautilus Flyback "
        "Chronograph in white gold.",
    ),
    (
        "5740/1G",
        2018,
        None,
        "current",
        "Nautilus Perpetual Calendar 40 mm 18K white gold on bracelet. "
        "Cal. 240 Q (ultra-thin). First Grand Complication in the Nautilus. "
        "Blue sunburst dial. Day, date, month, leap year, 24-hr, moon phase. "
        "Thinnest PP perpetual calendar. Extraordinary piece; six-figure "
        "secondary market pricing. Tiffany-stamped versions exist.",
    ),
    (
        "5167R",
        2016,
        None,
        "current",
        "Aquanaut Selfwinding 40.8 mm 18K rose gold on brown composite strap. "
        "Cal. 324 S C. Brown sunburst embossed dial. Rose gold applied "
        "numerals with lume. Pairs with 5167A as the gold equivalent.",
    ),
    (
        "5164A",
        2011,
        2025,
        "discontinued",
        "Aquanaut Travel Time 40.8 mm stainless steel. Cal. 324 S C FUS. "
        "Dual time zone with home/local pushers at 8 and 10 o'clock. Black "
        "dial. Discontinued Feb 2025. One of few steel complicated Aquanauts. "
        "Increasingly collectible.",
    ),
    (
        "5968A",
        2018,
        None,
        "current",
        "Aquanaut Chronograph 42.2 mm stainless steel. Cal. CH 28-520 C. "
        "First Aquanaut chronograph. Black dial with vivid orange accents "
        "on subdials, seconds hand, and strap insert. Sporty and youthful "
        "aesthetic. Baselworld 2018 debut.",
    ),
    (
        "5261R",
        2023,
        None,
        "current",
        "Aquanaut Luce Annual Calendar 39.9 mm 18K rose gold. Cal. 324 S QA "
        "LU. Ladies' complication piece with annual calendar, date, and moon "
        "phase. Diamond-set bezel. First annual calendar in Aquanaut line. "
        "Retail ~$61,510.",
    ),
    (
        "5327G",
        2018,
        None,
        "current",
        "Grand Complications Perpetual Calendar 39 mm white gold. Cal. 240 Q. "
        "Calatrava-style case with scalloped flanks. Royal blue sunburst dial "
        "with applied Breguet numerals. Day, date, month, leap year, moon "
        "phase. Elegant dressy perpetual.",
    ),
    (
        "5230P",
        2022,
        None,
        "current",
        "Complications World Time 38.5 mm platinum. Cal. 240 HU. Green "
        "guilloched dial -- platinum-exclusive color. Watches and Wonders 2022 "
        "debut. Part of a new wave of PP World Timers.",
    ),
    (
        "5231J",
        2019,
        None,
        "current",
        "Complications World Time 38.5 mm 18K yellow gold. Cal. 240 HU. "
        "Cloisonne Grand Feu enamel map dial depicting Europe, Africa, and "
        "the Americas. Handcrafted artisan dial. Baselworld 2019 debut. "
        "Rare Handcrafts category.",
    ),
    (
        "5231G",
        2022,
        None,
        "current",
        "Complications World Time 38.5 mm 18K white gold. Cal. 240 HU. "
        "Cloisonne Grand Feu enamel map of Southeast Asia and Oceania. "
        "Watches and Wonders 2022. Rare Handcrafts category. Highly "
        "collectible artisan piece.",
    ),
    (
        "5930P",
        2022,
        None,
        "current",
        "Complications World Time Flyback Chronograph 39.5 mm platinum. "
        "Cal. CH 28-520 HU. Green guilloched dial. Flyback chronograph + "
        "world time. Watches and Wonders 2022. Platinum-exclusive color. "
        "Complex multi-complication piece.",
    ),
    (
        "5531R",
        2018,
        None,
        "current",
        "Grand Complications World Time Minute Repeater 40.2 mm 18K rose gold. "
        "Cal. R 27 HU. FIRST minute repeater that chimes LOCAL time (not just "
        "home time) -- a world-first complication. Cloisonne enamel dial. "
        "Originally debuted 2017 as NY Special Edition. Regular production "
        "from 2018. Seven-figure pricing. Supreme haute horlogerie.",
    ),
    (
        "5326G",
        2022,
        None,
        "current",
        "Complications Annual Calendar Travel Time 41 mm white gold. "
        "Cal. 31-260 PS QA LU FUS 24H. First-ever combination of annual "
        "calendar + travel time in a single PP watch. Vintage-inspired "
        "Calatrava pilot style with hobnail caseband. Charcoal grey dial. "
        "Watches and Wonders 2022 debut.",
    ),
]
