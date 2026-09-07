# Verified FOMC Meeting Dataset

The initial dataset covers all 24 scheduled FOMC decisions from 2022 through 2024.

## Fields

- meeting date and 14:00 America/New_York decision time
- target-range upper bound immediately before and after the decision
- signed basis-point change
- cut, hold, or hike label
- primary Federal Reserve source URL

## Validation

The loader rejects rows when the stated basis-point change disagrees with the target bounds, the decision label disagrees with the calculated change, dates are unsorted, target ranges are discontinuous, or the source is not a Federal Reserve URL.

## Scope decision

2025 and 2026 will be added only after each meeting statement and target range are programmatically cross-checked. This avoids mixing future scheduled meetings with completed decisions.
