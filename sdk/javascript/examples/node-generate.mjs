/**
 * Node.js example: generate and verify a DBOM for a temp CSV file.
 */

import { writeFileSync, readFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { generate, verify } from "../src/index.js";

// Create a sample CSV
const csvContent = "id,name,value\n1,Alice,100\n2,Bob,200\n3,Carol,300\n";
const tmpFile = join(tmpdir(), `makoto-example-${Date.now()}.csv`);
writeFileSync(tmpFile, csvContent);
console.log(`Created sample file: ${tmpFile}\n`);

// Generate DBOM
const dbom = await generate({
  filePath: tmpFile,
  fileName: "example.csv",
  signer: "github:example-user",
  uri: "s3://my-data-bucket/example.csv",
  format: "csv",
});

console.log("Generated DBOM:");
console.log(JSON.stringify(dbom, null, 2));

// Save DBOM
const dbomPath = tmpFile + ".dbom.json";
writeFileSync(dbomPath, JSON.stringify(dbom, null, 2));
console.log(`\nSaved DBOM to: ${dbomPath}`);

// Verify
const _fileBuf = readFileSync(tmpFile);
const fileBuffer = _fileBuf.buffer.slice(_fileBuf.byteOffset, _fileBuf.byteOffset + _fileBuf.byteLength);
const result = await verify(dbom, fileBuffer);

if (result.valid) {
  console.log("\n✓ DBOM is valid — schema and file hash both pass");
} else {
  console.log("\n✗ Validation errors:");
  result.errors.forEach((e) => console.log(`  - ${e}`));
  process.exit(1);
}

// Simulate tampering
console.log("\nSimulating tampered file...");
const tampered = Buffer.from(csvContent + "4,Dave,999\n");
const result2 = await verify(dbom, tampered.buffer);
if (!result2.valid) {
  console.log("✓ Detected tampering:");
  result2.errors.forEach((e) => console.log(`  - ${e}`));
} else {
  console.log("✗ Tampering was not detected (unexpected)");
}
