"""Internal manuals and governance policies: claims, underwriting, complaints/TCF, privacy,
and financial crime. Written for staff, like the documents an insurer keeps on its intranet."""

from builder import Doc
from common import PROVINCES, RNG, TOWNS, case, money, person, place


def _purpose(d: Doc, purpose: str, scope: str, owner: str) -> None:
    d.h1("Purpose, scope and ownership")
    d.p(purpose, scope)
    d.table(
        ["Item", "Detail"],
        [
            ["Policy owner", owner],
            ["Approved by", "Board Risk and Compliance Committee (fictional)"],
            ["Review cycle", "At least once every 12 months, or sooner if the law changes"],
            ["Applies to", "All employees, contractors and outsourced service providers of Kestrel Ridge"],
            ["Breaches", "Breaches of this document are disciplinary matters and may be reported to the regulator"],
        ],
        [0.3, 0.7],
    )


def _raci(d: Doc, activities: list[str]) -> None:
    """Who is Responsible, Accountable, Consulted and Informed for each activity."""
    d.h1("Roles and responsibilities")
    d.p("R = responsible (does the work), A = accountable (signs off), C = consulted, I = informed.")
    roles = ["Front-line staff", "Team leader", "Department head", "Compliance", "Executive committee"]
    rows = []
    for act in activities:
        pattern = RNG.choice([
            ["R", "A", "I", "C", "I"], ["R", "R", "A", "C", "I"], ["I", "R", "A", "C", "I"],
            ["C", "R", "R", "A", "I"], ["I", "C", "R", "R", "A"],
        ])
        rows.append([act] + pattern)
    d.table(["Activity"] + roles, rows, [0.35, 0.13, 0.13, 0.13, 0.13, 0.13])


def _training(d: Doc, topic: str) -> None:
    d.h1("Training and monitoring")
    d.table(
        ["Audience", "Training", "When", "Pass mark"],
        [
            ["New employees", f"{topic} induction module", "Within 30 days of joining", "80%"],
            ["All employees", f"{topic} refresher", "Every 12 months", "80%"],
            ["Team leaders", "Supervising and escalating", "Every 12 months", "85%"],
            ["Intermediaries with binder authority", f"{topic} for intermediaries", "Before authority is granted", "80%"],
            ["Board members", "Governance briefing", "Every 12 months", "Attendance"],
        ],
        [0.3, 0.32, 0.23, 0.15],
    )
    d.p(
        "Compliance monitors adherence through quarterly file reviews and reports exceptions to "
        "the Board Risk and Compliance Committee. Repeated exceptions in a team lead to a "
        "remediation plan with a named owner and a deadline."
    )


def _version_history(d: Doc, entries: list[tuple[str, str, str]]) -> None:
    d.h1("Version history")
    d.table(["Version", "Date", "Change"], [list(e) for e in entries], [0.15, 0.2, 0.65])


# --- claims manual ---------------------------------------------------------------------------


def claims_manual() -> Doc:
    d = Doc(
        filename="KR-OPS-001-claims-management-manual.pdf",
        title="Claims Management Manual",
        subtitle="Procedures, service levels and authority limits for short-term claims",
        code="KR-OPS-001",
        audience="Claims staff, assessors and team leaders (internal)",
    )
    _purpose(
        d,
        "This manual sets out how Kestrel Ridge handles short-term insurance claims from first "
        "notification to settlement or rejection, so that every claimant is treated fairly and "
        "consistently and the Policyholder Protection Rules are met.",
        "It applies to household, motor and business claims. Life and funeral claims follow the "
        "Life Claims Procedure (KR-OPS-002), which is not part of this set.",
        "Head of Claims",
    )
    d.h1("Claims lifecycle", new_page=True)
    steps = [
        ("First notification of loss (FNOL)", "Capture the claim on the claims system within 1 business day of notification, confirm cover is in force and premiums are paid, and send the acknowledgement."),
        ("Validation", "Check the policy schedule, sums insured, excesses, endorsements and any prior claims. Confirm the claimant is the policyholder or an authorised person."),
        ("Investigation", "Gather documents, appoint an assessor where required, and obtain repair quotes or replacement values."),
        ("Decision", "Accept, partially accept or reject the claim, applying the policy wording and this manual."),
        ("Settlement", "Pay the claim or authorise repairs, deduct excesses, and record salvage and recoveries."),
        ("Closure", "Close the file once payments, recoveries and correspondence are complete, and run the quality checklist."),
    ]
    d.table(["Stage", "What happens"], [list(s) for s in steps], [0.3, 0.7])

    d.h1("Service level agreements")
    d.p("Service levels are measured in business days from the event shown, and are reported to the Claims Committee monthly.")
    slas = [
        ["Acknowledge a new claim", "2 business days", "Claim notification"],
        ["Appoint an assessor (if required)", "2 business days", "Claim notification"],
        ["Assessor's report", "5 business days", "Appointment"],
        ["Claims decision", "10 business days", "Receipt of all required information"],
        ["Written reasons for rejection", "With the decision", "Decision"],
        ["Payment after agreement", "5 business days", "Agreement of the amount"],
        ["Respond to a request to reconsider", "15 business days", "Receipt of the request"],
    ]
    d.table(["Activity", "Target", "Measured from"], slas, [0.45, 0.25, 0.30])
    d.p("Any claim that breaches a service level twice is escalated to the team leader automatically.")

    d.h1("Assessors and loss adjusters", new_page=True)
    d.clauses(
        "Appoint an assessor for every claim above R50,000, every motor claim where the vehicle "
        "may be a write-off, and any claim flagged by the fraud rules.",
        "Appoint a loss adjuster for business claims above R500,000 and for all business "
        "interruption claims.",
        "Assessors must be on the approved panel, must declare any conflict of interest, and may "
        "not negotiate settlements beyond their mandate.",
        "Desktop assessments based on photographs and quotes may be used for household claims "
        "below R50,000 where the cause is clear.",
    )

    d.h1("Authority limits")
    d.p("Staff may approve settlements up to the limits below. Amounts are per claim, including VAT, before excess.")
    d.table(
        ["Role", "Settle", "Reject"],
        [
            ["Claims handler", "Up to R50,000", "Up to R50,000, with team leader review"],
            ["Senior claims handler", "Up to R150,000", "Up to R150,000"],
            ["Team leader", "Up to R500,000", "Up to R500,000"],
            ["Claims manager", "Up to R2,000,000", "Up to R2,000,000"],
            ["Head of Claims", "Up to R10,000,000", "Any amount"],
            ["Claims Committee", "Above R10,000,000", "Any ex gratia payment above R100,000"],
        ],
        [0.3, 0.35, 0.35],
    )
    d.clauses(
        "Every rejection of a claim above R50,000 must be reviewed by a second person with "
        "authority for that amount before the letter is sent.",
        "Ex gratia payments (payments we are not obliged to make) up to R100,000 may be approved "
        "by a claims manager and must be recorded with reasons.",
    )

    d.h1("Rejecting a claim", new_page=True)
    d.clauses(
        ("A rejection letter must state, in plain language:", [
            "the reasons for the rejection;",
            "the specific policy clause relied on, quoted in full;",
            "that the claimant may make representations to us within 90 days of the letter;",
            "that the claimant may refer the matter to the ombud, with the ombud's contact details;",
            "the time limit for legal action: the claimant may start legal proceedings within 6 months of the expiry of the 90-day period or of our response to the representations, whichever is later.",
        ]),
        "Never reject a claim for non-disclosure unless the fact not disclosed is material to the "
        "risk and would have changed our decision to accept the policy or its terms.",
        "Where a claim is rejected because of a late report, record how the delay prejudiced the assessment.",
    )

    d.h1("Fraud indicators and referral")
    d.p(
        "Claims handlers must refer a claim to the Financial Crime Unit when two or more of the "
        "indicators below are present, or when any single indicator marked high risk is present. "
        "Do not tell the claimant that the claim has been referred.",
    )
    indicators = [
        ["Claim within 90 days of policy start or a cover increase", "Medium"],
        ["Claimant is unusually pushy about a quick cash settlement", "Medium"],
        ["Invoices or receipts appear altered, or from businesses that cannot be traced", "High"],
        ["Items claimed are inconsistent with the claimant's lifestyle or the sum insured", "Medium"],
        ["Multiple claims for similar items within 12 months", "Medium"],
        ["Police case number cannot be verified with SAPS", "High"],
        ["The vehicle was for sale, or had high mileage and repair needs, when stolen", "Medium"],
        ["The claimant has claims with other insurers for the same event", "High"],
        ["Damage is inconsistent with the cause described", "Medium"],
        ["The claimant refuses access to the assessor", "High"],
    ]
    d.table(["Indicator", "Risk"], indicators, [0.8, 0.2])

    d.h1("Recoveries and salvage", new_page=True)
    d.clauses(
        "Where a third party caused the loss, open a recovery file within 10 business days of "
        "settlement. Recover the claimant's excess as well, and refund it to them when recovered.",
        "Salvage from written-off vehicles is sold through approved salvage auctions. The salvage "
        "value is credited to the claim.",
        "Recoveries below R5,000 may be written off by a team leader if the cost of pursuing "
        "them is higher than the expected recovery.",
    )
    d.h1("Quality assurance")
    d.clauses(
        "Team leaders review at least 5 closed files per handler per month against the quality checklist.",
        "Every rejected claim is included in the monthly sample until the handler scores 90% or "
        "more for three consecutive months.",
        "Quality results feed into the Treating Customers Fairly dashboard (see KR-GOV-002).",
    )
    _version_history(d, [
        ("4.0", "1 March 2025", "Authority limits revised"),
        ("4.1", "1 September 2025", "Fraud indicators expanded"),
        ("4.2", "1 March 2026", "Desktop assessments introduced for household claims below R50,000"),
    ])

    _raci(d, [
        "Capture a new claim", "Appoint an assessor", "Approve a settlement within authority",
        "Approve an ex gratia payment", "Sign a rejection letter", "Refer suspected fraud",
        "Open a recovery file", "Review claim quality", "Report claims MI to the Claims Committee",
    ])
    _training(d, "Claims handling")
    d.annexure("B", "Standard letters")
    letters = [
        ("Acknowledgement of claim", "Thank you for reporting your claim on [date]. Your claim number is [number] and [handler] is handling it. We will contact you within 2 business days if we need more information. You can track your claim on our website."),
        ("Request for information", "To assess your claim we need the following: [list]. Please send these within 14 days. If we do not receive them, we will not be able to finish assessing your claim, and we will write to you before closing it."),
        ("Appointment of an assessor", "We have appointed [assessor], an independent assessor, to inspect the damage. They will contact you within 2 business days to arrange a visit. Please give them access to the property and any information they ask for."),
        ("Settlement offer", "We have accepted your claim for [amount]. After the excess of [excess], we will pay [net amount] into your account within 5 business days of your acceptance. If you do not agree with the amount, please tell us why."),
        ("Rejection of claim", "We have carefully considered your claim and are unable to pay it because [reasons]. We relied on clause [clause] of your policy, which reads: [quote]. You may make representations to us within 90 days of this letter. You may also refer the matter to the National Financial Ombud Scheme South Africa. You may start legal proceedings within 6 months of the expiry of the 90-day period or of our response to your representations, whichever is later."),
        ("Closure of claim", "Your claim [number] is now closed. Thank you for your patience. If you have any questions or concerns about how we handled your claim, please contact us or our complaints team."),
    ]
    for title, body in letters:
        d.h3(title)
        d.p(body)
    d.annexure("C", "Claims management information, 2025")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for product in ("Household", "Motor", "Business"):
        d.h3(f"{product} claims reported per month")
        rows = []
        for prov in PROVINCES:
            base = RNG.randrange(40, 900)
            rows.append([prov] + [str(max(5, round(base * RNG.uniform(0.75, 1.3)))) for _ in months])
        d.table(["Province"] + months, rows, [0.16] + [0.07] * 12)
    d.h3("Service level performance, 2025")
    d.table(
        ["Measure", "Target", "Achieved"],
        [[a, t, f"{RNG.uniform(88, 99.5):.1f}%"] for a, t, _ in slas],
        [0.5, 0.25, 0.25],
    )
    d.annexure("A", "Case studies")
    for n in range(1, 121):
        who = person()
        town, prov = place()
        amount = RNG.randrange(20_000, 2_500_000, 5_000)
        role = (
            "a claims handler" if amount <= 50_000 else
            "a senior claims handler" if amount <= 150_000 else
            "a team leader" if amount <= 500_000 else
            "a claims manager" if amount <= 2_000_000 else
            "the Head of Claims"
        )
        assessor = "must" if amount > 50_000 else "need not"
        d.h3(f"Case {n}: claim of {money(amount)}")
        d.p(
            f"{who} of {town}, {prov}, submits a claim of {money(amount)}. Under the authority "
            f"limits it can be settled by {role}, and an assessor {assessor} be appointed. "
            + ("Because it is above R50,000, a rejection would need a second reviewer. " if amount > 50_000 else "")
            + ("As a business claim above R500,000, a loss adjuster is appointed. " if amount > 500_000 and n % 2 else ""),
        )

    case("Above what claim amount must an assessor be appointed?", "R50,000", d,
         "Appoint an assessor for every claim above R50,000")
    case("Who may settle a claim of R400,000?", "A team leader (authority up to R500,000)", d, "Up to R500,000")
    case("How long does a claimant have to make representations after a rejection?", "90 days from the rejection letter", d,
         "within 90 days of the letter")
    case("Within how many business days must a new claim be acknowledged?", "2 business days", d,
         "Acknowledge a new claim")
    case("When must a claim be referred to the Financial Crime Unit?", "When two or more indicators, or any single high-risk indicator, are present", d,
         "two or more of the indicators below are present")
    case("How many closed files are quality-reviewed per handler each month?", "At least 5", d,
         "at least 5 closed files per handler per month")
    return d


# --- underwriting ------------------------------------------------------------------------------


def underwriting() -> Doc:
    d = Doc(
        filename="KR-UW-001-underwriting-guidelines.pdf",
        title="Personal Lines Underwriting Guidelines",
        subtitle="Risk acceptance, rating factors and referral rules",
        code="KR-UW-001",
        audience="Underwriters and intermediaries with binder authority (internal)",
    )
    _purpose(
        d,
        "These guidelines define which household and motor risks Kestrel Ridge accepts, on what "
        "terms, and when a risk must be referred to a senior underwriter.",
        "They apply to new business, renewals and mid-term changes for personal lines.",
        "Head of Underwriting",
    )
    d.h1("Risk acceptance principles", new_page=True)
    d.clauses(
        "We price for risk fairly: similar risks pay similar premiums, and every loading must be "
        "justified by data or a documented underwriting reason.",
        "We do not decline or load a risk because of race, gender, religion, disability or any "
        "other ground prohibited by the Constitution or the Promotion of Equality and Prevention "
        "of Unfair Discrimination Act.",
        "Applicants with more than 3 claims in the past 3 years on household or motor cover must "
        "be referred to a senior underwriter.",
        "Applicants whose previous insurer cancelled their policy for non-disclosure or fraud in "
        "the past 5 years are declined.",
    )
    d.h1("Household risks")
    d.h2("Construction")
    d.table(
        ["Construction", "Acceptance", "Loading"],
        [
            ["Brick or concrete walls, tile, slate or metal roof", "Standard", "None"],
            ["Brick walls, thatched roof", "Accept with SANS 10313 lightning conductor", "50% on buildings, 25% on contents"],
            ["Prefabricated or timber frame", "Refer", "20% to 40%"],
            ["Wendy houses and other wooden structures", "Outbuildings only", "Sum insured limited to R50,000"],
            ["Informal dwellings", "Decline", "Not applicable"],
        ],
        [0.38, 0.32, 0.30],
    )
    d.h2("Location")
    d.clauses(
        "Properties within 100 metres of a river, dam or the sea, or below the 1-in-50-year flood "
        "line, must be referred, and flood cover may be excluded.",
        "Properties on dolomite land in Gauteng need a geotechnical report before subsidence "
        "cover is offered.",
        "Smallholdings must have the main dwelling within 1 km of a tarred road for standard "
        "acceptance, because of fire-brigade response times.",
    )
    d.h2("Sum insured checks")
    d.clauses(
        "Buildings sums insured below R7,500 per square metre in metropolitan areas must be "
        "questioned, because they are likely to be underinsured.",
        "Contents sums insured above R1,500,000 must be referred and require an inventory.",
        "Specified all risks items above R50,000 require a valuation certificate not older than 24 months.",
    )
    d.h1("Motor risks", new_page=True)
    d.clauses(
        "Vehicles older than 20 years are accepted for third party, fire and theft cover only, "
        "unless they are collector's vehicles with an agreed value.",
        "Imported vehicles that are not on the TransUnion guide must be referred.",
        "Vehicles with a retail value above R350,000 require an approved tracking device; above "
        "R1,000,000 a second recovery device is required.",
        "Drivers with more than 2 at-fault claims in 3 years, or a drunk-driving conviction in "
        "the past 5 years, must be referred.",
    )
    d.h2("High-theft vehicle list")
    d.p("The following vehicle groups carry a 15% theft loading because of their theft and hijacking frequency in South Africa:")
    d.table(
        ["Vehicle group", "Reason", "Loading"],
        [
            ["Double-cab bakkies", "High hijacking frequency", "15%"],
            ["Compact SUVs", "High theft frequency", "15%"],
            ["Minibuses used privately", "Parts demand", "15%"],
            ["Popular hatchbacks older than 8 years", "Parts demand", "10%"],
        ],
        [0.4, 0.4, 0.2],
    )
    d.h1("Rating factors")
    d.p("Personal lines premiums use these factors. Underwriters may not override the rating engine by more than 10% without senior approval.")
    factors = [
        ["Area risk zone", "Based on postal code claims experience", "0.8 to 1.6"],
        ["Claims history (3 years)", "Number and size of claims", "1.0 to 2.0"],
        ["Security", "Alarm, armed response, electric fence", "0.85 to 1.0"],
        ["Voluntary excess", "Higher excess chosen", "0.80 to 1.0"],
        ["Driver age", "Under 25, 25–64, 65+", "0.95 to 1.5"],
        ["Licence years", "Fewer than 2 years", "1.2"],
        ["Vehicle use", "Private or business", "1.0 to 1.25"],
        ["Overnight parking", "Garage, carport, street", "0.9 to 1.3"],
    ]
    d.table(["Factor", "Basis", "Multiplier range"], factors, [0.3, 0.45, 0.25])
    d.h1("Referral authority", new_page=True)
    d.table(
        ["Underwriter level", "Household sum insured", "Motor retail value"],
        [
            ["Underwriter", "Up to R3,000,000", "Up to R750,000"],
            ["Senior underwriter", "Up to R10,000,000", "Up to R2,000,000"],
            ["Underwriting manager", "Above R10,000,000", "Above R2,000,000"],
        ],
        [0.34, 0.33, 0.33],
    )
    _version_history(d, [
        ("3.5", "1 March 2025", "Dolomite rules added"),
        ("4.0", "1 March 2026", "Thatch loading revised to 50%"),
    ])
    _raci(d, [
        "Accept a standard risk", "Load or exclude a risk", "Decline an application",
        "Refer a risk above authority", "Approve a rating override above 10%",
        "Update the area risk zones", "Review the high-theft vehicle list",
    ])
    _training(d, "Underwriting")
    d.annexure("A", "Area risk zones by town and district")
    d.p(
        "Zones are recalculated every 12 months from 5 years of claims experience. Zone A is "
        "the lowest risk. The factor multiplies the base household rate.",
    )
    districts = ["Central", "North", "South", "East", "West", "Industrial", "Smallholdings", "Townships"]
    for prov in PROVINCES:
        d.h3(prov)
        rows = []
        for town in TOWNS[prov]:
            for district in districts:
                zone = RNG.choice(["A", "B", "B", "C", "C", "D"])
                factor = {"A": 0.85, "B": 1.0, "C": 1.2, "D": 1.45}[zone]
                rows.append([town, district, zone, f"{factor:.2f}", RNG.choice(["Standard", "Standard", "Refer flood", "Armed response required"])])
        d.table(["Town", "District", "Zone", "Factor", "Note"], rows, [0.24, 0.22, 0.1, 0.12, 0.32])
    d.annexure("B", "Referral examples")
    for n in range(1, 61):
        who = person()
        town, prov = place()
        si = RNG.randrange(500_000, 14_000_000, 100_000)
        level = "an underwriter" if si <= 3_000_000 else "a senior underwriter" if si <= 10_000_000 else "the underwriting manager"
        d.h3(f"Referral {n}")
        d.p(
            f"An intermediary submits a household risk for {who} in {town}, {prov}, with a "
            f"sum insured of {money(si)}. Under the referral authority, it can be accepted by {level}."
            + (" The roof is thatched, so the 50% buildings loading and a SANS 10313 lightning conductor apply." if n % 4 == 0 else "")
            + (" The property is 60 metres from a river, so it is referred and flood cover may be excluded." if n % 5 == 0 else "")
        )

    case("What loading applies to a thatched roof?", "50% on buildings and 25% on contents, with a SANS 10313 lightning conductor", d,
         "50% on buildings, 25% on contents")
    case("When must a property near water be referred?", "Within 100 metres of a river, dam or the sea, or below the 1-in-50-year flood line", d,
         "within 100 metres of a river, dam or the sea")
    case("When is a second vehicle recovery device required?", "When the retail value is above R1,000,000", d,
         "R1,000,000 a second recovery device is required")
    case("What theft loading applies to double-cab bakkies?", "15%", d, "Double-cab bakkies")
    case("What happens to an applicant cancelled for fraud by a previous insurer?", "Declined, if within the past 5 years", d,
         "cancelled their policy for non-disclosure or fraud in the past 5 years are declined")
    return d


# --- complaints & TCF --------------------------------------------------------------------------


def complaints_tcf() -> Doc:
    d = Doc(
        filename="KR-GOV-002-complaints-and-tcf-policy.pdf",
        title="Complaints Management and Treating Customers Fairly Policy",
        subtitle="How we resolve complaints and deliver fair outcomes",
        code="KR-GOV-002",
        audience="All staff and intermediaries",
    )
    _purpose(
        d,
        "This policy explains how Kestrel Ridge receives, records, resolves and learns from "
        "complaints, and how we embed the six Treating Customers Fairly (TCF) outcomes in our "
        "business, as required by the Policyholder Protection Rules.",
        "It covers complaints from policyholders, claimants, beneficiaries and members of the "
        "public about any Kestrel Ridge product, service or intermediary acting for us.",
        "Chief Compliance Officer",
    )
    d.h1("The six TCF outcomes", new_page=True)
    outcomes = [
        ("Outcome 1", "Customers can be confident that they are dealing with firms where TCF is central to the corporate culture."),
        ("Outcome 2", "Products and services marketed and sold are designed to meet the needs of identified customer groups."),
        ("Outcome 3", "Customers are given clear information and are kept appropriately informed before, during and after the time of contracting."),
        ("Outcome 4", "Where customers receive advice, the advice is suitable and takes account of their circumstances."),
        ("Outcome 5", "Customers are provided with products that perform as firms have led them to expect, and the associated service is of an acceptable standard."),
        ("Outcome 6", "Customers do not face unreasonable post-sale barriers to change products, switch providers, submit claims or make complaints."),
    ]
    d.table(["Outcome", "What it means"], [list(o) for o in outcomes], [0.18, 0.82])
    d.h2("How we measure TCF")
    d.table(
        ["Measure", "Target", "Owner"],
        [
            ["Claims rejection rate (household)", "Below 12%", "Head of Claims"],
            ["Complaints upheld in the customer's favour", "Reported monthly, no target", "Complaints Manager"],
            ["Complaints resolved within 6 weeks", "95%", "Complaints Manager"],
            ["Ombud determinations against us", "Fewer than 10 per year", "Chief Compliance Officer"],
            ["Policies lapsed within 3 months of sale", "Below 8%", "Head of Distribution"],
        ],
        [0.45, 0.3, 0.25],
    )
    d.h1("Complaints process", new_page=True)
    d.clauses(
        "Any employee who receives a complaint must log it on the complaints register on the "
        "same business day, whether it is resolved immediately or not.",
        "Acknowledge the complaint in writing within 3 business days, giving the reference "
        "number and the name of the person handling it.",
        "Resolve the complaint within 6 weeks. If it cannot be resolved within 6 weeks, inform "
        "the complainant of the reasons and their right to go to the ombud.",
        "Complaints about a claim rejection are reviewed by someone who was not involved in the "
        "original decision.",
        "The final response must explain the outcome, the reasons, any compensation offered, and "
        "the complainant's right to refer the matter to the National Financial Ombud Scheme South "
        "Africa within 6 months.",
        "Compensation for poor service (goodwill payments) up to R5,000 may be approved by the "
        "Complaints Manager; above R5,000 the Chief Compliance Officer must approve.",
    )
    d.h1("Complaint categories")
    cats = [
        ["Claims", "Rejections, delays, settlement amounts"],
        ["Policy administration", "Incorrect premiums, debit orders, documents"],
        ["Sales and advice", "Unsuitable products, misleading information"],
        ["Service", "Unanswered calls, rude staff, missed callbacks"],
        ["Privacy", "Personal information concerns — also notify the Information Officer"],
        ["Intermediary conduct", "Complaints about brokers or agents acting for us"],
    ]
    d.table(["Category", "Examples"], cats, [0.3, 0.7])
    d.h1("Records and reporting")
    d.clauses(
        "The complaints register must be kept for at least 5 years from the date a complaint is resolved.",
        "The Complaints Manager reports complaint volumes, causes and turnaround times to the "
        "Board Risk and Compliance Committee every quarter.",
        "Complaint data is reported to the FSCA in the format and at the times the regulator requires.",
        "Root-cause analysis is done for any complaint category that rises by more than 20% in a quarter.",
    )
    _version_history(d, [("2.0", "1 March 2026", "Aligned to the National Financial Ombud Scheme")])
    _raci(d, [
        "Log a complaint", "Acknowledge a complaint", "Investigate a claims complaint",
        "Approve goodwill up to R5,000", "Approve goodwill above R5,000",
        "Respond to the ombud", "Quarterly complaints report", "Root-cause analysis",
    ])
    _training(d, "Complaints and TCF")
    d.annexure("A", "Complaint case studies")
    for n in range(1, 91):
        who = person()
        cat = RNG.choice(cats)[0]
        days = RNG.randrange(5, 60)
        d.h3(f"Case {n}: {cat.lower()} complaint")
        d.p(
            f"{who} complains about {cat.lower()}. The complaint is acknowledged within 3 business "
            f"days and resolved after {days} days"
            + (", within the 6-week target." if days <= 42 else
               ", outside the 6-week target, so the complainant was told the reasons and their right to go to the ombud."),
        )

    case("Within how many business days must a complaint be acknowledged?", "3 business days", d,
         "Acknowledge the complaint in writing within 3 business days")
    case("What is the target to resolve complaints?", "Within 6 weeks", d, "Resolve the complaint within 6 weeks")
    case("Who can approve a goodwill payment of R8,000?", "The Chief Compliance Officer (above R5,000)", d,
         "above R5,000 the Chief Compliance Officer must approve")
    case("How long must the complaints register be kept?", "At least 5 years from resolution", d,
         "kept for at least 5 years")
    case("What is TCF outcome 6?", "No unreasonable post-sale barriers to change products, switch providers, claim or complain", d,
         "unreasonable post-sale barriers")
    return d


# --- privacy ---------------------------------------------------------------------------------


def privacy() -> Doc:
    d = Doc(
        filename="KR-GOV-004-privacy-and-information-protection-policy.pdf",
        title="Privacy and Information Protection Policy",
        subtitle="POPIA compliance, retention and security incident response",
        code="KR-GOV-004",
        audience="All staff, contractors and operators",
    )
    _purpose(
        d,
        "This policy sets out how Kestrel Ridge complies with the Protection of Personal "
        "Information Act 4 of 2013 (POPIA) and keeps personal information secure.",
        "It applies to all personal information of policyholders, claimants, beneficiaries, "
        "employees and suppliers, in any format.",
        "Information Officer (the Chief Executive Officer, who has delegated duties to the Deputy Information Officer)",
    )
    d.h1("The eight conditions for lawful processing", new_page=True)
    conditions = [
        ("Accountability", "Kestrel Ridge is responsible for complying with all the conditions."),
        ("Processing limitation", "Process only what is adequate, relevant and not excessive, with a lawful justification such as the contract or consent."),
        ("Purpose specification", "Collect information for a specific, defined purpose and keep it no longer than needed."),
        ("Further processing limitation", "Further processing must be compatible with the original purpose."),
        ("Information quality", "Take reasonable steps to keep information complete, accurate and up to date."),
        ("Openness", "Tell people what we collect and why, through privacy notices."),
        ("Security safeguards", "Protect information against loss, damage and unauthorised access."),
        ("Data subject participation", "People may access and correct their information."),
    ]
    d.table(["Condition", "What it requires"], [list(c) for c in conditions], [0.3, 0.7])
    d.h1("Special personal information")
    d.clauses(
        "Health information, criminal records and biometric information are special personal "
        "information. We process them only where POPIA allows, for example to assess life and "
        "disability claims, and with the data subject's consent where required.",
        "Medical underwriting information may be seen only by underwriting and claims staff with "
        "a need to know, and is stored in the restricted medical vault.",
    )
    d.h1("Retention schedule", new_page=True)
    d.table(
        ["Record", "Minimum retention", "Reason"],
        [
            ["Policy records", "5 years after the policy ends", "FICA and insurance regulations"],
            ["Claim files", "5 years after the claim is closed", "Prescription and regulatory review"],
            ["Customer due diligence records", "5 years after the relationship ends", "FICA section 23"],
            ["Call recordings", "5 years", "Regulatory requirements for advice"],
            ["Complaints register", "5 years after resolution", "Policyholder Protection Rules"],
            ["Unsuccessful applications", "12 months", "Dispute handling"],
            ["CCTV footage at offices", "30 days unless needed for an incident", "Security"],
        ],
        [0.35, 0.33, 0.32],
    )
    d.h1("Requests from data subjects")
    d.clauses(
        "Access requests (PAIA Form 2 or POPIA Form 1) are logged by the Deputy Information "
        "Officer and answered within 30 days.",
        "Correction or deletion requests (POPIA Form 2) are answered within 30 days. We may "
        "refuse to delete information the law requires us to keep, and must explain why.",
        "Objections to direct marketing must be actioned within 7 business days.",
    )
    d.h1("Security compromises", new_page=True)
    d.clauses(
        "Any employee who suspects that personal information has been lost, stolen or accessed "
        "without authorisation must report it to the information security team within 1 hour "
        "of becoming aware of it.",
        "The Information Officer must notify the Information Regulator, using the prescribed "
        "form, as soon as reasonably possible. Our internal target is within 72 hours of "
        "confirming the compromise.",
        "Affected data subjects must be notified in writing as soon as reasonably possible, "
        "unless the Information Regulator or SAPS asks us to delay because it would impede an investigation.",
        "Every compromise is recorded in the incident register, with its cause, the information "
        "affected, the people notified and the corrective actions.",
    )
    d.h1("Operators and cross-border transfers")
    d.clauses(
        "Service providers who process personal information for us (operators), such as call "
        "centres, assessors and cloud providers, must sign a written agreement with security obligations.",
        "Personal information may be transferred outside South Africa only to countries with "
        "adequate protection, or with binding agreements that give equivalent protection.",
    )
    _version_history(d, [("3.0", "1 March 2026", "Incident response target set at 72 hours")])
    _raci(d, [
        "Report a suspected compromise", "Contain a compromise", "Notify the Information Regulator",
        "Notify data subjects", "Answer an access request", "Approve an operator agreement",
        "Approve a cross-border transfer", "Maintain the retention schedule",
    ])
    _training(d, "Privacy and POPIA")
    d.annexure("A", "Incident scenarios")
    events = [
        "a laptop with claim files is stolen from an assessor's car",
        "an email with a client's medical report is sent to the wrong broker",
        "a phishing email leads to a staff member's mailbox being accessed",
        "printed policy schedules are found in a public bin",
        "a call-centre operator's database is exposed on the internet",
    ]
    for n in range(1, 61):
        e = events[(n - 1) % len(events)]
        d.h3(f"Scenario {n}")
        d.p(
            f"Situation: {e}. The employee reports it to the information security team within 1 "
            "hour. The team confirms the compromise, the Information Officer notifies the "
            "Information Regulator within 72 hours of confirmation, and the affected data "
            f"subjects ({RNG.randrange(1, 4000)} people) are told what happened and what they can do.",
        )

    case("How quickly must staff report a suspected data breach internally?", "Within 1 hour of becoming aware", d,
         "within 1 hour of becoming aware of it")
    case("What is the internal target for notifying the Information Regulator?", "Within 72 hours of confirming the compromise", d,
         "within 72 hours of confirming the compromise")
    case("How long are claim files kept?", "5 years after the claim is closed", d, "5 years after the claim is closed")
    case("How long is CCTV footage kept?", "30 days unless needed for an incident", d, "30 days unless needed for an incident")
    case("How quickly must direct-marketing objections be actioned?", "Within 7 business days", d,
         "actioned within 7 business days")
    return d


# --- financial crime -------------------------------------------------------------------------


def financial_crime() -> Doc:
    d = Doc(
        filename="KR-GOV-003-financial-crime-and-fraud-policy.pdf",
        title="Financial Crime, Anti-Money Laundering and Fraud Policy",
        subtitle="FICA compliance, reporting and fraud prevention",
        code="KR-GOV-003",
        audience="All staff (internal)",
    )
    _purpose(
        d,
        "This policy explains how Kestrel Ridge prevents its products being used for money "
        "laundering, terrorist financing and fraud, and how it meets the Financial Intelligence "
        "Centre Act 38 of 2001 (FICA).",
        "Long-term insurance products are covered by FICA as accountable-institution business; "
        "short-term products are covered by our fraud controls and by the reporting duties that "
        "apply to every business.",
        "Money Laundering Reporting Officer (MLRO)",
    )
    d.h1("Risk-based approach", new_page=True)
    d.clauses(
        "Our Risk Management and Compliance Programme (RMCP) rates every client as low, medium "
        "or high risk using product, channel, geography and client factors.",
        "Domestic prominent influential persons (DPIPs) and foreign prominent public officials "
        "(FPPOs) are high risk. Business relationships with them need senior management approval "
        "and their source of funds must be established.",
        "Every client is screened against the targeted financial sanctions list before a policy "
        "is issued and whenever the list changes.",
    )
    d.h1("Customer due diligence")
    d.table(
        ["Risk", "Identity verification", "Additional steps"],
        [
            ["Low", "ID number verified against the Department of Home Affairs", "None"],
            ["Medium", "As low, plus proof of address", "Source of funds for single premiums above R100,000"],
            ["High", "As medium", "Source of wealth, senior approval, enhanced monitoring every 6 months"],
        ],
        [0.15, 0.45, 0.40],
    )
    d.h1("Reporting to the Financial Intelligence Centre", new_page=True)
    d.clauses(
        "Suspicious and unusual transaction reports (STRs) must be filed with the FIC as soon as "
        "possible, and no later than 15 business days after the suspicion arose.",
        "Cash threshold reports (CTRs) must be filed for cash transactions above R49,999.99, "
        "within 3 business days. Kestrel Ridge does not accept cash premiums, so a CTR would "
        "arise only if a cash payment was received in error.",
        "Terrorist property reports must be filed immediately when property linked to terrorism "
        "or a sanctioned person is identified.",
        "Never tell the client, or anyone not entitled to know, that a report was or will be made "
        "(tipping off is a criminal offence).",
        "Staff report suspicions internally to the MLRO, who decides whether to file. The MLRO's "
        "decision and reasons are recorded.",
    )
    d.h1("Fraud prevention")
    d.clauses(
        "All new claims pass through automated fraud rules and industry database checks.",
        "Staff may report fraud anonymously through the ethics hotline, 0800 000 333 (fictional), "
        "which is operated by an independent provider.",
        "Kestrel Ridge prosecutes fraud wherever evidence allows and reports convicted fraudsters "
        "to industry fraud databases.",
        "Internal fraud by employees leads to dismissal, criminal charges and recovery of losses.",
    )
    d.h1("Records and training")
    d.clauses(
        "Customer due diligence and transaction records are kept for at least 5 years after the "
        "business relationship ends or the transaction is concluded.",
        "Every employee completes financial crime training when they join and every 12 months after.",
        "The RMCP is reviewed by internal audit at least every 2 years.",
    )
    _version_history(d, [("5.1", "1 March 2026", "CTR guidance updated")])
    _raci(d, [
        "Verify a client's identity", "Screen against the sanctions list", "Approve a DPIP or FPPO relationship",
        "Report a suspicion internally", "File an STR with the FIC", "File a CTR",
        "Review the RMCP", "Investigate internal fraud",
    ])
    _training(d, "Financial crime")
    d.annexure("A", "Red-flag scenarios")
    flags = [
        "a client pays a large single premium and cancels the policy within the cooling-off period, asking for the refund to be paid to a third party",
        "a beneficiary is changed to an unrelated person shortly before the life insured dies",
        "a client is reluctant to give source-of-funds information",
        "several policies are bought by the same person in different family names",
        "a client overpays premiums and asks for the excess to be refunded to a different bank",
    ]
    for n in range(1, 61):
        d.h3(f"Scenario {n}")
        d.p(
            f"Situation: {flags[(n - 1) % len(flags)]}. Action: report internally to the MLRO, "
            "who considers filing an STR within 15 business days. Do not tell the client."
        )

    case("How soon must a suspicious transaction report be filed?", "No later than 15 business days after the suspicion arose", d,
         "no later than 15 business days after the suspicion arose")
    case("What is the cash threshold reporting amount?", "Cash transactions above R49,999.99", d,
         "cash transactions above R49,999.99")
    case("How often must staff do financial crime training?", "When they join and every 12 months after", d,
         "when they join and every 12 months after")
    case("Who approves a relationship with a prominent influential person?", "Senior management", d,
         "need senior management approval")
    return d
