"""All tunable settings in one place: roles, search keywords, cities, filter patterns.

India entry-level tech jobs for a fresh Computer Science graduate: 0–2 years, internships included.
"""
import re

# How far back to collect (the UI then narrows to 1 day / 3 days / ... / 2 weeks).
DAYS_BACK = 14
# Jobs posted before this are not stored at all (company boards keep old jobs open for months).
KEEP_DAYS = 21

# --------------------------------------------------------------------------------------
# Role groups, matched on the job TITLE. A job can be in several groups.
# --------------------------------------------------------------------------------------
ROLES = {
    "Software Engineer / SDE": [
        r"\bsoftware\s*(development\s*|dev\s*)?(engineer|engg|developer)", r"\bsde\b", r"\bswe\b",
        r"\bmember\s*of\s*technical\s*staff", r"\bmts\b", r"\bprogrammer\b", r"\bapplication\s*(developer|engineer)",
        r"\b(associate|junior|jr\.?|graduate|trainee|entry[\s-]*level)\s*(software\s*|it\s*)?(engineer|developer|programmer)\b",
        r"\b(engineer|developer|software|it|technology)\s*(trainee|apprentice)\b", r"\bgraduate\s*engineer\s*trainee",
        r"\bproduct\s*engineer\b", r"\bforward\s*deployed\s*engineer", r"\bsolutions?\s*engineer\b",
        r"\bsoftware\s*(development|engineering)\b", r"\b(sde|swe|software|engineering|developer|tech(nology)?)\s*interns?(hip)?\b",
    ],
    "Backend": [
        r"\bback[\s-]*end\b", r"\bjava\b(?!\s*script)", r"\bpython\b", r"\bgolang\b", r"\bgo\s*(lang\s*)?(developer|engineer)\b",
        r"\bnode\.?\s*js\b|\bnodejs\b|\bnode\s*developer", r"\.net\b|\bdot\s*net\b|\bc#", r"\bphp\b|\blaravel\b",
        r"\bdjango\b|\bflask\b|\bfastapi\b", r"\bspring(\s*boot)?\b", r"\bruby\b|\brails\b", r"\bapi\s*(developer|engineer)",
        r"\brust\b", r"\bscala\b", r"\bc\+\+", r"\bmicroservices?\b",
    ],
    "Frontend": [
        r"\bfront[\s-]*end\b", r"\breact(\.?js)?\b(?!\s*native)", r"\bangular\b", r"\bvue(\.?js)?\b", r"\bnext\.?js\b",
        r"\bui\s*(developer|engineer)\b", r"\bjavascript\b", r"\btypescript\b", r"\bweb\s*(developer|engineer|development)\b",
    ],
    "Full Stack": [r"\bfull[\s-]*stack\b", r"\bmern\b", r"\bmean\s*stack\b"],
    "Mobile": [
        r"\bandroid\b", r"\bios\b", r"\bflutter\b", r"\breact\s*native\b", r"\bmobile\s*(app(lication)?\s*)?(developer|engineer|development)",
        r"\bswift\b", r"\bkotlin\b",
    ],
    "AI / ML": [
        r"\bai\b", r"\bml\b", r"\bartificial\s*intelligence", r"\bmachine\s*learning", r"\bdeep\s*learning",
        r"\bgen\s*-?\s*ai\b|\bgenerative\b", r"\bllms?\b", r"\bnlp\b", r"\bcomputer\s*vision\b", r"\bdata\s*scien",
        r"\bmlops\b", r"\bapplied\s*scien", r"\bprompt\s*engineer", r"\bagentic\b|\bai\s*agents?\b", r"\bresearch\s*engineer",
    ],
    "Data": [
        r"\bdata\s*(engineer|analyst|analytics|engineering)\b", r"\bbig\s*data\b", r"\betl\b", r"\banalytics\s*engineer",
        r"\bbi\s*(developer|engineer|analyst)\b", r"\bpower\s*bi\b", r"\bsql\s*developer", r"\btableau\b", r"\bspark\b",
        r"\bdatabricks\b", r"\bsnowflake\b",
    ],
    "DevOps / Cloud": [
        r"\bdev\s*ops\b|\bdevsecops\b", r"\bsre\b", r"\bsite\s*reliability", r"\bcloud\s*(engineer|developer)",
        r"\bplatform\s*engineer", r"\binfrastructure\s*engineer", r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bkubernetes\b",
    ],
    "QA / SDET": [
        r"\bsdet\b", r"\bqa\b", r"\bquality\s*assurance", r"\bsoftware\s*quality", r"\btest(ing)?\s*(engineer|automation|analyst)",
        r"\bautomation\s*(test|tester|engineer|testing)", r"\btester\b", r"\bselenium\b", r"\bsoftware\s*test",
    ],
    "Other developer": [
        r"\bsalesforce\b", r"\bsap\s*(abap|developer|technical)", r"\bservicenow\b", r"\bembedded\b", r"\bfirmware\b",
        r"\bblockchain\b|\bweb3\b|\bsolidity\b", r"\bgame\s*(developer|programmer|engineer)", r"\bunity\b|\bunreal\b",
        r"\bsecurity\s*engineer\b|\bcyber\s*security\b|\bappsec\b", r"\bdeveloper\b", r"\bcoder\b", r"\brpa\b|\buipath\b",
    ],
}

# Titles that are never developer jobs, even if they mention "AI", "Python", "Java", ...
NOT_DEV = re.compile(
    r"\b(sales|business\s*development|bde|bdm|marketing|seo|telecall\w*|tele[\s-]*sales|counsell?or|counsell?ing|"
    r"customer|bpo|voice\s*process|non[\s-]*voice|call\s*cent(er|re)|recruit\w*|talent\s*acquisition|hr|human\s*resources?|"
    r"teacher|tutor|faculty|professor|lecturer|trainer|mentor|educator|content|writer|copywriter|graphic|video\s*editor|"
    r"accountant|accounts|account\s*(executive|manager)|finance|financial|operations\s*(executive|associate)|back\s*office|"
    r"data\s*entry|admin|administrator|receptionist|support|helpdesk|help\s*desk|service\s*desk|technician|"
    r"field\s*(engineer|executive|sales)|civil|mechanical|electrical|ece|eee|hardware|network\s*(engineer|admin)|"
    r"pre[\s-]*sales|product\s*manager|project\s*manager|program\s*manager|scrum|business\s*analyst|designer|"
    r"delivery\s*(manager|executive|boy)|insurance|loan|relationship|logistics|warehouse|driver|nurse|pharma\w*|medical|"
    r"doctor|legal|lawyer|chef|guard|annotat\w*|labell?(ing|er)|transcri\w*|"
    r"social\s*media|community|events?|procurement|purchase|store|retail|ad\s*ops|growth\s*hacker|influencer|"
    r"speaker|subject\s*matter\s*expert|sme|rater|evaluator|search\s*quality|translator|linguist|"
    r"cnc|vmc|cam\s*programmer|plc|scada|autocad|solidworks|revit|draughtsman|draftsman)\b",
    re.I,
)

# --------------------------------------------------------------------------------------
# Seniority: hide these (the candidate is a fresher).
# --------------------------------------------------------------------------------------
SENIOR_TITLE = re.compile(
    r"\b(senior|snr|sr\.?|lead|leader|principal|(?<!technical\s)staff|architect|manager|mgr|head|director|vp|"
    r"vice\s*president|avp|chief|cto|expert|mid[\s-]*(level|senior)?|intermediate|experienced|specialist\s*(ii|iii)|"
    r"(sde|swe|engineer|developer|scientist|analyst|programmer)\s*[-–]?\s*(ii|iii|iv|v|2|3|4|5)|l[4-9])\b",
    re.I,
)
# A posting whose minimum required experience is this many years or more is hidden.
# 0–2 year postings are fine (min 0 or 1); "2+ years", "3-5 years" etc. are hidden.
MAX_EXPERIENCE_YEARS = 2

# --------------------------------------------------------------------------------------
# Search terms sent to the job sites (broad; titles are re-checked locally).
# --------------------------------------------------------------------------------------
SEARCH_KEYWORDS = [
    "software engineer", "software developer", "python developer", "java developer",
    "full stack developer", "frontend developer", "react developer", "backend developer",
    "node js developer", "android developer", "flutter developer", "ai engineer",
    "machine learning engineer", "data engineer", "data analyst", "devops engineer",
    "cloud engineer", "qa automation engineer", ".net developer", "web developer",
]
# Smaller set for the slow / rate-limited sites (LinkedIn, Indeed, Glassdoor).
SEARCH_KEYWORDS_LIGHT = [
    "software engineer fresher", "software developer", "entry level software engineer",
    "python developer", "full stack developer", "ai engineer", "data engineer", "software engineer intern",
]
# Naukri internship searches (keyword → internships only).
INTERNSHIP_KEYWORDS = ["software", "web development", "python", "machine learning", "data science"]

# --------------------------------------------------------------------------------------
# Cities. A job can be in several (Naukri lists "Hyderabad, Bengaluru, Delhi / NCR").
# --------------------------------------------------------------------------------------
AREAS = {
    "Bengaluru": ["bengaluru", "bangalore", "blr", "whitefield", "electronic city", "koramangala", "marathahalli"],
    "Hyderabad": ["hyderabad", "secunderabad", "hitec city", "hitech city", "gachibowli", "madhapur", "kondapur", "telangana"],
    "Pune": ["pune", "pimpri", "chinchwad", "hinjewadi", "hinjawadi", "kharadi", "magarpatta"],
    "Chennai": ["chennai", "madras", "sholinganallur", "guindy", "tambaram", "perungudi", "siruseri", "porur"],
    "Delhi NCR": ["delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida", "greater noida", "ghaziabad", "faridabad"],
    "Mumbai": ["mumbai", "bombay", "navi mumbai", "thane", "powai", "andheri", "vashi"],
    "Kolkata": ["kolkata", "calcutta", "salt lake"],
    "Ahmedabad": ["ahmedabad", "gandhinagar", "gift city", "vadodara", "surat"],
    "Kerala": ["kochi", "cochin", "ernakulam", "kakkanad", "trivandrum", "thiruvananthapuram", "technopark", "kozhikode", "calicut", "kerala"],
    "Coimbatore": ["coimbatore"],
    "Andhra Pradesh": ["visakhapatnam", "vizag", "vijayawada", "guntur", "tirupati", "amaravati", "andhra pradesh", "kakinada", "nellore"],
    "Other India": [
        "india", "jaipur", "chandigarh", "mohali", "indore", "bhopal", "bhubaneswar", "nagpur", "lucknow", "mysore", "mysuru",
        "mangalore", "mangaluru", "hubli", "madurai", "trichy", "tiruchirappalli", "dehradun", "kanpur", "patna", "ranchi",
        "raipur", "goa", "nashik", "aurangabad", "sambhajinagar", "jodhpur", "udaipur", "vellore", "salem", "erode",
        "panchkula", "ludhiana", "amritsar", "guwahati", "varanasi", "agra", "meerut", "rajkot", "belgaum", "belagavi",
    ],
    "Remote": ["remote", "work from home", "wfh", "anywhere in india", "pan india", "work from anywhere"],
}

# Clearly outside India (used only when no Indian place is mentioned).
FOREIGN = re.compile(
    r"\b(usa|u\.s\.a?|united\s*states|america|canada|toronto|vancouver|uk|u\.k\.|united\s*kingdom|london|england|ireland|dublin|"
    r"europe|emea|germany|berlin|munich|france|paris|netherlands|amsterdam|spain|poland|portugal|switzerland|sweden|"
    r"australia|sydney|melbourne|new\s*zealand|singapore|malaysia|dubai|uae|abu\s*dhabi|saudi|riyadh|qatar|doha|kuwait|"
    r"oman|bahrain|japan|tokyo|korea|china|hong\s*kong|taiwan|philippines|manila|vietnam|indonesia|thailand|israel|"
    r"mexico|brazil|argentina|colombia|south\s*africa|nigeria|kenya|egypt|other\s*international|overseas|abroad|"
    r"san\s*francisco|new\s*york|seattle|austin|boston|chicago|los\s*angeles|bay\s*area|silicon\s*valley|latam|americas)\b",
    re.I,
)

# --------------------------------------------------------------------------------------
# India-specific traps.
# --------------------------------------------------------------------------------------
# Phrases that DENY a fee ("no registration fee") are removed before SCAM is checked.
NO_FEE = re.compile(
    r"\b(no|zero|nil|free\s*of|without\s*any|never\s*(ask|charge)s?\s*(for\s*)?(any\s*)?|don'?t\s*(pay|charge))\s*"
    r"(registration\s*|training\s*|joining\s*|hidden\s*|placement\s*|processing\s*)?(fees?|charges?|costs?|deposits?|money|payments?)\b",
    re.I,
)
SCAM = re.compile(
    r"\b((registration|training|joining|security|refundable|placement|course|processing|documentation|kit|"
    r"onboarding|certification)\s*(fee|fees|charges?|deposit|amount)|pay\s*(a\s*|the\s*)?(fee|deposit)|"
    r"(100\s*%|guaranteed?)\s*(job|placement|interview)s?|job\s*guarantee|placement\s*guarantee|"
    r"pay\s*after\s*(placement|getting\s*(a\s*)?job)|income\s*share\s*agreement|learn\s*(and|&)\s*earn|"
    r"pay\s*(rs\.?|inr|₹)\s*\d|course\s*(cum|\+)\s*(job|internship)|training\s*cum\s*(job|placement)|"
    r"live\s*(project\s*)?training|training\s*(and|&|\+)\s*(placement|internship))",
    re.I,
)
NO_BOND = re.compile(r"\b(no|without\s*any|zero)\s*(service\s*)?bond\b", re.I)
BOND_YEARS = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-\s]?(years?|yrs?|months?)\s*(?:of\s*)?(?:service\s*)?(?:bond|service\s*agreement|commitment)"
    r"|(?:bond|service\s*agreement)\s*(?:of|for|period|duration|tenure)?\s*[:\-–]?\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(years?|yrs?|months?)",
    re.I,
)
BOND_ANY = re.compile(r"\b(service\s*bond|bond\s*(is\s*)?(applicable|mandatory|required)|sign\s*(a\s*)?bond|employment\s*bond)\b", re.I)
CONSULTANCY = re.compile(
    r"\b(consult(ancy|ants?)|placements?|manpower|staffing|recruit\w*|hr\s*(solutions|services|consult\w*)|"
    r"talent\s*(solutions|hub|partners?)|hiring\s*partner|outsourcing|job\s*(portal|consultants?))\b",
    re.I,
)
CONSULTANCY_OK = re.compile(r"\b(tata\s*consultancy|deloitte|boston\s*consulting|mckinsey|kpmg|ibm|accenture|capgemini)\b", re.I)

# --------------------------------------------------------------------------------------
# Skills shown as tags (from the site's own list, plus these words found in the text).
# --------------------------------------------------------------------------------------
SKILL_WORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Golang", "Rust", "Kotlin", "Swift", "PHP", "Ruby", "Scala",
    "SQL", "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "Django", "Flask", "FastAPI", "Spring Boot",
    ".NET", "Flutter", "React Native", "Android", "iOS", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
    "Linux", "Git", "MongoDB", "PostgreSQL", "MySQL", "Redis", "Kafka", "Spark", "Airflow", "Snowflake", "Databricks",
    "Power BI", "Tableau", "Pandas", "PyTorch", "TensorFlow", "scikit-learn", "LLM", "GenAI", "LangChain", "RAG",
    "NLP", "Computer Vision", "Machine Learning", "Deep Learning", "Selenium", "Cypress", "Playwright", "REST", "GraphQL",
    "Microservices", "HTML", "CSS", "Tailwind",
]

# --------------------------------------------------------------------------------------
# Company career boards (official, exact post times). Found with a probe on 2026-11-16:
# each of these had openings in India. Add more any time.
# --------------------------------------------------------------------------------------
BOARDS = {
    "greenhouse": [
        "okta", "databricks", "mongodb", "highradius", "stripe", "inmobi", "gitlab", "zetaglobal", "rubrik", "toast",
        "razorpaysoftwareprivatelimited", "fivetran", "glance", "elastic", "hackerrank", "airbnb", "twilio", "roblox",
        "chargepoint", "druva", "coinbase", "groww", "datadog", "turing", "observeai", "anthropic", "samsara",
        "mixpanel", "appsflyer", "figma", "block", "duolingo", "scaleai", "vercel", "cockroachlabs",
    ],
    "lever": ["paytm", "meesho", "zeta", "fampay", "mindtickle", "cred", "linkedin", "pocketfm", "spotify"],
    "ashby": ["tekion", "sarvam", "clickhouse", "openai", "atlan", "redis", "notion", "deepgram", "temporal", "amplitude", "writer"],
}

# --------------------------------------------------------------------------------------
# Links shown on the site for places that cannot be collected automatically.
# --------------------------------------------------------------------------------------
EXTRA_LINKS = [
    ("Wellfound (AngelList): startup jobs in India", "https://wellfound.com/role/l/software-engineer/india"),
    ("Cutshort: developer jobs", "https://cutshort.io/jobs/software-developer-jobs"),
    ("Hirist: IT jobs", "https://www.hirist.tech/"),
    ("Google careers: early-career roles in India", "https://www.google.com/about/careers/applications/jobs/results/?location=India&target_level=EARLY"),
    ("Microsoft careers: students & graduates (India)", "https://jobs.careers.microsoft.com/global/en/search?lc=India&exp=Students%20and%20graduates"),
    ("Amazon jobs: SDE in India", "https://www.amazon.jobs/en/search?base_query=software+development+engineer&loc_query=India"),
    ("TCS NextStep (NQT)", "https://nextstep.tcs.com/"),
    ("Infosys careers", "https://career.infosys.com/joblist"),
    ("Wipro careers", "https://careers.wipro.com/"),
    ("Accenture India careers", "https://www.accenture.com/in-en/careers/jobsearch"),
    ("Unstop: jobs & hiring challenges", "https://unstop.com/jobs"),
    ("Reddit r/developersIndia: hiring posts", "https://www.reddit.com/r/developersIndia/search/?q=hiring%20fresher&sort=new"),
    ("Google Jobs: software engineer fresher India", "https://www.google.com/search?q=software+engineer+fresher+jobs+india&ibp=htl;jobs"),
]
