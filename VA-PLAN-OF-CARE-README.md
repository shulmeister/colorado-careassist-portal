# VA Plan of Care Generator

## Overview

Converts VA Form 10-7080 (Approved Referral for Medical Care) into a professional Home Health Certification and Plan of Care (485) with automatic PDF generation and VA-compliant file naming.

## Features

✓ **Automatic VA Naming Convention**
- Follows exact VA protocol for file naming
- Example: `Crowley.W.3414_VA0055325584.Reeder.C.CC.D.02.04.2026.02.04.2026.001.pdf`

✓ **PDF & HTML Download**
- Professional PDF ready for VA submission
- HTML backup for archiving

✓ **Complete Form Capture**
- All veteran demographics
- Referral information
- Clinical data and diagnoses
- ADL dependencies
- Services authorized

✓ **Integrated into Portal**
- Accessible as a tile in the unified portal
- Requires portal authentication

## Usage

### Access the Tool

1. **Portal Tile**: Click "VA Plan of Care Generator" from the portal dashboard
2. **Direct URL**: `https://careassist-unified-0a11ddb45ac0.herokuapp.com/va-plan-of-care`

### Fill Out the Form

1. Open the VA Form 10-7080 PDF you received from the VA
2. Enter the data into the web form:
   - Veteran information (page 1)
   - Referral details (page 1-2)
   - PCP information (page 1)
   - Clinical information (page 5-6)
   - Select ADL dependencies (page 6)

### Generate the Plan of Care

1. Click "Preview Plan of Care"
2. Review the generated document
3. Click "Download PDF" to save with auto-generated filename
4. Submit to VA within 5 days of starting services

## VA Naming Convention

**Format:**
```
LastName.FirstInitial.Last4SSN_VACONSULTNUMBER.PCPLastName.PCP1stInitial.AgencyCode.CertificationDate.StartDate.AgencyDocNum
```

**Example:**
```
Crowley.W.3414_VA0055325584.Reeder.C.CC.D.02.04.2026.02.04.2026.001.pdf
```

**Field Breakdown:**
- `Crowley` - Veteran last name
- `W` - Veteran first initial
- `3414` - Last 4 of SSN
- `VA0055325584` - VA Consult Number (from Form 10-7080)
- `Reeder` - PCP last name
- `C` - PCP first initial
- `CC.D` - Agency Code (Colorado Care Assist Denver)
- `02.04.2026` - Certification Date (Referral Issue Date)
- `02.04.2026` - Start Date (First Appointment Date)
- `001` - Agency Document Number

## Required Fields

These fields are **required** for proper file naming:

- ✓ Veteran Last Name
- ✓ Veteran First Name
- ✓ Last 4 SSN
- ✓ VA Consult Number (Referral Number from Form 10-7080)
- ✓ PCP Last Name
- ✓ PCP First Name
- ✓ Referral Issue Date (becomes Certification Date)
- ✓ First Appointment Date (becomes Start Date)
- ✓ Agency Code (default: CC.D)
- ✓ Agency Document Number (default: 001)

## Data Mapping from VA Form 10-7080

| VA Form 10-7080 Field | Generator Field |
|----------------------|-----------------|
| Veteran Name | Last Name, First Name, Middle Name |
| Veteran Date of Birth | Date of Birth |
| Last 4 SSN | Extract from full SSN |
| Referral Number | VA Consult Number |
| Referral Issue Date | Certification Date |
| First Appointment Date | Start Date |
| Referring Provider | PCP Last/First Name, NPI |
| VA Facility | Facility Name, Phone, Fax |
| Provisional Diagnosis | Diagnosis |
| Reason for Request | Clinical Information |
| Service Requested | Hours Per Week |
| Duration | Authorization Duration |
| Services Needed | ADL Dependencies |

## VA Submission Requirements

1. **Timing**: Submit within **5 days** of starting services
2. **Format**: PDF format (generated automatically)
3. **Filename**: VA naming convention (auto-generated)
4. **Content**: Must include physician certification signature (blank line provided)
5. **Reference**: Include VA Consult Number on all billing

## Technical Details

- **Technology**: Pure HTML/CSS/JavaScript (no backend dependencies)
- **PDF Library**: html2pdf.js (CDN-loaded)
- **Authentication**: Portal SSO required
- **Browser Support**: All modern browsers
- **Mobile Friendly**: Responsive design

## Files Modified

1. `/portal/portal_app.py` - Added route `/va-plan-of-care`
2. `/portal/portal_setup.py` - Added tool to database setup
3. `/VA-PLAN-OF-CARE-README.md` - This documentation

## Contact

For naming convention questions:
**Tamatha Anding**
Email: Tamatha.Anding@va.gov

---

**Version:** 1.0
**Created:** January 27, 2026
**By:** Colorado Care Assist - Jason Shulman
