import type {ReactNode} from 'react';
import type {Viewport} from 'next';
import './styles.css';
import I18n from './lib/I18n';
export const metadata = { title: 'ArchAItect · Plot Intelligence', description: 'Explainable building concepts — prototype' };
export const viewport: Viewport = { colorScheme: 'dark', themeColor: '#111112' };
export default function Layout({children}:{children:ReactNode}) {return <html lang="en"><body>{children}<I18n /></body></html>}
