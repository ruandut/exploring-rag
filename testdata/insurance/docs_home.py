"""KR-PL-001 — Household Policy Wording (Buildings, Contents, All Risks, Liability)."""

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

BUILDINGS_EXCESS = 2500
CONTENTS_EXCESS = 1500
GEYSER_EXCESS = 2000
ALL_RISKS_EXCESS = 750
POWER_SURGE_LIMIT = 25000
LIABILITY_LIMIT = 5_000_000
UNOCCUPIED_DAYS = 60
EARLY_CLAIM_EXCESS = 1000  # extra excess for claims in the first 90 days


def build() -> Doc:
    d = Doc(
        filename="KR-PL-001-household-policy-wording.pdf",
        title="Household Insurance Policy Wording",
        subtitle="Buildings · Household Contents · All Risks · Personal Liability",
        code="KR-PL-001",
    )
    how_to_read(d, "Kestrel Ridge Household Insurance Policy")

    # --- definitions ---------------------------------------------------------------------
    d.h1("Definitions", new_page=True)
    d.p("In this policy the following words have the meanings below, wherever they appear.")
    terms = [
        ("Accidental damage", "Sudden, unexpected and unintended physical damage caused by an external force."),
        ("Buildings", "The private dwelling at the risk address, including its outbuildings, swimming pool, tennis court, boundary walls, gates, fixed solar installations, paving and driveways, and the fixtures and fittings that belong to you as owner."),
        ("Business day", "Any day other than a Saturday, Sunday or South African public holiday."),
        ("Contents", "Household goods and personal effects that belong to you or members of your household, or for which you are legally responsible, while inside the buildings at the risk address. Contents does not include motor vehicles, caravans, trailers or watercraft."),
        ("Excess", "The first amount of each claim that you must pay yourself. The excesses that apply are shown in this wording and on your schedule."),
        ("Forcible entry", "Entry into the buildings by force and violence that leaves visible signs of damage at the point of entry."),
        ("Geyser", "A fixed water heater, including electric, solar and heat-pump geysers, together with its pipes, valves, drip tray and thermostat."),
        ("Household", "You, your spouse or life partner, and your children and other relatives who normally live with you, as well as domestic employees while they live at the risk address."),
        ("Market value", "The cost of replacing an item with one of the same type and condition, taking wear and tear into account."),
        ("Period of insurance", "The period from the start date on the schedule to the date the policy is cancelled, renewed monthly or ends for any reason."),
        ("Power surge", "A sudden increase in electrical voltage, including one caused by lightning or the restoration of supply after load-shedding."),
        ("Replacement value", "The cost of replacing an item with a new item of the same or nearest equivalent kind, without any deduction for wear and tear."),
        ("Risk address", "The address of the insured property shown on your schedule."),
        ("Schedule", "The document that shows your personal details, the sections you have chosen, your sums insured, premium, excesses and endorsements."),
        ("Subsidence", "The downward movement of the ground beneath the buildings, other than settlement or movement of made-up ground."),
        ("Sum insured", "The maximum amount we will pay under a section or item, as shown on the schedule."),
        ("Unoccupied", "The buildings are not lived in overnight by you or a member of your household with your permission."),
        ("Valuables", "Jewellery, watches, furs, works of art, collections of stamps, coins or medals, and items of gold, silver or other precious metals."),
        ("We, us, our", "Kestrel Ridge Insurance Limited (a fictional insurer)."),
        ("You, your", "The policyholder named in the schedule."),
    ]
    d.table(["Term", "Meaning"], [[t, m] for t, m in terms], [0.22, 0.78])

    # --- buildings -----------------------------------------------------------------------
    d.h1("Section A: Buildings", new_page=True)
    d.h2("What we cover")
    d.clauses(
        "We cover the buildings against loss or damage caused by fire, lightning, explosion, "
        "storm, wind, hail, snow, flood, earthquake, theft or attempted theft involving forcible "
        "entry, malicious damage, impact by vehicles, animals, falling trees or aircraft, and "
        "the bursting or overflowing of water tanks, pipes and apparatus.",
        "We pay the reasonable cost of repairing or rebuilding the damaged part of the buildings "
        "to the condition it was in when new, but not better, up to the sum insured.",
        ("Additional costs we pay in connection with a valid buildings claim:", [
            "professional fees of architects, engineers and quantity surveyors, up to 15% of the claim;",
            "the cost of removing debris and demolishing damaged parts, up to 10% of the claim;",
            "rent for alternative accommodation while the buildings cannot be lived in, up to 25% of the buildings sum insured and for no longer than 6 months;",
            "the cost of complying with municipal building regulations when rebuilding.",
        ]),
    )
    d.h2("Geysers")
    d.clauses(
        "We cover the cost of repairing or replacing a geyser that bursts or leaks, and the "
        "resulting damage to the buildings. Damage to contents caused by the water is covered "
        "under Section B if you have contents cover with us.",
        f"A geyser excess of {money(GEYSER_EXCESS)} applies to each geyser claim instead of the "
        "basic buildings excess.",
        "When a geyser must be replaced, the replacement must comply with SANS 10254, which "
        "includes fitting a drip tray, a vacuum breaker and a pressure-control valve. We pay "
        "for these compliance items as part of the claim.",
        "We do not pay for a geyser that has simply worn out, for example where it leaks because "
        "of rust over a long period, or for repairs to the solar panels of a solar geyser unless "
        "they were damaged by a covered event.",
        "We cover a maximum of two geyser claims in any 12-month period. After that you can "
        "still claim for the resulting water damage, but not for replacing the geyser itself.",
    )
    d.h2("Subsidence, landslip and heave")
    d.clauses(
        "Subsidence, landslip and heave are covered only if the schedule says so. If you have "
        "this extension, an additional excess of 10% of the claim, with a minimum of R10,000, "
        "applies.",
        "We do not cover damage caused by the normal settlement, shrinkage or expansion of the "
        "buildings, or by faulty design, defective foundations or poor workmanship.",
        "We do not cover subsidence damage to swimming pools, paving, boundary walls or gates "
        "unless the dwelling itself is damaged at the same time by the same cause.",
    )
    d.h2("Roofs and thatch")
    d.clauses(
        "If the main roof of the dwelling is thatched, or more than 20% of the total roof area "
        "of all buildings is thatch, you must tell us. We charge a higher premium for thatch, "
        "and a lightning conductor that complies with SANS 10313 must be installed.",
        "If a thatched roof is damaged by fire or lightning and there is no compliant lightning "
        "conductor, we will pay only 50% of the claim.",
        "Wear and tear of roof coverings, including leaking roofs that have not been maintained, "
        "is not covered. Damage to the interior caused by rain entering through a roof damaged "
        "by storm or hail is covered.",
    )
    d.h2("What we do not cover under Section A")
    d.clauses(
        "Wear and tear, gradual deterioration, rust, rot, mould and damp.",
        "Damage that happens while the buildings have been unoccupied for more than "
        f"{UNOCCUPIED_DAYS} consecutive days, unless you told us in advance and we agreed in writing.",
        "Damage to retaining walls, unless the retaining wall collapses as a direct result of a "
        "flood or storm and was designed by an engineer.",
        "Damage caused by water seeping slowly from pipes over a long period, or by rising damp.",
        "Theft or malicious damage by people living at the risk address or by your tenants.",
        "Damage caused by building work, alterations or repairs being done at the risk address.",
    )

    # --- contents ------------------------------------------------------------------------
    d.h1("Section B: Household contents", new_page=True)
    d.h2("What we cover")
    d.clauses(
        "We cover your contents against loss or damage caused by the same events as Section A, "
        "while the contents are in the buildings at the risk address.",
        "We pay the replacement value of items that are lost or damaged beyond repair, or the "
        "reasonable cost of repair, at our option. Clothing and household linen are settled at "
        "market value.",
        "We may choose to replace an item through one of our approved suppliers instead of "
        "paying cash. If you prefer a cash settlement, we pay the amount it would have cost us "
        "through our supplier.",
    )
    d.h2("Theft")
    d.clauses(
        "Theft is covered only if there was forcible entry into the buildings, or if the theft "
        "involved violence or the threat of violence against a person at the risk address.",
        "You must report any theft, robbery or malicious damage to the South African Police "
        "Service within 48 hours of discovering it and give us the case number.",
        "Theft from an open area of the property, such as a garden, stoep or open carport, is "
        "covered only for garden furniture and equipment, and only up to R10,000 per claim.",
        "Theft from an outbuilding that is not connected to the main dwelling is limited to "
        "R15,000 per claim.",
    )
    d.h2("Security requirements")
    d.p(
        "The security you must have depends on your contents sum insured. These requirements "
        "are warranties: if a required measure is not in place and working when a theft "
        "happens, we will not pay the theft claim.",
    )
    d.table(
        ["Contents sum insured", "Minimum security required"],
        [
            ["Up to R150,000", "Burglar bars on all opening windows, and security gates on all external doors"],
            ["R150,001 to R500,000", "As above, plus a monitored alarm system linked to an armed response company"],
            ["Above R500,000", "As above, plus an electric fence or perimeter beams, and the alarm must be armed whenever the dwelling is unoccupied"],
        ],
        [0.3, 0.7],
    )
    d.h2("Power surge and load-shedding")
    d.clauses(
        "We cover damage to electrical appliances, motors and electronic equipment caused by a "
        f"power surge, up to {money(POWER_SURGE_LIMIT)} per event.",
        "Damage caused when electricity is restored after load-shedding is treated as a power "
        "surge. Failure of equipment because of normal wear, or damage while equipment is being "
        "repaired, is not covered.",
        "We may ask for a report from a qualified technician confirming that a power surge caused "
        "the damage.",
    )
    d.h2("Contents limits")
    d.table(
        ["Item", "Limit"],
        [
            ["Valuables in total", "One third of the contents sum insured, unless specified under All Risks"],
            ["Any single valuable item", "R25,000, unless specified under All Risks"],
            ["Cash and bank cards", "R3,000 per claim"],
            ["Documents and title deeds (cost of replacing)", "R5,000 per claim"],
            ["Food in freezers spoiled by power failure", "R5,000 per claim"],
            ["Guests' belongings", "R7,500 per claim"],
            ["Contents temporarily removed (e.g. a child at university)", "15% of the contents sum insured"],
        ],
        [0.55, 0.45],
    )
    d.h2("Underinsurance (average)")
    d.p(
        "If your contents are worth more than the sum insured when a loss happens, you are "
        "underinsured and carry part of the loss yourself. We reduce the claim in the same "
        "proportion that the sum insured bears to the actual value. For example, if your "
        "contents are worth R400,000 but insured for R300,000, we pay 75% of each claim.",
    )

    # --- all risks -----------------------------------------------------------------------
    d.h1("Section C: All risks", new_page=True)
    d.clauses(
        "All risks cover protects items you take with you, such as jewellery, cameras, cellphones, "
        "laptops, bicycles and sports equipment, anywhere in the Republic of South Africa, "
        "Botswana, Eswatini, Lesotho, Namibia and Zimbabwe.",
        "Cover outside these countries is limited to 90 days per trip.",
        "Unspecified items are covered up to the unspecified all risks sum insured on your "
        "schedule, with a limit of R7,500 for any one item. Items worth more than this must be "
        "specified individually with a valuation certificate or proof of purchase not older "
        "than 24 months.",
        f"The all risks excess is {money(ALL_RISKS_EXCESS)} per claim, or 10% of the claim if more, "
        "for cellphones and laptops.",
        "Theft from an unattended vehicle is covered only if the items were locked in the boot "
        "or a closed glove compartment and there are visible signs of forced entry into the vehicle.",
        "We do not cover items left unattended in a public place, damage caused by cleaning or "
        "repairs, or electrical or mechanical breakdown.",
    )

    # --- liability -----------------------------------------------------------------------
    d.h1("Section D: Personal liability")
    d.clauses(
        "We cover the amounts you and your household become legally liable to pay to other "
        "people for accidental death, bodily injury or illness, or for accidental damage to "
        f"their property, up to {money(LIABILITY_LIMIT)} per event.",
        "This includes liability as the owner or occupier of the risk address, liability as a "
        "tenant for damage to the landlord's buildings, and liability arising from your pets.",
        "We do not cover liability arising from your business or profession, from motor "
        "vehicles, from contracts you entered into, or towards members of your household.",
        "You must not admit liability or make any offer to settle without our written consent.",
    )

    # --- excess & premium ----------------------------------------------------------------
    d.h1("Excesses", new_page=True)
    d.p(
        "The table below shows the excesses that apply unless your schedule says otherwise. "
        "Where more than one excess applies to the same claim, they are added together.",
    )
    d.table(
        ["Claim type", "Excess"],
        [
            ["Buildings (basic)", money(BUILDINGS_EXCESS)],
            ["Geyser", money(GEYSER_EXCESS)],
            ["Subsidence and landslip (if covered)", "10% of the claim, minimum R10,000"],
            ["Contents (basic)", money(CONTENTS_EXCESS)],
            ["Power surge", money(CONTENTS_EXCESS)],
            ["All risks (general)", money(ALL_RISKS_EXCESS)],
            ["All risks: cellphones and laptops", f"{money(ALL_RISKS_EXCESS)} or 10% of the claim, whichever is more"],
            ["Personal liability", "R2,500"],
            ["Any claim in the first 90 days of a new policy", f"Additional {money(EARLY_CLAIM_EXCESS)}"],
        ],
        [0.6, 0.4],
    )
    d.h1("Premiums")
    d.clauses(
        "Premiums are payable monthly in advance by debit order, unless your schedule shows an "
        "annual premium.",
        "If we do not receive a monthly premium, you have a grace period of 15 days from the "
        "due date to pay it. You remain covered during the grace period. If the premium is "
        "still unpaid after the grace period, the policy lapses from the end of the last month "
        "for which we received a premium.",
        "If a debit order fails, we will try to collect the premium once more within the grace "
        "period and will tell you by SMS or email.",
        "We may change your premium, excesses or cover by giving you at least 31 days' written "
        "notice. Premiums are usually reviewed once a year on the anniversary of your policy.",
        "No-claim bonus: if you have not claimed for 3 consecutive years, we reduce your contents "
        "premium by 10%. One claim reduces the bonus to zero.",
    )
    d.h1("Cancellation and cooling-off")
    d.clauses(
        "You may cancel this policy at any time by telling us. Cancellation takes effect from "
        "the date you choose, but not earlier than the date you tell us.",
        "If you cancel within 31 days of receiving your policy documents and have not claimed, "
        "we refund all premiums paid. This is your cooling-off right.",
        "We may cancel the policy by giving you 31 days' written notice to your last known "
        "email or postal address. We may cancel immediately if you commit fraud.",
    )

    # --- claims --------------------------------------------------------------------------
    d.h1("How to claim", new_page=True)
    d.clauses(
        "Report any claim to us as soon as possible, and in any event within 30 days of the "
        "event. We may reject a claim that is reported later than this if the delay has "
        "prejudiced our ability to assess it.",
        "Take reasonable steps to prevent further loss or damage, for example by switching off "
        "the water supply after a geyser bursts or covering a damaged roof.",
        "Do not dispose of damaged items or start permanent repairs until we have had the "
        "chance to inspect them, unless we agree otherwise. Emergency repairs up to R5,000 may "
        "be done without our consent.",
        "Give us all the information and documents we reasonably ask for, such as quotes, "
        "invoices, photographs, proof of ownership and the police case number.",
        "For claims above R50,000, we may appoint an assessor or loss adjuster to inspect the "
        "damage. You must give them access to the risk address.",
    )
    d.h2("What happens after you claim")
    d.clauses(
        "We acknowledge your claim within 2 business days and tell you who is handling it.",
        "We will decide whether to accept your claim within 10 business days of receiving all "
        "the information we need. If we need more time, we tell you why.",
        "If we reject your claim, we tell you in writing why, which policy clause we relied on, "
        "and how to ask us to reconsider. You have 90 days from our letter to ask us to "
        "reconsider the decision, and 6 months from the end of those 90 days, or from our "
        "response to your request, to start legal proceedings.",
        "We pay accepted claims within 5 business days of agreeing the amount with you.",
    )

    # --- general exclusions & conditions -------------------------------------------------
    d.h1("General exclusions")
    d.p("These exclusions apply to every section of the policy.")
    d.clauses(
        "War, invasion, civil war, rebellion, revolution, insurrection or military power.",
        "Riot, strike, civil commotion, public disorder and terrorism. In South Africa these "
        "risks are covered by SASRIA SOC Limited, and SASRIA cover is added to your policy "
        "automatically for a separate small premium shown on your schedule.",
        "Nuclear material, radioactive contamination and nuclear weapons.",
        "Pollution and contamination, unless caused by a sudden and accidental event.",
        "Loss of data, computer viruses and failure of electronic equipment to recognise a date.",
        "Any loss caused deliberately by you or a member of your household.",
        "Consequential loss, such as loss of income or loss of enjoyment, unless a section "
        "specifically covers it.",
    )
    d.h1("General conditions")
    d.clauses(
        "You must take all reasonable precautions to prevent loss or damage and keep insured "
        "property in a good state of repair.",
        "If any claim is fraudulent in any respect, we reject the whole claim, may cancel the "
        "policy from the date of the fraudulent act, and may recover any amounts already paid.",
        "If another policy also covers the same loss, we pay only our proportionate share.",
        "After paying a claim, we may take over your rights against anyone who caused the loss "
        "(subrogation). You must help us recover the amount.",
        "This policy is governed by the law of the Republic of South Africa, and South African "
        "courts have jurisdiction.",
    )
    complaints(d)
    privacy_notice(d)
    regulatory(d)

    # --- annexures -----------------------------------------------------------------------
    _premium_annexure(d)
    _worked_examples(d)
    _faq(d)
    _endorsements(d)
    d.annexure("E", "Specimen policy schedules")
    d.p("Specimen schedules for fictitious policyholders, showing how cover and premiums appear on a real schedule.")
    schedules = specimen_schedules(d, "KRH", 30, _schedule_sections)

    # --- answer key ----------------------------------------------------------------------
    case("What excess applies to a burst geyser claim?", money(GEYSER_EXCESS), d,
         f"A geyser excess of {money(GEYSER_EXCESS)} applies to each geyser claim")
    case("How many geyser replacement claims are covered in 12 months?", "Two", d,
         "maximum of two geyser claims in any 12-month period")
    case("How soon must a household theft be reported to the police?", "Within 48 hours of discovering it", d,
         "within 48 hours of discovering it")
    case("After how many days of being unoccupied is damage to the buildings excluded?", f"More than {UNOCCUPIED_DAYS} consecutive days", d,
         f"unoccupied for more than {UNOCCUPIED_DAYS} consecutive days")
    case("What is the power surge limit on the household policy?", f"{money(POWER_SURGE_LIMIT)} per event", d,
         f"up to {money(POWER_SURGE_LIMIT)} per event")
    case("What security is needed for contents insured above R500,000?", "Burglar bars, security gates, a monitored alarm with armed response, and an electric fence or perimeter beams; the alarm must be armed when unoccupied", d,
         "plus an electric fence or perimeter beams")
    case("How long is the grace period for a missed monthly household premium?", "15 days from the due date", d,
         "grace period of 15 days from the due date")
    case("What happens to a thatch fire claim without a lightning conductor?", "Only 50% of the claim is paid", d,
         "we will pay only 50% of the claim")
    case("What is the personal liability limit?", f"{money(LIABILITY_LIMIT)} per event", d,
         "for accidental damage to their property, up to")
    case("How long can alternative accommodation be paid after a buildings claim?", "Up to 25% of the buildings sum insured, for no longer than 6 months", d,
         "for no longer than 6 months")
    case("What is the single-item limit for unspecified all risks items?", "R7,500", d,
         "with a limit of R7,500 for any one item")
    case("How long is the cooling-off period on the household policy?", "31 days, if no claim was made", d,
         "within 31 days of receiving your policy documents")
    case("What extra excess applies to a claim in the first 90 days?", money(EARLY_CLAIM_EXCESS), d,
         "Any claim in the first 90 days of a new policy")
    case("How much cash is covered under household contents?", "R3,000 per claim", d,
         "Cash and bank cards")
    case("What does the no-claim bonus give after 3 claim-free years?", "A 10% reduction of the contents premium", d,
         "we reduce your contents premium by 10%")
    for sched in schedules[:4]:
        contents = next(si for sec, si, _ in sched["rows"] if sec == "Household contents")
        case(f"What is the household contents sum insured on policy {sched['number']}?", money(contents), d,
             sched["number"])
    return d


def _schedule_sections(rng):
    buildings = rng.randrange(900_000, 6_500_000, 50_000)
    contents = rng.randrange(150_000, 1_200_000, 10_000)
    rows = [
        ("Buildings", buildings, round(buildings / 100_000 * rng.uniform(34, 52), 2)),
        ("Household contents", contents, round(contents / 100_000 * rng.uniform(80, 120), 2)),
    ]
    if rng.random() < 0.7:
        ar = rng.randrange(10_000, 120_000, 5_000)
        rows.append(("All risks (unspecified and specified)", ar, round(ar * rng.uniform(0.009, 0.014), 2)))
    rows.append(("Personal liability", "R5,000,000", 14.50))
    if rng.random() < 0.4:
        rows.append(("Accidental damage extension", "R50,000", round(rng.uniform(28, 55), 2)))
    return rows


ENDORSEMENTS = [
    ("HE01", "Thatch roof", "The buildings have a thatched roof. Fire and lightning claims are paid in full only if a SANS 10313-compliant lightning conductor is installed and certified."),
    ("HE02", "Subsidence and landslip", "Subsidence, landslip and heave are covered, subject to an additional excess of 10% of the claim with a minimum of R10,000."),
    ("HE03", "Accidental damage", "Accidental damage to contents in the dwelling is covered up to the limit shown on the schedule. Damage to cellphones, laptops and spectacles is excluded."),
    ("HE04", "Holiday home", "The buildings are a holiday home that may be unoccupied. The unoccupancy exclusion does not apply, but theft is covered only with forcible entry and an armed alarm."),
    ("HE05", "Flood exclusion", "Damage caused by flood, including a river overflowing its banks, is excluded because the property is within the flood line."),
    ("HE06", "Home business", "Office equipment used for a home business is covered as contents up to R50,000. Business stock and customers' goods are excluded."),
    ("HE07", "Electric fence warranty", "An electric fence must be installed and working. Theft claims are not covered if the fence was not working at the time."),
    ("HE08", "Tenant's liability", "You rent the dwelling. Liability for damage to the landlord's buildings is covered up to R500,000."),
    ("HE09", "Solar installation", "The solar panels, inverter and batteries at the risk address are covered as buildings up to the amount on the schedule, including theft and power surge."),
    ("HE10", "Borehole and pump", "The borehole pump and its electrical components are covered against lightning and power surge up to R25,000."),
    ("HE11", "Domestic employee liability", "Your legal liability to domestic employees for injury not covered by COIDA is covered up to R1,000,000."),
    ("HE12", "Increased geyser limit", "One additional geyser replacement claim is covered in a 12-month period."),
]


def _endorsements(d: Doc) -> None:
    d.annexure("D", "Standard endorsements")
    d.p(
        "Endorsements change the cover for a specific policy. An endorsement applies only if its "
        "code appears on your schedule. Where an endorsement and the policy wording differ, the "
        "endorsement applies.",
    )
    for code, name, text in ENDORSEMENTS:
        d.h3(f"Endorsement {code}: {name}")
        d.p(text)
        d.p(
            "All other terms, exclusions and conditions of the policy remain unchanged. This "
            "endorsement is effective from the date shown against it on the schedule and is "
            "reviewed at each renewal."
        )



def _premium_annexure(d: Doc) -> None:
    d.annexure("A", "Indicative monthly premium guide")
    d.p(
        "The tables below show indicative monthly premiums per R100,000 of sum insured for a "
        "standard brick-and-tile dwelling with the minimum security required. Your actual "
        "premium depends on your claims history, the construction of the buildings, the "
        "security in place and the excess you choose. Thatch, flood-zone and holiday-home "
        "risks are rated separately. Premiums include VAT and exclude the SASRIA premium.",
    )
    for area in ("Metropolitan", "Urban", "Rural and smallholding"):
        d.h3(f"{area} areas")
        base = {"Metropolitan": 95, "Urban": 82, "Rural and smallholding": 108}[area]
        rows = []
        for prov in PROVINCES:
            factor = 1 + (PROVINCES.index(prov) % 4) * 0.06
            b = round(base * factor * 0.42, 2)
            c = round(base * factor, 2)
            rows.append([prov, money(b), money(c), money(round(c * 1.18, 2))])
        d.table(
            ["Province", "Buildings per R100,000", "Contents per R100,000", "Contents with valuables over 1/3"],
            rows,
            [0.28, 0.24, 0.24, 0.24],
        )
    d.note(
        "Example: a contents sum insured of R350,000 in an urban area of Gauteng with a base "
        "rate of R82.00 per R100,000 costs 3.5 × R82.00 = R287.00 per month before discounts."
    )


def _worked_examples(d: Doc) -> None:
    d.annexure("B", "Worked claim examples")
    d.p(
        "These examples show how the policy terms are applied to typical claims. They are "
        "illustrations only; every claim is assessed on its own facts.",
    )
    kinds = [
        "geyser", "storm", "theft", "surge", "allrisks", "theft_no_force", "unoccupied", "average",
        "lightning", "flood", "liability", "early",
    ]
    for n in range(1, 145):
        kind = kinds[(n - 1) % len(kinds)]
        who = person()
        town, prov = place()
        d.h3(f"Example {n}: {_title(kind)}")
        if kind == "geyser":
            cost = RNG.randrange(9_000, 24_000, 100)
            water = RNG.randrange(2_000, 15_000, 100)
            d.p(
                f"{who} of {town}, {prov}, wakes to water running through the ceiling: the "
                f"150-litre geyser in the roof has burst. The plumber's invoice to replace the "
                f"geyser with a SANS 10254-compliant installation is {money(cost)}, and repairing "
                f"the ceiling and repainting costs {money(water)}. The geyser excess of "
                f"{money(GEYSER_EXCESS)} applies once to the buildings claim.",
                f"Settlement: {money(cost)} + {money(water)} − {money(GEYSER_EXCESS)} = "
                f"{money(cost + water - GEYSER_EXCESS)}.",
            )
        elif kind == "storm":
            roof = RNG.randrange(12_000, 80_000, 500)
            d.p(
                f"A hailstorm in {town} damages the roof of the home of {who}. A roofing "
                f"contractor quotes {money(roof)} to replace broken tiles and damaged waterproofing. "
                f"The roof had been maintained, so wear and tear does not apply.",
                f"Settlement: {money(roof)} − {money(BUILDINGS_EXCESS)} buildings excess = "
                f"{money(roof - BUILDINGS_EXCESS)}.",
            )
        elif kind == "theft":
            stolen = RNG.randrange(8_000, 60_000, 250)
            d.p(
                f"Burglars break a window at the home of {who} in {town} and steal a television, "
                f"a laptop and jewellery. The case is reported to SAPS the same morning. The "
                f"replacement value of the items is {money(stolen)}, and the burglar bars and "
                f"alarm required for the sum insured were in place and working.",
                f"Settlement: {money(stolen)} − {money(CONTENTS_EXCESS)} contents excess = "
                f"{money(stolen - CONTENTS_EXCESS)}.",
            )
        elif kind == "surge":
            dmg = RNG.randrange(6_000, 40_000, 100)
            paid = min(dmg, POWER_SURGE_LIMIT)
            d.p(
                f"When power returns after load-shedding in {town}, a surge damages the fridge, "
                f"gate motor and router of {who}. A technician confirms surge damage and quotes "
                f"{money(dmg)}. The power surge limit is {money(POWER_SURGE_LIMIT)} per event.",
                f"Settlement: {money(paid)} − {money(CONTENTS_EXCESS)} = "
                f"{money(paid - CONTENTS_EXCESS)}"
                + (" (the claim was capped at the limit)." if dmg > POWER_SURGE_LIMIT else "."),
            )
        elif kind == "allrisks":
            phone = RNG.randrange(6_000, 28_000, 100)
            excess = max(ALL_RISKS_EXCESS, round(phone * 0.1))
            d.p(
                f"{who} drops a specified cellphone while hiking near {town}; the screen and "
                f"board are damaged beyond repair. The replacement value is {money(phone)}. "
                f"For cellphones the excess is {money(ALL_RISKS_EXCESS)} or 10% of the claim, "
                f"whichever is more, which here is {money(excess)}.",
                f"Settlement: {money(phone)} − {money(excess)} = {money(phone - excess)}.",
            )
        elif kind == "theft_no_force":
            d.p(
                f"Items worth {money(RNG.randrange(5_000, 20_000, 250))} go missing from the home "
                f"of {who} in {town}. There is no sign of forced entry, and a visitor had access "
                f"to the house that day.",
                "Outcome: the claim is declined, because theft from the buildings is covered "
                "only where there was forcible entry or violence (Section B, Theft).",
            )
        elif kind == "unoccupied":
            days = RNG.randrange(UNOCCUPIED_DAYS + 5, 120)
            d.p(
                f"{who} spends {days} consecutive days overseas and does not arrange for anyone "
                f"to stay at the home in {town}. During that time a pipe bursts and floods the "
                "kitchen. We had not been told about the absence.",
                f"Outcome: the buildings claim is declined, because the buildings had been "
                f"unoccupied for more than {UNOCCUPIED_DAYS} consecutive days without our "
                "written agreement.",
            )
        elif kind == "lightning":
            cost = RNG.randrange(8_000, 60_000, 500)
            d.p(
                f"Lightning strikes the home of {who} near {town}, {prov}, damaging the DB board, "
                f"the gate motor and the alarm panel. An electrician's report confirms lightning "
                f"damage of {money(cost)} to fixtures that form part of the buildings.",
                f"Settlement: {money(cost)} − {money(BUILDINGS_EXCESS)} = {money(cost - BUILDINGS_EXCESS)}.",
            )
        elif kind == "flood":
            cost = RNG.randrange(25_000, 180_000, 1_000)
            d.p(
                f"Heavy rain causes a stream behind the property of {who} in {town} to overflow, "
                f"flooding the garage and lounge. Repairs to the buildings cost {money(cost)}. The "
                "schedule does not carry the flood exclusion endorsement (HE05).",
                f"Settlement: {money(cost)} − {money(BUILDINGS_EXCESS)} = {money(cost - BUILDINGS_EXCESS)}. "
                "If endorsement HE05 had applied, the claim would have been declined.",
            )
        elif kind == "liability":
            award = RNG.randrange(40_000, 600_000, 5_000)
            d.p(
                f"A delivery driver slips on the wet stairs at the home of {who} in {town} and "
                f"claims for medical costs and lost income. Our attorneys settle the claim for "
                f"{money(award)}, well within the personal liability limit of {money(LIABILITY_LIMIT)}.",
                f"Settlement: {money(award)} − R2,500 liability excess = {money(award - 2_500)}, paid to the third party.",
            )
        elif kind == "early":
            stolen = RNG.randrange(10_000, 45_000, 500)
            total = CONTENTS_EXCESS + EARLY_CLAIM_EXCESS
            d.p(
                f"Six weeks after taking out the policy, {who} of {town} suffers a burglary with "
                f"forced entry. The stolen items are worth {money(stolen)}. Because the claim is in "
                f"the first 90 days, the additional {money(EARLY_CLAIM_EXCESS)} excess applies on top "
                f"of the {money(CONTENTS_EXCESS)} contents excess.",
                f"Settlement: {money(stolen)} − {money(total)} = {money(stolen - total)}.",
            )
        else:
            insured = RNG.randrange(150_000, 400_000, 10_000)
            actual = round(insured * RNG.uniform(1.2, 1.6), -4)
            loss = RNG.randrange(20_000, 90_000, 1_000)
            share = insured / actual
            d.p(
                f"A fire in the lounge of {who} in {town} destroys contents worth {money(loss)}. "
                f"The contents are insured for {money(insured)}, but the assessor values all the "
                f"contents at {money(actual)}, so they are underinsured.",
                f"Settlement: {money(loss)} × {money(insured)} ÷ {money(actual)} = "
                f"{money(round(loss * share))}, less the {money(CONTENTS_EXCESS)} excess = "
                f"{money(round(loss * share) - CONTENTS_EXCESS)}.",
            )


def _title(kind: str) -> str:
    return {
        "geyser": "burst geyser",
        "storm": "hail damage to the roof",
        "theft": "burglary with forced entry",
        "surge": "power surge after load-shedding",
        "allrisks": "damaged cellphone under all risks",
        "theft_no_force": "theft without forced entry",
        "unoccupied": "damage while the home was unoccupied",
        "average": "underinsured contents",
        "lightning": "lightning damage to fixtures",
        "flood": "flood after heavy rain",
        "liability": "visitor injured on the property",
        "early": "claim in the first 90 days",
    }[kind]


def _faq(d: Doc) -> None:
    d.annexure("C", "Frequently asked questions")
    faqs = [
        ("Does the policy cover damage caused by load-shedding?", "Yes, damage caused when power is restored is treated as a power surge and is covered up to the power surge limit, as long as you have contents cover. Equipment that simply fails because of age is not covered."),
        ("Is my solar installation covered?", "Fixed solar panels, inverters and batteries are part of the buildings if they are permanently installed. Portable inverters and batteries are contents. Tell us about solar installations so that your sum insured is adequate."),
        ("Do I need a police case number for every claim?", "Only for theft, attempted theft, robbery and malicious damage. You must report these to SAPS within 48 hours."),
        ("What if my home is a sectional title unit?", "The body corporate insures the buildings. You insure your contents with us, and you may add cover for improvements you made to the unit."),
        ("Can I choose my own repairer?", "You may get your own quotes, but we may ask for a second quote or use an approved supplier. We pay what it would have cost through our supplier."),
        ("Are my children's belongings at university covered?", "Yes, contents temporarily removed are covered up to 15% of the contents sum insured, but theft must involve forcible entry."),
        ("What should I do first when a geyser bursts?", "Switch off the water at the mains and the geyser's electrical isolator, then call our claims line. Emergency repairs up to R5,000 may be done without our consent."),
        ("Is accidental damage to my television covered?", "Accidental damage to contents is covered only if your schedule includes the accidental damage extension. Without it, only the listed events are covered."),
        ("How do I avoid being underinsured?", "Review your contents sum insured at least once a year and after big purchases. Our online calculator lists the typical value of items room by room."),
        ("Does the policy cover my domestic worker's belongings?", "Yes, while the domestic worker lives at the risk address, their belongings form part of your contents."),
        ("What is SASRIA cover?", "SASRIA SOC Limited is the state-owned insurer that covers riot, strike, public disorder and terrorism. We add SASRIA cover to your policy and collect its premium for SASRIA."),
        ("Can I pause my policy while I'm away?", "No, but tell us if the home will be unoccupied for more than 60 consecutive days. We may agree to continue cover with conditions such as regular inspections."),
        ("Are pets covered?", "Pets are not covered as contents, but your legal liability for damage or injury your pets cause to other people is covered under personal liability."),
        ("How is a total loss of the buildings settled?", "We pay the cost of rebuilding to the same standard, up to the buildings sum insured, plus professional fees and debris removal within their limits."),
        ("Will one claim cancel my no-claim bonus?", "Yes. One claim reduces the no-claim bonus to zero, and it builds up again after 3 claim-free years."),
    ]
    for q, a in faqs:
        d.h3(q)
        d.p(a)
