# Versioning Policy v1.0

> **Status**: ACTIVE
> **Applies to**: Matrix v1.x

## Semantic Versioning

Matrix, [SemVer](https://semver.org/) kullanır:

```
MAJOR.MINOR.PATCH
  │     │     └── Bugfix (geri uyumlu)
  │     └────── Yeni özellik (geri uyumlu)
  └─────────── Breaking change (v1.x içinde YASAK)
```

## Version Rules

### PATCH (x.y.Z)
- Bugfix
- Performance iyileştirme
- Dokümantasyon düzeltme
- **Kontrat değişikliği: YOK**

### MINOR (x.Y.0)
- Yeni optional alan ekleme
- Yeni event kind ekleme
- Yeni UI kategori ekleme
- **Kontrat değişikliği: Sadece ekleme (geri uyumlu)**

### MAJOR (X.0.0)
- Breaking change
- **v1.x içinde YASAK**
- v2.0.0 için planlanır

## Release Tags

```
matrix_v1.0.0-rc1    # Release candidate
matrix_v1.0.0        # Final release
matrix_v1.0.1        # Patch
matrix_v1.1.0        # Minor
```

## Freeze Gate

v1.0.0 sonrası:
- Kontrat değişikliği PR'ı otomatik fail
- Conformance suite zorunlu pass
- Breaking change = PR reject

## Contract Compatibility Matrix

| Contract | v1.0 | v1.1 |
|----------|------|------|
| CandidateBundle | ✓ | ✓ |
| Telemetry | ✓ | ✓ |
| Interfaces | ✓ | ✓ |

## Cloud Blocker

Cloud development, Matrix v1.0.0 FINAL olmadan BAŞLAMAZ.

```python
# Cloud runner check (stub)
if MATRIX_VERSION < "1.0.0":
    raise RuntimeError("Cloud requires Matrix v1.0.0+")
```

---

*Effective: 2025-12-21*
