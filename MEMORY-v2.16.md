# EnPro FM Portal v2.16 - Memory/Handoff

## Current State (April 9, 2026)
**Production URL:** https://enpro-fm-portal.onrender.com  
**Branch:** v2.16-clean  
**Last Commit:** 1fa36f7 - Remove follow-up options after product lookup

## What Works

### 1. Side-by-Side Compare ✅
- Two cards side-by-side (blue vs green borders)
- Shows: Description, Manufacturer, Micron, Media, Max Temp, Max PSI, Price, Stock
- Follow-up text: "What would you like to compare next — other manufacturers, specs, or applications?"
- Streaming event: `compare` (server.py line 471-472)

### 2. Pregame (Meeting Prep) ✅
- Triggers on: "meeting", "customer", "pregame" keywords
- Returns: headline, picks (part numbers + reasons), follow_up question, body (advice)
- Structured JSON response from GPT-4.1-mini
- Renders as: headline → body bullets → picks with reasons → follow-up question

### 3. Quote Tracker Hidden ✅
- CSS: `#quoteTracker { display: none !important; }`
- `.quote-tracker { display: none !important; }`

### 4. Auth (PIN-based) ✅
- Login page with user dropdown
- 0000 PIN works for testing
- 7-day session cookies

## What Was Removed (Broken)

### Follow-up Options After Product Lookup ❌ REMOVED
- ~~"Show more [manufacturer] products"~~
- ~~"Compare this part number"~~
- ~~"Pregame a meeting with this product"~~
- ~~"See compatible housings"~~
- ~~"Check chemical compatibility"~~

**Why:** These options failed because:
1. MERV ratings not in catalog data
2. Chemical compat crosswalk incomplete  
3. Housings lookup not implemented
4. Manufacturer search hit dead ends

### Now: Just show clean product card, no options

## Test Files Created

| File | Purpose |
|------|---------|
| `tests/compare-test.spec.js` | Screenshot compare UI |
| `tests/pregame-test.spec.js` | API test pregame response |
| `tests/scenarios.spec.js` | 10 automated scenarios |
| `tampermonkey-convo-fixed.js` | 4-turn conversation script |
| `download_data.py` | Azure blob data downloader |

## Key Code Changes

### router.py
- Line 650: Added "meeting" and "customer" as pregame keywords
- Line 471-472: Added `compare` streaming event
- Lines 1590-1602: Removed follow-up options from product lookup

### static/app.js
- Line 631-641: Handle `compare` streaming event
- Lines 1679-1736: `renderCompareTable()` - two cards side-by-side
- Removed `appendFollowUps()` calls after product cards

### static/index.html
- Line 1022: CSS to hide quote tracker

## Known Issues / TODO

1. **Conversation Flow Broken**
   - Pregame asks follow-up question
   - User answers with specs ("MERV 14", "5 micron")
   - System fails because those fields not in catalog
   - Need: Fallback response when data is missing

2. **Data Gaps**
   - MERV ratings missing
   - Chemical compatibility incomplete
   - Housing crosswalks not linked

3. **Voice vs Text Discrepancy**
   - Voice uses `/api/voice-search` → routes to chat
   - Text uses `/api/chat/stream` 
   - Sometimes different responses

## Demo Script (Working Scenarios)

### Scenario 1: Compare
1. "compare HC9020FCN4Z vs HC9021FAS4Z"
2. Shows two cards side-by-side
3. Shows follow-up prompt

### Scenario 2: Pregame Brewery
1. "brewery customer meeting tomorrow"
2. Gets headline about yeast/batch consistency
3. Gets picks with reasons
4. Gets follow-up question

### Scenario 3: Part Lookup
1. "CLR140XK"
2. Shows clean product card
3. No broken follow-up options

## Branches

- `v2.16-clean` - Current production (NEW)
- `master` - Last known good backup (v2.13)
- `v2.16-conversational-ai` - Experimental (not deployed)

## Next Steps (When Ready)

1. Fix conversation engine to handle missing data gracefully
2. Add working follow-ups that don't promise what we can't deliver
3. Test with real customer scenarios
4. Merge to master when stable

## Environment Variables Needed

```bash
AZURE_BLOB_SAS="se=2027-03-25T00%3A00%3A00Z&sp=rl&spr=https&sv=2026-02-06&ss=b&srt=sco&sig=..."
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=enproaidatav1;..."
AZURE_OPENAI_ENDPOINT=https://enpro-filtration-ai.cognitiveservices.azure.com/
AZURE_OPENAI_KEY=...
AZURE_WHISPER_ENDPOINT=https://enpro-whisper.openai.azure.com/
AZURE_WHISPER_KEY=...
SESSION_SECRET=...
DATABASE_URL=...
```

## Key People

- **Andrew** - Product owner, knows what reps need
- **Peter** - Enpro contact for data/offices
- **You** - Building the conversation engine

---

**Summary:** v2.16 works for demos but conversation flow needs redesign. Broken options removed. Clean compare and pregame work. Data gaps (MERV, chemical, housings) cause failures when users ask for them.
