function setAllDayTimes(startsAtId, endsAtId, checked) {
    const startTime = document.getElementById(startsAtId + '_1');
    const endTime = document.getElementById(endsAtId + '_1');
    if (!startTime || !endTime) {
        return;
    }
    if (checked) {
        startTime.value = '00:00';
        endTime.value = '23:59';
        startTime.dispatchEvent(new Event('change', { bubbles: true }));
        endTime.dispatchEvent(new Event('change', { bubbles: true }));
        startTime.disabled = true;
        endTime.disabled = true;
    } else {
        startTime.disabled = false;
        endTime.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const cb = document.getElementById('id_all_day');
    if (cb && cb.checked) {
        setAllDayTimes('id_starts_at', 'id_ends_at', true);
    }
});
