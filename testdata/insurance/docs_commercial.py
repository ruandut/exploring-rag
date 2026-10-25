"""KR-CL-001 — Business Insurance Policy Wording (small and medium enterprises)."""

from builder import Doc
from common import (
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

OCCUPATIONS = [
    ("Offices: accountants, attorneys, consultants", "1", "Standard"),
    ("Medical and dental practices", "1", "Standard"),
    ("Hair and beauty salons", "2", "Standard"),
    ("Clothing and footwear retail", "2", "Standard"),
    ("Pharmacies", "3", "Alarm with armed response required"),
    ("Cellphone and electronics retail", "4", "Refer: high theft risk, safe and CCTV required"),
    ("Jewellers", "5", "Refer: specialist cover only"),
    ("Restaurants with deep fryers", "3", "Automatic fire suppression over fryers required"),
    ("Bakeries", "3", "Oven and extraction cleaning log required"),
    ("Hardware and building supplies", "3", "Standard"),
    ("Liquor stores and taverns", "4", "Refer: cash and theft controls required"),
    ("Panel beaters and motor workshops", "4", "Refer: spray booth fire rating"),
    ("Printing and packaging", "3", "Standard, paper stock fire load reviewed"),
    ("Furniture manufacturing", "4", "Dust extraction and sprinklers above R5,000,000"),
    ("Veterinary clinics", "2", "Standard"),
    ("Crèches and pre-schools", "2", "Liability referred above 50 children"),
    ("Guest houses up to 10 rooms", "2", "Standard"),
    ("Spaza shops and convenience stores", "3", "Burglar bars and safe required"),
    ("Fireworks, explosives and gas filling", "6", "Decline"),
    ("Nightclubs", "6", "Decline"),
]

BI_PERIOD_MONTHS = 12
MONEY_SAFE = 50_000
MONEY_TRANSIT = 25_000
PUBLIC_LIABILITY = 10_000_000
GIT_LIMIT = 250_000

INDUSTRIES = [
    "a bakery", "a hardware store", "an accounting practice", "a hair salon", "a restaurant",
    "a pharmacy", "a car-parts wholesaler", "a printing business", "a veterinary clinic",
    "a clothing boutique",
]


def build() -> Doc:
    d = Doc(
        filename="KR-CL-001-business-insurance-policy-wording.pdf",
        title="Business Insurance Policy Wording",
        subtitle="For small and medium enterprises",
        code="KR-CL-001",
        audience="Business policyholders and intermediaries",
    )
    how_to_read(d, "Kestrel Ridge Business Insurance Policy")
    d.h1("Definitions", new_page=True)
    terms = [
        ("Business", "The business activities described on the schedule and no other."),
        ("Damage", "Physical loss, destruction or damage."),
        ("Gross profit", "Turnover less the cost of goods and materials used, as defined in the business interruption section."),
        ("Indemnity period", "The period starting on the date of the damage during which the results of the business are affected, but not longer than the period shown on the schedule."),
        ("Money", "Cash, bank notes, cheques, postal orders, vouchers and revenue stamps belonging to the business."),
        ("Premises", "The buildings and land at the addresses shown on the schedule that you use for the business."),
        ("Stock", "Goods held for sale, raw materials and work in progress."),
        ("Employee", "Any person under a contract of service with you, including temporary staff."),
        ("Turnover", "Money paid or payable to you for goods sold and services rendered in the course of the business."),
    ]
    d.table(["Term", "Meaning"], [[t, m] for t, m in terms], [0.22, 0.78])

    sections = [
        ("Fire", [
            "We cover damage to the buildings, plant, machinery, stock and contents at the premises caused by fire, lightning, explosion, storm, wind, water, hail, snow, earthquake and impact.",
            "The premises must have at least the fire-fighting equipment required by the local fire department, serviced at least once every 12 months by a SAQCC-registered company.",
            "If fire-fighting equipment was not serviced within the last 12 months, we may reduce a fire claim by up to 25%.",
            "Stock declarations: if you choose a stock declaration basis, you must declare the value of stock monthly. Underdeclaration reduces claims proportionally.",
        ]),
        ("Business interruption", [
            "If the business is interrupted because of damage covered under the Fire section, we pay the loss of gross profit caused by the reduced turnover and the increased cost of working during the indemnity period.",
            f"The maximum indemnity period is {BI_PERIOD_MONTHS} months unless the schedule shows a longer period.",
            "A time excess of 72 hours applies: we do not pay for loss of gross profit in the first 72 hours after the damage.",
            "Loss caused by the failure of the public electricity supply, including scheduled load-shedding, is not covered unless the schedule includes the utility supply extension, which pays after the supply has been interrupted for more than 24 consecutive hours.",
            "Prevention of access: we pay loss of gross profit when access to the premises is prevented by damage to nearby property, up to 10% of the business interruption sum insured.",
        ]),
        ("Office contents", [
            "We cover furniture, fittings, office equipment and computers at the premises against the Fire section events and against theft involving forcible entry.",
            "Computers and portable electronic equipment older than 5 years are settled at market value.",
        ]),
        ("Theft", [
            "We cover theft of contents and stock from the premises following forcible and violent entry or exit, or following armed robbery.",
            "Theft by employees is not covered under this section; see Fidelity guarantee.",
            "The premises must have the security shown on the schedule. If a required alarm is not working or not armed when the premises are closed, the theft claim will not be paid.",
        ]),
        ("Money", [
            f"Money in a locked safe at the premises outside business hours is covered up to {money(MONEY_SAFE)}.",
            f"Money in transit to or from the bank is covered up to {money(MONEY_TRANSIT)} per trip. Amounts above this must be transported by a registered cash-in-transit company.",
            "Money left on the premises outside business hours and not in a locked safe is covered up to R5,000.",
            "Losses must be reported to the police within 24 hours, and you must keep a daily record of money received and banked.",
        ]),
        ("Goods in transit", [
            f"We cover goods belonging to you, or for which you are responsible, while in transit in your own vehicles within South Africa, up to {money(GIT_LIMIT)} per load.",
            "Goods must be secured with straps or tarpaulins, and a vehicle carrying goods must not be left unattended unless it is locked and parked in a secure area.",
            "Theft from an unattended vehicle overnight is not covered unless the vehicle was in a locked building or a fenced, guarded yard.",
        ]),
        ("Public liability", [
            f"We cover your legal liability for accidental injury to people and damage to their property arising from the business, up to {money(PUBLIC_LIABILITY)} per event.",
            "Product liability is included for products you supply in South Africa. Products exported to the United States of America or Canada are excluded.",
            "Defence costs incurred with our consent are paid in addition to the limit.",
        ]),
        ("Fidelity guarantee", [
            "We cover loss of money or goods caused by theft or fraud by an employee, discovered during the period of insurance and within 12 months of the act.",
            "You must check employees' references and perform criminal record checks on employees who handle money.",
            "Once you discover that an employee was dishonest, cover for that employee ends immediately.",
        ]),
        ("Electronic equipment", [
            "We cover accidental damage to computers, servers, point-of-sale terminals and similar equipment, including damage from power surges.",
            "Equipment must be connected to surge protection. Without surge protection, power surge claims are subject to an additional excess of 20%.",
            "Data reinstatement costs are covered up to R50,000 per event, but not cyber attacks or ransomware, which need separate cyber cover.",
        ]),
    ]
    for name, items in sections:
        d.h1(f"Section: {name}", new_page=name in ("Fire", "Money", "Public liability"))
        d.clauses(*items)

    d.h1("Excesses", new_page=True)
    d.table(
        ["Section", "Excess"],
        [
            ["Fire", "R5,000 or 2.5% of the claim, whichever is more"],
            ["Business interruption", "72-hour time excess"],
            ["Office contents and theft", "R3,500"],
            ["Money", "R2,500"],
            ["Goods in transit", "10% of the claim, minimum R5,000"],
            ["Public liability", "R10,000 per event"],
            ["Fidelity guarantee", "R15,000"],
            ["Electronic equipment", "R2,500, plus 20% if no surge protection"],
        ],
        [0.45, 0.55],
    )
    d.h1("General conditions")
    d.clauses(
        "The premises must be kept in good repair and you must comply with all occupational "
        "health and safety, fire and municipal regulations.",
        "If the business changes, moves, is sold or stops trading, you must tell us within 30 days.",
        "Premiums are adjusted at renewal using your declared turnover, wages and stock values. "
        "You must send us your declarations within 60 days of your financial year-end.",
        "Claims must be reported within 30 days. Business interruption claims must be "
        "substantiated by your accountant within 6 months of the end of the indemnity period.",
        "Monthly premiums have a 15-day grace period.",
    )
    complaints(d)
    privacy_notice(d)
    regulatory(d)

    d.annexure("A", "Occupation classes")
    d.p(
        "Every business is placed in an occupation class from 1 (lowest risk) to 6 (declined) "
        "based on its fire, theft and liability risk. The class sets the base rate and any "
        "special conditions.",
    )
    d.table(["Occupation", "Class", "Acceptance and conditions"], [list(o) for o in OCCUPATIONS], [0.45, 0.1, 0.45])
    d.annexure("B", "Worked claim examples")
    for n in range(1, 91):
        who = person()
        town, prov = place()
        biz = RNG.choice(INDUSTRIES)
        if n % 3 == 0:
            turnover = RNG.randrange(150_000, 900_000, 10_000)
            margin = RNG.choice([0.35, 0.4, 0.45, 0.5])
            weeks = RNG.randrange(3, 20)
            lost = round(turnover * 12 / 52 * weeks * margin)
            d.h3(f"Example {n}: fire closes {biz}")
            d.p(
                f"A kitchen fire closes {biz} owned by {who} in {town}, {prov}, for {weeks} weeks. "
                f"Average monthly turnover is {money(turnover)} and the gross profit rate is "
                f"{int(margin * 100)}%. The first 72 hours are excluded by the time excess.",
                f"Approximate loss of gross profit: {money(turnover)} × 12 ÷ 52 × {weeks} weeks × "
                f"{int(margin * 100)}% = {money(lost)}, less the 72-hour time excess.",
            )
        elif n % 3 == 1:
            cash = RNG.randrange(30_000, 120_000, 1_000)
            paid = min(cash, MONEY_SAFE)
            d.h3(f"Example {n}: safe stolen after hours")
            d.p(
                f"Thieves break into {biz} in {town} at night and remove the safe, which held "
                f"{money(cash)}. Money in a locked safe outside business hours is covered up to "
                f"{money(MONEY_SAFE)}.",
                f"Settlement: {money(paid)} − R2,500 excess = {money(paid - 2500)}.",
            )
        else:
            load = RNG.randrange(60_000, 400_000, 5_000)
            paid = min(load, GIT_LIMIT)
            ex = max(5_000, round(paid * 0.1))
            d.h3(f"Example {n}: goods stolen in transit")
            d.p(
                f"A delivery bakkie of {biz} is hijacked on its way from {town} with stock worth "
                f"{money(load)}. The goods in transit limit is {money(GIT_LIMIT)} per load.",
                f"Settlement: {money(paid)} − {money(ex)} excess = {money(paid - ex)}.",
            )

    case("What is the maximum business interruption indemnity period?", f"{BI_PERIOD_MONTHS} months unless the schedule says longer", d,
         f"The maximum indemnity period is {BI_PERIOD_MONTHS} months")
    case("How much money in a locked safe after hours is covered?", money(MONEY_SAFE), d,
         f"Money in a locked safe at the premises outside business hours is covered up to {money(MONEY_SAFE)}")
    case("What time excess applies to business interruption?", "72 hours", d, "A time excess of 72 hours applies")
    case("What is the public liability limit for businesses?", f"{money(PUBLIC_LIABILITY)} per event", d,
         "arising from the business, up to")
    case("Is load-shedding covered under business interruption?", "Only with the utility supply extension, after more than 24 consecutive hours", d,
         "more than 24 consecutive hours")
    case("How often must fire-fighting equipment be serviced?", "At least once every 12 months by a SAQCC-registered company", d,
         "serviced at least once every 12 months")
    case("Are exports to the USA covered under product liability?", "No, products exported to the USA or Canada are excluded", d,
         "Products exported to the United States of America or Canada are excluded")
    case("What occupation class are jewellers?", "Class 5 — refer, specialist cover only", d, "Jewellers")
    d.annexure("C", "Specimen policy schedules")
    for sched in specimen_schedules(d, "KRB", 25, _schedule_sections)[:2]:
        fire = sched["rows"][0][1]
        case(f"What is the fire sum insured on policy {sched['number']}?", money(fire), d, sched["number"])
    return d


def _schedule_sections(rng):
    fire = rng.randrange(800_000, 12_000_000, 50_000)
    gp = rng.randrange(500_000, 6_000_000, 50_000)
    rows = [
        ("Fire: buildings, contents and stock", fire, round(fire * rng.uniform(0.00010, 0.00018), 2)),
        ("Business interruption: gross profit (12 months)", gp, round(gp * rng.uniform(0.00006, 0.00011), 2)),
        ("Office contents", rng.randrange(50_000, 400_000, 10_000), round(rng.uniform(120, 480), 2)),
        ("Money", "R50,000 safe / R25,000 transit", round(rng.uniform(60, 180), 2)),
        ("Public liability", "R10,000,000", round(rng.uniform(150, 420), 2)),
    ]
    if rng.random() < 0.5:
        rows.append(("Goods in transit", "R250,000 per load", round(rng.uniform(140, 380), 2)))
    if rng.random() < 0.4:
        rows.append(("Fidelity guarantee", rng.randrange(50_000, 500_000, 25_000), round(rng.uniform(90, 260), 2)))
    return rows
