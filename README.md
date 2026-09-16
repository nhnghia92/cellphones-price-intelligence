# CellphoneS Price Intelligence - Free Cloud MVP

Architecture: CellphoneS -> GitHub Actions -> Playwright scraper -> Google Sheets -> rule engine -> Gemini Free Tier -> AI_INSIGHTS/DASHBOARD.

## GitHub Secrets
- GOOGLE_SERVICE_ACCOUNT_JSON
- GOOGLE_SHEET_ID
- GEMINI_API_KEY

## GitHub Variables (optional)
- GEMINI_MODEL = gemini-2.5-flash-lite
- CELLPHONES_URL = https://cellphones.com.vn/phu-kien/sac-dien-thoai/sac.html?order=filter_price&dir=asc&sac_cong_suat=45w-duoi-67w
- MIN_CHANGE_PCT = 5

The workflow runs 4 times/day: 09:00, 12:00, 18:00, 23:00 Vietnam time.

Important: the scraper selectors may need adjustment if CellphoneS changes its HTML or anti-bot behavior.
