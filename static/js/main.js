// ============================================================
// FILE: static/js/main.js
// PURPOSE: Hindi/English toggle + shared utilities
// LAST UPDATED: Phase 1
// ============================================================

// ------------------------------------------------------------
// SECTION 1: TRANSLATIONS
// ------------------------------------------------------------
const translations = {
    en: {
        // Navigation
        nav_dashboard:  "Dashboard",
        nav_calculator: "Calculator",
        nav_checklist:  "Checklist",
        nav_expert:     "Ask Expert",
        nav_auctions:   "Auctions",
        nav_admin:      "Admin",
        nav_logout:     "Logout",
        nav_login:      "Login",
        nav_pricing:      "Pricing",
        nav_legislation:  "Legislation",

        // Legislation page
        leg_page_title:   "Legislation & Rule-Change Digest",
        leg_page_subtitle:"Plain-language summaries of Rajasthan mining rule changes. Always verify with an expert before acting on any summary.",
        leg_official_link:"View Official Document",
        leg_source:       "Source",
        leg_verified_prefix: "Verified:",
        leg_pending_verify:  "Pending verification",
        leg_verify_note:  "information only, please verify with expert",
        leg_empty:        "No legislation entries published yet. Check back soon.",

        // Home page
        hero_headline:     "Rajasthan Mining Compliance, Done Right the First Time",
        hero_subhead:      "Royalty, DMF, and NPV calculated on verified historical rates. Deadlines tracked automatically. Regulatory changes explained in plain language. And a 30-year mining-law expert one message away — so an outdated rate or a missed return never becomes a lakhs-rupee penalty.",
        hero_cta_calc:     "Calculate My Fees →",
        hero_cta_pricing:  "See Pricing",
        pain_heading:      "Where Compliance Goes Wrong",
        pain1_title:       "Wrong Rate Applied",
        pain1_body:        "Royalty and DMF rates are revised by notification every few years. Apply last year's rate to this year's dispatch — or a current rate to a back-period — and you invite recovery notices, interest, and an inspector's scrutiny.",
        pain2_title:       "Missed Deadlines",
        pain2_body:        "Six-monthly environmental compliance reports, annual returns, DMF contributions — each runs on its own calendar. A single lapsed deadline can stall dispatch permissions and freeze a working mine.",
        pain3_title:       "Unexpected Penalties",
        pain3_body:        "NPV and dead-rent computations for lease grant and renewal are unforgiving. A single error in the calculation can swing the figure by ₹10 lakh or more — and the department's number is the one that counts.",
        features_heading:  "Everything Your Mine's Compliance Demands — In One Platform",
        features_subhead:  "Purpose-built for Rajasthan's minor-mineral regime. Not generic compliance software.",
        feat_calc_title:   "Instant Fee Calculator",
        feat_calc_body:    "Compute royalty, DMF, and NPV against the rate legally in force on any date — current or historical. Change the lease year and the calculator applies the exact notified rate that governed it, with the source notification shown on every result.",
        feat_cal_title:    "Compliance Calendar",
        feat_cal_body:     "Every statutory deadline — six-monthly EC reports, annual returns, DMF submissions — tracked from your lease and EC grant dates. Automatic reminders seven days and one day before each due date, so nothing lapses.",
        feat_expert_title: "Ask an Expert",
        feat_expert_body:  "A direct line to a mining-law consultant with 30 years of Rajasthan practice. Your query reaches the expert pre-filled with your mine's details, with a first response within 24 hours — judgement on the grey areas no software can settle.",
        feat_leg_title:    "Legislation Digest",
        feat_leg_body:     "Every amendment to Rajasthan's minor-mineral rules, read closely and rewritten in plain Hindi and English. Know exactly what changed, which rule it touches, and what it means for your operation — before it reaches an inspector's checklist.",
        pricing_heading:   "Simple, Transparent Pricing",
        pricing_subhead:   "Less than the cost of a single penalty notice.",
        leg_band_heading:  "The Rules, Kept Current",
        leg_band_subhead:  "Rajasthan's mining regulations change often. We read every amendment and explain it plainly.",
        leg_band_empty:    "Our legislation library is being verified by our expert and goes live shortly.",
        leg_band_cta:      "Browse the Legislation Library →",

        // Login page
        login_title:    "Login to MineralLaw.in",
        login_subtitle: "Enter your phone number to receive a one-time login code",
        phone_label:    "Mobile Number",
        send_otp:       "Send OTP",
        otp_sent:       "OTP sent to",
        otp_label:      "Enter 6-digit OTP",
        verify_otp:     "Verify & Login",
        change_number:  "← Change number",
        consent_note:   "By logging in, you agree to our Terms of Service. We collect your phone number and mining details only to provide compliance services. Your data is stored in India and never sold.",

        // Dashboard
        dash_health:       "Compliance Health",
        dash_calculator:   "Fee Calculator",
        dash_expert:       "Ask Expert",
        dash_checklist:    "Compliance Checklist",
        dash_activity:     "Recent Activity",
        dash_account:      "Account",
        dash_phone:        "Phone",
        dash_name:         "Name",
        dash_email:        "Email",
        dash_company:      "Company",
        dash_plan:         "Plan",
        dash_member_since: "Member since",
        dash_signout:      "Sign Out",
        dash_data_rights:  "Your Data Rights (DPDP Act 2023)",

        // Calculator
        calc_title:        "Mining Fee Calculator",
        calc_subtitle:     "Estimate royalty, DMF, and NPV for Rajasthan minor mineral mines. Every result shows the applicable notification number and date.",
        calc_mine_details: "Mine Details",
        calc_mineral:      "Mineral Type",
        calc_date:         "Rate Date",
        calc_area:         "Mine Area (hectares)",
        calc_production:   "Annual Production (tonnes/year)",
        calc_lease:        "Lease Period (years)",
        calc_results:      "Calculation Results",
        calc_royalty:      "Annual Royalty",
        calc_dmf:          "Annual DMF",
        calc_total:        "Total Annual Govt. Payment",
        calc_notice:       "Important Legal Notice",

        // Checklist
        check_title:       "EC Compliance Checklist",
        check_subtitle:    "Step-by-step guide for Rajasthan minor mineral mines. Print this page and carry it to the government office.",
        check_print:       "🖨 Print",
        check_cta:         "Ask Expert for Your Mine",

        // Ask Expert
        expert_title:      "Ask an Expert",
        expert_subtitle:   "Get a response from a mining law specialist within 24 hours. Your query will open a pre-filled Gmail draft — just hit Send.",
        expert_mineral:    "Mineral / Mine Type",
        expert_question:   "Your Question",
        expert_gmail:      "Open Gmail",
        expert_next:       "What Happens Next",

        // Pricing
        pricing_title:     "Simple, Transparent Pricing",
        pricing_subtitle:  "Built for Rajasthan mine owners. Less than the cost of one penalty notice.",
        pricing_faq:       "Frequently Asked Questions",

        // Auctions page
        auction_title:           "Mine Auctions — Rajasthan",
        auction_subtitle:        "Government mine blocks in Rajasthan are allotted via official e-auction. Track open auctions and access the official portals below.",
        auction_live_label:      "🟢 Auctions currently open",
        auction_none_label:      "No auctions currently flagged. Check the official portal below.",
        auction_verified_prefix: "Last updated",
        auction_mstc_title:      "MSTC Minor Mineral Block Auction (Rajasthan)",
        auction_mstc_desc:       "Official Government of India e-auction platform where Rajasthan minor mineral blocks are auctioned.",
        auction_dmg_title:       "DMG Rajasthan — Notifications & Tender Documents",
        auction_dmg_desc:        "Department of Mines and Geology, Rajasthan — official notifications, tender documents, and auction schedules.",
        auction_gis_title:       "DMG Mineral Map (GIS)",
        auction_gis_desc:        "Official map of mines, leases, and auction blocks in Rajasthan.",
        auction_disclaimer:      "MineralLaw.in is not affiliated with MSTC or DMG. These links open official government portals. Always verify auction details on the official portal before bidding.",

        // News & Events page
        news_title:    "News & Events",
        news_source:   "Source: Department of Mines & Geology, Govt. of Rajasthan",
        news_updated:  "Updated daily from the official DMG portal.",
        filter_all:    "All",
        filter_auction:"Auctions",
        filter_tender: "Tenders",
        filter_mineral:"Minerals",
        filter_notice: "Notices",
        news_empty:    "No items in this category.",
        nav_news:      "News",
    },

    // ⚠️ PLACEHOLDER HINDI — father must verify all legal/technical terms before launch (Phase 2 per project spec).
    hi: {
        // Navigation
        nav_dashboard:  "डैशबोर्ड",
        nav_calculator: "कैलकुलेटर",
        nav_checklist:  "चेकलिस्ट",
        nav_expert:     "विशेषज्ञ से पूछें",
        nav_auctions:   "नीलामी",
        nav_admin:      "एडमिन",
        nav_logout:     "लॉगआउट",
        nav_login:      "लॉगिन",
        nav_pricing:      "मूल्य",
        nav_legislation:  "कानून",

        // Legislation page
        leg_page_title:   "कानून एवं नियम परिवर्तन",
        leg_page_subtitle:"राजस्थान खनन नियम परिवर्तनों के सरल-भाषा सारांश। कोई भी कदम उठाने से पहले विशेषज्ञ से सत्यापित करें।",
        leg_official_link:"आधिकारिक दस्तावेज़ देखें",
        leg_source:       "स्रोत",
        leg_verified_prefix: "सत्यापित:",
        leg_pending_verify:  "सत्यापन लंबित",
        leg_verify_note:  "केवल जानकारी — विशेषज्ञ से सत्यापित करें",
        leg_empty:        "अभी कोई प्रविष्टि प्रकाशित नहीं। शीघ्र वापस देखें।",

        // Home page
        hero_headline:     "राजस्थान खनन अनुपालन — पहली बार में, सही तरीके से।",
        hero_subhead:      "रॉयल्टी, DMF और NPV — सत्यापित ऐतिहासिक दरों पर सटीक गणना। हर समय-सीमा की स्वतः निगरानी। नियमों में बदलाव सरल भाषा में। और 30 वर्षों के अनुभवी खनन-विधि विशेषज्ञ बस एक संदेश दूर — ताकि कोई पुरानी दर या छूटी हुई विवरणी कभी लाखों के जुर्माने में न बदले।",
        hero_cta_calc:     "मेरी फ़ीस की गणना करें →",
        hero_cta_pricing:  "मूल्य निर्धारण देखें",
        pain_heading:      "अनुपालन में चूक कहाँ होती है",
        pain1_title:       "गलत दर का प्रयोग",
        pain1_body:        "रॉयल्टी और DMF की दरें हर कुछ वर्षों में अधिसूचना द्वारा संशोधित होती हैं। इस वर्ष के निर्गमन पर पिछले वर्ष की दर — या किसी पूर्व-अवधि पर वर्तमान दर — लगाने का अर्थ है वसूली नोटिस, ब्याज और निरीक्षक की जाँच।",
        pain2_title:       "छूटी हुई समय-सीमाएँ",
        pain2_body:        "छह-माही पर्यावरण अनुपालन रिपोर्ट, वार्षिक विवरणी, DMF अंशदान — प्रत्येक की अपनी समय-सारणी है। एक भी समय-सीमा चूकने पर निर्गमन अनुमति रुक सकती है और चालू खदान ठप पड़ सकती है।",
        pain3_title:       "अप्रत्याशित जुर्माने",
        pain3_body:        "पट्टा स्वीकृति और नवीनीकरण के लिए NPV और डेड-रेंट की गणना में कोई छूट नहीं। गणना में एक त्रुटि आँकड़े को ₹10 लाख या उससे अधिक तक बदल सकती है — और मान्य वही होता है जो विभाग का आँकड़ा हो।",
        features_heading:  "आपकी खदान के अनुपालन की हर ज़रूरत — एक ही मंच पर",
        features_subhead:  "राजस्थान के गौण खनिज तंत्र के लिए विशेष रूप से निर्मित। कोई सामान्य अनुपालन सॉफ़्टवेयर नहीं।",
        feat_calc_title:   "त्वरित शुल्क कैलकुलेटर",
        feat_calc_body:    "किसी भी तिथि — वर्तमान या ऐतिहासिक — पर विधिक रूप से प्रभावी दर के अनुसार रॉयल्टी, DMF और NPV की गणना करें। पट्टा वर्ष बदलें और कैलकुलेटर उसी अधिसूचित दर को लागू करेगा जो उस समय प्रभावी थी, और हर परिणाम पर स्रोत अधिसूचना दर्शाई जाएगी।",
        feat_cal_title:    "अनुपालन कैलेंडर",
        feat_cal_body:     "हर वैधानिक समय-सीमा — छह-माही EC रिपोर्ट, वार्षिक विवरणी, DMF जमा — आपके पट्टा और EC स्वीकृति तिथि से ट्रैक की जाती है। प्रत्येक नियत तिथि से सात दिन और एक दिन पूर्व स्वतः अनुस्मारक, ताकि कुछ न छूटे।",
        feat_expert_title: "विशेषज्ञ से पूछें",
        feat_expert_body:  "राजस्थान में 30 वर्षों के अनुभवी खनन-विधि सलाहकार से सीधा संपर्क। आपका प्रश्न आपकी खदान के विवरण सहित विशेषज्ञ तक पहुँचता है, और पहला उत्तर 24 घंटे के भीतर — उन पेचीदा पहलुओं पर निर्णय जो कोई सॉफ़्टवेयर नहीं दे सकता।",
        feat_leg_title:    "विधान सार-संग्रह",
        feat_leg_body:     "राजस्थान के गौण-खनिज नियमों के हर संशोधन का बारीकी से अध्ययन कर सरल हिंदी और अंग्रेज़ी में प्रस्तुत। जानें कि वास्तव में क्या बदला, कौन-सा नियम प्रभावित हुआ, और आपके संचालन के लिए इसका क्या अर्थ है — इससे पहले कि यह किसी निरीक्षक की सूची तक पहुँचे।",
        pricing_heading:   "सरल, पारदर्शी मूल्य निर्धारण",
        pricing_subhead:   "एक जुर्माना नोटिस की लागत से भी कम।",
        leg_band_heading:  "नियम, सदैव अद्यतन",
        leg_band_subhead:  "राजस्थान के खनन नियम अक्सर बदलते हैं। हम हर संशोधन को पढ़ते हैं और उसे सरल भाषा में समझाते हैं।",
        leg_band_empty:    "हमारी विधान लाइब्रेरी विशेषज्ञ द्वारा सत्यापित की जा रही है और शीघ्र ही उपलब्ध होगी।",
        leg_band_cta:      "विधान लाइब्रेरी देखें →",

        // Login page
        login_title:    "MineralLaw.in में लॉगिन करें",
        login_subtitle: "एक बार का लॉगिन कोड प्राप्त करने के लिए अपना फोन नंबर दर्ज करें",
        phone_label:    "मोबाइल नंबर",
        send_otp:       "OTP भेजें",
        otp_sent:       "OTP भेजा गया",
        otp_label:      "6 अंकों का OTP दर्ज करें",
        verify_otp:     "सत्यापित करें और लॉगिन करें",
        change_number:  "← नंबर बदलें",
        consent_note:   "लॉगिन करके आप हमारी सेवा शर्तों से सहमत होते हैं। हम आपका फोन नंबर और खनन विवरण केवल अनुपालन सेवाएं प्रदान करने के लिए एकत्र करते हैं।",

        // Dashboard
        dash_health:       "अनुपालन स्वास्थ्य",
        dash_calculator:   "शुल्क कैलकुलेटर",
        dash_expert:       "विशेषज्ञ से पूछें",
        dash_checklist:    "अनुपालन चेकलिस्ट",
        dash_activity:     "हाल की गतिविधि",
        dash_account:      "खाता",
        dash_phone:        "फोन",
        dash_name:         "नाम",
        dash_email:        "ईमेल",
        dash_company:      "कंपनी",
        dash_plan:         "प्लान",
        dash_member_since: "सदस्य बने",
        dash_signout:      "साइन आउट",
        dash_data_rights:  "आपके डेटा अधिकार (DPDP अधिनियम 2023)",

        // Calculator
        calc_title:        "खनन शुल्क कैलकुलेटर",
        calc_subtitle:     "राजस्थान लघु खनिज खदानों के लिए रॉयल्टी, DMF और NPV का अनुमान लगाएं। हर परिणाम में लागू अधिसूचना संख्या और तिथि दिखाई जाती है।",
        calc_mine_details: "खदान विवरण",
        calc_mineral:      "खनिज प्रकार",
        calc_date:         "दर तिथि",
        calc_area:         "खदान क्षेत्र (हेक्टेयर)",
        calc_production:   "वार्षिक उत्पादन (टन/वर्ष)",
        calc_lease:        "पट्टा अवधि (वर्ष)",
        calc_results:      "गणना परिणाम",
        calc_royalty:      "वार्षिक रॉयल्टी",
        calc_dmf:          "वार्षिक DMF",
        calc_total:        "कुल वार्षिक सरकारी भुगतान",
        calc_notice:       "महत्वपूर्ण कानूनी सूचना",

        // Checklist
        check_title:       "EC अनुपालन चेकलिस्ट",
        check_subtitle:    "राजस्थान लघु खनिज खदानों के लिए चरण-दर-चरण मार्गदर्शिका। यह पृष्ठ प्रिंट करें और सरकारी कार्यालय में ले जाएं।",
        check_print:       "🖨 प्रिंट",
        check_cta:         "अपनी खदान के लिए विशेषज्ञ से पूछें",

        // Ask Expert
        expert_title:      "विशेषज्ञ से पूछें",
        expert_subtitle:   "24 घंटे के भीतर खनन कानून विशेषज्ञ से उत्तर पाएं। आपका प्रश्न पूर्व-भरे Gmail ड्राफ्ट में खुलेगा — बस Send दबाएं।",
        expert_mineral:    "खनिज / खदान प्रकार",
        expert_question:   "आपका प्रश्न",
        expert_gmail:      "Gmail खोलें",
        expert_next:       "आगे क्या होगा",

        // Pricing
        pricing_title:     "सरल, पारदर्शी मूल्य",
        pricing_subtitle:  "राजस्थान खनन मालिकों के लिए। एक जुर्माना नोटिस की लागत से भी कम।",
        pricing_faq:       "अक्सर पूछे जाने वाले प्रश्न",

        // Auctions page
        auction_title:           "खान नीलामी — राजस्थान",
        auction_subtitle:        "राजस्थान में सरकारी खान ब्लॉक आधिकारिक ई-नीलामी के माध्यम से आवंटित किए जाते हैं। खुली नीलामियों की जानकारी और आधिकारिक पोर्टल नीचे देखें।",
        auction_live_label:      "🟢 नीलामियाँ वर्तमान में खुली हैं",
        auction_none_label:      "अभी कोई नीलामी सक्रिय नहीं। नीचे आधिकारिक पोर्टल देखें।",
        auction_verified_prefix: "अंतिम अपडेट",
        auction_mstc_title:      "MSTC लघु खनिज ब्लॉक नीलामी (राजस्थान)",
        auction_mstc_desc:       "भारत सरकार का आधिकारिक ई-नीलामी मंच जहाँ राजस्थान के लघु खनिज ब्लॉकों की नीलामी होती है।",
        auction_dmg_title:       "DMG राजस्थान — अधिसूचनाएँ और निविदा दस्तावेज़",
        auction_dmg_desc:        "खान और भूविज्ञान विभाग, राजस्थान — आधिकारिक अधिसूचनाएँ, निविदा दस्तावेज़ और नीलामी कार्यक्रम।",
        auction_gis_title:       "DMG खनिज मानचित्र (GIS)",
        auction_gis_desc:        "राजस्थान में खानों, पट्टों और नीलामी ब्लॉकों का आधिकारिक मानचित्र।",
        auction_disclaimer:      "MineralLaw.in का MSTC या DMG से कोई संबंध नहीं है। ये लिंक आधिकारिक सरकारी पोर्टल खोलते हैं। बोली लगाने से पहले नीलामी विवरण की पुष्टि आधिकारिक पोर्टल पर करें।",

        // News & Events page
        news_title:    "समाचार एवं कार्यक्रम",
        news_source:   "स्रोत: खान एवं भूविज्ञान विभाग, राजस्थान सरकार",
        news_updated:  "आधिकारिक DMG पोर्टल से प्रतिदिन अद्यतन।",
        filter_all:    "सभी",
        filter_auction:"नीलामी",
        filter_tender: "निविदा",
        filter_mineral:"खनिज",
        filter_notice: "सूचनाएं",
        news_empty:    "इस श्रेणी में कोई आइटम नहीं।",
        nav_news:      "समाचार",
    }
};

// ------------------------------------------------------------
// SECTION 2: LANGUAGE TOGGLE
// ------------------------------------------------------------
function applyLanguage(lang) {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });
    const btn = document.getElementById('lang-toggle-btn');
    if (btn) btn.textContent = lang === 'en' ? 'हि' : 'EN';
    localStorage.setItem('minerallaw_lang', lang);
    document.documentElement.lang = lang;

    // Legislation page: toggle DB-stored bilingual content
    const isHi = lang === 'hi';
    document.querySelectorAll('.leg-en').forEach(el => el.classList.toggle('hidden', isHi));
    document.querySelectorAll('.leg-hi').forEach(el => el.classList.toggle('hidden', !isHi));
}

function toggleLanguage() {
    const current = localStorage.getItem('minerallaw_lang') || 'en';
    applyLanguage(current === 'en' ? 'hi' : 'en');
}

// ------------------------------------------------------------
// SECTION 3: THEME TOGGLE
// ------------------------------------------------------------
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('minerallaw_theme', next);
}

// Apply saved language on every page load
// (Theme is applied by the pre-paint inline script in <head> — no re-application needed here)
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('minerallaw_lang') || 'en';
    applyLanguage(saved);
});