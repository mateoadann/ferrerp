import { Composition } from 'remotion';
import { Demo } from './Demo';

/* Duración: 65 segundos a 30fps = 1950 frames */
const FPS = 30;
const DURACION_SEGUNDOS = 65;

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
