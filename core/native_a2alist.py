"""Native agents listed on a2alist.ai. Most are not on a2a-registry.org, so they are reached straight from their own card."""

A2ALIST = [
    {"id": "a2alist.wellknown", "title": "Wellknown Index", "tagline": "Find AI agents, MCP servers and tools by capability",
     "description": "Live index of AI agents, MCP servers and tools. Ask it to find agents for a task, rank candidates with a "
                    "recommendation (start with 'resolve:'), or check a record's observed liveness (start with 'status:'). "
                    "Answers are third-party metadata.",
     "vendor": "Wellknown", "site": "https://wellknown.network", "card": "https://wellknown.network/.well-known/agent-card.json",
     "key_env": "WELLKNOWN_API_KEY", "key_header": "Authorization", "key_prefix": "Bearer ", "key_optional": True,
     "key_url": "https://wellknown.network",
     "skills": ["Search agents & tools", "Resolve with recommendation", "Liveness status"],
     "example": "find an agent that can localize product copy into Japanese",
     "note": "Works without a key; a wk_live_ key only raises rate limits."},
    {"id": "a2alist.musedin", "title": "MusedIn", "tagline": "Job network for AI agents",
     "description": "Agents join, get hired, post jobs and start projects; deliveries are paid in USDC. Ask for open jobs, find "
                    "workers or people by skill, or get a free job draft for something you need done.",
     "vendor": "MusedIn", "site": "https://musedin.com", "card": "https://musedin.com/.well-known/agent-card.json",
     "key_env": "MUSEDIN_API_KEY", "key_header": "Authorization", "key_prefix": "Bearer ", "key_optional": True,
     "key_url": "https://musedin.com/api/quickstart",
     "skills": ["Find jobs", "Find workers", "Draft a job", "Find people", "Join MusedIn"],
     "example": "Which jobs are open on MusedIn?",
     "note": "Reads need no key. A token from POST https://musedin.com/api/quickstart is needed to apply or post jobs."},
    {"id": "a2alist.ticketfairy", "title": "Ticket Fairy", "tagline": "Public event search",
     "description": "Searches public events with no account: filter by text, country, state, upcoming or past, page and sort. "
                    "Buying tickets uses Ticket Fairy's signed checkout, which this tab does not do.",
     "vendor": "Ticket Fairy", "site": "https://www.ticketfairy.com",
     "card": "https://www.ticketfairy.com/.well-known/agent-card.json",
     "skills": ["Search events"],
     "example": '{"country": "AU", "section_type": "upcoming", "page": 1, "size": 5, "sort": "start_date", "order": "asc"}',
     "note": "Takes a JSON filter object, not free text."},
    {"id": "a2alist.heym", "title": "Heym Site Agent", "tagline": "Ask about Heym, the self-hosted AI agent platform",
     "description": "Searches every page, workflow template, playground demo, blog post and doc on heym.run, and reads its "
                    "changelog. Ask in plain words.",
     "vendor": "Heym", "site": "https://heym.run", "card": "https://heym.run/.well-known/agent-card.json",
     "skills": ["Site summary", "Search site", "Changelog", "Blog posts", "Find templates"],
     "example": "What is Heym and does it have templates for customer support?"},
    {"id": "a2alist.surfingdog", "title": "Surfing Dog Search", "tagline": "Businesses that AI agents can book, order or message",
     "description": "A public directory of businesses with agent-reachable doors (booking pages, UCP/ACP shops, MCP, A2A, APIs, "
                    "agent inboxes). Find businesses by what they do and where, or check what an agent can do with a "
                    "business's website.",
     "vendor": "Surfing Dog", "site": "https://surfingdog.ai", "card": "https://surfingdog.ai/.well-known/agent-card.json",
     "skills": ["Search businesses", "Check a business", "Report a door"],
     "example": "dentist in Austin"},
    {"id": "a2alist.elderlycare", "title": "Elderly Care Match", "tagline": "Licensed senior care in Washington State",
     "description": "Searches licensed Washington senior care: adult family homes, assisted living, memory care, nursing homes "
                    "and 55+ communities, filtered by city, ZIP, county, Medicaid, price and open beds. Also searches family "
                    "care guides.",
     "vendor": "Elderly Care Match", "site": "https://www.elderlycarematch.com",
     "card": "https://www.elderlycarematch.com/.well-known/agent-card.json",
     "skills": ["Find care facilities", "Facility details", "Care guides", "Placement help link"],
     "example": "assisted living in Seattle that accepts Medicaid"},
    {"id": "a2alist.carejobs", "title": "CareJobs.Now", "tagline": "Open US healthcare jobs and posted pay",
     "description": "Open US healthcare jobs read nightly from hospitals' and health systems' own job boards: search by kind of "
                    "job, state, employer or pay, see posted hourly pay, and which employers are hiring.",
     "vendor": "CareJobs.Now", "site": "https://carejobs.now", "card": "https://carejobs.now/.well-known/agent-card.json",
     "skills": ["Search healthcare jobs", "Healthcare pay", "Employers & states"],
     "example": "ICU nurse jobs in Texas paying over $50 an hour"},
    {"id": "a2alist.robottraining", "title": "RobotTraining.jobs", "tagline": "Robot training jobs and what they pay",
     "description": "Open robot-training roles (teleoperation, demonstration and data collection, humanoid operation, fleet ops, "
                    "AV and drone testing) from about 74 employers' careers pages, read daily, with hourly pay and market counts.",
     "vendor": "RobotTraining.jobs", "site": "https://robottraining.jobs",
     "card": "https://robottraining.jobs/.well-known/agent-card.json",
     "skills": ["Search jobs", "Pay by kind of work", "Market size"],
     "example": "remote robot teleoperation jobs in India"},
    {"id": "a2alist.arcasos", "title": "ARCASOS", "tagline": "Korean short-term rentals (1 week minimum)",
     "description": "Natural-language search over South Korean short-term rentals: pet-friendly homes, private spaces, river, "
                    "ocean, city or mountain views, and neighbourhoods. Can draft a booking request; it never books or charges.",
     "vendor": "ARCASOS", "site": "https://arcasos.com", "card": "https://arcasos.com/.well-known/agent-card.json",
     "skills": ["Search rentals", "Booking request draft", "Booking status"],
     "example": "pet-friendly private house near Gangnam station for 1 week"},
    {"id": "a2alist.sami", "title": "Sami Vacation Stays", "tagline": "Panama vacation stays: FAQ and discovery calls",
     "description": "Answers questions about Sami Vacation Stays, a personalised Panama hospitality service, from its published "
                    "FAQ in English, French, Spanish and German. Send 'list' for all 30 questions.",
     "vendor": "Sami Vacation Stays", "site": "https://www.samivacationstays.com",
     "card": "https://www.samivacationstays.com/.well-known/agent-card.json",
     "skills": ["FAQ", "Discovery call slots", "Book a discovery call"],
     "example": "Is Panama safe for tourists?"},
    {"id": "a2alist.boim", "title": "BOIM", "tagline": "Korean business directory and public bid finder",
     "description": "Read-only directory of 2.7M+ Korean businesses, vendor procurement records, live public-sector bid notices "
                    "and traditional market days. Query in Korean or English (region + business type, product or name).",
     "vendor": "PublicID Inc.", "site": "https://boim.io", "card": "https://boim.io/.well-known/agent-card.json",
     "skills": ["Find businesses & bids", "Traditional markets"],
     "example": "hair salon in Sejong"},
    {"id": "a2alist.sitepatent", "title": "SitePatent", "tagline": "Search the SitePatent directory",
     "description": "Keyword search over approved SitePatent directory listings: title, tagline, categories and link.",
     "vendor": "SitePatent", "site": "https://sitepatent.com", "card": "https://sitepatent.com/.well-known/agent-card.json",
     "skills": ["Search listings"], "example": "ai code review"},
    {"id": "a2alist.trooids", "title": "TrooIDs", "tagline": "Reception agent for TrooIDs and Digital DNA",
     "description": "Answers about TrooIDs and Digital DNA from the trooids.com knowledge bundle with sources, and routes "
                    "visitors to sales, hiring or support department agents.",
     "vendor": "Information Engine B.V.", "site": "https://trooids.com", "card": "https://trooids.com/.well-known/agent-card.json",
     "skills": ["Reception", "Grounded answers", "Department routing"], "example": "Is TrooIDs a blockchain project?"},
    {"id": "a2alist.hellou", "title": "Hellou AI", "tagline": "HellouOne shared WhatsApp inbox: plans, trial, demo",
     "description": "Answers questions about HellouOne, a shared WhatsApp inbox with AI agents for teams in the US and Latin "
                    "America: plans and prices, the free 7-day trial, booking a demo and reaching sales. English and Spanish.",
     "vendor": "Hellou AI", "site": "https://hellou.ai", "card": "https://hellou.ai/.well-known/agent-card.json",
     "skills": ["Plans & prices", "Start trial", "Book demo", "Contact sales"], "example": "How much is HellouOne?"},
    {"id": "a2alist.outfame", "title": "Outfame Assistant", "tagline": "Outfame plans, free Instagram tools and blog",
     "description": "Answers questions about Outfame's plans and first-month prices, its free Instagram and AI tools, blog "
                    "articles on Instagram and TikTok growth, and how to get started.",
     "vendor": "Outfame", "site": "https://www.outfame.com", "card": "https://www.outfame.com/.well-known/agent-card.json",
     "skills": ["Plans & pricing", "Free tools", "Blog search", "Getting started"],
     "example": "Which free Instagram tools does Outfame have?"},
    {"id": "a2alist.bradford", "title": "Bradford Operations", "tagline": "Post-production: glitch and texture looks, color, DCP",
     "description": "A New York post-production company. Ask whether Bradford can do something for footage or a film: glitch "
                    "and texture looks (OpenFX plugins for DaVinci Resolve), DCP mastering, color, online and deliverables.",
     "vendor": "Bradford Operations", "site": "https://www.bradfordoperations.com",
     "card": "https://www.bradfordoperations.com/.well-known/agent-card.json",
     "skills": ["Glitch looks", "Texture looks", "DCP mastering", "Post-production services"],
     "example": "I want my footage to have a VHS glitch effect"},
    {"id": "a2alist.nabung", "title": "nabung.id", "tagline": "Indonesian personal finance playbook",
     "description": "Evidence-based personal finance and passive investing for Indonesians: emergency fund, BPJS and pension "
                    "gap, SBN, deposito, index funds, sharia options, investment tax and scam avoidance. Indonesian or English.",
     "vendor": "nabung.id", "site": "https://nabung.id", "card": "https://nabung.id/.well-known/agent-card.json",
     "skills": ["Cashflow & emergency fund", "Scam safety", "BPJS & retirement", "Short-term money", "Index funds", "Tax"],
     "example": "how big should my emergency fund be?"},
    {"id": "a2alist.describe", "title": "describe.net", "tagline": "On-chain wallet reputation before you pay",
     "description": "Vets a wallet's on-chain ERC-8004 reputation (EVM 0x... or Solana) for free: identities, score and ratings "
                    "per chain. Send any text without an address for the live index size.",
     "vendor": "Ultravioleta DAO", "site": "https://describe.net", "card": "https://api.describe.net/.well-known/agent-card.json",
     "skills": ["Vet a wallet", "Index status"], "example": "status"},
    {"id": "a2alist.agentsvc", "title": "agentsvc.io", "tagline": "127 web tools for agents (pay per call)",
     "description": "Web scraping to Markdown, summaries, data extraction, email verification, OCR and PDF, news and paper "
                    "search, weather, satellite images, company checks and more. Most tools are paid per call (x402).",
     "vendor": "agentsvc.io", "site": "https://agentsvc.io", "card": "https://agentsvc.io/.well-known/agent-card.json",
     "skills": ["Web scrape", "Email verify", "News search", "Weather", "Audio transcribe", "Satellite image"],
     "example": '{"skill": "weather", "location": "Hyderabad"}',
     "note": "Paid tools answer with a payment request instead of a result."},
]

for _a in A2ALIST:
    _a.update(direct=True, source="a2alist.ai", source_url="https://a2alist.ai")
    _a.setdefault("docs", _a["card"])
    _a.setdefault("key_env", None)
    _a.setdefault("key_header", None)
    _a.setdefault("key_url", _a["site"])
