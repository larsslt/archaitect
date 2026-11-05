import {PHASE_DEVELOPMENT_SERVER} from 'next/constants.js';
// Keep validation builds from overwriting the live development server's chunks.
export default (phase) => ({distDir: phase === PHASE_DEVELOPMENT_SERVER ? '.next' : '.next-build'});
