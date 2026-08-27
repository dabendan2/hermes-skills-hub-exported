---
name: taiwan-cpbl-cheerleader-schedule
description: Extract and verify CPBL cheerleader monthly appearance rosters from schedule images using Vision OCR.
---

# Taiwan CPBL Cheerleader Schedule (Vision OCR)

Extract, verify, and normalize monthly home game appearance rosters for CPBL cheerleading squads in Taiwan (Passion Sisters, Fubon Angels, Dragon Beauties, Rakuten Girls, Uni-Girls, Wing Stars) from social media schedule images.

## Trigger
- User asks for CPBL cheerleader monthly schedules or appearance dates.
- User provides a roster infographic/grid schedule image for Vision OCR parsing.

## Workflow Rules
1. **Strict Sourcing & Truthfulness**: Download schedule images directly matching the requested month. If a squad has NOT officially published the schedule for that month, report **"Not Yet Published (尚未公布)"** directly. NEVER substitute with older month images or mislabel files.
2. **Cache-First Execution**:
   - Check `~/.cache/cpbl_cheerleader_schedules/` for existing `<squad>_<month>_*.png` or `.json`.
   - If missing, fetch schedule post images via `meta-access` skill:
     `~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p fb --scope <handle> --keywords <keywords> -o ~/.cache/cpbl_cheerleader_schedules -d`
   - Run Vision OCR: `scripts/extract_schedule.py ~/.cache/cpbl_cheerleader_schedules/<image_name>`

## Official Squad Social Accounts & Handles
| Squad | FB Handle / ID | IG Handle | Search Keywords |
| :--- | :--- | :--- | :--- |
| **Passion Sisters** | `Passionsisters` | `passionsisters_official` | `班表`, `8月` |
| **Fubon Angels** | `FubonAngels` | `fubon_angels_official` | `班表`, `8月` |
| **Rakuten Girls** | `RakutenGirls.official` | `rakuten_girls` | `八月`, `班表` |
| **Uni-Girls** | `loveunigirls` | `unigirls_official` | `班表`, `女孩日` |
| **Wing Stars** | `tsgwingstars` | `wingstars_official` | `班表`, `雄鷹班表` |
| **Dragon Beauties** | `100069085601345` | `dragon_beauties_official` | `班表`, `下半季` |

## Programmatic Scripts

### Vision OCR Parser (`scripts/extract_schedule.py`)
Processes multiple carousel schedule slides concurrently using `gemini-3.6-flash` and outputs structured JSON.

```bash
# Direct execution (shebang enabled)
scripts/extract_schedule.py ~/.cache/cpbl_cheerleader_schedules/passionsisters_8_1.png
```

## Pitfalls
- **Blacklisted Aggregators**: Never use `lala.pythings.dev` or third-party unverified aggregators.
- **Carousel Completeness**: Squad schedules span multiple slides (usually 2-4 slides). Always process all carousel slides for full roster coverage.
