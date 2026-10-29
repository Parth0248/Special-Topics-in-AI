"""Curated offline dataset for deterministic execution and testing of Agent A.

Contains diverse candidate companies across industries, funding stages,
geographies, headcount bands, and rich real-world growth triggers.
"""

from typing import Any, Dict, List

MOCK_COMPANIES: List[Dict[str, Any]] = [
    # --- FINTECH ---
    {
        "company_name": "NovaPay Solutions",
        "website": "https://www.novapaysolutions.io",
        "industry": "Fintech",
        "sub_industry": "Cross-Border B2B Payments & Treasury",
        "headquarters": "San Francisco, CA, USA",
        "employee_count": 145,
        "employee_count_range": "51-200",
        "funding_stage": "Series B",
        "total_funding_raised": "$38M",
        "growth_signals": [
            "Raised $25M Series B funding led by Horizon Capital",
            "Expanding APAC sales engineering team by 40 headcount",
            "Achieved SOC 2 Type II compliance certification",
            "Launched multi-currency automated FX hedging API",
        ],
        "overview": (
            "NovaPay Solutions develops enterprise cross-border payment rails and automated "
            "treasury workflows for fast-growing global SaaS and marketplace businesses."
        ),
        "key_offerings": [
            "Multi-Currency Settlement Gateway",
            "Real-time FX Hedging Engine",
            "Automated Vendor Payout Reconciliation",
        ],
        "source_references": [
            "https://techcrunch.com/2025/novapay-series-b-expansion",
            "https://fintechfutures.com/novapay-crossborder-rails",
        ],
    },
    {
        "company_name": "FinFlow Global",
        "website": "https://www.finflow.co.uk",
        "industry": "Fintech",
        "sub_industry": "Open Banking & Lending Infrastructure",
        "headquarters": "London, UK",
        "employee_count": 85,
        "employee_count_range": "51-200",
        "funding_stage": "Series A",
        "total_funding_raised": "$14M",
        "growth_signals": [
            "Announced 120% YoY revenue growth in 2025",
            "Integrated EU PSD3 open banking compliance rails",
            "Hired former Stripe VP as Chief Commercial Officer",
            "Partnered with Tier-1 European digital challenger banks",
        ],
        "overview": (
            "FinFlow Global provides embedded financial APIs that allow digital lenders and neobanks "
            "to assess borrower cashflow and underwrite loans in real-time."
        ),
        "key_offerings": [
            "Open Banking Cashflow Scorer",
            "Embedded Lending Widget SDK",
            "Instant Bank Account Verification API",
        ],
        "source_references": [
            "https://fintechnews.ch/finflow-secures-series-a",
            "https://sifted.eu/articles/finflow-uk-banking-expansion",
        ],
    },
    {
        "company_name": "AstraWealth",
        "website": "https://www.astrawealth.sg",
        "industry": "Fintech",
        "sub_industry": "AI Wealth Management & Robo-Advisory",
        "headquarters": "Singapore",
        "employee_count": 48,
        "employee_count_range": "11-50",
        "funding_stage": "Series A",
        "total_funding_raised": "$9.5M",
        "growth_signals": [
            "Secured Capital Markets Services license from MAS (Singapore)",
            "Launched AI tax-loss harvesting engine for ASEAN markets",
            "Surpassed $500M in assets under management (AUM)",
            "Expanding engineering team in Kuala Lumpur and Jakarta",
        ],
        "overview": (
            "AstraWealth is a private wealth tech platform utilizing generative models to provide "
            "institutional-grade personalized portfolio management for mass-affluent investors across Southeast Asia."
        ),
        "key_offerings": [
            "Robo-Advisory Engine for Private Banks",
            "Algorithmic Tax-Loss Harvesting",
            "Multi-Asset Thematic Portfolios",
        ],
        "source_references": [
            "https://e27.co/astrawealth-series-a-singapore",
            "https://dealstreetasia.com/stories/astrawealth-mas-license",
        ],
    },
    {
        "company_name": "CrediPulse AI",
        "website": "https://www.credipulse.ai",
        "industry": "Fintech",
        "sub_industry": "Credit Underwriting & Risk Intelligence",
        "headquarters": "New York, NY, USA",
        "employee_count": 230,
        "employee_count_range": "201-500",
        "funding_stage": "Series C",
        "total_funding_raised": "$72M",
        "growth_signals": [
            "Signed top-5 US commercial bank for enterprise loan origination",
            "Published benchmark showing 34% reduction in non-performing loans",
            "Opened European regional HQ in Frankfurt, Germany",
        ],
        "overview": (
            "CrediPulse AI deploys explainable deep learning models that evaluate unstructured "
            "financial records to deliver real-time risk ratings for commercial lenders."
        ),
        "key_offerings": [
            "Explainable AI Credit Decision Engine",
            "Commercial Loan Monitoring Radar",
            "Portfolio Stress-Testing Suite",
        ],
        "source_references": [
            "https://americanbanker.com/news/credipulse-enterprise-rollout",
            "https://businesswire.com/news/credipulse-series-c-72m",
        ],
    },

    # --- HEALTHCARE AI / HEALTHTECH ---
    {
        "company_name": "BioSynthetica",
        "website": "https://www.biosynthetica.health",
        "industry": "Healthcare AI",
        "sub_industry": "Computational Pathology & Oncology Diagnostics",
        "headquarters": "Boston, MA, USA",
        "employee_count": 115,
        "employee_count_range": "51-200",
        "funding_stage": "Series B",
        "total_funding_raised": "$42M",
        "growth_signals": [
            "Received FDA 510(k) clearance for AI biopsy analysis software",
            "Formed co-development partnership with Mayo Clinic",
            "Expanded wet-lab computational footprint in Cambridge, MA",
            "Published clinical validation study in Nature Medicine",
        ],
        "overview": (
            "BioSynthetica accelerates cancer diagnosis by analyzing whole-slide digital pathology "
            "images using foundation vision models, reducing turnaround time from days to minutes."
        ),
        "key_offerings": [
            "Digital Slide Triage Cloud",
            "Rare Cell Detection Model",
            "Integrated Pathology LIMS Connector",
        ],
        "source_references": [
            "https://nature.com/articles/biosynthetica-pathology-ai",
            "https://medcitynews.com/biosynthetica-series-b-fda",
        ],
    },
    {
        "company_name": "MedVantage Systems",
        "website": "https://www.medvantagesys.ch",
        "industry": "Healthcare AI",
        "sub_industry": "Clinical Workflow Automation",
        "headquarters": "Zurich, Switzerland",
        "employee_count": 68,
        "employee_count_range": "51-200",
        "funding_stage": "Series A",
        "total_funding_raised": "$16M",
        "growth_signals": [
            "Deployed across 40 hospital networks in Switzerland and Germany",
            "CE mark certified under European Medical Device Regulation (MDR)",
            "Doubled technical staff in Zurich and Munich",
        ],
        "overview": (
            "MedVantage Systems provides an ambient AI clinical documentation assistant that integrates "
            "directly into major Electronic Health Record (EHR) platforms."
        ),
        "key_offerings": [
            "Ambient Clinical Scribe",
            "EHR Automated Coding Engine",
            "Multilingual Consultation Summarizer",
        ],
        "source_references": [
            "https://swisshealthtech.ch/medvantage-series-a",
            "https://healthcareitnews.com/medvantage-ehr-integration",
        ],
    },
    {
        "company_name": "CarePath Health",
        "website": "https://www.carepathhealth.com",
        "industry": "Healthcare AI",
        "sub_industry": "Remote Patient Monitoring & Chronic Care",
        "headquarters": "Austin, TX, USA",
        "employee_count": 36,
        "employee_count_range": "11-50",
        "funding_stage": "Seed",
        "total_funding_raised": "$4.5M",
        "growth_signals": [
            "Grew monitored patient active base by 300% in 12 months",
            "Closed initial enterprise pilot with major Texas HMO",
            "Hired Head of Regulatory Compliance from CMS",
        ],
        "overview": (
            "CarePath Health combines cellular IoT biometric devices with predictive anomaly "
            "detection to prevent hospital readmissions for congestive heart failure and diabetes."
        ),
        "key_offerings": [
            "Continuous Patient Vital Monitoring Hub",
            "Predictive Decompensation Alerts",
            "Telehealth Nurse Dashboard",
        ],
        "source_references": [
            "https://austintech.com/carepath-seed-funding",
            "https://mhealthintelligence.com/carepath-remote-monitoring",
        ],
    },
    {
        "company_name": "NeuroGen Diagnostics",
        "website": "https://www.neurogendiagnostics.ca",
        "industry": "Healthcare AI",
        "sub_industry": "Genomic Risk Assessment & Bioinformatics",
        "headquarters": "Toronto, ON, Canada",
        "employee_count": 185,
        "employee_count_range": "51-200",
        "funding_stage": "Series C",
        "total_funding_raised": "$58M",
        "growth_signals": [
            "Initiated multi-center clinical trials across 12 university medical centers",
            "Acquired gene-variant analysis startup BioVariant Labs",
            "Expanded into US health-system commercial contracts",
        ],
        "overview": (
            "NeuroGen Diagnostics leverages deep learning models on whole-genome sequencing data "
            "to calculate polygenic risk scores for early-onset neurodegenerative disorders."
        ),
        "key_offerings": [
            "Polygenic Risk Calculation Platform",
            "Variant Classification Pipeline",
            "Genetic Counselor Decision Portal",
        ],
        "source_references": [
            "https://betakit.com/neurogen-series-c-58m",
            "https://genomeweb.com/informatics/neurogen-clinical-validation",
        ],
    },

    # --- ENTERPRISE SAAS & AI AGENTS ---
    {
        "company_name": "OmniScale DevOps",
        "website": "https://www.omniscale.dev",
        "industry": "Enterprise SaaS",
        "sub_industry": "Autonomous Cloud Infrastructure & SRE",
        "headquarters": "Seattle, WA, USA",
        "employee_count": 175,
        "employee_count_range": "51-200",
        "funding_stage": "Series B",
        "total_funding_raised": "$35M",
        "growth_signals": [
            "Hired VP of Global Enterprise Sales from Datadog",
            "Launched autonomous Kubernetes cost & incident remediation agent",
            "Expanded partner integration into AWS and Google Cloud Marketplaces",
            "Reported 140% net revenue retention (NRR)",
        ],
        "overview": (
            "OmniScale DevOps builds multi-agent AI co-pilots for site reliability engineers, "
            "automatically investigating production alerts, pinpointing root causes, and deploying fixes."
        ),
        "key_offerings": [
            "Autonomous SRE Incident Resolver",
            "Kubernetes Cloud Cost Optimizer",
            "Continuous Distributed Tracing Agent",
        ],
        "source_references": [
            "https://cloudcomputingnews.com/omniscale-series-b",
            "https://devops.com/omniscale-autonomous-sre",
        ],
    },
    {
        "company_name": "CogniTask AI",
        "website": "https://www.cognitask.ai",
        "industry": "Enterprise SaaS",
        "sub_industry": "Enterprise Agent Orchestration",
        "headquarters": "San Jose, CA, USA",
        "employee_count": 62,
        "employee_count_range": "51-200",
        "funding_stage": "Series A",
        "total_funding_raised": "$12.5M",
        "growth_signals": [
            "Tripled ARR in 2025 across Fortune 500 legal and procurement teams",
            "Released open-source agent evaluation benchmark",
            "Integrated with Salesforce and ServiceNow platforms",
        ],
        "overview": (
            "CogniTask AI offers an enterprise multi-agent workflow platform that orchestrates "
            "document extraction, compliance verification, and ERP record synchronization."
        ),
        "key_offerings": [
            "Multi-Agent Workflow Studio",
            "Contract Analysis Agent",
            "Automated Procurement Auditor",
        ],
        "source_references": [
            "https://venturebeat.com/ai/cognitask-enterprise-agents-12m",
            "https://forbes.com/cognitask-enterprise-ai-growth",
        ],
    },
    {
        "company_name": "DataPrism Analytics",
        "website": "https://www.dataprismanalytics.de",
        "industry": "Enterprise SaaS",
        "sub_industry": "Federated Data Governance & BI",
        "headquarters": "Berlin, Germany",
        "employee_count": 128,
        "employee_count_range": "51-200",
        "funding_stage": "Series B",
        "total_funding_raised": "$28M",
        "growth_signals": [
            "Secured enterprise contract with 3 DAX-40 automotive manufacturers",
            "Achieved EU AI Act compliance verification certificate",
            "Opened regional sales hub in Paris and London",
        ],
        "overview": (
            "DataPrism Analytics provides a federated semantic query layer that connects disparate "
            "cloud data warehouses without moving sensitive personal information across borders."
        ),
        "key_offerings": [
            "Federated Semantic Lakehouse Layer",
            "Automated GDPR Data Lineage Mapper",
            "Conversational BI Analyst Agent",
        ],
        "source_references": [
            "https://tech.eu/dataprism-series-b-germany",
            "https://handelsblatt.com/unternehmen/dataprism-growth",
        ],
    },
    {
        "company_name": "SecureMesh Cyber",
        "website": "https://www.securemesh.io",
        "industry": "Enterprise SaaS",
        "sub_industry": "Zero-Trust Identity & Access Security",
        "headquarters": "Tel Aviv, Israel",
        "employee_count": 94,
        "employee_count_range": "51-200",
        "funding_stage": "Series A",
        "total_funding_raised": "$18M",
        "growth_signals": [
            "Named Gartner Cool Vendor in Identity-First Security",
            "Released agentic identity protection module for AI application access",
            "Expanded US enterprise sales team by 15 account executives",
        ],
        "overview": (
            "SecureMesh Cyber secures machine-to-machine identities, microservices, and AI agents "
            "with zero-trust cryptographic verification and automated least-privilege policies."
        ),
        "key_offerings": [
            "Ephemeral Token Access Broker",
            "Service-to-Service Zero Trust Mesh",
            "Automated Least-Privilege Enforcer",
        ],
        "source_references": [
            "https://calcalistech.com/securemesh-series-a-tel-aviv",
            "https://darkreading.com/identity/securemesh-zero-trust-mesh",
        ],
    },

    # --- CLEANTECH & CLIMATE ---
    {
        "company_name": "TerraWatt Energy",
        "website": "https://www.terrawattenergy.com",
        "industry": "CleanTech",
        "sub_industry": "Grid-Scale Battery Energy Storage AI",
        "headquarters": "Boulder, CO, USA",
        "employee_count": 120,
        "employee_count_range": "51-200",
        "funding_stage": "Series B",
        "total_funding_raised": "$32M",
        "growth_signals": [
            "Awarded $8M grant from US Department of Energy (DOE)",
            "Contracted 400MWh of battery optimization capacity with independent power producers",
            "Hired Chief Technology Officer from Tesla Energy",
        ],
        "overview": (
            "TerraWatt Energy optimizes grid battery asset dispatch and wholesale energy market bidding "
            "through real-time algorithmic forecasting and thermal health degradation modeling."
        ),
        "key_offerings": [
            "Wholesale Energy Arbitrage Algorithmic Dispatch",
            "Battery Health & Degradation Digital Twin",
            "Renewable Curtailment Mitigator",
        ],
        "source_references": [
            "https://canarymedia.com/articles/terrawatt-energy-doe-grant",
            "https://energy-storage.news/terrawatt-series-b-storage-software",
        ],
    },
    {
        "company_name": "CarbonTrace Technologies",
        "website": "https://www.carbontrace.se",
        "industry": "CleanTech",
        "sub_industry": "Supply Chain Scope 3 Carbon Accounting",
        "headquarters": "Stockholm, Sweden",
        "employee_count": 42,
        "employee_count_range": "11-50",
        "funding_stage": "Seed",
        "total_funding_raised": "$5.2M",
        "growth_signals": [
            "Signed commercial pilots with 3 Nordic retail chains",
            "Integrated with SAP and Oracle SCM enterprise systems",
            "Selected for EU Horizon Climate Innovation accelerator",
        ],
        "overview": (
            "CarbonTrace automates Scope 3 greenhouse gas calculations for supply chains by ingesting "
            "supplier bills of materials, shipping manifests, and localized emission factor databases."
        ),
        "key_offerings": [
            "Automated Scope 3 Carbon Ingestion Engine",
            "Supplier Decarbonization Portal",
            "CSRD Compliance Audit Exporter",
        ],
        "source_references": [
            "https://arcticstartup.com/carbontrace-secures-seed-funding",
            "https://greenbiz.com/carbontrace-scope3-accounting",
        ],
    },
    {
        "company_name": "SolarEdge Logistics",
        "website": "https://www.solaredgelogistics.com",
        "industry": "CleanTech",
        "sub_industry": "Industrial Microgrid Monitoring & Smart Inverters",
        "headquarters": "Phoenix, AZ, USA",
        "employee_count": 215,
        "employee_count_range": "201-500",
        "funding_stage": "Series C",
        "total_funding_raised": "$68M",
        "growth_signals": [
            "Deployed smart microgrid controllers across 250 distribution centers",
            "Entered into strategic partnership with regional utilities in Sunbelt",
            "Generated $45M in hardware and software recurring revenue",
        ],
        "overview": (
            "SolarEdge Logistics provides distributed energy resource management software (DERMS) "
            "for commercial fleets and manufacturing hubs transitioning to rooftop solar and fleet electrification."
        ),
        "key_offerings": [
            "Fleet EV Charging Microgrid Controller",
            "Commercial Rooftop Solar Forecaster",
            "Demand Charge Avoidance Algorithm",
        ],
        "source_references": [
            "https://solarbuildermag.com/solaredge-logistics-expansion",
            "https://pv-magazine-usa.com/solaredge-series-c-funding",
        ],
    },

    # --- CYBERSECURITY ---
    {
        "company_name": "VaultGuard AI",
        "website": "https://www.vaultguard.ai",
        "industry": "CyberSecurity",
        "sub_industry": "AI Application Security & LLM Guardrails",
        "headquarters": "Atlanta, GA, USA",
        "employee_count": 140,
        "employee_count_range": "51-200",
        "funding_stage": "Series B",
        "total_funding_raised": "$30M",
        "growth_signals": [
            "Awarded Department of Defense defense-tech innovation contract",
            "Defended against 10M+ prompt injection attacks in enterprise deployments",
            "Hired VP of Product from Palo Alto Networks",
        ],
        "overview": (
            "VaultGuard AI safeguards enterprise generative AI deployments with real-time prompt "
            "sanitization, hallucination detection, and secret leakage prevention proxies."
        ),
        "key_offerings": [
            "In-Line GenAI Firewall Proxy",
            "Prompt Injection & Jailbreak Detector",
            "Sensitive PII & Secret Redaction Gateway",
        ],
        "source_references": [
            "https://securityweek.com/vaultguard-series-b-ai-security",
            "https://csoonline.com/vaultguard-dod-contract",
        ],
    },
    {
        "company_name": "SentinelByte",
        "website": "https://www.sentinelbyte.com.au",
        "industry": "CyberSecurity",
        "sub_industry": "Automated Cloud Compliance & Posture (CSPM)",
        "headquarters": "Melbourne, Australia",
        "employee_count": 52,
        "employee_count_range": "51-200",
        "funding_stage": "Series A",
        "total_funding_raised": "$11M",
        "growth_signals": [
            "Expanded into Singapore and Japan enterprise markets",
            "Launched instant automated compliance mappings for ISO 27001 and Essential Eight",
            "Maintained 99.8% customer retention over 24 months",
        ],
        "overview": (
            "SentinelByte continuously inspects AWS, Azure, and GCP multi-cloud infrastructure to remediate "
            "misconfigurations, drifted security groups, and exposed cloud data storage."
        ),
        "key_offerings": [
            "Multi-Cloud CSPM Scanner",
            "Continuous Essential Eight Auditor",
            "Automated Terraform Remediation Pull Requests",
        ],
        "source_references": [
            "https://innovationaus.com/sentinelbyte-raises-series-a",
            "https://itnews.com.au/sentinelbyte-cloud-compliance",
        ],
    },

    # --- SUPPLY CHAIN & LOGISTICS ---
    {
        "company_name": "FreightPulse Automation",
        "website": "https://www.freightpulse.com",
        "industry": "Supply Chain",
        "sub_industry": "Intermodal Freight Optimization",
        "headquarters": "Chicago, IL, USA",
        "employee_count": 270,
        "employee_count_range": "201-500",
        "funding_stage": "Growth",
        "total_funding_raised": "$85M",
        "growth_signals": [
            "Signed nationwide agreement with top-3 US retail corporation",
            "Optimized over 5 million intermodal freight container moves",
            "Opened new innovation operations hub in Dallas, TX",
        ],
        "overview": (
            "FreightPulse connects rail, drayage trucking, and maritime terminals with dynamic "
            "machine learning scheduling, slashing dwell times and fuel consumption."
        ),
        "key_offerings": [
            "Intermodal Container Drayage Optimizer",
            "Predictive Rail Dwell Estimator",
            "Automated Freight Bill Audit Suite",
        ],
        "source_references": [
            "https://freightwaves.com/news/freightpulse-growth-round",
            "https://joc.com/technology/freightpulse-retail-contract",
        ],
    },
    {
        "company_name": "RouteIQ Logistics",
        "website": "https://www.routeiq.nl",
        "industry": "Supply Chain",
        "sub_industry": "Last-Mile Delivery Route Optimization",
        "headquarters": "Amsterdam, Netherlands",
        "employee_count": 88,
        "employee_count_range": "51-200",
        "funding_stage": "Series A",
        "total_funding_raised": "$15M",
        "growth_signals": [
            "Expanded fleet optimization customer base to 50 logistics operators",
            "Achieved 18% reduction in last-mile diesel fuel emissions for clients",
            "Launched dynamic traffic and urban zero-emission zone dispatch",
        ],
        "overview": (
            "RouteIQ provides dynamic, real-time routing algorithms for urban last-mile delivery fleets, "
            "factoring in battery charge levels, zero-emission traffic zones, and customer delivery windows."
        ),
        "key_offerings": [
            "Dynamic Last-Mile Dispatch Engine",
            "EV Fleet Delivery Planner",
            "Driver Mobile Turn-by-Turn Navigation SDK",
        ],
        "source_references": [
            "https://siliconcanals.com/routeiq-series-a-amsterdam",
            "https://postandparcel.info/routeiq-lastmile-optimisation",
        ],
    },

    # --- EDTECH & AI EDUCATION ---
    {
        "company_name": "ScholarMind AI",
        "website": "https://www.scholarmind.ie",
        "industry": "EdTech",
        "sub_industry": "Adaptive AI STEM Tutoring",
        "headquarters": "Dublin, Ireland",
        "employee_count": 32,
        "employee_count_range": "11-50",
        "funding_stage": "Seed",
        "total_funding_raised": "$3.8M",
        "growth_signals": [
            "Completed successful pilot across 50 secondary school districts in the UK and Ireland",
            "Demonstrated 22% improvement in standardized STEM test scores",
            "Received EU Digital Education Horizon grant",
        ],
        "overview": (
            "ScholarMind AI personalizes mathematics and science curricula using adaptive knowledge "
            "graphs and conversational Socratic reasoning to support secondary school students."
        ),
        "key_offerings": [
            "Socratic STEM Tutoring Assistant",
            "Adaptive Knowledge Gap Diagnoser",
            "Teacher Curriculum Insights Dashboard",
        ],
        "source_references": [
            "https://siliconrepublic.com/start-ups/scholarmind-ai-seed-funding",
            "https://edtechnology.co.uk/scholarmind-stem-pilot",
        ],
    },
]
