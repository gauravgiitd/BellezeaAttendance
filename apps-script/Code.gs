const CONFIG = {
  // Paste these IDs when Resident Master and Attendance are separate Google Sheet files.
  // If both tabs are in the same bound spreadsheet, leave both blank.
  RESIDENT_SPREADSHEET_ID: '1AqK5Vnpi63Hk8K3AYAhZ5fjtMF-V_LR7u7wzDeE1Ms0',
  ATTENDANCE_SPREADSHEET_ID: '1uNJJP8yEgCgW0q2OnWt9LbmRJJ2yTTJQevfviJquXC0',
  RESIDENT_SHEET_NAME: 'Sheet1',
  ATTENDANCE_SHEET_NAME: 'Attendance',
  VOTING_GROUP_SHEET_NAME: 'Voting Group',
  TIMEZONE: 'Asia/Kolkata',
  DUPLICATE_SCOPE: 'PASSCODE_PER_DAY',
};

const RESIDENT_COLUMNS = [
  'Passcode',
  'Name',
  'Flat',
  'Mobile No',
  'Email',
  'User Type',
  'Status',
  'User Id (Do Not Edit)',
  'House Id (Do Not Edit)',
];

const ATTENDANCE_COLUMNS = [
  'Timestamp',
  'Attendance Date',
  'Source',
  'QR Raw Data',
  'Passcode',
  'Name',
  'Flat',
  'Mobile No',
  'Email',
  'User Type',
  'Status',
  'User Id (Do Not Edit)',
  'House Id (Do Not Edit)',
];

const VOTING_GROUP_COLUMNS = [
  'House No',
  'Resident Type',
  'Resident Name',
  'User Id (Do Not Edit)',
  'House Id (Do Not Edit)',
];

function doGet(event) {
  const params = event && event.parameter ? event.parameter : {};

  try {
    if (params.action === 'markAttendance') {
      return jsonp_(
        markAttendance({
          qrRawData: params.qrRawData || '',
          source: params.source || 'online',
        }),
        params.callback
      );
    }

    if (params.action === 'listSheets') {
      return jsonp_(listSheets_(), params.callback);
    }

    if (params.action === 'dashboard') {
      return jsonp_(dashboard_(), params.callback);
    }

    return jsonp_({
      ok: true,
      message: 'Attendance backend is running.',
    }, params.callback);
  } catch (error) {
    return jsonp_({
      ok: false,
      message: error && error.message ? error.message : 'Unexpected backend error.',
    }, params.callback);
  }
}

function markAttendance(payload) {
  const qrRawData = String(payload && payload.qrRawData ? payload.qrRawData : '').trim();
  const source = String(payload && payload.source ? payload.source : 'online').trim();
  const passcode = extractPasscode_(qrRawData);

  if (!passcode) {
    return failure_('I could not find a valid passcode in that QR code.');
  }

  const residentSpreadsheet = getResidentSpreadsheet_();
  const attendanceSpreadsheet = getAttendanceSpreadsheet_();
  const residentSheet = getSheet_(residentSpreadsheet, CONFIG.RESIDENT_SHEET_NAME);
  const attendanceSheet = getSheet_(attendanceSpreadsheet, CONFIG.ATTENDANCE_SHEET_NAME);
  const votingGroupSheet = getSheet_(attendanceSpreadsheet, CONFIG.VOTING_GROUP_SHEET_NAME);
  const residentRows = readObjects_(residentSheet);

  const resident = findResidentByPasscodeFromRows_(residentRows, passcode);
  if (!resident) {
    return failure_('No resident matched this passcode. Please check that the MyGate QR is current.');
  }
  if (!isOwnerUserType_(resident['User Type'])) {
    return failure_(`${resident.Name} is listed as ${resident['User Type'] || 'non-owner'} and is not allowed to mark attendance.`);
  }

  const now = new Date();
  const attendanceDate = Utilities.formatDate(now, CONFIG.TIMEZONE, 'yyyy-MM-dd');
  ensureHeaders_(attendanceSheet, ATTENDANCE_COLUMNS);

  const existing = findExistingAttendance_(attendanceSheet, passcode, attendanceDate);
  if (existing) {
    return success_({
      duplicate: true,
      message: `Attendance was already marked today for ${resident.Name}.`,
      resident,
      passcode,
      attendanceDate,
    });
  }

  appendAttendance_(attendanceSheet, {
    Timestamp: now,
    'Attendance Date': attendanceDate,
    Source: source,
    'QR Raw Data': qrRawData,
    Passcode: passcode,
    Name: resident.Name || '',
    Flat: resident.Flat || '',
    'Mobile No': resident['Mobile No'] || '',
    Email: resident.Email || '',
    'User Type': resident['User Type'] || '',
    Status: resident.Status || '',
    'User Id (Do Not Edit)': resident['User Id (Do Not Edit)'] || '',
    'House Id (Do Not Edit)': resident['House Id (Do Not Edit)'] || '',
  });
  const votingGroupRowsAdded = appendVotingGroupOwners_(residentRows, votingGroupSheet, resident);

  return success_({
    duplicate: false,
    message: `Attendance marked for ${resident.Name}.`,
    resident,
    passcode,
    attendanceDate,
    votingGroupRowsAdded,
  });
}

function extractPasscode_(qrRawData) {
  const firstToken = String(qrRawData || '').trim().split(/\s+/)[0] || '';
  const digits = firstToken.match(/\d+/);
  return digits ? String(Number(digits[0])) : '';
}

function findResidentByPasscode_(sheet, passcode) {
  return findResidentByPasscodeFromRows_(readObjects_(sheet), passcode);
}

function findResidentByPasscodeFromRows_(rows, passcode) {
  const normalizedPasscode = normalizePasscode_(passcode);

  for (const row of rows) {
    if (normalizePasscode_(row.Passcode) === normalizedPasscode) {
      return pickColumns_(row, RESIDENT_COLUMNS);
    }
  }

  return null;
}

function findExistingAttendance_(sheet, passcode, attendanceDate) {
  const rows = readObjects_(sheet);
  const normalizedPasscode = normalizePasscode_(passcode);

  return rows.find((row) => {
    const samePasscode = normalizePasscode_(row.Passcode) === normalizedPasscode;
    const rowDate = normalizeDate_(row['Attendance Date'] || row.Timestamp);
    return samePasscode && rowDate === attendanceDate;
  });
}

function appendAttendance_(sheet, valuesByHeader) {
  const headers = getHeaders_(sheet);
  const row = headers.map((header) => {
    if (Object.prototype.hasOwnProperty.call(valuesByHeader, header)) {
      return valuesByHeader[header];
    }
    return '';
  });
  sheet.appendRow(row);
}

function appendVotingGroupOwners_(residentRows, votingGroupSheet, attendanceResident) {
  const houseId = normalizeHouseId_(attendanceResident['House Id (Do Not Edit)']);
  if (!houseId) return 0;

  ensureHeaders_(votingGroupSheet, VOTING_GROUP_COLUMNS);

  const existingKeys = new Set(
    readObjects_(votingGroupSheet)
      .map((row) => votingGroupKey_(row['House Id (Do Not Edit)'], row['User Id (Do Not Edit)']))
      .filter(Boolean)
  );

  const ownerRows = residentRows
    .filter((row) => normalizeHouseId_(row['House Id (Do Not Edit)']) === houseId)
    .filter((row) => String(row['User Type'] || '').toLowerCase().includes('owner'))
    .filter((row) => normalizeId_(row['User Id (Do Not Edit)']));

  const rowsToAppend = [];
  ownerRows.forEach((ownerRow) => {
    const key = votingGroupKey_(ownerRow['House Id (Do Not Edit)'], ownerRow['User Id (Do Not Edit)']);
    if (!key || existingKeys.has(key)) return;
    existingKeys.add(key);
    rowsToAppend.push({
      'House No': ownerRow.Flat || '',
      'Resident Type': ownerRow['User Type'] || '',
      'Resident Name': ownerRow.Name || '',
      'User Id (Do Not Edit)': ownerRow['User Id (Do Not Edit)'] || '',
      'House Id (Do Not Edit)': ownerRow['House Id (Do Not Edit)'] || '',
    });
  });

  if (!rowsToAppend.length) return 0;

  const headers = getHeaders_(votingGroupSheet);
  const values = rowsToAppend.map((row) => headers.map((header) => row[header] || ''));
  votingGroupSheet
    .getRange(votingGroupSheet.getLastRow() + 1, 1, values.length, headers.length)
    .setValues(values);
  return rowsToAppend.length;
}

function dashboard_() {
  const residentSpreadsheet = getResidentSpreadsheet_();
  const attendanceSpreadsheet = getAttendanceSpreadsheet_();
  const residentSheet = getSheet_(residentSpreadsheet, CONFIG.RESIDENT_SHEET_NAME);
  const attendanceSheet = getSheet_(attendanceSpreadsheet, CONFIG.ATTENDANCE_SHEET_NAME);
  const votingGroupSheet = getSheet_(attendanceSpreadsheet, CONFIG.VOTING_GROUP_SHEET_NAME);

  const residentRows = readObjects_(residentSheet);
  const attendanceRows = readObjects_(attendanceSheet);
  const votingGroupRows = readObjects_(votingGroupSheet);

  const totalVillaIds = new Set(
    residentRows
      .filter((row) => normalizeHouseId_(row['House Id (Do Not Edit)']))
      .filter((row) => String(row.Status || '').toLowerCase() !== 'inactive')
      .map((row) => normalizeHouseId_(row['House Id (Do Not Edit)']))
  );
  const representedVillaIds = new Set(
    votingGroupRows
      .map((row) => normalizeHouseId_(row['House Id (Do Not Edit)']))
      .filter(Boolean)
  );

  const attendees = attendanceRows
    .filter((row) => normalizeId_(row['User Id (Do Not Edit)']) || normalizePasscode_(row.Passcode))
    .map((row) => ({
      name: row.Name || '',
      flat: row.Flat || '',
      userType: row['User Type'] || '',
      houseId: row['House Id (Do Not Edit)'] || '',
      timestamp: normalizeTimestampForSort_(row.Timestamp),
      attendanceTime: formatAttendanceTimestamp_(row.Timestamp),
    }))
    .sort((a, b) => b.timestamp - a.timestamp)
    .map((row) => ({
      name: row.name,
      flat: row.flat,
      userType: row.userType,
      houseId: row.houseId,
      attendanceTime: row.attendanceTime,
    }));

  return success_({
    totalVillas: totalVillaIds.size,
    representedVillas: representedVillaIds.size,
    representationPct: totalVillaIds.size ? Math.round((representedVillaIds.size / totalVillaIds.size) * 1000) / 10 : 0,
    attendeeCount: attendees.length,
    attendees,
  });
}

function readObjects_(sheet) {
  const range = sheet.getDataRange();
  const values = range.getValues();
  if (values.length < 2) return [];

  const headers = values[0].map((value) => String(value).trim());
  return values.slice(1)
    .filter((row) => row.some((cell) => cell !== ''))
    .map((row) => {
      const object = {};
      headers.forEach((header, index) => {
        object[header] = row[index];
      });
      return object;
    });
}

function ensureHeaders_(sheet, requiredHeaders) {
  const existingHeaders = getHeaders_(sheet);

  if (existingHeaders.length === 0) {
    sheet.getRange(1, 1, 1, requiredHeaders.length).setValues([requiredHeaders]);
    sheet.setFrozenRows(1);
    return;
  }

  const missingHeaders = requiredHeaders.filter((header) => !existingHeaders.includes(header));
  if (missingHeaders.length === 0) return;

  sheet
    .getRange(1, existingHeaders.length + 1, 1, missingHeaders.length)
    .setValues([missingHeaders]);
}

function getHeaders_(sheet) {
  const lastColumn = sheet.getLastColumn();
  if (lastColumn === 0) return [];
  return sheet.getRange(1, 1, 1, lastColumn).getValues()[0]
    .map((value) => String(value).trim())
    .filter(Boolean);
}

function pickColumns_(row, columns) {
  return columns.reduce((result, column) => {
    result[column] = row[column] == null ? '' : row[column];
    return result;
  }, {});
}

function normalizePasscode_(value) {
  if (value == null || value === '') return '';
  const text = String(value).trim();
  const digits = text.match(/\d+/);
  return digits ? String(Number(digits[0])) : text;
}

function normalizeHouseId_(value) {
  return normalizeId_(value);
}

function normalizeId_(value) {
  if (value == null || value === '') return '';
  const text = String(value).trim();
  const digits = text.match(/\d+/);
  return digits ? String(Number(digits[0])) : text;
}

function isOwnerUserType_(value) {
  return String(value || '').toLowerCase().includes('owner');
}

function votingGroupKey_(houseId, userId) {
  const normalizedHouseId = normalizeHouseId_(houseId);
  const normalizedUserId = normalizeId_(userId);
  if (!normalizedHouseId || !normalizedUserId) return '';
  return `${normalizedHouseId}::${normalizedUserId}`;
}

function normalizeDate_(value) {
  if (!value) return '';
  if (Object.prototype.toString.call(value) === '[object Date]') {
    return Utilities.formatDate(value, CONFIG.TIMEZONE, 'yyyy-MM-dd');
  }
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return Utilities.formatDate(parsed, CONFIG.TIMEZONE, 'yyyy-MM-dd');
  }
  return String(value).trim().slice(0, 10);
}

function normalizeTimestampForSort_(value) {
  if (!value) return 0;
  if (Object.prototype.toString.call(value) === '[object Date]') return value.getTime();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function formatAttendanceTimestamp_(value) {
  if (!value) return '';
  const date = Object.prototype.toString.call(value) === '[object Date]' ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).trim();
  return Utilities.formatDate(date, CONFIG.TIMEZONE, 'dd-MMM-yyyy HH:mm');
}

function getResidentSpreadsheet_() {
  if (CONFIG.RESIDENT_SPREADSHEET_ID) {
    return SpreadsheetApp.openById(CONFIG.RESIDENT_SPREADSHEET_ID);
  }
  return SpreadsheetApp.getActiveSpreadsheet();
}

function getAttendanceSpreadsheet_() {
  if (CONFIG.ATTENDANCE_SPREADSHEET_ID) {
    return SpreadsheetApp.openById(CONFIG.ATTENDANCE_SPREADSHEET_ID);
  }
  return SpreadsheetApp.getActiveSpreadsheet();
}

function getSheet_(spreadsheet, sheetName) {
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    const availableSheets = spreadsheet.getSheets().map((candidate) => candidate.getName()).join(', ');
    throw new Error(`Missing sheet: ${sheetName}. Available tabs: ${availableSheets}`);
  }
  return sheet;
}

function listSheets_() {
  const residentSpreadsheet = getResidentSpreadsheet_();
  const attendanceSpreadsheet = getAttendanceSpreadsheet_();

  return success_({
    residentSpreadsheetName: residentSpreadsheet.getName(),
    residentTabs: residentSpreadsheet.getSheets().map((sheet) => sheet.getName()),
    attendanceSpreadsheetName: attendanceSpreadsheet.getName(),
    attendanceTabs: attendanceSpreadsheet.getSheets().map((sheet) => sheet.getName()),
  });
}

function success_(data) {
  return {
    ok: true,
    ...data,
  };
}

function failure_(message) {
  return {
    ok: false,
    message,
  };
}

function jsonp_(payload, callback) {
  const json = JSON.stringify(payload);

  if (!callback) {
    return ContentService
      .createTextOutput(json)
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (!/^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$/.test(callback)) {
    return ContentService
      .createTextOutput(JSON.stringify({
        ok: false,
        message: 'Invalid callback name.',
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  return ContentService
    .createTextOutput(`${callback}(${json});`)
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}
