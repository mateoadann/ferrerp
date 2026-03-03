import { Composition } from 'remotion';
import { Demo } from './Demo';

/* Duración: 80 segundos a 30fps = 2400 frames */
const FPS = 30;
const DURACION_SEGUNDOS = 80;

export const RemotionRoot: React.FC = () => {
    return (
        <Composition
            id="Demo"
            component={Demo}
            durationInFrames={FPS * DURACION_SEGUNDOS}
            fps={FPS}
            width={1280}
            height={720}
        />
    );
};
