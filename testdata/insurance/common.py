"""Shared pieces for the fictional Kestrel Ridge document set: sections every South African
policy document carries (regulatory information, complaints, privacy notice), deterministic
"random" data for worked examples, and the answer key that generate.py writes as JSONL."""

import random

from builder import COMPANY, LIFE_COMPANY, Doc

RNG = random.Random(20260301)  # fixed seed: the same PDFs every run

PROVINCES = [
    "Gauteng",
    "Western Cape",
    "KwaZulu-Natal",
    "Eastern Cape",
    "Free State",
    "Limpopo",
    "Mpumalanga",
    "North West",
    "Northern Cape",
]
TOWNS = {
    "Gauteng": ["Johannesburg", "Pretoria", "Soweto", "Benoni", "Centurion", "Midrand"],
    "Western Cape": ["Cape Town", "Stellenbosch", "George", "Paarl", "Somerset West"],
    "KwaZulu-Natal": ["Durban", "Pietermaritzburg", "Ballito", "Richards Bay", "Umhlanga"],
    "Eastern Cape": ["Gqeberha", "East London", "Mthatha", "Makhanda"],
    "Free State": ["Bloemfontein", "Welkom", "Bethlehem"],
    "Limpopo": ["Polokwane", "Thohoyandou", "Tzaneen"],
    "Mpumalanga": ["Mbombela", "eMalahleni", "Secunda"],
    "North West": ["Rustenburg", "Mahikeng", "Klerksdorp"],
    "Northern Cape": ["Kimberley", "Upington", "Springbok"],
}
FIRST = [
    "Thabo", "Naledi", "Sipho", "Ayanda", "Pieter", "Annelie", "Fatima", "Riaan", "Lerato",
    "Zanele", "Johan", "Priya", "Kagiso", "Nomvula", "Andile", "Megan", "Tumelo", "Refilwe",
    "Mohammed", "Chantelle", "Bongani", "Lindiwe", "Ruan", "Kayla", "Musa", "Palesa", "Deon",
    "Anika", "Themba", "Yusuf",
]
LAST = [
    "Mokoena", "Dlamini", "van der Merwe", "Naidoo", "Botha", "Khumalo", "Pillay", "Nkosi",
    "Smith", "Mahlangu", "Pretorius", "Ndlovu", "Jacobs", "Mthembu", "Govender", "Venter",
    "Sithole", "Adams", "Molefe", "Coetzee",
]

CASES: list[dict] = []


def case(question: str, answer: str, doc: Doc, evidence: str) -> None:
    """One answer-key entry. The evidence must appear verbatim in the document's text —
    generate.py checks every one against the extracted PDF text."""
    CASES.append(
        {
            "kind": "qa",
            "question": question,
            "reference_answer": answer,
            "relevant_documents": [doc.filename],
            "evidence": evidence,
        }
    )


def refusal(question: str) -> None:
    """A question none of the documents answer — a good system says it doesn't know."""
    CASES.append({"kind": "refusal", "question": question})


def person() -> str:
    return f"{RNG.choice(FIRST)} {RNG.choice(LAST)}"


def place() -> tuple[str, str]:
    prov = RNG.choice(PROVINCES)
    return RNG.choice(TOWNS[prov]), prov


def money(amount: float) -> str:
    """R12,345 or R12,345.67 — South African rand, comma thousands."""
    if abs(amount - round(amount)) < 0.005:
        return f"R{round(amount):,}"
    return f"R{amount:,.2f}"


def fmt_date(day: int, month: int, year: int = 2026) -> str:
    months = [
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December",
    ]
    return f"{day} {months[month - 1]} {year}"


# --- sections every policy document carries ----------------------------------------------


def how_to_read(doc: Doc, product: str) -> None:
    doc.h1("About this policy wording")
    doc.p(
        f"This document is the policy wording for the {product}. Read it together with your "
        "policy schedule, which shows the sections you have chosen, your sums insured, your "
        "premium and any endorsements that apply only to you. The policy wording, the schedule "
        "and any endorsements together form the contract between you and us.",
        "Where the schedule and this wording differ, the schedule applies. Headings are there "
        "to help you find your way and do not change the meaning of a clause. Words in bold "
        "type the first time they appear have the meaning given in the Definitions section.",
    )
    doc.h2("Plain language commitment")
    doc.p(
        "We have tried to write this policy in plain language, as the Policyholder Protection "
        "Rules expect. If anything is unclear, ask your intermediary or contact us before you "
        "need to claim. We would rather explain a clause now than disappoint you later.",
    )
    doc.h2("Your duty of disclosure")
    doc.clauses(
        "You must give us full and truthful answers to every question we ask when you apply, "
        "when you renew and when you change your cover. A material fact is any fact that a "
        "reasonable, prudent person would consider relevant to whether we accept the risk and "
        "on what terms.",
        "If you do not disclose a material fact, or misrepresent one, we may change the terms "
        "of the policy, reduce a claim payment in proportion to the premium you would have "
        "paid, or cancel the policy from the date of the non-disclosure, as the law allows.",
        "You must tell us within 30 days of any change that may affect your cover, such as a "
        "change of address, a change in the use of insured property, or new security measures.",
    )


def regulatory(doc: Doc, *, life: bool = False) -> None:
    insurer = LIFE_COMPANY if life else COMPANY
    act = "Long-term Insurance Act 52 of 1998" if life else "Short-term Insurance Act 53 of 1998"
    doc.h1("Regulatory information", new_page=True)
    doc.p(
        f"{insurer} is a licensed insurer in terms of the Insurance Act 18 of 2017 and is "
        "regulated by the Prudential Authority (for its financial soundness) and the Financial "
        "Sector Conduct Authority (FSCA, for how it treats customers). This policy is also "
        f"subject to the {act} and the Policyholder Protection Rules made under it.",
        "Our fictional registration details: registration number 2009/000000/06, authorised "
        "financial services provider FSP 99901. Registered office: 14 Fictional Avenue, "
        "Sandton, 2196. These details exist only in this test document.",
    )
    doc.h2("Disclosures under the FAIS Act")
    doc.clauses(
        "Advice on this product is given by your intermediary, who must be authorised under the "
        "Financial Advisory and Intermediary Services Act 37 of 2002 (FAIS Act) and must give "
        "you their FSP number, their professional indemnity cover and any conflicts of interest.",
        "Intermediaries are paid commission by us within the limits set by regulation. You may "
        "ask your intermediary to disclose the commission they earn on your policy.",
        "If you buy directly from us without advice, our call-centre staff may give you factual "
        "information but may not recommend a product to you.",
    )
    doc.h2("Important contact details")
    doc.table(
        ["Who", "What for", "How to reach them"],
        [
            ["Kestrel Ridge claims", "Report a claim, 24 hours a day", "0800 000 111 (fictional) · claims@kestrelridge.example"],
            ["Kestrel Ridge client care", "Policy changes and questions", "0800 000 222 (fictional) · care@kestrelridge.example"],
            ["Kestrel Ridge complaints", "Complaints about us", "complaints@kestrelridge.example"],
            ["National Financial Ombud Scheme South Africa (NFO)", "Unresolved complaints", "See the NFO's website"],
            ["Financial Sector Conduct Authority (FSCA)", "Conduct of insurers", "See the FSCA's website"],
            ["Information Regulator", "Personal information complaints", "See the Information Regulator's website"],
        ],
        [0.28, 0.32, 0.40],
    )


def complaints(doc: Doc) -> None:
    doc.h1("Complaints")
    doc.p(
        "We want to hear from you when something goes wrong. A complaint is any expression of "
        "dissatisfaction about our service or product, whether or not you use the word "
        "complaint. Complaining never affects how we treat your claims or your cover.",
    )
    doc.clauses(
        "Contact us at complaints@kestrelridge.example, by phone, or through your intermediary. "
        "We acknowledge every complaint within 3 business days and give you the name of the "
        "person handling it.",
        "We aim to resolve complaints within 6 weeks of receiving them. If we need longer, we "
        "tell you why and when you can expect an answer.",
        "If you are not satisfied with our final response, or we have not resolved your "
        "complaint within 6 weeks, you may refer it to the National Financial Ombud Scheme South "
        "Africa (NFO), which deals with complaints about insurers at no cost to you.",
        "The ombud generally expects you to refer a complaint within 6 months of our final "
        "response. Using the ombud does not take away your right to go to court.",
    )


def privacy_notice(doc: Doc) -> None:
    doc.h1("How we use your personal information")
    doc.p(
        "We process personal information in line with the Protection of Personal Information "
        "Act 4 of 2013 (POPIA). This notice summarises what we do; our full Privacy and "
        "Information Protection Policy (document KR-GOV-004) explains it in detail.",
    )
    doc.clauses(
        "We use your information to assess your application, administer your policy, handle "
        "claims, prevent and detect fraud, and meet our legal duties.",
        "We may share information with intermediaries, assessors, repairers, reinsurers and "
        "industry databases used by insurers to prevent fraud, only as far as needed for these "
        "purposes.",
        "You may ask to see the information we hold about you and ask us to correct it. We "
        "respond to access requests within 30 days.",
        "We keep policy and claim records for at least 5 years after the policy ends, because "
        "the law requires it.",
    )


# --- specimen schedules: realistic bulk, and exact identifiers to retrieve -------------------

STREETS = ["Acacia", "Protea", "Jacaranda", "Marula", "Baobab", "Fynbos", "Aloe", "Karee", "Wild Olive", "Yellowwood"]


def specimen_schedules(doc: Doc, prefix: str, count: int, sections) -> list[dict]:
    """Add an annexure of specimen policy schedules for fictitious clients.

    sections(rng) returns [(section, sum insured, premium)] for one schedule. Returns the
    schedules so the caller can turn a few of them into answer-key questions."""
    from builder import COMPANY  # noqa: F401 - documents the issuer below

    made = []
    for n in range(count):
        number = f"{prefix}-{100_200 + n * 37}"
        who = person()
        town, prov = place()
        start = fmt_date(RNG.randrange(1, 28), RNG.randrange(1, 13), RNG.choice([2023, 2024, 2025]))
        rows = sections(RNG)
        total = round(sum(r[2] for r in rows), 2)
        sasria = round(total * 0.012, 2)
        doc.h3(f"Specimen schedule {n + 1}: policy {number}")
        doc.table(
            ["Field", "Detail"],
            [
                ["Policy number", number],
                ["Policyholder", f"{who} (fictitious person)"],
                ["Risk address", f"{RNG.randrange(1, 240)} {RNG.choice(STREETS)} Street, {town}, {prov}"],
                ["Inception date", start],
                ["Payment", "Monthly debit order on the " + RNG.choice(["1st", "15th", "25th"]) + " of each month"],
                ["Intermediary", f"{RNG.choice(LAST)} Brokers (fictional), FSP {RNG.randrange(10000, 59999)}"],
            ],
            [0.3, 0.7],
        )
        doc.table(
            ["Section", "Sum insured / limit", "Monthly premium"],
            [[s, si if isinstance(si, str) else money(si), money(p)] for s, si, p in rows]
            + [["SASRIA", "As per sections", money(sasria)], ["Total monthly premium", "", money(round(total + sasria, 2))]],
            [0.45, 0.3, 0.25],
        )
        made.append({"number": number, "who": who, "town": town, "rows": rows, "total": round(total + sasria, 2)})
    return made
