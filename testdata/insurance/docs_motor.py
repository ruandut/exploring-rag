"""KR-PL-002 — Private Motor Policy Wording."""

from builder import Doc
from common import (
    PROVINCES,
    RNG,
    case,
    complaints,
    how_to_read,
    money,
    person,
    place,
    privacy_notice,
    regulatory,
    specimen_schedules,
)

MODELS = [
    ("Toyota", "Hilux 2.8 GD-6 double cab", "D"), ("Toyota", "Corolla Cross 1.8", "C"), ("Toyota", "Fortuner 2.8", "D"),
    ("Toyota", "Starlet 1.5", "A"), ("Volkswagen", "Polo Vivo 1.4", "A"), ("Volkswagen", "Polo 1.0 TSI", "B"),
    ("Volkswagen", "Amarok 2.0 BiTDI", "D"), ("Volkswagen", "T-Cross 1.0 TSI", "C"), ("Ford", "Ranger 2.0 BiT double cab", "D"),
    ("Ford", "EcoSport 1.5", "B"), ("Ford", "Everest 2.0", "D"), ("Suzuki", "Swift 1.2", "A"), ("Suzuki", "Jimny 1.5", "C"),
    ("Suzuki", "Ertiga 1.5", "B"), ("Hyundai", "Grand i10 1.2", "A"), ("Hyundai", "Creta 1.5", "C"), ("Hyundai", "Tucson 2.0", "C"),
    ("Kia", "Picanto 1.2", "A"), ("Kia", "Sonet 1.5", "B"), ("Kia", "Sportage 2.0", "C"), ("Nissan", "Navara 2.5 double cab", "D"),
    ("Nissan", "Magnite 1.0", "B"), ("Isuzu", "D-Max 3.0 double cab", "D"), ("Mahindra", "Pik Up 2.2 double cab", "D"),
    ("Mahindra", "XUV300 1.2", "B"), ("Renault", "Kwid 1.0", "A"), ("Renault", "Kiger 1.0", "B"), ("Haval", "Jolion 1.5T", "C"),
    ("Chery", "Tiggo 4 Pro 1.5", "C"), ("BMW", "3 Series 320i", "E"), ("BMW", "X3 xDrive20d", "E"), ("Mercedes-Benz", "C200", "E"),
    ("Mercedes-Benz", "GLC 300", "E"), ("Audi", "A3 Sportback 35 TFSI", "E"), ("Audi", "Q5 40 TDI", "E"), ("Land Rover", "Defender 110", "E"),
    ("Mazda", "CX-5 2.0", "C"), ("Honda", "Fit 1.5", "B"), ("Honda", "CR-V 1.5T", "C"), ("Toyota", "Land Cruiser 300", "E"),
]
GROUP_NOTES = {
    "A": "Entry hatchbacks: low repair costs, moderate theft for parts",
    "B": "Small cars and crossovers",
    "C": "Mid-size SUVs and crossovers",
    "D": "Bakkies and large SUVs: high hijacking frequency, 15% theft loading",
    "E": "Premium and luxury vehicles: high repair costs, tracking device required",
}

BASIC_PCT = 0.05
BASIC_MIN = 5000
YOUNG_DRIVER = 3500
WINDSCREEN_PCT = 0.25
WINDSCREEN_MIN = 1000
TRACKER_VALUE = 350_000
CAR_HIRE_DAYS = 30


def basic_excess(claim: int) -> int:
    return max(BASIC_MIN, round(claim * BASIC_PCT))


def build() -> Doc:
    d = Doc(
        filename="KR-PL-002-private-motor-policy-wording.pdf",
        title="Private Motor Insurance Policy Wording",
        subtitle="Comprehensive · Third Party, Fire and Theft · Third Party Only",
        code="KR-PL-002",
    )
    how_to_read(d, "Kestrel Ridge Private Motor Insurance Policy")

    d.h1("Definitions", new_page=True)
    terms = [
        ("Regular driver", "The person who drives the vehicle most often, named on your schedule."),
        ("Retail value", "The value of the vehicle in the current TransUnion Auto Dealers' Guide for its make, model, year and mileage, adjusted for its condition."),
        ("Trade value", "The value a dealer would pay for the vehicle, as shown in the TransUnion Auto Dealers' Guide."),
        ("Write-off", "A vehicle that we decide is not economical to repair, or that has been stolen or hijacked and not recovered within 21 days."),
        ("Hijacking", "The theft of the vehicle by force or threat of force while a person is in or next to it."),
        ("Licensed driver", "A person who holds a valid South African driving licence, or a foreign licence recognised in South Africa, for the class of vehicle being driven."),
        ("Tracking device", "A vehicle tracking and recovery device approved by us, installed by an accredited installer and kept active by a paid subscription."),
        ("Approved repairer", "A panel beater on our network that meets our quality and pricing standards."),
        ("Accessories", "Equipment fitted to the vehicle that is not standard for the model, such as tow bars, canopies, sound systems and mag wheels."),
        ("Young driver", "A driver who is younger than 25 years at the time of the event."),
    ]
    d.table(["Term", "Meaning"], [[t, m] for t, m in terms], [0.22, 0.78])

    d.h1("Types of cover", new_page=True)
    d.table(
        ["Cover", "Your vehicle", "Other people's property and vehicles"],
        [
            ["Comprehensive", "Accidental damage, fire, theft, hijacking, hail, flood", "Covered"],
            ["Third party, fire and theft", "Fire, theft and hijacking only", "Covered"],
            ["Third party only", "Not covered", "Covered"],
        ],
        [0.28, 0.42, 0.30],
    )
    d.h2("Comprehensive cover")
    d.clauses(
        "We cover accidental loss of or damage to the vehicle and its standard accessories, "
        "including damage caused by collision, overturning, fire, theft, hijacking, hail, flood "
        "and malicious damage.",
        "Non-standard accessories are covered only if they are listed on the schedule.",
        "We pay the reasonable cost of repairs at an approved repairer, or the retail value if "
        "the vehicle is a write-off, less any excess. If you still owe money on the vehicle, we "
        "pay the finance house first.",
        "If the vehicle is less than 12 months old and has travelled fewer than 10,000 km, and "
        "it is written off, we replace it with a new vehicle of the same make and model.",
    )
    d.h2("Third party liability")
    d.clauses(
        "We cover your legal liability for damage to other people's property, including their "
        "vehicles, caused by an accident involving your vehicle, up to R5,000,000 per event.",
        "Liability for death or bodily injury on South African roads is dealt with by the Road "
        "Accident Fund. This policy covers bodily injury claims only where the Road Accident "
        "Fund Act does not apply.",
    )

    d.h1("Who may drive", new_page=True)
    d.clauses(
        "Any licensed driver may drive the vehicle with your permission, but additional "
        "excesses apply to drivers who are not the regular driver.",
        "There is no cover while the vehicle is driven by a person who is not a licensed "
        "driver, or who has a learner's licence and is not accompanied by a licensed driver "
        "sitting next to them.",
        "There is no cover while the driver is under the influence of alcohol or drugs to the "
        "extent that their ability to drive is impaired, or has a blood alcohol concentration "
        "above the legal limit of 0.05 grams per 100 millilitres, or refuses to give a sample.",
        "If the vehicle is used for e-hailing, lift clubs that charge a fee, or delivery work, "
        "you must have the business use extension on your schedule.",
    )

    d.h1("Security requirements")
    d.clauses(
        f"If the retail value of the vehicle is more than {money(TRACKER_VALUE)}, an approved "
        "tracking device must be installed and active. If it is not active when the vehicle is "
        "stolen or hijacked, we will not pay the theft or hijacking claim.",
        "The vehicle must be locked, with its windows closed and its anti-theft devices "
        "activated, whenever it is left unattended.",
        "Overnight, the vehicle must be kept at the address on your schedule in a locked garage "
        "or behind locked gates, unless you are travelling.",
    )

    d.h1("Excesses", new_page=True)
    d.table(
        ["Excess", "Amount"],
        [
            ["Basic excess (comprehensive)", f"{int(BASIC_PCT * 100)}% of the claim, minimum {money(BASIC_MIN)}"],
            ["Young driver (under 25)", f"Additional {money(YOUNG_DRIVER)}"],
            ["Driver licensed for less than 2 years", "Additional R3,000"],
            ["Driver not the regular driver", "Additional R2,000"],
            ["Theft or hijacking", "10% of the claim, minimum R7,500"],
            ["Windscreen and glass", f"{int(WINDSCREEN_PCT * 100)}% of the claim, minimum {money(WINDSCREEN_MIN)}"],
            ["Single-vehicle accident at night (22:00–04:00)", "Additional R2,500"],
            ["Third party claims", "R2,500"],
        ],
        [0.55, 0.45],
    )
    d.p(
        "Excesses are added together when more than one applies. For example, a young driver "
        "who is not the regular driver pays the basic excess plus R3,500 plus R2,000.",
    )

    d.h1("Extra benefits with comprehensive cover")
    d.clauses(
        f"Car hire: after an insured accident, theft or hijacking, we pay for a Group B hire "
        f"vehicle for up to {CAR_HIRE_DAYS} days while your vehicle is repaired or the claim is settled, if your "
        "schedule includes the car hire option.",
        "Towing and storage: we pay the reasonable cost of towing the vehicle to the nearest "
        "approved repairer or our storage yard, and storage until the claim is decided.",
        "Emergency roadside assistance: jump starts, flat tyres, lock-outs and up to 10 litres "
        "of fuel delivery, three times per year.",
        "Trauma counselling after a hijacking, for you and your passengers, up to 6 sessions.",
        "Credit shortfall: if the vehicle is a write-off and the finance settlement is more than "
        "the retail value, we pay the difference up to 25% of the retail value, if your schedule "
        "includes this option.",
    )

    d.h1("What we do not cover", new_page=True)
    d.clauses(
        "Wear and tear, mechanical or electrical breakdown, and damage to tyres caused by "
        "braking, punctures, cuts or bursts.",
        "Damage caused by driving the vehicle when it was not roadworthy, where this caused or "
        "contributed to the accident.",
        "Loss or damage while the vehicle is used for racing, rallies, speed tests or on a race track.",
        "Loss of use, depreciation, or a reduction in the market value of the vehicle after repairs.",
        "Theft of the vehicle by a person to whom you gave the keys, for example a buyer on a "
        "test drive who does not return it, unless you have the fraudulent sale extension.",
        "Damage caused by water entering the engine because the vehicle was driven through a "
        "flooded road.",
        "Any loss outside the Republic of South Africa, Botswana, Eswatini, Lesotho, Namibia, "
        "Zimbabwe and Mozambique.",
    )

    d.h1("Claims", new_page=True)
    d.clauses(
        "Report a hijacking or theft to the South African Police Service within 24 hours and to "
        "us as soon as possible. Give us the case number.",
        "Report an accident to the police within 24 hours if anyone was injured, or within the "
        "next business day if not, as the National Road Traffic Act requires.",
        "Report every claim to us within 30 days of the event.",
        "At the scene of an accident, do not admit liability. Take photographs and write down "
        "the other driver's name, ID number, licence number, insurer and vehicle registration.",
        "We decide whether a vehicle is a write-off. If the repair cost is more than 70% of the "
        "retail value, the vehicle will normally be written off.",
        "We pay for repairs directly to the approved repairer. You pay the excess to the "
        "repairer when you collect the vehicle.",
        "A stolen or hijacked vehicle that is not recovered within 21 days is treated as a "
        "write-off and settled at retail value.",
    )
    d.h1("Premiums, grace period and cancellation")
    d.clauses(
        "Premiums are payable monthly in advance. If a monthly premium is not received, you have "
        "a grace period of 15 days to pay it, during which you remain covered.",
        "We review premiums once a year and give you 31 days' notice of any change.",
        "You may cancel at any time. If you cancel within 31 days of receiving your policy and "
        "have not claimed, we refund all premiums paid.",
        "A claim-free discount of 5% per year applies after the first claim-free year, up to 25%.",
    )
    complaints(d)
    privacy_notice(d)
    regulatory(d)

    _rating_annexure(d)
    _model_groups(d)
    _examples(d)
    d.annexure("D", "Specimen policy schedules")
    schedules = specimen_schedules(d, "KRM", 30, _schedule_sections)

    case("What is the basic excess on a comprehensive motor claim?", f"5% of the claim, minimum {money(BASIC_MIN)}", d,
         f"5% of the claim, minimum {money(BASIC_MIN)}")
    case("What additional excess does a driver under 25 pay?", money(YOUNG_DRIVER), d,
         f"Additional {money(YOUNG_DRIVER)}")
    case("Above what vehicle value is a tracking device required?", f"Retail value above {money(TRACKER_VALUE)}", d,
         f"more than {money(TRACKER_VALUE)}, an approved tracking device must be installed")
    case("How soon must a hijacking be reported to the police?", "Within 24 hours", d,
         "Report a hijacking or theft to the South African Police Service within 24 hours")
    case("How many days of car hire are covered?", f"Up to {CAR_HIRE_DAYS} days (Group B), if the option is on the schedule", d,
         f"for up to {CAR_HIRE_DAYS} days")
    case("When is a stolen car treated as a write-off?", "If it is not recovered within 21 days", d,
         "not recovered within 21 days is treated as a write-off")
    case("What is the windscreen excess?", f"25% of the claim, minimum {money(WINDSCREEN_MIN)}", d,
         f"25% of the claim, minimum {money(WINDSCREEN_MIN)}")
    case("At what repair cost is a car normally written off?", "When repairs cost more than 70% of the retail value", d,
         "more than 70% of the retail value")
    case("What blood alcohol level voids motor cover?", "Above 0.05 grams per 100 millilitres", d,
         "0.05 grams per 100 millilitres")
    case("When is a written-off car replaced with a new one?", "If it is under 12 months old and has done fewer than 10,000 km", d,
         "fewer than 10,000 km")
    case("Which rating group is the Toyota Hilux 2.8 GD-6 double cab in?", "Group D", d, "Hilux 2.8 GD-6 double cab")
    for sched in schedules[:3]:
        vehicle = sched["rows"][0][0]
        case(f"Which vehicle is insured on policy {sched['number']}?", vehicle.removeprefix("Comprehensive: "), d, sched["number"])
    return d


def _schedule_sections(rng):
    make, model, group = rng.choice(MODELS)
    value = {"A": (150_000, 260_000), "B": (230_000, 380_000), "C": (380_000, 650_000),
             "D": (550_000, 950_000), "E": (750_000, 2_400_000)}[group]
    retail = rng.randrange(value[0], value[1], 5_000)
    rate = {"A": 3.1, "B": 3.4, "C": 3.9, "D": 4.6, "E": 5.4}[group] / 100 / 12
    rows = [(f"Comprehensive: {make} {model}", retail, round(retail * rate, 2))]
    if rng.random() < 0.6:
        rows.append(("Car hire (Group B, 30 days)", "30 days", 89.00))
    if rng.random() < 0.5:
        rows.append(("Credit shortfall", "25% of retail value", round(retail * 0.00012, 2)))
    rows.append(("Third party liability", "R5,000,000", 0.00))
    return rows


def _model_groups(d: Doc) -> None:
    d.annexure("C", "Vehicle rating groups")
    d.p(
        "Every vehicle is placed in a rating group that reflects its repair cost, parts prices "
        "and theft risk. The groups below apply to the models listed; models not listed are "
        "grouped by the underwriter.",
    )
    d.table(["Group", "Description"], [[g, t] for g, t in GROUP_NOTES.items()], [0.15, 0.85])
    d.table(
        ["Make", "Model", "Rating group"],
        [[mk, md, g] for mk, md, g in MODELS],
        [0.25, 0.55, 0.20],
    )


def _rating_annexure(d: Doc) -> None:
    d.annexure("A", "Indicative comprehensive premium rates")
    d.p(
        "Indicative monthly premium as a percentage of retail value per year, for a regular "
        "driver aged 35 with no claims in 3 years, a tracking device where required and an "
        "overnight garage. Rates are divided by 12 for the monthly premium.",
    )
    groups = [("Hatchback", 3.1), ("Sedan", 3.4), ("SUV", 3.9), ("Bakkie (double cab)", 4.6), ("Luxury and performance", 5.4)]
    for name, base in groups:
        d.h3(name)
        rows = []
        for prov in PROVINCES:
            f = 1 + (PROVINCES.index(prov) % 3) * 0.08
            rows.append([prov] + [f"{base * f * age:.2f}%" for age in (1.45, 1.0, 0.92, 1.1)])
        d.table(["Province", "Age 18–24", "Age 25–44", "Age 45–64", "Age 65+"], rows, [0.32, 0.17, 0.17, 0.17, 0.17])


def _examples(d: Doc) -> None:
    d.annexure("B", "Worked claim examples")
    for n in range(1, 131):
        who = person()
        town, prov = place()
        kind = n % 5
        if kind == 0:
            repair = RNG.randrange(18_000, 120_000, 500)
            ex = basic_excess(repair)
            d.h3(f"Example {n}: collision repaired at an approved repairer")
            d.p(
                f"{who} rear-ends another car at a traffic light in {town}, {prov}. The approved "
                f"repairer quotes {money(repair)}. The basic excess is 5% of the claim with a "
                f"minimum of {money(BASIC_MIN)}, so it is {money(ex)}.",
                f"We pay the repairer {money(repair - ex)}; {who.split()[0]} pays {money(ex)} on collection.",
            )
        elif kind == 1:
            repair = RNG.randrange(15_000, 70_000, 500)
            ex = basic_excess(repair) + YOUNG_DRIVER
            d.h3(f"Example {n}: young driver")
            d.p(
                f"The 21-year-old son of {who} skids into a pole in {town}. Repairs cost "
                f"{money(repair)}. Because the driver is under 25, the young driver excess of "
                f"{money(YOUNG_DRIVER)} is added to the basic excess of {money(basic_excess(repair))}.",
                f"Total excess {money(ex)}; we pay {money(repair - ex)}.",
            )
        elif kind == 2:
            glass = RNG.randrange(2_500, 14_000, 100)
            ex = max(WINDSCREEN_MIN, round(glass * WINDSCREEN_PCT))
            d.h3(f"Example {n}: cracked windscreen")
            d.p(
                f"A stone cracks the windscreen of {who}'s car on the N1 near {town}. The "
                f"replacement costs {money(glass)}. The glass excess is 25% with a minimum of "
                f"{money(WINDSCREEN_MIN)}: {money(ex)}.",
                f"We pay {money(glass - ex)}.",
            )
        elif kind == 3:
            value = RNG.randrange(380_000, 900_000, 5_000)
            d.h3(f"Example {n}: hijacking of a vehicle without an active tracker")
            d.p(
                f"{who}'s SUV, with a retail value of {money(value)}, is hijacked in {town}. The "
                f"tracking subscription had lapsed two months earlier. Because the retail value is "
                f"above {money(TRACKER_VALUE)}, an active tracking device was required.",
                "Outcome: the hijacking claim is declined. Trauma counselling is still offered.",
            )
        else:
            value = RNG.randrange(120_000, 340_000, 5_000)
            ex = max(7_500, round(value * 0.10))
            d.h3(f"Example {n}: theft, not recovered")
            d.p(
                f"{who}'s hatchback is stolen from a shopping centre parking lot in {town} and is "
                f"not recovered within 21 days. The retail value in the TransUnion guide is "
                f"{money(value)}. The theft excess is 10% with a minimum of R7,500: {money(ex)}.",
                f"Settlement: {money(value - ex)}, paid to the finance house first if money is owed.",
            )
