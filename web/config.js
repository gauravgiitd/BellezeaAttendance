const localHostnames = new Set(['localhost', '127.0.0.1', '::1']);

window.AttendanceConfig = {
  apiUrl: localHostnames.has(window.location.hostname)
    ? 'http://127.0.0.1:8000'
    : 'https://bellezea-elections-api.onrender.com',
  legacyAttendanceApiUrl: 'https://script.google.com/macros/s/AKfycbzcpfc8wd23PwmJjTqN8CQ1YwUlK-ItVNfKDQtjloTR4YI0bwf12887KguSSGNWRVuZyw/exec',
};
