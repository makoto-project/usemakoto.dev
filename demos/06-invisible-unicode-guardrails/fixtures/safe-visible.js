// safe-visible.js — A simple data validation utility
// No invisible Unicode, no hidden content, no obfuscation.

function validateRecord(record) {
  if (!record || typeof record !== "object") {
    return { valid: false, reason: "Record must be a non-null object" };
  }

  const required = ["id", "timestamp", "value"];
  for (const field of required) {
    if (!(field in record)) {
      return { valid: false, reason: `Missing required field: ${field}` };
    }
  }

  if (typeof record.value !== "number" || Number.isNaN(record.value)) {
    return { valid: false, reason: "Field 'value' must be a finite number" };
  }

  return { valid: true, reason: null };
}

module.exports = { validateRecord };
