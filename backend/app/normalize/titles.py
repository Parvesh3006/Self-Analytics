"""Role family and seniority from a job title. Order matters: most specific rules first."""
import re

ROLE_RULES: list[tuple[str, str]] = [
    ("Machine Learning / AI", r"machine learning|\bml\b|\bai\b|deep learning|\bnlp\b|computer vision|llm|applied scientist|research scientist|prompt engineer|mlops"),
    ("Data Science", r"data scien|decision scien|quantitative (analyst|research)|\bquant\b"),
    ("Data Engineering", r"data engineer|analytics engineer|etl|data platform|data warehouse|big data|data architect"),
    ("Data Analysis / BI", r"data analy|business intelligence|\bbi\b (analyst|developer)|reporting analyst|insights analyst|analytics"),
    ("Security", r"secur|cyber|penetration|\bsoc\b|infosec|threat|vulnerability"),
    ("DevOps / SRE / Cloud", r"devops|\bsre\b|site reliability|cloud (engineer|architect)|platform engineer|infrastructure engineer|kubernetes|systems? administrator|sysadmin"),
    ("Mobile", r"\bios\b|android|mobile (engineer|developer)|flutter|react native"),
    ("Frontend", r"front[\s-]?end|\bui (engineer|developer)|react developer|angular developer|vue developer|web developer|web designer developer"),
    ("Backend", r"back[\s-]?end|api (engineer|developer)|java developer|python developer|golang|\.net developer|php developer|ruby developer|node(\.js)? developer"),
    ("Full Stack", r"full[\s-]?stack"),
    ("QA / Test", r"\bqa\b|quality assurance|\bsdet\b|test (engineer|automation|analyst|lead)|tester"),
    ("Embedded / Hardware", r"embedded|firmware|fpga|asic|hardware engineer|electronics|silicon|\bpcb\b|rtl|verification engineer"),
    ("Engineering Management", r"engineering manager|head of engineering|vp,? (of )?engineering|director,? (of )?engineering|\bcto\b|tech(nical)? lead manager"),
    ("Solutions / Sales Engineering", r"solutions? (engineer|architect|consultant)|sales engineer|pre[\s-]?sales|forward deployed|customer engineer"),
    ("IT Support / Administration", r"it support|help ?desk|service desk|desktop support|technical support|network (engineer|administrator)|database administrator|\bdba\b"),
    ("Software Engineering", r"software|developer|programmer|\bswe\b|\bsde\b|coder|architect"),
    ("Product Management", r"product (manager|owner|lead|director)|head of product|\bpm\b"),
    ("Project / Program Management", r"project (manager|coordinator|lead)|program(me)? manager|delivery manager|scrum master"),
    ("Design / UX", r"\bux\b|\bui\b|designer|user research|creative director"),
    ("Mechanical / Civil / Electrical Engineering", r"mechanical|civil|electrical|structural|chemical|process|manufacturing|industrial|mining|aerospace|rail|environmental engineer|geotechnical"),
    ("Engineering (other)", r"engineer"),
    ("Sales", r"\bsales\b|account (executive|manager)|business development|\bbdr\b|\bsdr\b|partnerships"),
    ("Marketing", r"marketing|\bseo\b|content (strategist|writer|manager)|growth|brand|copywriter|social media|communications"),
    ("Customer Success / Support", r"customer (success|support|service|experience)|client (success|service)|support (specialist|agent)"),
    ("Finance / Accounting", r"financ|account(ant|ing)|audit|tax\b|treasury|payroll|controller|bookkeep|actuar"),
    ("HR / Recruiting", r"recruit|talent|human resources|\bhr\b|people (partner|operations)"),
    ("Legal / Compliance", r"legal|counsel|compliance|paralegal|attorney|lawyer|regulatory"),
    ("Healthcare", r"nurse|nursing|physician|doctor|clinical|medical|pharmac|therap|dentist|care (worker|assistant)|paramedic"),
    ("Education", r"teacher|lecturer|professor|tutor|instructor|trainer"),
    ("Operations", r"operations|logistics|supply chain|procurement|warehouse|office manager|administrator|administrative|assistant"),
    ("Business Analysis", r"business analyst|consultant|strategy|analyst"),
]
_COMPILED = [(name, re.compile(rx, re.I)) for name, rx in ROLE_RULES]

SENIORITY_RULES: list[tuple[str, str]] = [
    ("Executive", r"\b(chief|cto|ceo|cfo|ciso|vp|vice president|head of|director)\b"),
    ("Manager", r"\b(manager|mgr)\b"),
    ("Principal / Staff", r"\b(principal|staff|distinguished|fellow)\b"),
    ("Lead", r"\b(lead|architect)\b"),
    ("Senior", r"\b(senior|sr\.?|snr|iii|iv)\b"),
    ("Intern / Graduate", r"\b(intern|internship|graduate|grad|trainee|apprentice|werkstudent|praktikum|stagiaire)\b"),
    ("Junior", r"\b(junior|jr\.?|entry[\s-]level|associate|ii?)\b"),
]
_SEN = [(name, re.compile(rx, re.I)) for name, rx in SENIORITY_RULES]


def role_family(title: str) -> str:
    for name, rx in _COMPILED:
        if rx.search(title):
            return name
    return "Other"


def seniority(title: str) -> str:
    for name, rx in _SEN:
        if rx.search(title):
            return name
    return "Mid / Unspecified"
