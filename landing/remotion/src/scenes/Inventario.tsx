import {
    AbsoluteFill,
    interpolate,
    useCurrentFrame,
} from 'remotion';
import { colores } from '../Demo';

/* Escena de Inventario: lista de productos con stock y alertas */
export const Inventario: React.FC = () => {
    const frame = useCurrentFrame();

    const productos = [
        { codigo: 'FER-001', nombre: 'Tornillo 6x50mm (x100)', stock: 250, minimo: 50, estado: 'ok' },
        { codigo: 'FER-003', nombre: 'Llave combinada 10mm', stock: 35, minimo: 20, estado: 'ok' },
        { codigo: 'FER-005', nombre: 'Cinta aisladora 10m', stock: 8, minimo: 30, estado: 'bajo' },
        { codigo: 'FER-007', nombre: 'Candado 40mm', stock: 5, minimo: 15, estado: 'bajo' },
        { codigo: 'FER-009', nombre: 'Bulón 8x60mm (x50)', stock: 120, minimo: 40, estado: 'ok' },
        { codigo: 'FER-011', nombre: 'Pintura látex blanca 4L', stock: 3, minimo: 10, estado: 'bajo' },
        { codigo: 'FER-013', nombre: 'Disyuntor bipolar 20A', stock: 45, minimo: 10, estado: 'ok' },
    ];

    return (
        <AbsoluteFill
            style={{
                backgroundColor: colores.background,
                fontFamily: 'Inter, sans-serif',
                display: 'flex',
            }}
        >
            {/* Sidebar mínimo */}
            <div
                style={{
                    width: 240,
                    backgroundColor: colores.sidebar,
                    padding: '20px 16px',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 8px' }}>
                    <div
                        style={{
                            width: 32,
                            height: 32,
                            backgroundColor: colores.primary,
                            borderRadius: 8,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'white',
                            fontSize: 18,
                            fontWeight: 700,
                        }}
                    >
                        F
                    </div>
                    <span style={{ color: '#F9FAFB', fontSize: 18, fontWeight: 700 }}>
                        FerrERP
                    </span>
                </div>
            </div>

            {/* Contenido */}
            <div style={{ flex: 1, padding: 32 }}>
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 24,
                    }}
                >
                    <h2 style={{ fontSize: 22, fontWeight: 600, color: colores.foreground }}>
                        Inventario
                    </h2>
                    <div
                        style={{
                            padding: '8px 16px',
                            backgroundColor: colores.primary,
                            color: 'white',
                            borderRadius: 8,
                            fontSize: 13,
                            fontWeight: 600,
                        }}
                    >
                        + Nuevo producto
                    </div>
                </div>

                {/* Tabla */}
                <div
                    style={{
                        backgroundColor: colores.surface,
                        border: `1px solid ${colores.border}`,
                        borderRadius: 12,
                        overflow: 'hidden',
                    }}
                >
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                {['Código', 'Producto', 'Stock', 'Mínimo', 'Estado'].map((h) => (
                                    <th
                                        key={h}
                                        style={{
                                            padding: '12px 16px',
                                            backgroundColor: '#F5F5F5',
                                            fontSize: 12,
                                            fontWeight: 600,
                                            color: colores.foregroundSecondary,
                                            textTransform: 'uppercase',
                                            textAlign: 'left',
                                            letterSpacing: 0.5,
                                        }}
                                    >
                                        {h}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {productos.map((p, i) => {
                                const rowOpacity = interpolate(
                                    frame,
                                    [10 + i * 12, 30 + i * 12],
                                    [0, 1],
                                    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
                                );
                                const esBajo = p.estado === 'bajo';

                                return (
                                    <tr
                                        key={p.codigo}
                                        style={{
                                            opacity: rowOpacity,
                                            backgroundColor: esBajo ? '#FEE2E2' : 'transparent',
                                        }}
                                    >
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                                fontFamily: 'JetBrains Mono, monospace',
                                                fontSize: 13,
                                                fontWeight: 500,
                                            }}
                                        >
                                            {p.codigo}
                                        </td>
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                                fontSize: 14,
                                                color: colores.foreground,
                                            }}
                                        >
                                            {p.nombre}
                                        </td>
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                                fontSize: 14,
                                                fontWeight: 600,
                                                color: esBajo ? colores.error : colores.foreground,
                                            }}
                                        >
                                            {p.stock}
                                        </td>
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                                fontSize: 14,
                                                color: colores.foregroundSecondary,
                                            }}
                                        >
                                            {p.minimo}
                                        </td>
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                            }}
                                        >
                                            <span
                                                style={{
                                                    padding: '4px 10px',
                                                    borderRadius: 4,
                                                    fontSize: 12,
                                                    fontWeight: 600,
                                                    backgroundColor: esBajo ? '#FEE2E2' : '#DCFCE7',
                                                    color: esBajo ? colores.error : colores.success,
                                                }}
                                            >
                                                {esBajo ? 'Stock bajo' : 'OK'}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </AbsoluteFill>
    );
};
