/* global DateTimeShortcuts */
// The global comment is for linters, to let them know these Django admin JS variables are available.

function setEndsAtDuration(hours, startsAtFieldId, endsAtFieldId) {
    // For MultiWidget, the inputs are indexed by 0 and 1
    const startsAtDateInput = document.getElementById(startsAtFieldId + '_0'); // Date input
    const startsAtTimeInput = document.getElementById(startsAtFieldId + '_1'); // Time input
    const endsAtDateInput = document.getElementById(endsAtFieldId + '_0');     // Date input
    const endsAtTimeInput = document.getElementById(endsAtFieldId + '_1');     // Time input

    if (!startsAtDateInput || !startsAtTimeInput || !endsAtDateInput || !endsAtTimeInput) {
        console.error('Could not find all required date/time input fields.', {
            startsAtFieldId, endsAtFieldId, 
            found: {
                startsAtDateInput: !!startsAtDateInput,
                startsAtTimeInput: !!startsAtTimeInput,
                endsAtDateInput: !!endsAtDateInput,
                endsAtTimeInput: !!endsAtTimeInput
            }
        });
        return;
    }

    const startsAtDateStr = startsAtDateInput.value;
    const startsAtTimeStr = startsAtTimeInput.value;

    if (!startsAtDateStr || !startsAtTimeStr) {
        alert('Please set the "Starts At" date and time first.');
        return;
    }

    // Parse the date and time into a JavaScript Date object
    let startsAtDateTime;
    try {
        // Parse date in YYYY-MM-DD format
        let [year, month, day] = startsAtDateStr.split('-').map(Number);
        // Parse time in HH:MM:SS or HH:MM format
        let timeParts = startsAtTimeStr.split(':').map(Number);
        let hour = timeParts[0] || 0;
        let minute = timeParts[1] || 0;
        let second = timeParts[2] || 0;
        
        // JavaScript months are 0-indexed (0=January, 11=December)
        startsAtDateTime = new Date(year, month - 1, day, hour, minute, second);

        if (isNaN(startsAtDateTime.getTime())) {
            throw new Error('Parsed date is invalid');
        }

    } catch (e) {
        console.error('Error parsing Starts At date/time:', startsAtDateStr, startsAtTimeStr, e);
        alert('Could not parse the "Starts At" date and time. Please ensure it is in a valid format (YYYY-MM-DD HH:MM).');
        return;
    }

    // Calculate the end date/time by adding the specified number of hours
    const endsAtDateTime = new Date(startsAtDateTime.getTime() + hours * 60 * 60 * 1000);

    // Format the date back to YYYY-MM-DD format
    const endsAtDateStr = endsAtDateTime.getFullYear() + '-' + 
                          ('0' + (endsAtDateTime.getMonth() + 1)).slice(-2) + '-' + 
                          ('0' + endsAtDateTime.getDate()).slice(-2);
    
    // Format the time back to HH:MM format for the time input
    const endsAtTimeStr = ('0' + endsAtDateTime.getHours()).slice(-2) + ':' + 
                          ('0' + endsAtDateTime.getMinutes()).slice(-2);

    // Set the values to the form fields
    endsAtDateInput.value = endsAtDateStr;
    endsAtTimeInput.value = endsAtTimeStr;

    // Trigger change events on the inputs to update Django's UI
    endsAtDateInput.dispatchEvent(new Event('change', { bubbles: true }));
    endsAtTimeInput.dispatchEvent(new Event('change', { bubbles: true }));
    
    // If DateTimeShortcuts is available (from Django admin), update the calendar/clock widgets
    if (typeof DateTimeShortcuts !== 'undefined') {
        // Try to update calendar and time widgets by triggering their update functions
        try {
            DateTimeShortcuts.handleCalendarQuickLink(endsAtDateInput.id, endsAtDateStr);
            DateTimeShortcuts.handleClockQuicklink(endsAtTimeInput.id, endsAtTimeStr);
        } catch (e) {
            console.log('DateTimeShortcuts update attempted but not critical if it fails:', e);
        }
    }
} 