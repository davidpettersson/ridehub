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

## Matching implementation

The matching implementation uses the recordlinkage package, and follows the prescribed
process of cleaning, indexing, comparing, classifying, and potentially evaluating. Any
classification must be unsupervised, the only evaluation that happens is manual and outside
the scope of this matching algorithm.

## Matching rules

 - Fields that contribute to matching:
   - First name
   - Last name
   - Date of birth
   - Email
   - Phone
   - Sex
   - City
   - Country
   - Postal code
 - Fields that yield higher confidence than the others:
   - First name
   - Last name
   - Date of birth
   - Sex

