import {
    AbsoluteFill,
    interpolate,
    spring,
    useCurrentFrame,
    useVideoConfig,
} from 'remotion';
import { colores, fontFamily, iconFontFamily } from '../config';
import { Sidebar, Header } from './Dashboard';

/*
 * Escena Reportes — réplica exacta de la app real.
 *
 * Layout: Sidebar + Header + Filtros de fecha + 3 Cards resumen +
 *         Gráfico "Ventas por Día" + Panel "Por Forma de Pago"
 */

const resumen = [
    { label: 'Total Ventas', valor: '$8,245,300.00' },
    { label: 'Cantidad de Ventas', valor: '187' },
    { label: 'Ticket Promedio', valor: '$44,092.51' },
];

const formasPago = [
    { metodo: 'Efectivo', monto: '$2,840,310.00' },
    { metodo: 'Tarjeta Débito', monto: '$1,531,140.00' },
    { metodo: 'Tarjeta Crédito', monto: '$2,142,200.00' },
    { metodo: 'Transferencia', monto: '$1,263,900.00' },
    { metodo: 'QR', monto: '$467,750.00' },
];

/* Datos del gráfico ventas por día (últimos 7 días visibles) */
const diasGrafico = ['25/02', '26/02', '27/02', '28/02', '01/03', '02/03', '03/03'];
const ventasPorDia = [980000, 1450000, 1180000, 750000, 1520000, 1290000, 1075300];
const maxVentaDia = 1600000;

export const Reportes: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    return (
        <AbsoluteFill style={{ fontFamily }}>
            <Sidebar activeItem="Reportes" />

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
                <Header titulo="FerrERP" />

                <div style={{ flex: 1, padding: 24, overflow: 'hidden' }}>
                    {/* Título + botón exportar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                        <h2 style={{ fontSize: 22, fontWeight: 600, color: colores.foreground, margin: 0 }}>
                            Reporte de Ventas
                        </h2>
                        <div
                            style={{
                                padding: '10px 20px',
                                backgroundColor: colores.surface,
                                color: colores.foreground,
                                border: `1px solid ${colores.border}`,
                                borderRadius: 8,
                                fontSize: 13,
                                fontWeight: 600,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                            }}
                        >
                            <span style={{ fontFamily: iconFontFamily, fontSize: 18 }}>download</span> Exportar Excel
                        </div>
                    </div>

                    {/* Filtros de fecha */}
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
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <span style={{ fontSize: 12, fontWeight: 500, color: colores.foreground }}>Desde</span>
                            <div
                                style={{
                                    padding: '9px 14px',
                                    border: `1px solid ${colores.border}`,
                                    borderRadius: 8,
                                    fontSize: 13,
                                    color: colores.foreground,
                                    minWidth: 140,
                                }}
                            >
                                01/02/2026
                            </div>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <span style={{ fontSize: 12, fontWeight: 500, color: colores.foreground }}>Hasta</span>
                            <div
                                style={{
                                    padding: '9px 14px',
                                    border: `1px solid ${colores.border}`,
                                    borderRadius: 8,
                                    fontSize: 13,
                                    color: colores.foreground,
                                    minWidth: 140,
                                }}
                            >
                                03/03/2026
                            </div>
                        </div>
                        <div
                            style={{
                                padding: '9px 20px',
                                backgroundColor: colores.primary,
                                color: colores.primaryForeground,
                                borderRadius: 8,
                                fontSize: 13,
                                fontWeight: 600,
                                alignSelf: 'flex-end',
                            }}
                        >
                            Filtrar
                        </div>
                    </div>

                    {/* Cards de resumen */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
                        {resumen.map((r, i) => {
                            const scale = spring({ frame: frame - i * 6, fps, config: { damping: 14, mass: 0.6 } });
                            return (
                                <div
                                    key={i}
                                    style={{
                                        background: colores.surface,
                                        border: `1px solid ${colores.border}`,
                                        borderRadius: 12,
                                        padding: '18px 20px',
                                        transform: `scale(${Math.min(scale, 1)})`,
                                        opacity: Math.min(scale, 1),
                                    }}
                                >
                                    <span style={{ fontSize: 12, fontWeight: 500, color: colores.foregroundSecondary, display: 'block', marginBottom: 8 }}>
                                        {r.label}
                                    </span>
                                    <span style={{ fontSize: 28, fontWeight: 700, color: colores.foreground }}>
                                        {r.valor}
                                    </span>
                                </div>
                            );
                        })}
                    </div>

                    {/* Gráfico + Formas de pago */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16 }}>
                        {/* Gráfico ventas por día */}
                        <div style={{ background: colores.surface, border: `1px solid ${colores.border}`, borderRadius: 12, padding: 18 }}>
                            <span style={{ fontSize: 15, fontWeight: 600, color: colores.foreground, display: 'block', marginBottom: 16 }}>
                                Ventas por Día
                            </span>
                            <div style={{ display: 'flex', height: 160 }}>
                                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingRight: 8, paddingBottom: 24 }}>
                                    {['$1.600.000', '$1.200.000', '$800.000', '$400.000'].map((l) => (
                                        <span key={l} style={{ fontSize: 9, color: colores.foregroundMuted, textAlign: 'right', minWidth: 55 }}>{l}</span>
                                    ))}
                                </div>
                                <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', borderBottom: `1px solid ${colores.borderMuted}` }}>
                                    {ventasPorDia.map((venta, i) => {
                                        const barH = venta > 0 ? (venta / maxVentaDia) * 130 : 0;
                                        const h = interpolate(frame, [30 + i * 4, 50 + i * 4], [0, barH], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
                                        return (
                                            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                                                <div style={{ width: 32, height: h, backgroundColor: 'rgba(224, 123, 84, 0.75)', borderRadius: '4px 4px 0 0' }} />
                                                <span style={{ fontSize: 10, color: colores.foregroundMuted }}>{diasGrafico[i]}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Por forma de pago */}
                        <div style={{ background: colores.surface, border: `1px solid ${colores.border}`, borderRadius: 12, padding: 18 }}>
                            <span style={{ fontSize: 15, fontWeight: 600, color: colores.foreground, display: 'block', marginBottom: 16 }}>
                                Por Forma de Pago
                            </span>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                                {formasPago.map((fp, i) => {
                                    const rowOpacity = interpolate(frame, [20 + i * 10, 35 + i * 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
                                    return (
                                        <div
                                            key={fp.metodo}
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                padding: '12px 0',
                                                borderBottom: i < formasPago.length - 1 ? `1px solid ${colores.borderMuted}` : 'none',
                                                opacity: rowOpacity,
                                            }}
                                        >
                                            <span style={{ fontSize: 13, color: colores.foreground }}>{fp.metodo}</span>
                                            <span style={{ fontSize: 13, fontWeight: 600, color: colores.foreground }}>{fp.monto}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </AbsoluteFill>
    );
};
