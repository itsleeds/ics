#!/usr/bin/env python3
"""Append newly discovered LCWIP URLs to scripts/discovered_urls.txt (Hermes web-search round)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "scripts", "discovered_urls.txt")

NEW = [
    # Guildford — main document (dataset only had Chapter 2)
    ("https://www.guildford.gov.uk/media/36792/Guildford-LCWIP-Chapter-1/pdf/Guildford_LCWIP_Chapter_1.pdf?m=1746179679717", "Guildford LCWIP Main Document (Chapter 1)"),
    # Norfolk — main countywide report (dataset only had summary report)
    ("https://www.norfolk.gov.uk/media/33545/Countywide-Local-Cycling-and-Walking-Infrastructure-Plan---main-report---February-2024/pdf/hmCountywide_LCWIP_2024_Accessible.pdf?m=1718357720090", "Norfolk Countywide LCWIP Main Report Feb 2024"),
    ("https://www.norfolk.gov.uk/media/20116/Greater-Norwich-Lcwip-Main-Report/pdf/2egreater-norwich-lcwip-main-report.pdf?m=1713194576383", "Norfolk Greater Norwich LCWIP Main Report"),
    # Somerset — 8 district LCWIPs on SharePoint guest links
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/Ee94bKyfwSRLusyvrErJ6YoBIRNcgFpTeDFuk1suiquEuw?e=hbE8pC", "Somerset Bridgwater LCWIP (3.17MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EVjxZcxHLRlKm7g40uVhezEBMgppAX3EjtdKwtimpg9HoQ?e=1070c6", "Somerset Taunton LCWIP (4.29MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EXokQSqTqNVNrM6qI99gJTkBGVdIHB48erdxfs8JiOBhMg?e=LTfXpn", "Somerset Yeovil LCWIP (3.90MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EcfwFLGyfuBOiYYbyOa8e20BxQQtCiCatCHCLKpQ6T2APA?e=RF3nyk", "Somerset Mendip LCWIP (22.4MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/Ec8zo9gJJ4dJt6yOs9cG4QIBFZZQj2h3RFOAy7h6NXx5UA?e=NAJtLs", "Somerset Frome LCWIP (18.7MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EbcroMhJms9Fh8VKPS-utW8BPNLkVhBwqe4csjmf3VXRoQ?e=jhagME", "Somerset Wellington LCWIP (1.6MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EVQQirlXPN5Nq9p_oSJ4FHkBaU225l8bEckFDKCsIRrmLw?e=MlN1pJ", "Somerset Burnham-On-Sea and Highbridge LCWIP (1.5MB)"),
    ("https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EQUkjhzzB71HhgCuaPSNSdAB_h-dvao7hjBFam3yLlFazQ?e=TNMmo1", "Somerset Chard LCWIP (1.6MB)"),
    # Devon — adopted LCWIPs on SharePoint guest links
    ("https://devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EeJwZo7atrNMu-Wm_PxK4P8B4pL3khBvIRz5qhepIyE82w?e=WVORrm", "Devon Countywide LCWIP (adopted Mar 2025)"),
    ("https://devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/ERuIoF-oOkpMoKdsxAcxyrkB5pvBHlVbnr3IgbTGA6LRMg?e=zWO26h", "Devon BBN (Barnstaple-Bideford-Northam) LCWIP adopted"),
    ("https://devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EQfXU7KHrKFKg8m3-bUREK4BpWPpWmRpxXcvEucn4bG8cw?e=ISQOUK", "Devon Exeter LCWIP adopted Jan 2024"),
    ("https://devoncc.sharepoint.com/sites/PublicDocs/Corporate/HaveYourSay/Forms/AllItems.aspx?id=%2Fsites%2FPublicDocs%2FCorporate%2FHaveYourSay%2FTransport%2FClyst%20Valley%20and%20New%20Communities%20LCWIP%2F70103323%2D001%20Clyst%20Valley%20and%20New%20Communities%20LCWIP%5Fv4%2Epdf&parent=%2Fsites%2FPublicDocs%2FCorporate%2FHaveYourSay%2FTransport%2FClyst%20Valley%20and%20New%20Communities%20LCWIP&p=true&ga=1", "Devon Clyst Valley and New Communities LCWIP adopted Mar 2025"),
    ("https://devoncc.sharepoint.com/:b:/s/PublicDocs/Highways/EU4nM80Nn0dJgord0EjNRrgB7mD0SaIJvB2WNe-dds-Z4w?e=WzZKrh", "Devon Heart of Teignbridge LCWIP adopted Jan 2024"),
    ("https://devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/ERZ8e2qsbJ9GjhUbHr2WFXgBlC12CbIM32S6CzdgOSBMSw", "Devon Cullompton and Tiverton LCWIP adopted Mar 2025"),
    # Wiltshire — additional district LCWIPs + framework draft
    ("https://www.wiltshire.gov.uk/media/19933/Calne-Local-Cycling-and-Walking-Infrastructure-Plan-LCWIP/pdf/Calne_Local_Cycling_and_Walking_Infrastructure_Plan_LCWIP.pdf?m=1776879791457", "Wiltshire Calne LCWIP"),
    ("https://www.wiltshire.gov.uk/media/19936/Melksham-Local-Cycling-and-Walking-Infrastructure-Plan-LCWIP/pdf/Melksham_Local_Cycling_and_Walking_Infrastructure_Plan_LCWIP.pdf?m=1776879792650", "Wiltshire Melksham LCWIP"),
    ("https://www.wiltshire.gov.uk/media/19934/Chippenham-Local-Cycling-and-Walking-Infrastructure-Plan-LCWIP/pdf/Chippenham_Local_Cycling_and_Walking_Infrastructure_Plan_LCWIP.pdf?m=1776879791667", "Wiltshire Chippenham LCWIP"),
    ("https://www.wiltshire.gov.uk/media/9640/Wiltshire-draft-LCWIP/pdf/Wiltshire_LCWIP_Framework_and_Interurban_Routes_Consultation_Draft_1i9m0rloi854u.pdf", "Wiltshire LCWIP Framework and Interurban Routes draft"),
    # Luton — newer main LCWIP (Mar 2026)
    ("https://www.luton.gov.uk/sites/default/files/2026-03/Local%20Cycling%20and%20Walking%20Infrastructure%20Plan.pdf", "Luton LCWIP (Mar 2026)"),
    # Lancashire — Fylde Coast LCWIP (Blackpool/Fylde/Wyre)
    ("https://www.lancashire.gov.uk/media/kzqpnp05/fylde-coast.pdf", "Lancashire Fylde Coast LCWIP (Blackpool/Fylde/Wyre)"),
    # North Northamptonshire — additional district LCWIPs
    ("https://northnorthants.moderngov.co.uk/documents/s21269/Appendix%20A.pdf", "North Northamptonshire Corby LCWIP"),
    ("https://www.ketteringtowncouncil.gov.uk/uploads/kettering-lcwip-report-sept-2023-1.pdf", "North Northamptonshire Kettering LCWIP (Sept 2023)"),
    # Tunbridge Wells — Phase 1 (dataset only had Phase 2)
    ("https://tunbridgewells.gov.uk/__data/assets/pdf_file/0003/385329/01_LCWIP-Phase-1-March-2021.pdf", "Tunbridge Wells LCWIP Phase 1 (Mar 2021)"),
    # Isles of Scilly — full stage documents (dataset only had landing page)
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Introduction%20and%20Forward_0.pdf", "Isles of Scilly LCWIP Introduction and Forward"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%201%20-%20Determining%20Scope_0.pdf", "Isles of Scilly LCWIP Stage 1"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%202%20-%20Gathering%20Information_0.pdf", "Isles of Scilly LCWIP Stage 2"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%203%20-%20Network%20Planning%20for%20Cycling_0.pdf", "Isles of Scilly LCWIP Stage 3 Cycling"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%203%20%26%204%20-%20Walking%20and%20Cycling%20Assessment%20Tables_0.pdf", "Isles of Scilly LCWIP Stage 3&4 Tables"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%204%20-%20Network%20Planning%20for%20Walking_0.pdf", "Isles of Scilly LCWIP Stage 4 Walking"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%205%20-%20Prioritising%20Improvements_0.pdf", "Isles of Scilly LCWIP Stage 5"),
    ("https://www.scilly.gov.uk/sites/default/files/document/environment-transport/Stage%206%20-%20Policy%20Integration%20and%20Application_0.pdf", "Isles of Scilly LCWIP Stage 6"),
    # Hertfordshire — district LCWIPs (dataset only had consultations landing page)
    ("https://www.stevenage.gov.uk/documents/planning-policy/evidential-studies/transport-infrastructure/local-cycling-and-walking-infrastructure-plan-2019.pdf", "Hertfordshire Stevenage LCWIP 2019"),
    ("https://watford.moderngov.co.uk/documents/s36726/Appendix%20F%20-%20Local%20Cycling%20and%20Walking%20Infrastructure%20Plan.pdf", "Hertfordshire Watford LCWIP (adopted Jan 2022)"),
    ("https://www.hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/dacorum-local-cycling-and-walking-infrastructure-plan.aspx", "Hertfordshire Dacorum LCWIP (adopted Apr 2026)"),
    ("https://www.hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/eastherts-local-cycling-and-walking-infrastructure-plan.aspx", "Hertfordshire East Herts LCWIP (adopted Jun 2026)"),
    ("https://www.hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/north-hertfordshire-local-cycling-and-walking-infrastructure-plan.aspx", "Hertfordshire North Herts LCWIP (adopted Sep 2023)"),
    ("https://www.hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/three-rivers-cycling-and-walking-infrastructure-plan.aspx", "Hertfordshire Three Rivers LCWIP (adopted Nov 2025)"),
    ("https://www.hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/welwyn-hatfield-lcwip.aspx", "Hertfordshire Welwyn Hatfield LCWIP (adopted Mar 2023)"),
    # West Northamptonshire — Northampton + Brackley/Daventry/Towcester LCWIPs (no docs in dataset)
    ("https://www.brixworthparishcouncil.gov.uk/wp-content/uploads/2026/06/Adoption-of-Local-Cycling-and-Walking-Infrastructure-Plan-for-Northampton-Appendix-B.pdf", "West Northamptonshire Northampton LCWIP Appendix B"),
    ("https://westnorthants.moderngov.co.uk/documents/s23340/Adoption+of+Local+Cycling+and+Walking+Infrastructure+Plans+for+Brackley+Daventry+and+Towcester+-+Ap.pdf", "West Northamptonshire Brackley/Daventry/Towcester LCWIPs"),
    # Cumberland — Carlisle / Workington / Whitehaven LCWIPs (no docs in dataset)
    ("https://www.cumberland.gov.uk/sites/default/files/2025-04/carlisle_lcwip_document.pdf", "Cumberland Carlisle LCWIP 2022"),
    ("https://www.cumberland.gov.uk/sites/default/files/2025-04/workington_follow-up_consultation_report.pdf", "Cumberland Workington LCWIP follow-up consultation report"),
    ("https://legacy.cumberland.gov.uk/elibrary/Content/Internet/538/18110/38384/44819114227.pdf", "Cumberland Whitehaven LCWIP Technical Report (WSP)"),
    # Suffolk — county LCWIP (no docs in dataset)
    ("https://www.suffolk.gov.uk/asset-library/local-cycling-and-walking-infrastructure-plan-for-suffolk.pdf", "Suffolk County LCWIP"),
    # Westmorland and Furness — Barrow LCWIP (no docs in dataset)
    ("https://www.westmorlandandfurness.gov.uk/sites/default/files/2026-06/Barrow%20Local%20Cycling%20and%20Walking%20Infrastructure%20Plans%20%28LCWIPs%29%20document.pdf", "Westmorland and Furness Barrow LCWIP"),
    # Blackburn with Darwen LCWIP (no docs in dataset)
    ("https://democracy.blackburn.gov.uk/documents/s22790/BwD%20LCWIP%20Phase%203%20Prioritisation%20report%20final.pdf", "Blackburn with Darwen LCWIP Phase 3 Prioritisation final"),
]

existing = set()
if os.path.exists(PATH):
    for line in open(PATH):
        line = line.strip()
        if line and not line.startswith("#"):
            existing.add(line.split("\t")[0].strip().lower())

added = 0
with open(PATH, "a") as f:
    for u, note in NEW:
        if u.strip().lower() in existing:
            continue
        f.write(f"{u}\t{note}\n")
        existing.add(u.strip().lower())
        added += 1
print(f"appended {added} new URLs (already-present skipped)")
