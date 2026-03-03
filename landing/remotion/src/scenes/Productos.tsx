import {
    AbsoluteFill,
    interpolate,
    useCurrentFrame,
} from 'remotion';
import { colores, fontFamily } from '../Demo';
import { Sidebar, Header } from './Dashboard';

/*
 * Escena Productos — réplica exacta de la app real.
 *
 * Layout: Sidebar + Header + Filtros + Tabla de productos
 * Columnas: CÓDIGO, NOMBRE, CATEGORÍA, STOCK, PRECIO, ESTADO, ACCIONES
 * Datos reales del seed de la app.
 */

const productos = [
    { codigo: 'AD002', nombre: 'Adhesivo Contacto 250ml', categoria: 'Adhesivos > Pegamentos', stock: '146 u', precio: '$1,800.00', activo: true },
    { codigo: 'PI005', nombre: 'Aguarras 1L', categoria: 'Pinturería > Pinturas', stock: '31 l', precio: '$1,200.00', activo: true },
    { codigo: 'HE002', nombre: 'Amoladora Angular 4 1/2"', categoria: 'Herramientas > Eléctricas', stock: '10 u', precio: '$32,000.00', activo: true },
    { codigo: 'TO006', nombre: 'Arandela Plana 8mm (x100)', categoria: 'Tornillería > Bulonería', stock: '80 u', precio: '$180.00', activo: true },
    { codigo: 'HE004', nombre: 'Atornillador Inalámbrico 12V', categoria: 'Herramientas > Eléctricas', stock: '5 u', precio: '$48,000.00', activo: true },
    { codigo: 'TO004', nombre: 'Bulón Hex. 8×50 c/tuerca (x20)', categoria: 'Tornillería > Bulonería', stock: '40 u', precio: '$800.00', activo: true },
    { codigo: 'EL002', nombre: 'Cable Unipolar 1.5mm (x100m)', categoria: 'Electricidad > Cables', stock: '24 m', precio: '$9,800.00', activo: true },
    { codigo: 'EL001', nombre: 'Cable Unipolar 2.5mm (x100m)', categoria: 'Electricidad > Cables', stock: '19 m', precio: '$15,000.00', activo: true },
];

const columnas = ['CÓDIGO', 'NOMBRE', 'CATEGORÍA', 'STOCK', 'PRECIO', 'ESTADO', 'ACCIONES'];

export const Productos: React.FC = () => {
    const frame = useCurrentFrame();

    return (
        <AbsoluteFill style={{ fontFamily }}>
            <Sidebar activeItem="Productos" />

            <div
                style={{
                    position: 'absolute',
                    left: 240,
                    top: 0,
                    right: 0,
                    bottom: 0,
                    display: 'flex',
                    flexDirection: 'column',
                }}
            >
                <Header titulo="FerrERP (Dev)" />

                <div style={{ flex: 1, padding: 24, overflow: 'hidden' }}>
                    {/* Título + botón */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                        <h2 style={{ fontSize: 22, fontWeight: 600, color: colores.foreground, margin: 0 }}>Productos</h2>
                        <div
                            style={{
                                padding: '10px 20px',
                                backgroundColor: colores.primary,
                                color: colores.primaryForeground,
                                borderRadius: 8,
                                fontSize: 13,
                                fontWeight: 600,
                            }}
                        >
                            + Nuevo Producto
                        </div>
                    </div>

                    {/* Filtros */}
                    <div
                        style={{
                            background: colores.surface,
                            border: `1px solid ${colores.border}`,
                            borderRadius: 12,
                            padding: 18,
                            marginBottom: 16,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 16,
                        }}
                    >
                        {/* Buscador */}
                        <div
                            style={{
                                flex: 1,
                                maxWidth: 380,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '9px 14px',
                                border: `1px solid ${colores.border}`,
                                borderRadius: 8,
                                color: colores.foregroundMuted,
                                fontSize: 13,
                            }}
                        >
                            🔍 Buscar por código o nombre...
                        </div>

                        {/* Select categoría */}
                        <div
                            style={{
                                padding: '9px 14px',
                                border: `1px solid ${colores.border}`,
                                borderRadius: 8,
                                fontSize: 13,
                                color: colores.foregroundSecondary,
                                minWidth: 180,
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                            }}
                        >
                            Todas las categorías
                            <span style={{ fontSize: 10 }}>▼</span>
                        </div>

                        {/* Checkboxes */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 13 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div
                                    style={{
                                        width: 16,
                                        height: 16,
                                        borderRadius: 3,
                                        backgroundColor: colores.primary,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        color: 'white',
                                        fontSize: 10,
                                    }}
                                >
                                    ✓
                                </div>
                                <span style={{ color: colores.foreground }}>Solo activos</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div
                                    style={{
                                        width: 16,
                                        height: 16,
                                        borderRadius: 3,
                                        border: `2px solid ${colores.border}`,
                                        backgroundColor: 'transparent',
                                    }}
                                />
                                <span style={{ color: colores.foreground }}>Bajo stock</span>
                            </div>
                        </div>
                    </div>

                    {/* Tabla de productos */}
                    <div
                        style={{
                            background: colores.surface,
                            border: `1px solid ${colores.border}`,
                            borderRadius: 12,
                            overflow: 'hidden',
                        }}
                    >
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr>
                                    {columnas.map((col) => (
                                        <th
                                            key={col}
                                            style={{
                                                padding: '11px 14px',
                                                backgroundColor: colores.muted,
                                                fontSize: 11,
                                                fontWeight: 600,
                                                color: colores.foregroundSecondary,
                                                textTransform: 'uppercase',
                                                textAlign: col === 'STOCK' || col === 'PRECIO' ? 'right' : 'left',
                                                letterSpacing: 0.5,
                                                borderBottom: `1px solid ${colores.border}`,
                                            }}
                                        >
                                            {col}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {productos.map((p, i) => {
                                    const rowOpacity = interpolate(
                                        frame,
                                        [10 + i * 8, 25 + i * 8],
                                        [0, 1],
                                        { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
                                    );
                                    return (
                                        <tr key={p.codigo} style={{ opacity: rowOpacity }}>
                                            {/* Código */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                    fontFamily: 'JetBrains Mono, monospace',
                                                    fontSize: 12,
                                                    fontWeight: 500,
                                                    color: colores.primary,
                                                }}
                                            >
                                                {p.codigo}
                                            </td>
                                            {/* Nombre */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                    fontSize: 13,
                                                    color: colores.secondary,
                                                    fontWeight: 500,
                                                }}
                                            >
                                                {p.nombre}
                                            </td>
                                            {/* Categoría */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                }}
                                            >
                                                <span
                                                    style={{
                                                        fontSize: 11,
                                                        color: colores.foregroundSecondary,
                                                        backgroundColor: colores.muted,
                                                        padding: '3px 8px',
                                                        borderRadius: 4,
                                                    }}
                                                >
                                                    {p.categoria}
                                                </span>
                                            </td>
                                            {/* Stock */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                    fontSize: 13,
                                                    textAlign: 'right',
                                                    color: colores.foreground,
                                                }}
                                            >
                                                {p.stock}
                                            </td>
                                            {/* Precio */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                    fontSize: 13,
                                                    fontWeight: 600,
                                                    textAlign: 'right',
                                                    color: colores.foreground,
                                                }}
                                            >
                                                {p.precio}
                                            </td>
                                            {/* Estado */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                }}
                                            >
                                                <span
                                                    style={{
                                                        fontSize: 11,
                                                        fontWeight: 600,
                                                        color: colores.success,
                                                        backgroundColor: colores.successBg,
                                                        padding: '3px 10px',
                                                        borderRadius: 4,
                                                    }}
                                                >
                                                    Activo
                                                </span>
                                            </td>
                                            {/* Acciones */}
                                            <td
                                                style={{
                                                    padding: '13px 14px',
                                                    borderBottom: `1px solid ${colores.borderMuted}`,
                                                    display: 'flex',
                                                    gap: 6,
                                                }}
                                            >
                                                <span style={{ fontSize: 16, opacity: 0.5 }}>✏️</span>
                                                <span style={{ fontSize: 16, opacity: 0.5 }}>👁</span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </AbsoluteFill>
    );
};
