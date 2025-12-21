# Members: Matching

## Context

We maintain a canonical membership record for each member of the club in this database.
The source information originates from a system called CCN Bikes. Each year, members
sign up for the current year using that system, producing a registration record. This
registration record is not linked to other registration records from previous years.

The membership application therefore is the canonical source. It imports the registrations
from CCN Bikes, and perform linking of registration records to canonical member records
in the database.

## Data model

### Member record

 - It contains the most recent information we have on this specific member.
 - The most recent information is gathered from the newest matched registration record.
 - Each member is assigned a cohort from when they first joined

### Registration record

 - It contains string values directly from the CCN Bikes CSV export
 - Members may format their names, addresses, and other details differently from year to year
 - Members may skip years, so there might be gaps in the data

### Match record

 - It contains a paper trail indicating which registrations support a particular member record
 - It indicates matching means, as well as a score for later auditing
 - Each registration can only be linked to one member (enforced via OneToOneField)
 - A member can have multiple match records (one per registration/year)

## Matching algorithm

The matching implementation uses the `recordlinkage` package and follows a two-phase
approach to handle both initial loads (no existing members) and incremental updates.

### Phase 1: Registration deduplication

Before matching to members, registrations are first matched against each other to
identify clusters of registrations belonging to the same person.

1. Build candidate pairs using blocking on `date_of_birth` and sorted neighborhood
   on `last_name`
2. Compare pairs using weighted field comparisons
3. Filter pairs above the confidence threshold
4. Build clusters using Union-Find algorithm on matching pairs

This ensures that multiple registrations from the same person (across different years)
are grouped together before member resolution.

### Phase 2: Member resolution

For each cluster of registrations:

1. If existing members exist, attempt to match the cluster to a member
2. If a single member matches above threshold: link all registrations to that member
3. If no member matches: create a new member from the most recent registration
4. If multiple members match with similar scores: skip as ambiguous for manual review

### Data updates

When linking registrations to a member:

 - Member data is updated from the most recent registration in the cluster
 - Cohort is set from the earliest registration's date (first day of month)

## Matching rules

### Fields and comparison methods

| Field | Method | Threshold | Weight |
|-------|--------|-----------|--------|
| First name | Jaro-Winkler | 0.85 | 3x |
| Date of birth | Exact | - | 3x |
| Sex | Exact | - | 3x |
| Last name | Jaro-Winkler | 0.85 | 2x |
| Email | Levenshtein | 0.9 | 1x |
| Phone | Levenshtein | 0.8 | 1x |
| City | Jaro-Winkler | 0.85 | 1x |
| Country | Exact | - | 1x |
| Postal code | Levenshtein | 0.9 | 1x |

### Confidence calculation

Confidence score is calculated as the weighted sum of field matches divided by total
possible weight (16). The most stable identity fields (first name, DOB, sex) contribute
3x, last name contributes 2x (can change with marriage), and contact/location fields
contribute 1x.

### Ambiguous match detection

A match is considered ambiguous when:
 - Multiple members match above the confidence threshold
 - The top two scores differ by 0.1 or less

Ambiguous clusters are skipped and reported to the console with full details of the
registrations and candidate members for manual review.

## Command usage

```bash
# Preview matching without making changes
python manage.py matchregistrations --dry-run

# Run with custom confidence threshold (default: 0.7)
python manage.py matchregistrations --min-confidence 0.8

# Run with debug output
python manage.py matchregistrations --debug

# Full run
python manage.py matchregistrations
```

### Output

The command reports:
 - Number of unprocessed registrations found
 - Number of unique person clusters identified
 - New members created
 - Existing members updated
 - Registrations linked
 - Ambiguous clusters skipped (with details)

## Match record values

| Method | Description |
|--------|-------------|
| `recordlinkage-new` | New member created for this cluster |
| `recordlinkage-dedup` | Matched to existing member via deduplication |

## Known limitations

### Duplicate members

If duplicate Member records exist in the database (same person with different emails
or slight name variations), the algorithm will flag registrations matching those
duplicates as ambiguous. This requires manual cleanup of the duplicate members before
re-running the matching.

### Manual evaluation

The algorithm uses unsupervised classification only. Ambiguous cases and low-confidence
matches require manual review and are outside the scope of automatic matching.

