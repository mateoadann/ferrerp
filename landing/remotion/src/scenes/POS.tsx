import {
    AbsoluteFill,
    interpolate,
    useCurrentFrame,
} from 'remotion';
import { colores } from '../Demo';

/* Escena del Punto de Venta: flujo de búsqueda, agregar producto, cobrar */
export const POS: React.FC = () => {
    const frame = useCurrentFrame();

    const productos = [
        { codigo: 'FER-001', nombre: 'Tornillo 6x50mm (x100)', precio: '$3.450', stock: 250 },
        { codigo: 'FER-002', nombre: 'Arandela plana 6mm (x50)', precio: '$890', stock: 180 },
        { codigo: 'FER-003', nombre: 'Llave combinada 10mm', precio: '$4.200', stock: 35 },
    ];

    const carrito = [
        { nombre: 'Tornillo 6x50mm (x100)', cant: 3, subtotal: '$10.350' },
        { nombre: 'Arandela plana 6mm (x50)', cant: 1, subtotal: '$890' },
        { nombre: 'Llave combinada 10mm', cant: 2, subtotal: '$8.400' },
    ];

    /* Fases de animación */
    const faseProductos = interpolate(frame, [0, 30], [0, 1], {
        extrapolateRight: 'clamp',
    });
    const faseCarrito = interpolate(frame, [150, 200], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
    });
    const fasePago = interpolate(frame, [450, 500], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
    });

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

            {/* Panel izquierdo: productos */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', opacity: faseProductos }}>
                <div
                    style={{
                        padding: '16px 24px',
                        borderBottom: `1px solid ${colores.border}`,
                        backgroundColor: colores.surface,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 16,
                    }}
                >
                    <div style={{ fontSize: 18, fontWeight: 600, color: colores.foreground }}>
                        Punto de Venta
                    </div>
                    <div
                        style={{
                            flex: 1,
                            maxWidth: 360,
                            padding: '8px 14px',
                            border: `1px solid ${colores.border}`,
                            borderRadius: 8,
                            fontSize: 14,
                            color: colores.foregroundMuted,
                        }}
                    >
                        🔍 Buscar producto...
                    </div>
                </div>

                {/* Tabla de productos */}
                <div style={{ flex: 1, padding: 24 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                {['Código', 'Producto', 'Precio', 'Stock', ''].map((h) => (
                                    <th
                                        key={h}
                                        style={{
                                            padding: '10px 16px',
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
                                const rowOpacity = interpolate(frame, [20 + i * 15, 40 + i * 15], [0, 1], {
                                    extrapolateLeft: 'clamp',
                                    extrapolateRight: 'clamp',
                                });
                                return (
                                    <tr key={p.codigo} style={{ opacity: rowOpacity }}>
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
                                            }}
                                        >
                                            {p.precio}
                                        </td>
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                                fontSize: 14,
                                            }}
                                        >
                                            {p.stock}
                                        </td>
                                        <td
                                            style={{
                                                padding: '14px 16px',
                                                borderBottom: `1px solid ${colores.border}`,
                                            }}
                                        >
                                            <div
                                                style={{
                                                    padding: '6px 12px',
                                                    backgroundColor: colores.primary,
                                                    color: 'white',
                                                    borderRadius: 6,
                                                    fontSize: 12,
                                                    fontWeight: 600,
                                                    textAlign: 'center',
                                                }}
                                            >
                                                Agregar
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Panel derecho: carrito */}
            <div
                style={{
                    width: 340,
                    backgroundColor: colores.surface,
                    borderLeft: `1px solid ${colores.border}`,
                    display: 'flex',
                    flexDirection: 'column',
                    opacity: faseCarrito,
                }}
            >
                <div
                    style={{
                        padding: '16px 20px',
                        borderBottom: `1px solid ${colores.border}`,
                        fontSize: 16,
                        fontWeight: 600,
                        color: colores.foreground,
                    }}
                >
                    Carrito (3 items)
                </div>

                <div style={{ flex: 1, padding: 16 }}>
                    {carrito.map((item, i) => {
                        const itemOpacity = interpolate(
                            frame,
                            [160 + i * 30, 190 + i * 30],
                            [0, 1],
                            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
                        );
                        return (
                            <div
                                key={item.nombre}
                                style={{
                                    padding: '12px 0',
                                    borderBottom: `1px solid ${colores.border}`,
                                    opacity: itemOpacity,
                                }}
                            >
                                <div style={{ fontSize: 14, color: colores.foreground, fontWeight: 500 }}>
                                    {item.nombre}
                                </div>
                                <div
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        marginTop: 4,
                                        fontSize: 13,
                                        color: colores.foregroundSecondary,
                                    }}
                                >
                                    <span>x{item.cant}</span>
                                    <span style={{ fontWeight: 600, color: colores.foreground }}>
                                        {item.subtotal}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Total y botón de pago */}
                <div style={{ padding: 20, borderTop: `1px solid ${colores.border}`, opacity: fasePago }}>
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            marginBottom: 16,
                        }}
                    >
                        <span style={{ fontSize: 16, fontWeight: 600, color: colores.foreground }}>
                            Total
                        </span>
                        <span style={{ fontSize: 22, fontWeight: 700, color: colores.primary }}>
                            $19.640
                        </span>
                    </div>
                    <div
                        style={{
                            padding: '14px 0',
                            backgroundColor: colores.primary,
                            color: 'white',
                            borderRadius: 12,
                            fontSize: 16,
                            fontWeight: 600,
                            textAlign: 'center',
                        }}
                    >
                        Confirmar venta
                    </div>
                </div>
            </div>
        </AbsoluteFill>
    );
};
