# Critical Bugs Found During Testing - Dec 12, 2025

## ❌ **CRITICAL BUGS:**

### 1. MyWay Visits Not Saving (HIGHEST PRIORITY)
**Problem:**
- User uploaded MyWay route for Nov 25 (4 visits parsed)
- Success message displayed
- But visits don't appear in Visits tab
- Last visit shown is Nov 24

**Possible Causes:**
- ActivityLogger.log_visit() failing and rolling back transaction
- Visit.to_dict() method missing fields
- Database constraint violation
- Timezone issues with visit_date filtering

**Fix Needed:**
- Check Mac Mini (Local) logs for errors
- Add try/catch around activity logging to prevent rollback
- Verify Visit records are being committed
- Test visit retrieval query

### 2. Hot Contacts Text Unreadable
**Problem:**
- Text in Hot Contacts sidebar still not readable
- Previous fix (text-foreground) didn't work

**Fix Needed:**
- Check actual rendered CSS classes
- May need explicit color values (e.g., `text-white` or `text-gray-100`)

### 3. Latest Activity Not Loading
**Problem:**
- "Failed to load activity log" error on Dashboard

**Fix Needed:**
- Check DashboardActivityLog component
- Verify `/admin/activityLogs` or `/api/activity-logs` endpoint

### 4. Contacts Missing Company Names
**Problem:**
- Contact detail pages show company name
- But contact list doesn't display companies

**Fix Needed:**
- Check ContactListContent component
- Verify `contact.company` vs `contact.company_name` field mapping

### 5. Company Filters Not Working
**Problem:**
- Left sidebar filters on Companies page don't work

**Fix Needed:**
- Check filter implementation in Companies list
- Verify backend filter parameters

### 6. Company Logos Missing
**Problem:**
- Company tiles should show logos (enriched via OpenAI API)
- Currently not implemented

**Fix Needed:**
- Add logo field to ReferralSource model
- Implement OpenAI-based logo lookup/generation
- Or use Clearbit/similar service for company logos

---

## 🔧 **FIX PRIORITY ORDER:**

1. **MyWay visits not saving** (CRITICAL - data loss issue)
2. **Hot Contacts text** (UX issue)
3. **Latest Activity loading** (Dashboard broken)
4. **Contacts company display** (Data display issue)
5. **Company filters** (Filter functionality)
6. **Company logos** (Nice-to-have enhancement)

---

## 📋 **NEXT STEPS:**

1. Check Mac Mini (Local) logs for visit upload errors
2. Fix ActivityLogger exception handling
3. Test visit upload again
4. Fix remaining UI issues
5. Deploy and re-test

