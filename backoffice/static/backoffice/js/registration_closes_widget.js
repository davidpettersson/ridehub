/* global DateTimeShortcuts */

function setRegistrationClosesAt(option, startsAtFieldId, registrationClosesFieldId) {
    // Get the field elements
    const startsAtDateInput = document.getElementById(startsAtFieldId + '_0'); // Date input
    const startsAtTimeInput = document.getElementById(startsAtFieldId + '_1'); // Time input
    const registrationClosesDateInput = document.getElementById(registrationClosesFieldId + '_0');
    const registrationClosesTimeInput = document.getElementById(registrationClosesFieldId + '_1');

    // Validate fields exist
    if (!startsAtDateInput || !startsAtTimeInput || !registrationClosesDateInput || !registrationClosesTimeInput) {
        console.error('Could not find all required date/time input fields.');
        return;
    }

    // Get start date/time values
    const startsAtDateStr = startsAtDateInput.value;
    const startsAtTimeStr = startsAtTimeInput.value;

    if (!startsAtDateStr || !startsAtTimeStr) {
        alert('Please set the "Starts At" date and time first.');
        return;
    }

    // Parse the start date and time into a JavaScript Date object
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

    // Calculate registration closes time based on the selected option
    let registrationClosesDateTime;

    switch (option) {
        case 'before_2hours':
            // 2 hours before event starts
            registrationClosesDateTime = new Date(startsAtDateTime.getTime() - (2 * 60 * 60 * 1000));
            break;
        case 'day_before_5pm':
            // Day before at 5:00 PM
            registrationClosesDateTime = new Date(startsAtDateTime);
            registrationClosesDateTime.setDate(registrationClosesDateTime.getDate() - 1);
            registrationClosesDateTime.setHours(17, 0, 0, 0);
            break;
        case 'day_before_noon':
            // Day before at 12:00 PM (noon)
            registrationClosesDateTime = new Date(startsAtDateTime);
            registrationClosesDateTime.setDate(registrationClosesDateTime.getDate() - 1);
            registrationClosesDateTime.setHours(12, 0, 0, 0);
            break;
        default:
            console.error('Invalid option:', option);
            return;
    }

    // Format the date back to YYYY-MM-DD format
    const closesDateStr = registrationClosesDateTime.getFullYear() + '-' + 
                         ('0' + (registrationClosesDateTime.getMonth() + 1)).slice(-2) + '-' + 
                         ('0' + registrationClosesDateTime.getDate()).slice(-2);
    
    // Format the time to HH:MM format for the time input
    const closesTimeStr = ('0' + registrationClosesDateTime.getHours()).slice(-2) + ':' + 
                         ('0' + registrationClosesDateTime.getMinutes()).slice(-2);

    // Set the values to the form fields
    registrationClosesDateInput.value = closesDateStr;
    registrationClosesTimeInput.value = closesTimeStr;

    // Trigger change events on the inputs to update Django's UI
    registrationClosesDateInput.dispatchEvent(new Event('change', { bubbles: true }));
    registrationClosesTimeInput.dispatchEvent(new Event('change', { bubbles: true }));
} 