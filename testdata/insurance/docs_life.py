"""KR-LF-001 — Funeral and Life Cover Policy Terms (long-term insurance)."""

from builder import LIFE_COMPANY, Doc
from common import RNG, case, complaints, money, person, place, privacy_notice, regulatory, specimen_schedules

WAITING_NATURAL_MONTHS = 6
SUICIDE_MONTHS = 24
GRACE_DAYS = 30
MAX_ENTRY_AGE = 74
PAYOUT_HOURS = 48

FUNERAL_COVER = [
    ("Main member", "R30,000", "R50,000", "R75,000"),
    ("Spouse", "R30,000", "R50,000", "R75,000"),
    ("Child aged 14 to 21", "R15,000", "R25,000", "R37,500"),
    ("Child aged 6 to 13", "R10,000", "R15,000", "R20,000"),
    ("Child aged 1 to 5", "R7,500", "R10,000", "R15,000"),
    ("Child under 1 (including stillborn after 26 weeks)", "R3,000", "R5,000", "R7,500"),
    ("Extended family member", "R10,000", "R15,000", "R20,000"),
]


def build() -> Doc:
    d = Doc(
        filename="KR-LF-001-funeral-and-life-policy-terms.pdf",
        title="Funeral and Life Cover Policy Terms",
        subtitle="Family Funeral Plan · Term Life Cover · Disability Benefit",
        code="KR-LF-001",
        company=LIFE_COMPANY,
    )
    d.h1("About these policy terms")
    d.p(
        f"These terms apply to life and funeral policies issued by {LIFE_COMPANY}, a fictional "
        "long-term insurer. Your policy schedule shows the plan you chose, the people covered, "
        "the cover amounts and your premium. These terms, the schedule and your application "
        "together form your contract.",
        "Long-term insurance pays a benefit when a defined event happens to a life insured, "
        "such as death or disability. It is not savings: if you stop paying premiums, the "
        "policy lapses and has no cash value.",
    )
    d.h1("Definitions", new_page=True)
    terms = [
        ("Accidental death", "Death caused solely and directly by violent, external and visible means, within 90 days of the accident."),
        ("Beneficiary", "The person you nominate to receive the benefit when the main member dies. If no valid beneficiary is alive, the benefit is paid to the main member's estate."),
        ("Child", "A biological, adopted or stepchild of the main member or spouse who is financially dependent on them, up to age 21, or up to age 25 if a full-time student."),
        ("Extended family member", "A parent, parent-in-law, grandparent, sibling, aunt, uncle, niece, nephew or cousin of the main member, up to the age of 85."),
        ("Life insured", "A person whose life is covered by the policy."),
        ("Main member", "The person who applies for and owns the policy and pays the premiums."),
        ("Spouse", "A person married to the main member under civil, customary or religious law, or a life partner who has lived with the main member for at least 12 months."),
        ("Waiting period", "The period from the start of cover during which a death from natural causes is not covered."),
    ]
    d.table(["Term", "Meaning"], [[t, m] for t, m in terms], [0.22, 0.78])

    d.h1("Family Funeral Plan", new_page=True)
    d.h2("Who can be covered")
    d.clauses(
        f"The main member must be between 18 and {MAX_ENTRY_AGE} years old when cover starts.",
        "You may cover your spouse, up to 6 children and up to 8 extended family members on one policy.",
        "Every life insured must be a South African citizen or permanent resident living in South Africa.",
    )
    d.h2("Cover amounts")
    d.p("Choose one of three plan levels. The cover amount for each person depends on their age and relationship to you.")
    d.table(["Life insured", "Bronze", "Silver", "Gold"], [list(r) for r in FUNERAL_COVER], [0.4, 0.2, 0.2, 0.2])
    d.h2("Waiting periods")
    d.clauses(
        f"A waiting period of {WAITING_NATURAL_MONTHS} months applies to death from natural causes for every life insured, "
        "starting on the date that person's cover starts.",
        "There is no waiting period for accidental death: cover for accidental death starts as "
        "soon as the first premium is received.",
        "When you increase cover, a new 6-month waiting period applies to the increased amount only.",
        f"Suicide is not covered within the first {SUICIDE_MONTHS} months of cover for that life insured. "
        "After this period, suicide is covered like any other death.",
        "If you move to us from another insurer without a break in cover and your previous "
        "policy had been in force for at least 6 months, we waive the waiting period up to the "
        "cover amount you had before.",
    )
    d.h2("Additional funeral benefits")
    d.clauses(
        "Grocery benefit: R2,500 paid with the main member's funeral claim on Silver and Gold plans.",
        "Tombstone benefit: R5,000 paid 6 months after the main member's death on the Gold plan.",
        "Repatriation: we arrange and pay to transport the body of a life insured who dies more "
        "than 200 km from home inside South Africa back to their home town.",
        "Premium waiver: if the main member dies, premiums for the remaining lives insured are "
        "waived for 6 months.",
    )
    d.h2("Claiming a funeral benefit")
    d.clauses(
        "Claims must be submitted within 6 months of the death. Late claims are considered only "
        "if there is a good reason for the delay.",
        ("We need:", [
            "a completed claim form signed by the claimant;",
            "a certified copy of the death certificate (BI-5) and the notification of death (DHA-1663);",
            "a certified copy of the deceased's and the claimant's identity documents;",
            "the claimant's bank details and a bank confirmation letter not older than 3 months;",
            "for unnatural deaths, a police report or inquest number.",
        ]),
        f"We pay valid funeral claims within {PAYOUT_HOURS} hours of receiving all the documents we need.",
    )

    d.h1("Term life cover", new_page=True)
    d.clauses(
        "Term life cover pays a lump sum to your beneficiaries if the life insured dies before "
        "the cover ends. Cover amounts range from R250,000 to R10,000,000.",
        "Cover lasts for the term you choose (10, 15 or 20 years) or until age 75, whichever comes first.",
        "Applications for more than R1,500,000 require medical underwriting, which may include "
        "blood tests, a medical examiner's report and an HIV test, paid for by us.",
        "The premium for term life cover is level for the first 5 years and then increases each "
        "year with your age, unless you chose a level premium for the whole term.",
        "Cover is not provided for death caused by participation in hazardous activities you did "
        "not disclose, such as motor racing, mountaineering above 6,000 metres or skydiving.",
    )
    d.h1("Disability benefit")
    d.clauses(
        "If you add the disability benefit, we pay a lump sum if the life insured becomes "
        "permanently unable to do their own occupation, or any occupation for which they are "
        "suited by education, training or experience, as chosen on the schedule.",
        "Disability must have lasted at least 6 months before we assess a claim, and must be "
        "confirmed by a specialist medical practitioner.",
        "Disability caused by a pre-existing condition within the first 24 months of cover is excluded.",
    )
    d.h1("Premiums and lapse", new_page=True)
    d.clauses(
        f"Premiums are paid monthly. If a premium is not received, you have a grace period of {GRACE_DAYS} days, "
        "during which you remain covered. If you die in the grace period, the unpaid premium "
        "is deducted from the claim.",
        "If the premium is still unpaid at the end of the grace period, the policy lapses and "
        "no benefits are payable.",
        "You may apply to reinstate a lapsed policy within 3 months of lapsing. A new waiting "
        "period may apply.",
        "Premiums increase by 5% every year on the policy anniversary, and cover increases by 5% "
        "as well, unless you choose not to increase.",
    )
    d.h1("Cooling-off and cancellation")
    d.clauses(
        "You may cancel within 30 days of receiving your policy documents, as long as no claim "
        "has been made, and we will refund all premiums paid.",
        "You may cancel at any time after that by giving us notice. No premium is refunded.",
    )
    complaints(d)
    privacy_notice(d)
    regulatory(d, life=True)

    d.annexure("A", "Monthly funeral premiums by age")
    for plan, scale in (("Bronze", 1.0), ("Silver", 1.55), ("Gold", 2.2)):
        d.h3(f"{plan} plan: main member and spouse")
        rows = []
        for age in range(18, MAX_ENTRY_AGE + 1):
            single = round((58 + (age - 18) ** 1.55 * 1.1) * scale, 2)
            rows.append([str(age), money(single), money(round(single * 1.72, 2)), money(round(single * 1.72 + 24 * scale, 2))])
        d.table(["Age of main member", "Main member only", "Main member and spouse", "Family (spouse + children)"], rows, [0.25, 0.25, 0.25, 0.25])
    d.h3("Term life cover: monthly premium per R100,000 of cover (non-smoker)")
    rows = []
    for age in range(18, 66):
        base = 4.2 + (age - 18) ** 1.9 * 0.012
        rows.append([str(age)] + [money(round(base * f, 2)) for f in (0.92, 1.0, 1.08)])
    d.table(["Age next birthday", "10-year term", "15-year term", "20-year term"], rows, [0.25, 0.25, 0.25, 0.25])
    d.note("Smokers pay 1.8 times these rates. Rates for cover above R1,500,000 depend on medical underwriting.")
    d.h3("Extended family members (per person, Bronze)")
    rows = [[f"{a}–{a + 9}", money(round(22 + (a - 25) ** 1.6 * 0.6, 2))] for a in range(25, 86, 10)]
    d.table(["Age", "Monthly premium"], rows, [0.5, 0.5])

    d.annexure("B", "Worked claim examples")
    for n in range(1, 91):
        who = person()
        town, prov = place()
        months = RNG.randrange(1, 30)
        accidental = n % 3 == 0
        plan, col = RNG.choice([("Bronze", 1), ("Silver", 2), ("Gold", 3)])
        d.h3(f"Example {n}: {'accidental' if accidental else 'natural'} death after {months} months")
        if accidental:
            d.p(
                f"The spouse of {who} of {town}, {prov}, dies in a road accident {months} months "
                f"after joining the {plan} plan. There is no waiting period for accidental death.",
                f"Outcome: {FUNERAL_COVER[1][col]} is paid within {PAYOUT_HOURS} hours of receiving all documents.",
            )
        elif months < WAITING_NATURAL_MONTHS:
            d.p(
                f"The mother of {who}, covered as an extended family member, dies of natural causes "
                f"{months} months after cover started. The {WAITING_NATURAL_MONTHS}-month waiting "
                "period for natural death has not ended.",
                "Outcome: the claim is declined, and premiums paid for this life insured are refunded.",
            )
        else:
            d.p(
                f"{who}, the main member on a {plan} plan, dies of a heart attack {months} months "
                f"after joining. The waiting period has passed.",
                f"Outcome: {FUNERAL_COVER[0][col]} is paid to the nominated beneficiary"
                + (", plus the R2,500 grocery benefit." if plan != "Bronze" else "."),
            )

    case("What is the waiting period for natural death on the funeral plan?", f"{WAITING_NATURAL_MONTHS} months", d,
         f"A waiting period of {WAITING_NATURAL_MONTHS} months applies to death from natural causes")
    case("Is there a waiting period for accidental death?", "No, accidental death is covered once the first premium is received", d,
         "There is no waiting period for accidental death")
    case("How long is suicide excluded on a life policy?", f"The first {SUICIDE_MONTHS} months of cover", d,
         f"Suicide is not covered within the first {SUICIDE_MONTHS} months")
    case("What is the grace period on a funeral policy?", f"{GRACE_DAYS} days", d,
         f"you have a grace period of {GRACE_DAYS} days")
    case("What is the maximum entry age for a main member?", f"{MAX_ENTRY_AGE} years", d,
         f"between 18 and {MAX_ENTRY_AGE} years old")
    case("How quickly are valid funeral claims paid?", f"Within {PAYOUT_HOURS} hours of receiving all documents", d,
         f"We pay valid funeral claims within {PAYOUT_HOURS} hours")
    case("How much funeral cover does a Gold plan give a child aged 6 to 13?", "R20,000", d,
         "Child aged 6 to 13")
    case("Above what amount does term life cover need medical underwriting?", "More than R1,500,000", d,
         "more than R1,500,000 require medical underwriting")
    case("How long is the cooling-off period on life policies?", "30 days, if no claim was made", d,
         "You may cancel within 30 days of receiving your policy documents")
    d.annexure("C", "Specimen policy schedules")
    for sched in specimen_schedules(d, "KRF", 25, _schedule_sections)[:2]:
        case(f"What plan level is policy {sched['number']} on?", sched["rows"][0][0].split(" ")[0], d, sched["number"])
    return d


def _schedule_sections(rng):
    plan, col = rng.choice([("Bronze", 1), ("Silver", 2), ("Gold", 3)])
    scale = {"Bronze": 1.0, "Silver": 1.55, "Gold": 2.2}[plan]
    age = rng.randrange(22, 70)
    main = round((58 + (age - 18) ** 1.55 * 1.1) * scale, 2)
    rows = [(f"{plan} plan: main member (age {age})", FUNERAL_COVER[0][col], main)]
    if rng.random() < 0.7:
        rows.append(("Spouse", FUNERAL_COVER[1][col], round(main * 0.72, 2)))
    for _ in range(rng.randrange(0, 4)):
        rows.append(("Child", FUNERAL_COVER[4][col], round(4 * scale, 2)))
    for _ in range(rng.randrange(0, 3)):
        rows.append(("Extended family member", FUNERAL_COVER[6][col], round(rng.uniform(28, 140), 2)))
    return rows
