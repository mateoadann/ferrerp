import {
    AbsoluteFill,
    interpolate,
    spring,
    useCurrentFrame,
    useVideoConfig,
} from 'remotion';
import { colores, sidebarItems, fontFamily, iconFontFamily } from '../config';

/*
 * Escena Dashboard — réplica exacta de la app real.
 *
 * Layout: Sidebar (240px) + Contenido principal
 * Contenido:
 *   - Header con título y fecha
 *   - 4 métricas (Ventas del día, Operaciones hoy, Stock bajo, Ctas por cobrar)
 *   - Gráfico de barras "Ventas últimos 7 días" + Panel "Alertas recientes"
 *   - Acciones rápidas
 */

const metricas = [
    {
        label: 'Ventas del día',
        valor: '$536,050.00',
        subtitulo: 'vs ayer: $119,310.00',
        badge: '+349%',
        badgeColor: colores.success,
        badgeBg: colores.successBg,
    },
    {
        label: 'Operaciones hoy',
        valor: '8',
        subtitulo: 'ventas realizadas',
        badge: '+8',
        badgeColor: colores.foregroundSecondary,
        badgeBg: colores.muted,
    },
    {
        label: 'Stock bajo',
        valor: '0',
        subtitulo: 'productos bajo mínimo',
        badge: 'OK',
        badgeColor: colores.success,
        badgeBg: colores.successBg,
    },
    {
        label: 'Cuentas por cobrar',
        valor: '$0.00',
        subtitulo: 'deudas pendientes',
        badge: '0 clientes',
        badgeColor: colores.primary,
        badgeBg: '#FDE8DF',
    },
];

const diasSemana = ['Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Mon', 'Tue'];
const ventasDia = [80000, 210000, 150000, 50000, 130000, 95000, 536050];
const maxVenta = 600000;

export const Dashboard: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    return (
        <AbsoluteFill style={{ fontFamily }}>
            <Sidebar activeItem="Dashboard" />

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
                    {/* Título + fecha */}
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: 20,
                        }}
                    >
                        <h2 style={{ fontSize: 22, fontWeight: 600, color: colores.foreground, margin: 0 }}>
                            Dashboard
                        </h2>
                        <span style={{ fontSize: 13, color: colores.foregroundSecondary }}>
                            03 de March, 2026
                        </span>
                    </div>

                    {/* Métricas */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20 }}>
                        {metricas.map((m, i) => {
                            const scale = spring({ frame: frame - i * 6, fps, config: { damping: 14, mass: 0.6 } });
                            return (
                                <div
                                    key={i}
                                    style={{
                                        background: colores.surface,
                                        border: `1px solid ${colores.border}`,
                                        borderRadius: 12,
                                        padding: '16px 18px',
                                        transform: `scale(${Math.min(scale, 1)})`,
                                        opacity: Math.min(scale, 1),
                                    }}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                                        <span style={{ fontSize: 12, fontWeight: 500, color: colores.foregroundSecondary }}>{m.label}</span>
                                        <span
                                            style={{
                                                fontSize: 11,
                                                fontWeight: 600,
                                                color: m.badgeColor,
                                                backgroundColor: m.badgeBg,
                                                padding: '2px 8px',
                                                borderRadius: 4,
                                            }}
                                        >
                                            {m.badge}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: 26, fontWeight: 700, color: colores.foreground, marginBottom: 2 }}>
                                        {m.valor}
                                    </div>
                                    <span style={{ fontSize: 11, color: colores.foregroundMuted }}>{m.subtitulo}</span>
                                </div>
                            );
                        })}
                    </div>

                    {/* Gráfico + Alertas */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, marginBottom: 20 }}>
                        {/* Gráfico de ventas */}
                        <div style={{ background: colores.surface, border: `1px solid ${colores.border}`, borderRadius: 12, padding: 18 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                                <span style={{ fontSize: 15, fontWeight: 600, color: colores.foreground }}>Ventas últimos 7 días</span>
                                <span style={{ fontSize: 12, color: colores.foregroundSecondary, border: `1px solid ${colores.border}`, padding: '4px 12px', borderRadius: 6 }}>
                                    Ver reporte completo
                                </span>
                            </div>
                            <div style={{ display: 'flex', height: 170 }}>
                                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingRight: 8, paddingBottom: 24 }}>
                                    {['$600.000', '$500.000', '$400.000', '$300.000', '$200.000', '$100.000', '$0'].map((l) => (
                                        <span key={l} style={{ fontSize: 9, color: colores.foregroundMuted, textAlign: 'right', minWidth: 55 }}>{l}</span>
                                    ))}
                                </div>
                                <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', borderBottom: `1px solid ${colores.borderMuted}` }}>
                                    {ventasDia.map((venta, i) => {
                                        const barH = (venta / maxVenta) * 140;
                                        const h = interpolate(frame, [40 + i * 4, 60 + i * 4], [0, barH], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
                                        return (
                                            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                                                <div style={{ width: 38, height: h, backgroundColor: 'rgba(224, 123, 84, 0.75)', borderRadius: '4px 4px 0 0' }} />
                                                <span style={{ fontSize: 10, color: colores.foregroundMuted }}>{diasSemana[i]}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Alertas recientes */}
                        <div style={{ background: colores.surface, border: `1px solid ${colores.border}`, borderRadius: 12, padding: 18 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                                <span style={{ fontSize: 15, fontWeight: 600, color: colores.foreground }}>Alertas recientes</span>
                                <span style={{ fontSize: 12, color: colores.foregroundSecondary, border: `1px solid ${colores.border}`, padding: '4px 12px', borderRadius: 6 }}>Ver todo</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 120, color: colores.foregroundMuted }}>
                                <span style={{ fontFamily: iconFontFamily, fontSize: 36, marginBottom: 8, opacity: 0.4 }}>check_circle</span>
                                <span style={{ fontSize: 13 }}>Sin alertas pendientes</span>
                            </div>
                        </div>
                    </div>

                    {/* Acciones rápidas */}
                    <div style={{ background: colores.surface, border: `1px solid ${colores.border}`, borderRadius: 12, padding: 18 }}>
                        <span style={{ fontSize: 15, fontWeight: 600, color: colores.foreground, display: 'block', marginBottom: 14 }}>Acciones rápidas</span>
                        <div style={{ display: 'flex', gap: 12 }}>
                            {[
                                { icon: 'point_of_sale', label: 'Nueva Venta', primary: true },
                                { icon: 'add', label: 'Nuevo Producto', primary: false },
                                { icon: 'person_add', label: 'Nuevo Cliente', primary: false },
                                { icon: 'tune', label: 'Ajustar Stock', primary: false },
                            ].map((a, i) => (
                                <div
                                    key={i}
                                    style={{
                                        padding: '10px 20px',
                                        borderRadius: 8,
                                        fontSize: 13,
                                        fontWeight: 600,
                                        backgroundColor: a.primary ? colores.primary : colores.surface,
                                        color: a.primary ? colores.primaryForeground : colores.foreground,
                                        border: a.primary ? 'none' : `1px solid ${colores.border}`,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 6,
                                    }}
                                >
                                    <span style={{ fontFamily: iconFontFamily, fontSize: 18 }}>{a.icon}</span>
                                    {a.label}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </AbsoluteFill>
    );
};

/* ===== Componentes compartidos (Sidebar y Header) ===== */

export const Sidebar: React.FC<{ activeItem: string }> = ({ activeItem }) => {
    return (
        <div
            style={{
                position: 'absolute',
                left: 0,
                top: 0,
                width: 240,
                height: '100%',
                backgroundColor: colores.sidebar,
                display: 'flex',
                flexDirection: 'column',
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 18px', height: 56, borderBottom: `1px solid ${colores.sidebarHover}` }}>
                <div style={{ width: 32, height: 32, backgroundColor: colores.primary, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 17, fontWeight: 700 }}>F</div>
                <span style={{ color: colores.sidebarForeground, fontSize: 17, fontWeight: 700 }}>FerrERP</span>
            </div>
            <div style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                {sidebarItems.map((item) => {
                    const isActive = item.label === activeItem;
                    return (
                        <div
                            key={item.label}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '9px 14px',
                                borderRadius: 8,
                                backgroundColor: isActive ? colores.sidebarHover : 'transparent',
                                color: isActive ? colores.sidebarForeground : colores.sidebarMuted,
                                fontSize: 13,
                                fontWeight: 500,
                            }}
                        >
                            <span style={{ fontFamily: iconFontFamily, fontSize: 18, color: isActive ? colores.primary : colores.sidebarMuted }}>{item.icon}</span>
                            <span>{item.label}</span>
                        </div>
                    );
                })}
            </div>
            <div style={{ borderTop: `1px solid ${colores.sidebarHover}`, padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 34, height: 34, borderRadius: '50%', backgroundColor: colores.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 14, fontWeight: 600 }}>A</div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ color: colores.sidebarForeground, fontSize: 13, fontWeight: 500 }}>Administrador</span>
                    <span style={{ color: colores.sidebarMuted, fontSize: 11 }}>Owner</span>
                </div>
            </div>
        </div>
    );
};

export const Header: React.FC<{ titulo: string }> = ({ titulo }) => {
    return (
        <div style={{ height: 56, display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 24px', backgroundColor: colores.surface, borderBottom: `1px solid ${colores.border}` }}>
            <span style={{ fontSize: 16, fontWeight: 600, color: colores.foreground }}>{titulo}</span>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <div style={{ width: 34, height: 34, borderRadius: 8, backgroundColor: colores.muted, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: iconFontFamily, fontSize: 20, color: colores.foregroundSecondary }}>notifications</div>
                <div style={{ width: 34, height: 34, borderRadius: 8, backgroundColor: colores.muted, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: iconFontFamily, fontSize: 20, color: colores.foregroundSecondary }}>account_circle</div>
            </div>
        </div>
    );
};
