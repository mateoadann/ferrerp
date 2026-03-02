# Protección de Ramas

## Flujo de Trabajo

```
feature/000-slug --> dev --> main
```

### Ramas

| Rama | Descripción | Push directo |
|------|-------------|--------------|
| `main` | Producción | Bloqueado |
| `dev` | Integración | Bloqueado |
| `feature/*` | Trabajo | Permitido |

## Hooks Locales

### Instalación

```bash
make install-hooks
```

Esto configura `git config core.hooksPath .githooks` y asegura que el hook sea ejecutable.

### Funcionamiento

El hook `pre-push` (`./githooks/pre-push`):

1. **Bloquea pushes directos** a `main` y `dev`
2. **Ejecuta tests** (`make test-dev-run`) antes de cualquier push a ramas no protegidas

Si intentas hacer push directo a `main` o `dev`:

```
ERROR: Push directo a 'main' no permitido.
Los cambios a main/dev deben hacerse via PR.
```

## GitHub Actions

El workflow `tests.yml` corre en:

- `push` a ramas `feature/**`
- `pull_request` hacia `dev` y `main`

El job se llama `pytest` y es requerido para poder mergear a `main` o `dev`.

## GitHub Rulesets

### Reglas Activas

| Ruleset | Rama | Requisitos |
|---------|------|------------|
| protect-main | main | PR + pytest |
| protect-dev | dev | PR + pytest |

### Detalles

- **required_approving_review_count**: 0 (solo maintainer)
- **required_status_checks**: pytest
- **Bloqueos**: force-push, deletion
- **Merge methods**: merge, squash, rebase

### Ver Rulesets

```bash
gh api repos/mateoadann/ferrerp/rulesets
```

### Re-crear Rulesets

```bash
# protect-main
gh api -X POST repos/mateoadann/ferrerp/rulesets \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  --input - <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "pull_request", "parameters": { "required_approving_review_count": 0, "allowed_merge_methods": ["merge", "squash", "rebase"], "dismiss_stale_reviews_on_push": true, "required_review_thread_resolution": true } },
    { "type": "required_status_checks", "parameters": { "strict_required_status_checks_policy": true, "required_status_checks": [{ "context": "pytest" }] } },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
JSON

# protect-dev
gh api -X POST repos/mateoadann/ferrerp/rulesets \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  --input - <<'JSON'
{
  "name": "protect-dev",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/dev"], "exclude": [] } },
  "rules": [
    { "type": "pull_request", "parameters": { "required_approving_review_count": 0, "allowed_merge_methods": ["merge", "squash", "rebase"], "dismiss_stale_reviews_on_push": true, "required_review_thread_resolution": true } },
    { "type": "required_status_checks", "parameters": { "strict_required_status_checks_policy": true, "required_status_checks": [{ "context": "pytest" }] } },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
JSON
```
