/* global DateTimeShortcuts */

/**
 * Add a duration in hours to a reference time
 * @param {Date} referenceTime - The reference date/time (e.g., starts_at)
 * @param {number} hours - Number of hours to add
 * @returns {Date} - A new Date object with the added hours
 */
function add_duration(referenceTime, hours) {
    if (!(referenceTime instanceof Date) || isNaN(referenceTime.getTime())) {
        console.error('Invalid reference time provided', referenceTime);
        return null;
    }

    if (typeof hours !== 'number' || isNaN(hours)) {
        console.error('Invalid hours value:', hours);
        return null;
    }

    // Create a new date object to avoid modifying the original
    const resultTime = new Date(referenceTime.getTime() + hours * 60 * 60 * 1000);
    return resultTime;
}

/**
 * Subtract a duration in hours from a reference time
 * @param {Date} referenceTime - The reference date/time (e.g., starts_at)
 * @param {number} hours - Number of hours to subtract
 * @returns {Date} - A new Date object with the subtracted hours
 */
function subtract_duration(referenceTime, hours) {
    if (!(referenceTime instanceof Date) || isNaN(referenceTime.getTime())) {
        console.error('Invalid reference time provided', referenceTime);
        return null;
    }

    if (typeof hours !== 'number' || isNaN(hours)) {
        console.error('Invalid hours value:', hours);
        return null;
    }

    // Create a new date object to avoid modifying the original
    const resultTime = new Date(referenceTime.getTime() - hours * 60 * 60 * 1000);
    return resultTime;
}

/**
 * Set time to a specific hour and minute on a specific day relative to reference date
 * @param {Date} referenceTime - The reference date/time (e.g., starts_at)
 * @param {string} relativeDate - Options: 'day_before', 'day_of', 'day_after', 'same_day'
 * @param {string} timeString - Time in 24-hour format (HH:MM)
 * @returns {Date} - A new Date object with the calculated time
 */
function set_specific_time(referenceTime, relativeDate, timeString) {
    if (!(referenceTime instanceof Date) || isNaN(referenceTime.getTime())) {
        console.error('Invalid reference time provided', referenceTime);
        return null;
    }

    // Create a new date object to avoid modifying the original
    const resultTime = new Date(referenceTime);
    
    // Adjust the date based on the relative date parameter
    switch (relativeDate) {
        case 'day_before':
            resultTime.setDate(resultTime.getDate() - 1);
            break;
        case 'day_after':
            resultTime.setDate(resultTime.getDate() + 1);
            break;
        case 'day_of':
        case 'same_day':
            // No date change needed
            break;
        default:
            console.error('Invalid relativeDate parameter:', relativeDate);
            return null;
    }
    
    // Parse and set the absolute time
    if (timeString && typeof timeString === 'string') {
        const [hours, minutes] = timeString.split(':').map(Number);
        
        if (isNaN(hours) || isNaN(minutes)) {
            console.error('Invalid time format, expected HH:MM:', timeString);
            return null;
        }
        
        resultTime.setHours(hours, minutes, 0, 0);
    }
    
    return resultTime;
}

/**
 * Parse a date and time string into a JavaScript Date object
 * @param {string} dateStr - Date string in YYYY-MM-DD format
 * @param {string} timeStr - Time string in HH:MM or HH:MM:SS format
 * @returns {Date|null} - A Date object or null if parsing fails
 */
function parseDateTime(dateStr, timeStr) {
    try {
        if (!dateStr || !timeStr) {
            return null;
        }
        
        // Parse date in YYYY-MM-DD format
        const [year, month, day] = dateStr.split('-').map(Number);
        
        // Parse time in HH:MM:SS or HH:MM format
        const timeParts = timeStr.split(':').map(Number);
        const hour = timeParts[0] || 0;
        const minute = timeParts[1] || 0;
        const second = timeParts[2] || 0;
        
        // JavaScript months are 0-indexed (0=January, 11=December)
        const dateTime = new Date(year, month - 1, day, hour, minute, second);
        
        if (isNaN(dateTime.getTime())) {
            return null;
        }
        
        return dateTime;
    } catch (e) {
        console.error('Error parsing date/time:', dateStr, timeStr, e);
        return null;
    }
}

/**
 * Format a Date object to a date string in YYYY-MM-DD format
 * @param {Date} date - The Date object to format
 * @returns {string} - Formatted date string
 */
function formatDate(date) {
    return date.getFullYear() + '-' + 
           ('0' + (date.getMonth() + 1)).slice(-2) + '-' + 
           ('0' + date.getDate()).slice(-2);
}

/**
 * Format a Date object to a time string in HH:MM format
 * @param {Date} date - The Date object to format
 * @returns {string} - Formatted time string
 */
function formatTime(date) {
    return ('0' + date.getHours()).slice(-2) + ':' + 
           ('0' + date.getMinutes()).slice(-2);
}

/**
 * Update a date/time field pair using the calculated time
 * @param {string} dateInputId - The ID of the date input field
 * @param {string} timeInputId - The ID of the time input field
 * @param {Date} calculatedDateTime - The calculated Date object
 * @returns {boolean} - Whether the update was successful
 */
function updateDateTimeFields(dateInputId, timeInputId, calculatedDateTime) {
    const dateInput = document.getElementById(dateInputId);
    const timeInput = document.getElementById(timeInputId);
    
    if (!dateInput || !timeInput || !calculatedDateTime) {
        console.error('Missing required elements or calculated time');
        return false;
    }
    
    // Format and set the values
    dateInput.value = formatDate(calculatedDateTime);
    timeInput.value = formatTime(calculatedDateTime);
    
    // Trigger change events
    dateInput.dispatchEvent(new Event('change', { bubbles: true }));
    timeInput.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Try to update Django admin widgets if available
    if (typeof DateTimeShortcuts !== 'undefined') {
        try {
            DateTimeShortcuts.handleCalendarQuickLink(dateInput.id, dateInput.value);
            DateTimeShortcuts.handleClockQuicklink(timeInput.id, timeInput.value);
        } catch (e) {
            console.log('DateTimeShortcuts update attempted but not critical if it fails:', e);
        }
    }
    
    return true;
}

/**
 * Set the ends at time by adding hours to the starts at time
 * @param {number} hours - Number of hours to add to the start time
 * @param {string} startsAtFieldId - ID of the starts_at field
 * @param {string} endsAtFieldId - ID of the ends_at field
 */
function setEndsAtTime(hours, startsAtFieldId, endsAtFieldId) {
    // For MultiWidget, the inputs are indexed by 0 and 1
    const startsAtDateInput = document.getElementById(startsAtFieldId + '_0'); // Date input
    const startsAtTimeInput = document.getElementById(startsAtFieldId + '_1'); // Time input
    const endsAtDateInput = document.getElementById(endsAtFieldId + '_0');     // Date input
    const endsAtTimeInput = document.getElementById(endsAtFieldId + '_1');     // Time input

    if (!startsAtDateInput || !startsAtTimeInput || !endsAtDateInput || !endsAtTimeInput) {
        console.error('Could not find all required date/time input fields.');
        return;
    }

    const startsAtDateStr = startsAtDateInput.value;
    const startsAtTimeStr = startsAtTimeInput.value;

    if (!startsAtDateStr || !startsAtTimeStr) {
        alert('Please set the "Starts At" date and time first.');
        return;
    }

    // Parse the date and time into a JavaScript Date object
    const startsAtDateTime = parseDateTime(startsAtDateStr, startsAtTimeStr);
    if (!startsAtDateTime) {
        alert('Could not parse the "Starts At" date and time. Please ensure it is in a valid format (YYYY-MM-DD HH:MM).');
        return;
    }

    // Calculate the end date/time by adding the specified number of hours
    const endsAtDateTime = add_duration(startsAtDateTime, hours);
    if (!endsAtDateTime) {
        alert('Could not calculate the "Ends At" date and time.');
        return;
    }

    // Update the ends_at form fields
    updateDateTimeFields(endsAtDateInput.id, endsAtTimeInput.id, endsAtDateTime);
}

/**
 * Set the registration closes time using various methods
 * @param {string} option - The option to use (hours_before, day_of, day_before)
 * @param {string} value - The value for the option (hours or time)
 * @param {string} startsAtFieldId - ID of the starts_at field
 * @param {string} registrationClosesFieldId - ID of the registration_closes_at field
 */
function setRegistrationClosesTime(option, value, startsAtFieldId, registrationClosesFieldId) {
    // For MultiWidget, the inputs are indexed by 0 and 1
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
    const startsAtDateTime = parseDateTime(startsAtDateStr, startsAtTimeStr);
    if (!startsAtDateTime) {
        alert('Could not parse the "Starts At" date and time. Please ensure it is in a valid format (YYYY-MM-DD HH:MM).');
        return;
    }

    // Calculate registration closes time based on the selected option
    let registrationClosesDateTime;

    if (option === 'hours_before') {
        // Hours before event starts
        const hours = parseFloat(value);
        if (isNaN(hours)) {
            console.error('Invalid hours value:', value);
            return;
        }
        registrationClosesDateTime = subtract_duration(startsAtDateTime, hours);
    } else if (option === 'day_of' || option === 'day_before') {
        // Specific time on day of or day before
        registrationClosesDateTime = set_specific_time(startsAtDateTime, option, value);
    } else {
        console.error('Invalid option:', option);
        return;
    }

    if (!registrationClosesDateTime) {
        alert('Could not calculate the registration closing time.');
        return;
    }

    // Update the registration closes form fields
    updateDateTimeFields(registrationClosesDateInput.id, registrationClosesTimeInput.id, registrationClosesDateTime);
} 