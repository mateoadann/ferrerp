import { useEffect } from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { colores, fontFamily, loadFonts } from './config';
import { Intro } from './scenes/Intro';
import { Dashboard } from './scenes/Dashboard';
import { Productos } from './scenes/Productos';
import { Reportes } from './scenes/Reportes';

/*
 * Composición principal del video demo de FerrERP.
 * Duración total: 38 segundos.
 *
 * Escenas:
 * 1. Intro (0-3s)          → Logo animado + nombre
 * 2. Dashboard (3-13s)     → Métricas, gráfico de ventas, alertas
 * 3. Productos (13-23s)    → Tabla de productos con filtros
 * 4. Reportes (23-33s)     → Reporte de ventas con gráficos
 * 5. Outro (33-38s)        → CTA final
 */

const FPS = 30;

export const Demo: React.FC = () => {
    useEffect(() => { loadFonts(); }, []);

    return (
        <AbsoluteFill style={{ backgroundColor: colores.background }}>
            {/* Intro: 0-3s */}
            <Sequence from={0} durationInFrames={FPS * 3}>
                <Intro />
            </Sequence>

            {/* Dashboard: 3-13s */}
            <Sequence from={FPS * 3} durationInFrames={FPS * 10}>
                <Dashboard />
            </Sequence>

            {/* Productos: 13-23s */}
            <Sequence from={FPS * 13} durationInFrames={FPS * 10}>
                <Productos />
            </Sequence>

            {/* Reportes: 23-33s */}
            <Sequence from={FPS * 23} durationInFrames={FPS * 10}>
                <Reportes />
            </Sequence>

            {/* Outro: 33-38s */}
            <Sequence from={FPS * 33} durationInFrames={FPS * 5}>
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
                ferrerp.app
            </p>
        </AbsoluteFill>
    );
};
