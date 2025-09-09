# Email Template Guidelines

## Template Maintenance
- Every email template in HTML has a corresponding text-based version
- Edits to email templates must primarily be made to the HTML version
- Always make sure to make a text-based version by updating the adjacent .txt file

## Link Management
- If an email has a hyperlink in it, always create a unit test to ensure it is correct
- Ensure that any hyperlinks use a base URL so that we don't have relative URLs
- Verify all email links work correctly in different email clients

## Testing Requirements
- Create unit tests for email templates with hyperlinks
- Test email rendering in both HTML and text formats