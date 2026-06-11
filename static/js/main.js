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
        nav_logout:     "Logout",
        nav_login:      "Login",
        nav_pricing:    "Pricing",

        // Home page
        hero_title:     "Rajasthan Mining Compliance",
        hero_subtitle:  "Never miss a government deadline. Never pay a penalty.",
        hero_desc:      "Track EC reports, calculate royalty fees, and get expert guidance — all in one place. Built for Rajasthan mine owners.",
        hero_cta:       "Get Started Free",
        hero_pricing:   "View Pricing",
        problem_title:  "⚠️ The Cost of Missing a Deadline",
        feature1_title: "Compliance Calendar",
        feature1_desc:  "Automatic reminders 7 days and 1 day before every EC report, annual return, and government deadline. Delivered to your WhatsApp.",
        feature2_title: "Fee Calculator",
        feature2_desc:  "Calculate exact royalty, DMF, and NPV amounts using verified Rajasthan government rates. Historical rates for past lease dates.",
        feature3_title: "Expert Consultation",
        feature3_desc:  "30 years of Rajasthan mining law expertise. Get answers to complex compliance questions within 24 hours.",
        trusted_by:     "Trusted by mine owners across Rajasthan",

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
    },

    // ⚠️ PLACEHOLDER HINDI — father must verify all legal/technical terms before launch (Phase 2 per project spec).
    hi: {
        // Navigation
        nav_dashboard:  "डैशबोर्ड",
        nav_calculator: "कैलकुलेटर",
        nav_checklist:  "चेकलिस्ट",
        nav_expert:     "विशेषज्ञ से पूछें",
        nav_logout:     "लॉगआउट",
        nav_login:      "लॉगिन",
        nav_pricing:    "मूल्य",

        // Home page
        hero_title:     "राजस्थान खनन अनुपालन",
        hero_subtitle:  "कोई सरकारी समय-सीमा न चूकें। कोई जुर्माना न भरें।",
        hero_desc:      "EC रिपोर्ट ट्रैक करें, रॉयल्टी शुल्क की गणना करें, और विशेषज्ञ मार्गदर्शन पाएं — सब एक जगह। राजस्थान के खनन मालिकों के लिए।",
        hero_cta:       "मुफ्त शुरू करें",
        hero_pricing:   "मूल्य देखें",
        problem_title:  "⚠️ समय-सीमा चूकने की कीमत",
        feature1_title: "अनुपालन कैलेंडर",
        feature1_desc:  "हर EC रिपोर्ट, वार्षिक रिटर्न और सरकारी समय-सीमा से 7 दिन और 1 दिन पहले WhatsApp पर स्वचालित अनुस्मारक।",
        feature2_title: "शुल्क कैलकुलेटर",
        feature2_desc:  "सत्यापित राजस्थान सरकारी दरों का उपयोग करके सटीक रॉयल्टी, DMF और NPV राशि की गणना करें।",
        feature3_title: "विशेषज्ञ परामर्श",
        feature3_desc:  "30 साल का राजस्थान खनन कानून अनुभव। 24 घंटे के भीतर जटिल अनुपालन प्रश्नों के उत्तर पाएं।",
        trusted_by:     "राजस्थान भर के खनन मालिकों द्वारा विश्वसनीय",

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
}

function toggleLanguage() {
    const current = localStorage.getItem('minerallaw_lang') || 'en';
    applyLanguage(current === 'en' ? 'hi' : 'en');
}

// Apply saved language on every page load
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('minerallaw_lang') || 'en';
    applyLanguage(saved);
});