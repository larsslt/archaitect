'use client';
/* Shared top navigation of a project: Projekte › Grundstück & Daten › Entwurf. */
import Link from 'next/link';
import {Building2, ChevronRight} from 'lucide-react';
import './projectsteps.css';

export type StepKey = 'plan' | 'entwurf' | 'studio';

export default function ProjectSteps({pid, active, name}: {pid: string; active: StepKey; name?: string}) {
  return (
    <nav className="psteps" aria-label="Projektschritte">
      <Link href="/" className="psteps-home" aria-label="Zu den Projekten"><Building2 size={15} />Projekte</Link>
      <ChevronRight size={13} className="sep" />
      {name && <><span className="pname" title={name}>{name}</span><ChevronRight size={13} className="sep" /></>}
      <Link href={`/hessen/plan?p=${pid}`} className={active === 'plan' ? 'on' : ''} aria-current={active === 'plan' ? 'step' : undefined}><b>1</b>Grundstück &amp; Daten</Link>
      <ChevronRight size={13} className="sep" />
      <Link href={`/entwurf?p=${pid}`} className={active === 'entwurf' ? 'on' : ''} aria-current={active === 'entwurf' ? 'step' : undefined}><b>2</b>Entwurf</Link>
    </nav>
  );
}
