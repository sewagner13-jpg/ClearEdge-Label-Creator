# Code Review Report - Critical Issues Found

## 🔴 CRITICAL SECURITY VULNERABILITIES

### 1. Path Traversal Vulnerability (simple_app.py:545-547)
**Severity:** CRITICAL
**Location:** `/api/download-label/{label_id}` endpoint

```python
@app.get("/api/download-label/{label_id}")
async def download_label(label_id: str):
    label_path = LABELS_DIR / f"{label_id}.pdf"  # ❌ NOT SANITIZED
```

**Problem:** User-controlled `label_id` is not sanitized. An attacker could request:
- `/api/download-label/../../etc/passwd`
- `/api/download-label/../../../root/.env`

**Impact:** Arbitrary file read vulnerability

---

### 2. Unsafe Filename Generation (simple_app.py:526)
**Severity:** HIGH
**Location:** Label ID generation

```python
label_id = f"label_{extracted_data.product.name.replace(' ', '_')}"  # ❌ UNSAFE
```

**Problem:** Product name could contain special characters like `/`, `..`, `\0`, etc.

**Example Attack:**
- Product name: `../../malicious`
- Resulting path: `/tmp/clearedge_labels/label_../../malicious.pdf`

**Impact:** Path traversal, file overwrite

---

### 3. Filename Collision (simple_app.py:502-503)
**Severity:** MEDIUM
**Location:** Temp file creation

```python
temp_path = LABELS_DIR / file.filename  # ❌ NOT SANITIZED
temp_path.write_bytes(content)
```

**Problems:**
1. `file.filename` not sanitized (could contain `../`, `/`, etc.)
2. Race condition if two users upload same filename simultaneously
3. No unique identifier per upload session

---

## 🟡 CODE QUALITY ISSUES

### 4. Import at Bottom of File (pdf_extract.py:137-138)
**Severity:** LOW (style issue, but works)

```python
# Line 137-138 (bottom of file)
import io  # ⚠️ Works but violates PEP 8
```

**Note:** Python executes all module-level code before functions run, so this works. However, PEP 8 recommends imports at the top for readability.

**Recommendation:** Move to top with other imports

---

### 5. No Input Validation for Mode (simple_app.py:487)
**Severity:** LOW

```python
mode: str = Form("shipped_dot")  # ❌ Any string accepted
```

**Problem:** No validation that mode is one of `["shipped_dot", "workplace"]`

**Impact:** Invalid mode passed to label generator could cause errors

---

### 6. Overly Broad Exception Handling (simple_app.py:540-541)
**Severity:** MEDIUM (information disclosure)

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))  # ❌ Leaks internals
```

**Problem:** Full exception message returned to user, could leak:
- API keys in error messages
- Internal file paths
- Stack traces with sensitive data

---

## 📊 Summary

| Severity | Count | Issues |
|----------|-------|--------|
| 🔴 CRITICAL | 1 | Path traversal vulnerability |
| 🟠 HIGH | 2 | Unsafe filename generation, file collision |
| 🟡 MEDIUM | 1 | Information disclosure via exceptions |
| 🟢 LOW | 2 | No mode validation, import style |

---

## ✅ RECOMMENDED FIXES

### Fix #1: Sanitize label_id (simple_app.py)
```python
from pathlib import Path
import re

@app.get("/api/download-label/{label_id}")
async def download_label(label_id: str):
    # Sanitize: only allow alphanumeric, underscore, dash
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', label_id)
    if not safe_id or safe_id != label_id:
        raise HTTPException(status_code=400, detail="Invalid label ID")

    label_path = LABELS_DIR / f"{safe_id}.pdf"

    # Verify path is within LABELS_DIR (prevent traversal)
    if not label_path.resolve().is_relative_to(LABELS_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")

    if not label_path.exists():
        raise HTTPException(status_code=404, detail="Label not found")

    return FileResponse(label_path, media_type="application/pdf", filename=f"{safe_id}.pdf")
```

### Fix #2: Sanitize product name for filename
```python
import re
import uuid

# Generate label
svg_content = label_generator.generate_svg(extracted_data, mode)
pdf_content = label_generator.generate_pdf(svg_content)

# Safe filename: sanitize + unique ID
safe_product_name = re.sub(r'[^a-zA-Z0-9_-]', '', extracted_data.product.name[:50])
unique_id = uuid.uuid4().hex[:8]
label_id = f"label_{safe_product_name}_{unique_id}"
label_path = LABELS_DIR / f"{label_id}.pdf"
```

### Fix #3: Move import to top (pdf_extract.py) - Optional style fix
```python
# Line 5-9
"""PDF text extraction with automatic OCR fallback."""

import io  # ← MOVE FROM LINE 138
import logging
from typing import List, Tuple
import pdfplumber
from pypdf import PdfReader
```

Then remove lines 104 and 137-138 (redundant imports).

### Fix #4: Validate mode parameter
```python
from enum import Enum

class LabelMode(str, Enum):
    SHIPPED_DOT = "shipped_dot"
    WORKPLACE = "workplace"

@app.post("/api/generate-label")
async def generate_label(
    files: List[UploadFile] = File(...),
    mode: LabelMode = Form(LabelMode.SHIPPED_DOT)  # ✓ Validated
):
    # ...
    svg_content = label_generator.generate_svg(extracted_data, mode.value)
```

### Fix #5: Safer exception handling
```python
except HTTPException:
    raise  # Re-raise HTTP exceptions
except ValueError as e:
    raise HTTPException(status_code=400, detail="Invalid input data")
except Exception as e:
    logger.error(f"Label generation failed: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Label generation failed")
```

### Fix #6: Sanitize uploaded filenames
```python
import secrets

for file in files:
    if not file.filename.endswith('.pdf'):
        continue

    content = await file.read()

    # Use secure random filename
    temp_filename = f"{secrets.token_hex(8)}.pdf"
    temp_path = LABELS_DIR / temp_filename
    temp_path.write_bytes(content)
    temp_files.append(temp_path)

    # Extract text...
```

---

## 🎯 Priority Actions

1. **IMMEDIATE**: Fix path traversal vulnerability (Security - file read)
2. **HIGH**: Sanitize product name for filenames (Security - file write)
3. **HIGH**: Sanitize uploaded filenames (Security + stability)
4. **MEDIUM**: Improve error handling (Security - info disclosure)
5. **LOW**: Add mode validation (Data validation)
6. **OPTIONAL**: Move imports to top (Code style)

---

**Report Generated:** $(date)
**Files Reviewed:** app/main.py, app/openai_client.py, app/pdf_extract.py, app/label_stub.py
