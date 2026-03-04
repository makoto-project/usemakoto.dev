/**
 * Generate a Makoto DBOM (Data Bill of Materials) record.
 */

import { randomUUID } from "crypto";

/**
 * Hash a buffer using SHA-256. Works in both Node.js and browsers.
 * @param {ArrayBuffer|Buffer} buffer
 * @returns {Promise<string>} hex digest
 */
function toArrayBuffer(buf) {
  if (Buffer.isBuffer(buf)) {
    return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  }
  if (buf instanceof Uint8Array) {
    return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  }
  return buf; // already ArrayBuffer
}

async function sha256Hex(buffer) {
  if (typeof globalThis.crypto?.subtle !== "undefined") {
    // Browser / Node 19+
    const hashBuf = await globalThis.crypto.subtle.digest("SHA-256", toArrayBuffer(buffer));
    return Array.from(new Uint8Array(hashBuf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } else {
    // Node.js fallback
    const { createHash } = await import("crypto");
    const hash = createHash("sha256");
    hash.update(Buffer.isBuffer(buffer) ? buffer : Buffer.from(new Uint8Array(toArrayBuffer(buffer))));
    return hash.digest("hex");
  }
}

/**
 * Generate a UUID. Works in Node 14+ and browsers.
 */
function newUUID() {
  if (typeof randomUUID === "function") return randomUUID();
  // Browser fallback
  return globalThis.crypto.randomUUID();
}

/**
 * Generate a DBOM for a file or buffer.
 *
 * @param {object} options
 * @param {string}      [options.filePath]     - Node only: path to file on disk
 * @param {ArrayBuffer} [options.fileBuffer]   - Pre-loaded file bytes
 * @param {string}      options.fileName       - File name (used to infer format)
 * @param {string}      options.signer         - Signer identity e.g. "github:username"
 * @param {string}      [options.uri]          - Source URI (defaults to fileName)
 * @param {Array}       [options.lineageSteps] - Custom lineage steps
 * @param {string}      [options.format]       - Data format (inferred from fileName if omitted)
 * @returns {Promise<object>} DBOM object
 */
export async function generate(options) {
  const { filePath, fileBuffer, fileName, signer, uri, lineageSteps, format } =
    options;

  let buffer;

  if (fileBuffer) {
    buffer = fileBuffer;
  } else if (filePath) {
    const { readFile } = await import("fs/promises");
    buffer = await readFile(filePath);
  } else {
    throw new Error("Either filePath or fileBuffer must be provided");
  }

  const fileHash = await sha256Hex(buffer);

  // Infer format
  const fmt =
    format ?? (fileName ? fileName.split(".").pop() || "unknown" : "unknown");

  // Source URI
  const sourceUri = uri ?? (filePath ? `file://${filePath}` : fileName ?? "unknown");

  // Signature: sha256(fileHash + signer)
  const sigInput = new TextEncoder().encode(fileHash + signer);
  const sigHash = await sha256Hex(sigInput);

  // Lineage
  const lineage = lineageSteps ?? [
    {
      step: 1,
      description: "Direct ingestion",
      tool: "makoto-js/0.1.0",
      input_hash: "n/a",
      output_hash: fileHash,
    },
  ];

  return {
    schema_version: "0.1",
    id: "dbom-" + newUUID(),
    created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    source: {
      uri: sourceUri,
      hash: { algorithm: "sha256", value: fileHash },
      format: fmt,
    },
    signature: {
      algorithm: "sha256",
      value: sigHash,
      signer,
    },
    lineage,
  };
}
