"""Migrar configuración ARCA de empresas a facturadores.

Para cada empresa que tenga cuit Y punto_venta_arca configurados,
crea un registro en facturadores copiando los datos fiscales y
credenciales ARCA.  Es idempotente: no crea duplicados si ya existe
un facturador con el mismo (empresa_id, cuit, punto_venta).

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

# Nombre que se pone como prefijo al nombre generado automáticamente
# para poder identificar facturadores creados por esta migración en downgrade.
_NOMBRE_PREFIX = '[Auto] '


def upgrade():
    """Crea facturadores a partir de la configuración ARCA de cada empresa."""
    conn = op.get_bind()

    # Obtener empresas con configuración ARCA (cuit y punto_venta_arca seteados)
    empresas = conn.execute(
        sa.text("""
            SELECT
                id,
                nombre,
                cuit,
                condicion_iva_id,
                condicion_iva,
                inicio_actividades,
                punto_venta_arca,
                certificado_arca,
                clave_privada_arca,
                ambiente_arca,
                arca_habilitado,
                email
            FROM empresas
            WHERE cuit IS NOT NULL
              AND cuit != ''
              AND punto_venta_arca IS NOT NULL
        """)
    ).fetchall()

    for emp in empresas:
        emp_id = emp[0]
        emp_nombre = emp[1]
        emp_cuit = emp[2]
        emp_condicion_iva_id = emp[3]
        emp_condicion_iva = emp[4]
        emp_inicio_actividades = emp[5]
        emp_punto_venta = emp[6]
        emp_certificado = emp[7]
        emp_clave_privada = emp[8]
        emp_ambiente = emp[9]
        emp_habilitado = emp[10]
        emp_email = emp[11]

        # Idempotencia: verificar que no exista ya un facturador
        # con la misma combinación (empresa_id, cuit, punto_venta).
        existe = conn.execute(
            sa.text("""
                SELECT 1 FROM facturadores
                WHERE empresa_id = :empresa_id
                  AND cuit = :cuit
                  AND punto_venta = :punto_venta
                LIMIT 1
            """),
            {
                'empresa_id': emp_id,
                'cuit': emp_cuit,
                'punto_venta': emp_punto_venta,
            },
        ).fetchone()

        if existe:
            continue

        # Generar nombre del facturador
        nombre_facturador = f'{_NOMBRE_PREFIX}{emp_nombre}'

        conn.execute(
            sa.text("""
                INSERT INTO facturadores (
                    empresa_id,
                    nombre,
                    razon_social,
                    cuit,
                    condicion_iva_id,
                    condicion_iva,
                    inicio_actividades,
                    punto_venta,
                    certificado,
                    clave_privada,
                    ambiente,
                    habilitado,
                    activo,
                    email_fiscal
                ) VALUES (
                    :empresa_id,
                    :nombre,
                    :razon_social,
                    :cuit,
                    :condicion_iva_id,
                    :condicion_iva,
                    :inicio_actividades,
                    :punto_venta,
                    :certificado,
                    :clave_privada,
                    :ambiente,
                    :habilitado,
                    :activo,
                    :email_fiscal
                )
            """),
            {
                'empresa_id': emp_id,
                'nombre': nombre_facturador,
                'razon_social': emp_nombre,  # Usa nombre como razón social
                'cuit': emp_cuit,
                'condicion_iva_id': emp_condicion_iva_id or 5,
                'condicion_iva': emp_condicion_iva,
                'inicio_actividades': emp_inicio_actividades,
                'punto_venta': emp_punto_venta,
                'certificado': emp_certificado,
                'clave_privada': emp_clave_privada,
                'ambiente': emp_ambiente or 'testing',
                'habilitado': bool(emp_habilitado),
                'activo': True,
                'email_fiscal': emp_email,
            },
        )


def downgrade():
    """Elimina los facturadores creados automáticamente por esta migración."""
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            DELETE FROM facturadores
            WHERE nombre LIKE :prefijo
        """),
        {'prefijo': f'{_NOMBRE_PREFIX}%'},
    )
