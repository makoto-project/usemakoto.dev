/**
 * Verify a Makoto DBOM against the schema and optionally a source file.
 */

export const SCHEMA_URL = "https://usemakoto.dev/schema/v0.1.json";

/** Bundled schema for offline fallback */
const BUNDLED_SCHEMA = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://usemakoto.dev/schema/v0.1.json",
  title: "Makoto DBOM Schema",
  type: "object",
  required: ["schema_version", "id", "created_at", "source", "signature", "lineage"],
  properties: {
    schema_version: { type: "string", const: "0.1" },
    id: { type: "string", pattern: "^dbom-" },
    created_at: { type: "string", format: "date-time" },
    source: {
      type: "object",
      required: ["uri", "hash", "format"],
      properties: {
        uri: { type: "string" },
        hash: {
          type: "object",
          required: ["algorithm", "value"],
          properties: {
            algorithm: { type: "string", enum: ["sha256"] },
            value: { type: "string", pattern: "^[a-f0-9]{64}$" },
          },
        },
        format: { type: "string" },
      },
    },
    signature: {
      type: "object",
      required: ["algorithm", "value", "signer"],
      properties: {
        algorithm: { type: "string", enum: ["sha256"] },
        value: { type: "string", pattern: "^[a-f0-9]{64}$" },
        signer: { type: "string" },
      },
    },
    lineage: {
      type: "array",
      minItems: 1,
      items: {
        type: "object",
        required: ["step", "description", "tool", "input_hash", "output_hash"],
        properties: {
          step: { type: "integer", minimum: 1 },
          description: { type: "string" },
          tool: { type: "string" },
          input_hash: { type: "string" },
          output_hash: { type: "string" },
        },
      },
    },
  },
};

async function loadSchema() {
  try {
    const res = await fetch(SCHEMA_URL);
    if (res.ok) return await res.json();
  } catch (_) {
    // fall through to bundled
  }
  return BUNDLED_SCHEMA;
}

async function sha256Hex(buffer) {
  // Normalize to a proper ArrayBuffer slice (handles Node.js pooled Buffers)
  function toArrayBuffer(buf) {
    if (Buffer.isBuffer(buf)) {
      return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    }
    if (buf instanceof Uint8Array) {
      return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    }
    return buf; // already ArrayBuffer
  }

  if (typeof globalThis.crypto?.subtle !== "undefined") {
    const hashBuf = await globalThis.crypto.subtle.digest("SHA-256", toArrayBuffer(buffer));
    return Array.from(new Uint8Array(hashBuf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } else {
    const { createHash } = await import("crypto");
    const hash = createHash("sha256");
    hash.update(Buffer.isBuffer(buffer) ? buffer : Buffer.from(new Uint8Array(toArrayBuffer(buffer))));
    return hash.digest("hex");
  }
}

/**
 * Verify a DBOM.
 *
 * @param {object} dbom - The DBOM object to verify
 * @param {ArrayBuffer|Buffer} [fileBuffer] - Optional file bytes to verify hash
 * @returns {Promise<{valid: boolean, errors: string[]}>}
 */
export async function verify(dbom, fileBuffer) {
  const errors = [];

  // Schema validation via Ajv (draft 2020-12)
  try {
    // Try Ajv 2020 first (supports JSON Schema 2020-12)
    let AjvClass;
    try {
      const mod = await import("ajv/dist/2020.js");
      AjvClass = mod.default;
    } catch (_) {
      const mod = await import("ajv");
      AjvClass = mod.default;
    }
    const { default: addFormats } = await import("ajv-formats");

    const schema = await loadSchema();
    // Strip $schema declaration so Ajv doesn't try to resolve it as a meta-schema
    const schemaForValidation = { ...schema };
    delete schemaForValidation.$schema;

    const ajv = new AjvClass({ allErrors: true });
    addFormats(ajv);

    const validate = ajv.compile(schemaForValidation);
    const valid = validate(dbom);
    if (!valid && validate.errors) {
      for (const err of validate.errors) {
        const path = err.instancePath || "/";
        errors.push(`Schema error at ${path}: ${err.message}`);
      }
    }
  } catch (e) {
    errors.push(`Schema validation failed: ${e.message}`);
  }

  // File hash verification
  if (fileBuffer !== undefined) {
    try {
      const actualHash = await sha256Hex(fileBuffer);
      const expectedHash = dbom?.source?.hash?.value ?? "";
      if (actualHash !== expectedHash) {
        errors.push(
          `File hash mismatch: expected ${expectedHash}, got ${actualHash}`
        );
      }
    } catch (e) {
      errors.push(`Failed to hash file buffer: ${e.message}`);
    }
  }

  return { valid: errors.length === 0, errors };
}
