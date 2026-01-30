# Newsletter Template Guide

## Structure

The newsletter template is designed to add value to readers with:
1. Brief updates (recent hires, service additions) - Optional, minimal
2. 3-4 curated articles/videos from credible sources (NYTimes, WSJ, KFF, VA, etc.)
3. Survey and Google Business Profile review links
4. Minimal self-promotional content

## Links Reference

### Google Business Profile Reviews
- **Denver**: https://g.page/r/CQhjbJz17xaDEBE/review
- **Colorado Springs**: https://g.page/r/CZb4OLGSmhxsEBE/review

### Survey Links
- **Client Satisfaction Survey**: https://forms.gle/zSCvFYV7DtmEhP9r9
- **Referral Partner Survey**: https://forms.gle/Bjcgg9Zgib12JPiD6

### Link Usage by Audience
- **Clients** → Use Client Satisfaction Survey
- **Referral Sources** → Use Referral Partner Survey
- **Google Review** → Use Denver (default) or choose based on contact location

## Template Variables

### Required Variables
- `{{MONTH}}` - Month name (e.g., "January 2025")
- `{{FIRSTNAME}}` - Contact's first name (Brevo merge tag)
- `{{SURVEY_LINK}}` - Link to survey (use appropriate survey for audience)
- `{{GBP_REVIEW_LINK}}` - Link to Google Business Profile review
- `{{ARTICLE1_URL}}`, `{{ARTICLE1_TITLE}}`, `{{ARTICLE1_SOURCE}}`, `{{ARTICLE1_SUMMARY}}`
- `{{ARTICLE2_URL}}`, `{{ARTICLE2_TITLE}}`, `{{ARTICLE2_SOURCE}}`, `{{ARTICLE2_SUMMARY}}`
- `{{ARTICLE3_URL}}`, `{{ARTICLE3_TITLE}}`, `{{ARTICLE3_SOURCE}}`, `{{ARTICLE3_SUMMARY}}`

### Optional Variables
- `{{ARTICLE4_URL}}`, `{{ARTICLE4_TITLE}}`, `{{ARTICLE4_SOURCE}}`, `{{ARTICLE4_SUMMARY}}` - 4th article (optional)
- `{{RECENT_HIRES}}` - HTML content about recent hires
- `{{SERVICE_ADDITIONS}}` - HTML content about service additions

## Two Audiences

1. **Referral Sources** - Focus on partnership, referral process, care coordination
2. **Clients** - Focus on services, support, resources

Both audiences receive the same structure but content can be customized.

## Content Philosophy

- **Value-first**: Focus on useful information, not self-promotion
- **Credible sources**: NYTimes, Wall Street Journal, KFF, VA, etc.
- **Brief updates**: Keep agency news minimal and relevant
- **Reader benefit**: Every piece of content should benefit the reader

## Example Article Format

```html
<div style="margin: 0 0 20px 0; padding: 15px; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 5px;">
    <p style="margin: 0 0 8px 0; font-size: 14px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">NYTimes</p>
    <h4 style="margin: 0 0 8px 0; font-size: 18px; color: #1f2937; line-height: 1.4;">
        <a href="https://example.com/article" style="color: #2563eb; text-decoration: none;">Article Title Here</a>
    </h4>
    <p style="margin: 0; font-size: 15px; color: #6b7280; line-height: 1.5;">Brief summary or why this matters...</p>
</div>
```

