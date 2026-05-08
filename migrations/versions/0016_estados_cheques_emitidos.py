"""Renombrar estados de cheques emitidos: en_cartera->emitido, cobrado->pagado.

Antes los cheques emitidos compartían los mismos estados que los recibidos
('en_cartera', 'cobrado'). Eso era confuso semánticamente: un cheque emitido
no está "en cartera" (eso aplica a recibidos) y la acción "cobrado" tampoco
encaja (lo que cobramos es un cheque recibido; un emitido lo "pagamos").

Esta migración renombra los valores de estado SOLO para tipo='emitido':
- 'en_cartera' -> 'emitido'
- 'cobrado'    -> 'pagado'

La validación de transiciones queda en `transicion_valida()` del modelo;
no se agrega CHECK constraint a la columna.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Renombrar estados solo para cheques emitidos
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'emitido' "
            "WHERE tipo = 'emitido' AND estado = 'en_cartera'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'pagado' "
            "WHERE tipo = 'emitido' AND estado = 'cobrado'"
        )
    )


def downgrade():
    conn = op.get_bind()

    # Revertir estados de cheques emitidos a la nomenclatura previa
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'en_cartera' "
            "WHERE tipo = 'emitido' AND estado = 'emitido'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE cheques SET estado = 'cobrado' "
            "WHERE tipo = 'emitido' AND estado = 'pagado'"
        )
    )
