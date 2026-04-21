"""Cheques v2: banco registry, cliente FK, tipo_cheque, estados.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Crear tabla bancos
    op.create_table(
        'bancos',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column(
            'empresa_id',
            sa.Integer,
            sa.ForeignKey('empresas.id'),
            nullable=False,
        ),
        sa.Column(
            'activo', sa.Boolean, nullable=False, server_default='1'
        ),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.UniqueConstraint(
            'empresa_id', 'nombre', name='uq_bancos_empresa_nombre'
        ),
    )
    op.create_index('ix_bancos_empresa_id', 'bancos', ['empresa_id'])

    # 2. Migrar datos: insertar bancos distintos desde cheques existentes
    conn = op.get_bind()

    # Obtener valores distintos de banco por empresa
    filas = conn.execute(
        sa.text(
            'SELECT DISTINCT empresa_id, TRIM(banco) AS banco_norm '
            'FROM cheques WHERE banco IS NOT NULL AND TRIM(banco) != \'\''
        )
    ).fetchall()

    bancos_insertados = {}  # (empresa_id, nombre_normalizado) -> banco_id
    for fila in filas:
        empresa_id = fila[0]
        nombre_raw = fila[1]
        # Normalizar: title case
        nombre_norm = nombre_raw.strip().title()
        clave = (empresa_id, nombre_norm)
        if clave not in bancos_insertados:
            result = conn.execute(
                sa.text(
                    'INSERT INTO bancos (nombre, empresa_id, activo) '
                    'VALUES (:nombre, :empresa_id, :activo)'
                ),
                {
                    'nombre': nombre_norm,
                    'empresa_id': empresa_id,
                    'activo': True,
                },
            )
            bancos_insertados[clave] = result.lastrowid or conn.execute(
                sa.text(
                    'SELECT id FROM bancos '
                    'WHERE empresa_id = :eid AND nombre = :nom'
                ),
                {'eid': empresa_id, 'nom': nombre_norm},
            ).scalar()

    # Crear banco "Sin banco" para cheques con banco NULL o vacío
    empresas_con_null = conn.execute(
        sa.text(
            'SELECT DISTINCT empresa_id FROM cheques '
            'WHERE banco IS NULL OR TRIM(banco) = \'\''
        )
    ).fetchall()
    for (empresa_id,) in empresas_con_null:
        clave = (empresa_id, 'Sin Banco')
        if clave not in bancos_insertados:
            result = conn.execute(
                sa.text(
                    'INSERT INTO bancos (nombre, empresa_id, activo) '
                    'VALUES (:nombre, :empresa_id, TRUE)'
                ),
                {'nombre': 'Sin Banco', 'empresa_id': empresa_id},
            )
            bancos_insertados[clave] = result.lastrowid or conn.execute(
                sa.text(
                    'SELECT id FROM bancos '
                    'WHERE empresa_id = :eid AND nombre = :nom'
                ),
                {'eid': empresa_id, 'nom': 'Sin Banco'},
            ).scalar()

    # 3. Agregar nuevas columnas a cheques
    with op.batch_alter_table('cheques') as batch_op:
        batch_op.add_column(
            sa.Column('banco_id', sa.Integer, nullable=True)
        )
        batch_op.add_column(
            sa.Column('cliente_id', sa.Integer, nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                'tipo_cheque',
                sa.String(20),
                nullable=False,
                server_default='cheque',
            )
        )

    # 4. Actualizar banco_id basado en el texto banco normalizado
    for (empresa_id, nombre_norm), banco_id in bancos_insertados.items():
        if nombre_norm == 'Sin Banco':
            conn.execute(
                sa.text(
                    'UPDATE cheques SET banco_id = :bid '
                    'WHERE empresa_id = :eid '
                    'AND (banco IS NULL OR TRIM(banco) = \'\')'
                ),
                {'bid': banco_id, 'eid': empresa_id},
            )
        else:
            # Buscar cheques cuyo banco normalizado coincida
            # (comparación case-insensitive via UPPER)
            conn.execute(
                sa.text(
                    'UPDATE cheques SET banco_id = :bid '
                    'WHERE empresa_id = :eid '
                    'AND UPPER(TRIM(banco)) = UPPER(:nom)'
                ),
                {'bid': banco_id, 'eid': empresa_id, 'nom': nombre_norm},
            )

    # 5. Convertir estados: pendiente->en_cartera, debitado->cobrado,
    #    anulado->en_cartera
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'en_cartera' "
            "WHERE estado = 'pendiente'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'cobrado' "
            "WHERE estado = 'debitado'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'en_cartera' "
            "WHERE estado = 'anulado'"
        )
    )

    # 6. Eliminar columna banco texto y agregar FKs/índices
    with op.batch_alter_table('cheques') as batch_op:
        batch_op.drop_column('banco')
        batch_op.create_foreign_key(
            'fk_cheques_banco_id', 'bancos', ['banco_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_cheques_cliente_id', 'clientes', ['cliente_id'], ['id']
        )

    op.create_index('ix_cheques_banco_id', 'cheques', ['banco_id'])
    op.create_index('ix_cheques_cliente_id', 'cheques', ['cliente_id'])
    op.create_index('ix_cheques_tipo_cheque', 'cheques', ['tipo_cheque'])


def downgrade():
    # Eliminar índices
    op.drop_index('ix_cheques_tipo_cheque', 'cheques')
    op.drop_index('ix_cheques_cliente_id', 'cheques')
    op.drop_index('ix_cheques_banco_id', 'cheques')

    # Recrear columna banco texto
    with op.batch_alter_table('cheques') as batch_op:
        batch_op.drop_constraint('fk_cheques_cliente_id', type_='foreignkey')
        batch_op.drop_constraint('fk_cheques_banco_id', type_='foreignkey')
        batch_op.add_column(
            sa.Column('banco', sa.String(100), nullable=True)
        )

    # Restaurar banco texto desde bancos tabla
    conn = op.get_bind()
    conn.execute(
        sa.text(
            'UPDATE cheques SET banco = ('
            '  SELECT bancos.nombre FROM bancos '
            '  WHERE bancos.id = cheques.banco_id'
            ')'
        )
    )

    # Revertir estados: en_cartera->pendiente, cobrado que era debitado
    # (no podemos distinguir, todos cobrado quedan como cobrado)
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'pendiente' "
            "WHERE estado = 'en_cartera'"
        )
    )
    # endosado y sin_fondos no existían antes, revertir a pendiente
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'pendiente' "
            "WHERE estado IN ('endosado', 'sin_fondos')"
        )
    )

    # Eliminar nuevas columnas
    with op.batch_alter_table('cheques') as batch_op:
        batch_op.drop_column('tipo_cheque')
        batch_op.drop_column('cliente_id')
        batch_op.drop_column('banco_id')

    # Hacer banco NOT NULL
    with op.batch_alter_table('cheques') as batch_op:
        batch_op.alter_column(
            'banco',
            existing_type=sa.String(100),
            nullable=False,
            existing_server_default=None,
        )

    # Eliminar tabla bancos
    op.drop_index('ix_bancos_empresa_id', 'bancos')
    op.drop_table('bancos')
