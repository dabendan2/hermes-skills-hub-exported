# CGMH Portal Technical Map

Discovered technical details for the Chang Gung Memorial Hospital (CGMH) registration portal.

## Selectors
- **Captcha Image**: `img#captcha` (Found on `/Query/V` and `/Query/V`).
- **Submit Button**: `button:has-text("送出查詢")`, `input[value*="查詢"]`, or `.btn-submit`.
- **Refresh Captcha Link**: `text=點擊刷新`.
- **Query Input Fields**:
  - ID Number: `input[name="idNumber"]` or `input.std.mb16.w100`
  - Birthday (YYYMMDD or YYMMDD): `input[name="birthday"]`
  - Verification: `input[name="verification"]` or `input.std.mr8`
- **First-Time vs Follow-Up (初診/複診)**:
  - Query form has `input[name="isFirst"]` radio (`N` for 複診, `Y` for 初診).
  - For patients whose initial visit has not yet taken place, selecting `isFirst="Y"` retrieves the pending first-visit registration.

## Result Strings
- **Success (No appointments)**: "查無資料，請確認輸入資料正確性!" or "查無掛號資料".
- **Success (After Cancellation)**: The target row is removed, and the "No data" message usually appears if it was the only appointment.

## Logic Branching
- **Pediatrics**: Restricted to < 18 years old.
- **First Visit**: Requires selecting the "初診" radio button, which changes the required fields (often asks for more personal info).
- **History**: Not available in this portal (`/Query/` or `/Info/`).
