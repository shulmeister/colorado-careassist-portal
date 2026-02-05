# VA Plan of Care Generator - Quick Reference Card

**URL:** https://portal.coloradocareassist.com/va-plan-of-care

---

## 🚀 Quick Start (3 Steps)

1. **Upload** VA Form 10-7080 PDF
2. **Review** auto-extracted data (22 fields)
3. **Download** PDF with VA-compliant filename

---

## 📋 Checklist Before Upload

- [ ] Have VA Form 10-7080 PDF ready
- [ ] Logged into portal
- [ ] PDF is clear and readable

---

## ✅ After Upload - Verify These

**CRITICAL FIELDS:**
- [ ] VA Consult Number (required for billing)
- [ ] First Appointment Date (required for filename)
- [ ] Veteran Last Name + First Initial
- [ ] Last 4 SSN
- [ ] PCP Name

---

## 📁 Filename Format

```
LastName.F.1234_VA000.PCP.P.CC.D.MM.DD.YYYY.001.pdf
```

**Example:**
```
Crowley.W.3414_VA0055325584.Reeder.C.CC.D.02.04.2026.001.pdf
```

**Components:**
1. Veteran: `Crowley.W.3414`
2. VA Consult: `VA0055325584`
3. PCP: `Reeder.C`
4. Agency: `CC.D`
5. Start Date: `02.04.2026`
6. Doc #: `001`

---

## ⚡ Keyboard Shortcuts

- **Tab** - Navigate between fields
- **Ctrl+Enter** - Preview Plan of Care
- **F12** - Open browser console (for debugging)

---

## 🎯 Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| 00.00.0000 in filename | Manually enter First Appointment Date |
| Wrong PCP name | Edit PCP Last/First Name fields |
| Missing ADLs | Check boxes manually |
| "Authentication required" | Log into portal first |
| Blank PDF pages | Already fixed in v2.0 |

---

## 📞 Quick Contacts

**VA Naming Questions:**
Tamatha.Anding@va.gov

**Tech Support:**
jason@coloradocareassist.com

---

## ⏱️ Important Deadlines

**Submit to VA within 5 DAYS** of starting services

---

## 💡 Pro Tips

✓ Keep VA Form 10-7080 open while reviewing
✓ Check browser console (F12) if extraction fails
✓ Download both PDF and HTML (backup)
✓ Always verify VA Consult Number twice
✓ Use consistent date format: MM.DD.YYYY

---

**Version 2.0** | Updated: January 27, 2026
