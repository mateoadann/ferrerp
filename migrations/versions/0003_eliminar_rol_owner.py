"""Eliminar rol owner — migrar owners a administrador y reducir Enum.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-04
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Convertir todos los owners existentes a administrador
    op.execute("UPDATE usuarios SET rol = 'administrador' WHERE rol = 'owner'")

    # 2. Recrear el Enum sin 'owner' (PostgreSQL no soporta DROP VALUE)
    # En SQLite (tests) los Enum son strings, no necesitan migración de tipo.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Quitar DEFAULT antes de cambiar el tipo (PostgreSQL lo requiere)
        op.execute("ALTER TABLE usuarios ALTER COLUMN rol DROP DEFAULT")
        op.execute("ALTER TYPE rol_usuario RENAME TO rol_usuario_old")
        op.execute(
            "CREATE TYPE rol_usuario AS ENUM ('administrador', 'vendedor')"
        )
        op.execute(
            "ALTER TABLE usuarios ALTER COLUMN rol TYPE rol_usuario "
            "USING rol::text::rol_usuario"
        )
        op.execute(
            "ALTER TABLE usuarios ALTER COLUMN rol "
            "SET DEFAULT 'vendedor'::rol_usuario"
        )
        op.execute("DROP TYPE rol_usuario_old")


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE usuarios ALTER COLUMN rol DROP DEFAULT")
        op.execute("ALTER TYPE rol_usuario RENAME TO rol_usuario_old")
        op.execute(
            "CREATE TYPE rol_usuario AS ENUM "
            "('owner', 'administrador', 'vendedor')"
        )
        op.execute(
            "ALTER TABLE usuarios ALTER COLUMN rol TYPE rol_usuario "
            "USING rol::text::rol_usuario"
        )
        op.execute(
            "ALTER TABLE usuarios ALTER COLUMN rol "
            "SET DEFAULT 'vendedor'::rol_usuario"
        )
        op.execute("DROP TYPE rol_usuario_old")
