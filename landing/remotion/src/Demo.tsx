import { AbsoluteFill, Sequence } from 'remotion';
import { Intro } from './scenes/Intro';
import { Dashboard } from './scenes/Dashboard';
import { Productos } from './scenes/Productos';
import { Reportes } from './scenes/Reportes';

/*
 * Composición principal del video demo de FerrERP.
 *
 * Escenas:
 * 1. Intro (0-4s)          → Logo animado + nombre
 * 2. Dashboard (4-20s)     → Métricas, gráfico de ventas, alertas
 * 3. Productos (20-40s)    → Tabla de productos con filtros
 * 4. Reportes (40-58s)     → Reporte de ventas con gráficos
 * 5. Outro (58-65s)        → CTA final
 *
 * Colores de la app:
 * --primary: #E07B54
 * --sidebar: #1F2937
 * --background: #FAFAFA
 * --foreground: #1A1A1A
 */

const FPS = 30;

/* Colores compartidos — idénticos a la app real */
export const colores = {
    primary: '#E07B54',
    primaryHover: '#D06A43',
    primaryForeground: '#FFFFFF',
    secondary: '#0D6E6E',
    sidebar: '#1F2937',
    sidebarForeground: '#F9FAFB',
    sidebarMuted: '#9CA3AF',
    sidebarHover: '#374151',
    background: '#FAFAFA',
    surface: '#FFFFFF',
    foreground: '#1A1A1A',
    foregroundSecondary: '#666666',
    foregroundMuted: '#888888',
    border: '#E5E5E5',
    borderMuted: '#F0F0F0',
    muted: '#F5F5F5',
    success: '#16A34A',
    successBg: '#DCFCE7',
    warning: '#F59E0B',
    warningBg: '#FEF3C7',
    error: '#DC2626',
    errorBg: '#FEE2E2',
};

/* Sidebar compartido — replica exacta de la app */
export const sidebarItems = [
    { icon: '📊', label: 'Dashboard' },
    { icon: '📦', label: 'Productos' },
    { icon: '🏭', label: 'Inventario' },
    { icon: '🛒', label: 'Compras' },
    { icon: '🏪', label: 'POS' },
    { icon: '🧾', label: 'Ventas' },
    { icon: '📄', label: 'Presupuestos' },
    { icon: '🧾', label: 'Facturación' },
    { icon: '👥', label: 'Clientes' },
    { icon: '💰', label: 'Caja' },
    { icon: '📈', label: 'Reportes' },
    { icon: '⚙️', label: 'Configuración' },
];

export const fontFamily = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif';

export const Demo: React.FC = () => {
    return (
        <AbsoluteFill style={{ backgroundColor: colores.background }}>
            {/* Intro: 0-4s */}
            <Sequence from={0} durationInFrames={FPS * 4}>
                <Intro />
            </Sequence>

            {/* Dashboard: 4-20s */}
            <Sequence from={FPS * 4} durationInFrames={FPS * 16}>
                <Dashboard />
            </Sequence>

            {/* Productos: 20-40s */}
            <Sequence from={FPS * 20} durationInFrames={FPS * 20}>
                <Productos />
            </Sequence>

            {/* Reportes: 40-58s */}
            <Sequence from={FPS * 40} durationInFrames={FPS * 18}>
                <Reportes />
            </Sequence>

            {/* Outro: 58-65s */}
            <Sequence from={FPS * 58} durationInFrames={FPS * 7}>
                <Outro />
            </Sequence>
        </AbsoluteFill>
    );
};

/* Escena de cierre con CTA */
const Outro: React.FC = () => {
    return (
        <AbsoluteFill
            style={{
                backgroundColor: colores.sidebar,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily,
            }}
        >
            <div
                style={{
                    width: 80,
                    height: 80,
                    backgroundColor: colores.primary,
                    borderRadius: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: 40,
                    fontWeight: 700,
                    marginBottom: 24,
                }}
            >
                F
            </div>
            <h1
                style={{
                    color: colores.sidebarForeground,
                    fontSize: 48,
                    fontWeight: 700,
                    marginBottom: 12,
                }}
            >
                FerrERP
            </h1>
            <p
                style={{
                    color: colores.sidebarMuted,
                    fontSize: 20,
                    marginBottom: 40,
                }}
            >
                Gestión integral para ferreterías
            </p>
            <div
                style={{
                    padding: '14px 32px',
                    backgroundColor: colores.primary,
                    borderRadius: 12,
                    color: 'white',
                    fontSize: 18,
                    fontWeight: 600,
                }}
            >
                Comenzar gratis →
            </div>
            <p
                style={{
                    color: colores.sidebarMuted,
                    fontSize: 14,
                    marginTop: 16,
                }}
            >
                ferrerp.com
            </p>
        </AbsoluteFill>
    );
};
