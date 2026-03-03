import {
    AbsoluteFill,
    interpolate,
    spring,
    useCurrentFrame,
    useVideoConfig,
} from 'remotion';
import { colores } from '../Demo';

/* Escena del Dashboard: muestra métricas animándose */
export const Dashboard: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const metricas = [
        { label: 'Ventas del día', valor: '$487.250', icono: '💰' },
        { label: 'Productos vendidos', valor: '156', icono: '📦' },
        { label: 'Clientes atendidos', valor: '42', icono: '👥' },
        { label: 'Ticket promedio', valor: '$11.601', icono: '🧾' },
    ];

    return (
        <AbsoluteFill
            style={{
                backgroundColor: colores.background,
                fontFamily: 'Inter, sans-serif',
                display: 'flex',
            }}
        >
            {/* Sidebar simulado */}
            <div
                style={{
                    width: 240,
                    backgroundColor: colores.sidebar,
                    padding: '20px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                }}
            >
                {/* Logo */}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '0 8px',
                        marginBottom: 20,
                    }}
                >
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
                    <span
                        style={{
                            color: '#F9FAFB',
                            fontSize: 18,
                            fontWeight: 700,
                        }}
                    >
                        FerrERP
                    </span>
                </div>

                {/* Items del menú */}
                {[
                    { nombre: 'Dashboard', activo: true },
                    { nombre: 'Ventas', activo: false },
                    { nombre: 'Productos', activo: false },
                    { nombre: 'Inventario', activo: false },
                    { nombre: 'Clientes', activo: false },
                    { nombre: 'Proveedores', activo: false },
                    { nombre: 'Caja', activo: false },
                    { nombre: 'Reportes', activo: false },
                ].map((item) => (
                    <div
                        key={item.nombre}
                        style={{
                            padding: '10px 16px',
                            borderRadius: 8,
                            backgroundColor: item.activo ? '#374151' : 'transparent',
                            color: item.activo ? '#F9FAFB' : '#9CA3AF',
                            fontSize: 14,
                            fontWeight: 500,
                        }}
                    >
                        {item.nombre}
                    </div>
                ))}
            </div>

            {/* Contenido principal */}
            <div style={{ flex: 1, padding: 32 }}>
                <h2
                    style={{
                        fontSize: 22,
                        fontWeight: 600,
                        color: colores.foreground,
                        marginBottom: 28,
                    }}
                >
                    Dashboard
                </h2>

                {/* Grid de métricas */}
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(4, 1fr)',
                        gap: 20,
                    }}
                >
                    {metricas.map((m, i) => {
                        const delay = i * 8;
                        const scale = spring({
                            frame: frame - delay,
                            fps,
                            config: { damping: 12 },
                        });
                        const opacity = interpolate(frame - delay, [0, 15], [0, 1], {
                            extrapolateLeft: 'clamp',
                            extrapolateRight: 'clamp',
                        });

                        return (
                            <div
                                key={m.label}
                                style={{
                                    backgroundColor: colores.surface,
                                    border: `1px solid ${colores.border}`,
                                    borderRadius: 12,
                                    padding: 20,
                                    transform: `scale(${scale})`,
                                    opacity,
                                }}
                            >
                                <div
                                    style={{
                                        fontSize: 13,
                                        color: colores.foregroundSecondary,
                                        fontWeight: 500,
                                        marginBottom: 8,
                                    }}
                                >
                                    {m.icono} {m.label}
                                </div>
                                <div
                                    style={{
                                        fontSize: 28,
                                        fontWeight: 700,
                                        color: colores.foreground,
                                    }}
                                >
                                    {m.valor}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Gráfico placeholder */}
                <div
                    style={{
                        marginTop: 28,
                        backgroundColor: colores.surface,
                        border: `1px solid ${colores.border}`,
                        borderRadius: 12,
                        padding: 24,
                        opacity: interpolate(frame, [40, 60], [0, 1], {
                            extrapolateLeft: 'clamp',
                            extrapolateRight: 'clamp',
                        }),
                    }}
                >
                    <div
                        style={{
                            fontSize: 16,
                            fontWeight: 600,
                            color: colores.foreground,
                            marginBottom: 20,
                        }}
                    >
                        Ventas de la semana
                    </div>
                    {/* Barras simuladas */}
                    <div
                        style={{
                            display: 'flex',
                            gap: 12,
                            alignItems: 'flex-end',
                            height: 160,
                        }}
                    >
                        {[65, 80, 45, 90, 70, 85, 95].map((h, i) => {
                            const barDelay = 50 + i * 5;
                            const barHeight = interpolate(
                                frame - barDelay,
                                [0, 20],
                                [0, h],
                                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
                            );
                            return (
                                <div
                                    key={i}
                                    style={{
                                        flex: 1,
                                        backgroundColor: colores.primary,
                                        borderRadius: '6px 6px 0 0',
                                        height: `${barHeight}%`,
                                        opacity: 0.85,
                                    }}
                                />
                            );
                        })}
                    </div>
                    <div
                        style={{
                            display: 'flex',
                            gap: 12,
                            marginTop: 8,
                        }}
                    >
                        {['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map((d) => (
                            <div
                                key={d}
                                style={{
                                    flex: 1,
                                    textAlign: 'center',
                                    fontSize: 12,
                                    color: colores.foregroundMuted,
                                }}
                            >
                                {d}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </AbsoluteFill>
    );
};
