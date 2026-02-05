# VA Plan of Care Generator

Converts VA Form 10-7080 (Approved Referral) into a Home Health Certification and Plan of Care (485) with automatic PDF generation and VA-compliant naming.

## Features

✓ **Automatic VA Naming Convention**
- Follows exact VA protocol: `LastName.FirstInitial.Last4.VACONSULTNUMBER.PCPLastName.PCP1stInitial.AgencyCode.CertificationDate.StartDate.AgencyDocNum`
- Example: `Crowley.W.3414_VA0055325584.Reeder.C.CCARE.02.04.2026.02.04.2026.001.pdf`

✓ **PDF & HTML Download**
- Download as professional PDF (ready to submit to VA)
- Download as HTML for archiving or editing

✓ **Complete Form Capture**
- Veteran demographics
- Referral information
- Clinical data
- ADL dependencies
- Services authorized

✓ **Professional Formatting**
- VA-compliant layout
- Print-ready design
- Clean, readable output

## Usage

### Option 1: Standalone File
1. Open `va-plan-of-care.html` in any web browser
2. Fill in the form with data from VA Form 10-7080
3. Click "Preview Plan of Care"
4. Click "Download PDF" to get the final document

### Option 2: Serve via Flask Portal
Add this route to your `portal_app.py`:

```python
@app.route('/va-plan-of-care')
def va_plan_of_care():
    return send_from_directory('static', 'va-plan-of-care.html')
```

Then access at: `http://localhost:5000/va-plan-of-care`

### Option 3: Deploy to Mac Mini
The file is already in the `static/` directory and will be deployed automatically with your Mac Mini app.

Access at: `https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care.html`

## VA Naming Convention

The filename is automatically generated using VA's exact specification:

**Format:**
```
LastName.FirstInitial.Last4SSN_VACONSULTNUMBER.PCPLastName.PCP1stInitial.AgencyCode.CertificationDate.StartDate.AgencyDocNum
```

**Example:**
```
Crowley.W.3414_VA0055325584.Reeder.C.CCARE.02.04.2026.02.04.2026.001.pdf
```

**Field Breakdown:**
- `Crowley` - Veteran last name
- `W` - Veteran first initial
- `3414` - Last 4 of SSN
- `VA0055325584` - VA Consult Number (Referral Number)
- `Reeder` - PCP last name
- `C` - PCP first initial
- `CCARE` - Agency Code (Colorado Care Assist)
- `02.04.2026` - Certification Date (Referral Issue Date)
- `02.04.2026` - Start Date (First Appointment Date)
- `001` - Agency Document Number

## Data Source: VA Form 10-7080

Extract the following information from the VA Form 10-7080:

### Page 1 - Header Section
- Veteran Name → split into Last, First, Middle
- Veteran DOB → Date of Birth field
- Referral Number → VA Consult Number (e.g., VA0055325584)
- Referral Issue Date → Certification Date
- First Appointment Date → Start Date
- Veteran Address → Address field
- Veteran Phone → Phone field
- Referring Provider → PCP Name
- Referring Provider NPI → PCP NPI

### Page 2 - Services Section
- Service Requested → Hours Per Week (e.g., "7 to 11 hrs Per Week")
- Duration → Authorization Duration (e.g., "180 Days")

### Page 5 - Clinical Information
- Provisional Diagnosis → Diagnosis field
- Reason for Request → Clinical Information

### Page 6 - Services Needed Section
- ADL Dependencies → Check applicable boxes

## Required Fields

These fields are **required** to generate a valid filename and Plan of Care:

- ✓ Veteran Last Name
- ✓ Veteran First Name
- ✓ Last 4 SSN
- ✓ VA Consult Number
- ✓ PCP Last Name
- ✓ PCP First Name
- ✓ Referral Issue Date (Certification Date)
- ✓ First Appointment Date (Start Date)
- ✓ Agency Code
- ✓ Agency Document Number

## VA Submission Requirements

1. **Timing**: Submit Plan of Care within **5 days** of starting services
2. **Format**: PDF format required
3. **Filename**: Must follow VA naming convention (automatically generated)
4. **Content**: Must include physician certification signature
5. **Reference**: All billing must include the VA Consult Number as Prior Authorization

## Contact for Naming Questions

For naming convention questions or clarifications:
**Tamatha Anding**
Email: Tamatha.Anding@va.gov

## Technical Details

- **No Dependencies**: Pure HTML/CSS/JavaScript
- **PDF Library**: html2pdf.js (CDN-loaded)
- **Browser Support**: All modern browsers (Chrome, Firefox, Safari, Edge)
- **Mobile Friendly**: Responsive design works on tablets
- **Offline Capable**: Can work offline after first load

## Files Created

- `/static/va-plan-of-care.html` - Main application
- `/static/VA-PLAN-OF-CARE-README.md` - This documentation

## Future Improvements

Potential enhancements:
- [ ] PDF upload with OCR to auto-fill from VA Form 10-7080
- [ ] Save/Load draft functionality (localStorage)
- [ ] Multiple veteran batch processing
- [ ] Integration with WellSky for auto-population
- [ ] Email submission to VA portal

## Version History

- **v1.0** (Jan 27, 2026): Initial release
  - Full form capture
  - Automatic VA naming
  - PDF/HTML download
  - Standalone operation

---

**Last Updated:** January 27, 2026
**Created By:** Colorado Care Assist - Jason Shulman
**VA Contact:** Tamatha.Anding@va.gov (naming conventions)
