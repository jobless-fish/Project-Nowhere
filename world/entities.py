"""External parties of the fictional Nowhere world: customers, partners, vendors, investors. All invented."""
import random

from .people import GIVEN, SURNAMES

# group -> [(company, domain, what they are)]
COMPANIES = {
    "insurer": [("한빛손해보험", "hanbit-ins.example", "손해보험사"), ("다온생명", "daon-life.example", "생명보험사"), ("새벽화재해상", "saebyeok-fire.example", "손해보험사"),
                ("청솔생명", "cheongsol-life.example", "생명보험사"), ("미르손해보험", "mir-ins.example", "손해보험사"), ("은하라이프", "eunha-life.example", "생명보험사")],
    "ga": [("청솔GA", "cheongsol-ga.example", "보험대리점"), ("해든파트너스GA", "haedeun-ga.example", "보험대리점"), ("온누리에셋GA", "onnuri-ga.example", "보험대리점")],
    "vendor": [("클라우드웍스", "cloudworks.example", "클라우드 인프라"), ("시큐어넷", "securenet.example", "보안 컨설팅"), ("리걸브릿지", "legalbridge.example", "법무법인"),
               ("피플리스트", "peoplelist.example", "채용 플랫폼"), ("오피스온", "officeon.example", "사무용품"), ("데이터레이크랩", "datalakelab.example", "데이터 플랫폼")],
    "investor": [("가온벤처스", "gaon-vc.example", "벤처캐피탈"), ("한강인베스트", "hangang-invest.example", "투자사")],
}
POOL = {g: [c for c in cs] for g, cs in COMPANIES.items()}


def contact(rnd: random.Random, group: str):
    """-> (display name, email) of a random contact person at a random company of the group."""
    co, domain, _kind = rnd.choice(POOL[group])
    (s, sr), (g, gr) = rnd.choice(SURNAMES), rnd.choice(GIVEN)
    return f"{s}{g} ({co})", f"{gr}.{sr}@{domain}", co
