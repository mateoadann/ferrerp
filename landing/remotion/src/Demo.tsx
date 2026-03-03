import { AbsoluteFill, Sequence } from 'remotion';
import { Intro } from './scenes/Intro';
import { Dashboard } from './scenes/Dashboard';
import { POS } from './scenes/POS';
import { Inventario } from './scenes/Inventario';

/*
 * Composición principal del video demo de FerrERP.
 *
 * Escenas:
 * 1. Intro (0-5s)       → Logo animado + nombre
 * 2. Dashboard (5-25s)  → Métricas del dashboard
 * 3. POS (25-50s)       → Flujo de venta completo
 * 4. Inventario (50-70s)→ Lista de productos y stock
 * 5. Outro (70-80s)     → CTA final
 *
 * Colores de la app:
 * --primary: #E07B54
 * --sidebar: #1F2937
 * --background: #FAFAFA
 * --foreground: #1A1A1A
 */

const FPS = 30;

/* Colores compartidos */
export const colores = {
    primary: '#E07B54',
    primaryHover: '#D06A43',
    secondary: '#0D6E6E',
    sidebar: '#1F2937',
    background: '#FAFAFA',
    surface: '#FFFFFF',
    foreground: '#1A1A1A',
    foregroundSecondary: '#666666',
    foregroundMuted: '#888888',
    border: '#E5E5E5',
    success: '#16A34A',
    warning: '#F59E0B',
    error: '#DC2626',
};

export const Demo: React.FC = () => {
    return (
        <AbsoluteFill style={{ backgroundColor: colores.background }}>
            {/* Intro: 0-5s (frames 0-149) */}
            <Sequence from={0} durationInFrames={FPS * 5}>
                <Intro />
            </Sequence>

            {/* Dashboard: 5-25s (frames 150-749) */}
            <Sequence from={FPS * 5} durationInFrames={FPS * 20}>
                <Dashboard />
            </Sequence>

            {/* POS: 25-50s (frames 750-1499) */}
            <Sequence from={FPS * 25} durationInFrames={FPS * 25}>
                <POS />
            </Sequence>

            {/* Inventario: 50-70s (frames 1500-2099) */}
            <Sequence from={FPS * 50} durationInFrames={FPS * 20}>
                <Inventario />
            </Sequence>

            {/* Outro: 70-80s (frames 2100-2399) */}
            <Sequence from={FPS * 70} durationInFrames={FPS * 10}>
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
                fontFamily: 'Inter, sans-serif',
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
                    color: '#F9FAFB',
                    fontSize: 48,
                    fontWeight: 700,
                    marginBottom: 12,
                }}
            >
                FerrERP
            </h1>
            <p
                style={{
                    color: '#9CA3AF',
                    fontSize: 20,
                    marginBottom: 40,
                }}
            >
                ferrerp.com
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
        </AbsoluteFill>
    );
};
