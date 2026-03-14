# Tests de Integración con ARCA

Tests que se conectan al ambiente de **homologación** de ARCA (ex-AFIP).

## Requisitos

- Certificado de homologación (`.crt`) y clave privada (`.key`)
- CUIT de testing autorizado en ARCA
- Dependencias del proyecto instaladas (`pip install -r requirements.txt`)

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `ARCA_TEST_CUIT` | CUIT de testing | `20304050607` |
| `ARCA_TEST_CERT_PATH` | Ruta absoluta al certificado `.crt` | `/home/user/certs/homo.crt` |
| `ARCA_TEST_KEY_PATH` | Ruta absoluta a la clave privada `.key` | `/home/user/certs/homo.key` |
| `ARCA_TEST_PUNTO_VENTA` | Punto de venta (opcional, default: 1) | `1` |

## Ejecución

```bash
# Todos los tests de integración
pytest -m integracion_arca --arca-test -v

# Solo WSFE (facturación)
pytest tests/integracion/test_arca_wsfe.py --arca-test -v

# Solo Padrón
pytest tests/integracion/test_arca_padron.py --arca-test -v
```

## Comportamiento en CI/CD

Estos tests **NO se ejecutan por defecto**. Sin la flag `--arca-test`, todos los tests
marcados con `@pytest.mark.integracion_arca` se skipean automáticamente.

```bash
# Ejecución normal (tests de integración se skipean)
pytest

# Verificar que se descubren pero se skipean
pytest --co -m integracion_arca
```

## Nota

Estos tests se conectan al ambiente de **HOMOLOGACIÓN** de ARCA.
**NO ejecutar contra producción.**
