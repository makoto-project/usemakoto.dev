# @makoto/sdk — JavaScript

Generate and verify [Makoto DBOM](https://usemakoto.dev) (Data Bill of Materials) files in JavaScript — works in Node.js and the browser.

## Install

```bash
npm install @makoto/sdk
```

## Quick Start — Node.js

```js
import { generate, verify } from "@makoto/sdk";

// Generate
const dbom = await generate({
  filePath: "data/sales.csv",
  fileName: "sales.csv",
  signer: "github:your-username",
  uri: "s3://my-bucket/sales.csv",
});

console.log(JSON.stringify(dbom, null, 2));

// Verify
const result = await verify(dbom);
console.log(result.valid ? "✓ Valid" : result.errors);
```

## Quick Start — Browser

```html
<script type="module">
  import { generate, verify } from "https://unpkg.com/@makoto/sdk";

  const file = document.querySelector('input[type="file"]').files[0];
  const buffer = await file.arrayBuffer();

  const dbom = await generate({
    fileBuffer: buffer,
    fileName: file.name,
    signer: "github:your-username",
  });

  const result = await verify(dbom, buffer);
  console.log(result.valid ? "✓ Valid" : result.errors);
</script>
```

## API

### `generate(options) → Promise<object>`

| Option | Type | Description |
|--------|------|-------------|
| `filePath` | string | Node only: path to file |
| `fileBuffer` | ArrayBuffer | Pre-loaded file bytes |
| `fileName` | string | File name (used for format inference) |
| `signer` | string | Signer identity (e.g. `github:username`) |
| `uri` | string | Source URI (optional) |
| `lineageSteps` | array | Custom lineage (optional) |
| `format` | string | Data format (optional, inferred) |

### `verify(dbom, fileBuffer?) → Promise<{valid, errors}>`

- `dbom` — DBOM object
- `fileBuffer` — optional `ArrayBuffer` to verify hash
- Returns `{ valid: boolean, errors: string[] }`

## Schema

DBOMs are validated against `https://usemakoto.dev/schema/v0.1.json`.
A bundled copy is included for offline use.

## Examples

See [`examples/`](examples/) for runnable scripts.
