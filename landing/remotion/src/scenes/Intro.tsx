import {
    AbsoluteFill,
    interpolate,
    spring,
    useCurrentFrame,
    useVideoConfig,
} from 'remotion';
import { colores } from '../Demo';

/* Escena de introducción: logo animado + nombre FerrERP */
export const Intro: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    /* Animación del logo (escala + opacidad) */
    const logoScale = spring({ frame, fps, config: { damping: 12, mass: 0.8 } });
    const logoOpacity = interpolate(frame, [0, 15], [0, 1], {
        extrapolateRight: 'clamp',
    });

    /* Animación del texto (aparece después del logo) */
    const textOpacity = interpolate(frame, [20, 40], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
    });
    const textY = interpolate(frame, [20, 40], [20, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
    });

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
            {/* Logo */}
            <div
                style={{
                    width: 100,
                    height: 100,
                    backgroundColor: colores.primary,
                    borderRadius: 20,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: 52,
                    fontWeight: 700,
                    transform: `scale(${logoScale})`,
                    opacity: logoOpacity,
                    marginBottom: 24,
                }}
            >
                F
            </div>

            {/* Nombre */}
            <div
                style={{
                    opacity: textOpacity,
                    transform: `translateY(${textY}px)`,
                }}
            >
                <h1
                    style={{
                        color: '#F9FAFB',
                        fontSize: 56,
                        fontWeight: 700,
                        textAlign: 'center',
                        marginBottom: 8,
                    }}
                >
                    FerrERP
                </h1>
                <p
                    style={{
                        color: '#9CA3AF',
                        fontSize: 22,
                        textAlign: 'center',
                    }}
                >
                    Sistema de gestión para ferreterías
                </p>
            </div>
        </AbsoluteFill>
    );
};
