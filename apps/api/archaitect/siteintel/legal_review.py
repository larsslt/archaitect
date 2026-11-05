"""Evidence-aware Hessen pre-assessment. No count of checks can certify legal admissibility."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime,timezone,date
from . import hessen_sources

HBO_PDF='https://wirtschaft.hessen.de/sites/wirtschaft.hessen.de/files/2026-04/hbo_broschuere_stand_oktober_2025-baupaket_i.pdf'
HBO_SHA256='32b2708ac7fb2f1a433a04e1f0c54bd76e28f2790ed74565363be668eea1e437'
# Topics are a declared screening scope, not a claim to have codified every provision.
TOPICS=[
 ('law_basis','Rechtsstand und anwendbare Gesetzesfassungen','hbo','Rechtsstand, Übergangsrecht und für den konkreten Plan maßgebliche BauNVO-/HBO-Fassungen zuordnen.'),
 ('use','Vorhaben, Nutzung, Gebäudeklasse und Sonderbau','hbo','Nutzung, Einheiten, Aufenthaltsraumhöhe, Gebäudeklasse und anwendbare Sondervorschriften feststellen.'),
 ('plan_law','Planungsrecht: § 30 / § 34 / § 35 BauGB','baugb','Anwendbare Rechtsgrundlage, Gebietstyp, gesicherte Erschließung und ggf. Einfügen/Befreiungen feststellen.'),
 ('plan_scope','Geltende Planfassung, Teilgebiet und Änderungen','baugb','Baugrundstück exakt zuordnen, Wirksamkeit, Änderungen, Überlagerungen und Teilgebiet am Original prüfen.'),
 ('grz','Grundflächen und Nebenanlagen','baunvo','GRZ und Nebenanlagen/Zufahrten/Versiegelung vollständig nach der für den Plan maßgeblichen Fassung erfassen.'),
 ('gfz','Geschossflächen und Vollgeschosse','baunvo','Vollgeschosskriterien und zusätzliche Anrechnung von Dach-/Untergeschossen sowie Plan-Ausnahmen feststellen.'),
 ('heights','First, Traufe, Attika und Höhenbezug','hbo','Maßgeblichen Messpunkt und Bezug (Rohboden, Straße, Gelände) je Dachtyp prüfen.'),
 ('roof','Dachform, Dachneigung und Gestaltung','hbo','Dachvorgaben und örtliche Gestaltungssatzung einschließlich Ausnahmen prüfen.'),
 ('envelope','Baugrenzen, Baulinien, Bauweise','baugb','Echte Baugrenzen und Baulinien digitalisieren/bestätigen; Abstandspuffer ist kein Baufensterbeleg.'),
 ('setbacks','Abstandsflächen und Grenzbebauung','hbo','Geländebezug je Wand, Dachaufbauten, Überdeckungen, Grenzgaragen, Nachbarrechte und Ausnahmen prüfen.'),
 ('easements','Baulasten, Dienstbarkeiten, Bestandsrechte','hbo','Aktuelle grundstücksbezogene Auskünfte, Rechte und bestehende Genehmigungen beiziehen.'),
 ('access','Zufahrt, Erschließung und Feuerwehrflächen','hbo','Rechtliche Sicherung, Breiten, Feuerwehrzufahrt, Rettungsgeräte und Löschwasser nachweisen.'),
 ('parking','Stellplätze und Fahrradabstellplätze','hbo','Aktuelle kommunale Satzung, Nutzung, Anzahl, Abmessungen und örtliche Sonderregeln prüfen.'),
 ('fire','Brandschutz und Rettungswege','hbo','Gebäudeklasse, Brandabschnitte, Bauteilanforderungen, zwei Rettungswege und notwendige Bescheinigungen prüfen.'),
 ('structure','Standsicherheit und Baugrund','hbo','Tragwerks-, Baugrund- und gegebenenfalls Prüf-/Nachweisberechtigtenunterlagen beiziehen.'),
 ('accessibility','Barrierefreiheit','hbo','Anwendbarkeit, Wohnungen/öffentlich zugängliche Bereiche, Wege, Türen und Sanitärräume prüfen.'),
 ('energy','Energie und Wärmeschutz','geg','Anwendbare Fassung des GModG/GEG und Übergangsrecht, Energiebedarf, Anlagentechnik und erforderliche Nachweise prüfen.'),
 ('noise','Schall, Immissionen und Nachbarschutz','bauvorlagen','Schall-/Immissionsnachweise, Nutzungen, Anlagen und relevante Konflikte beiziehen.'),
 ('drainage','Entwässerung, Niederschlagswasser, Leitungen','whg','Entwässerungssatzung, Anschluss-/Versickerungsnachweise und tatsächliche Leitungsauskünfte prüfen.'),
 ('flood','Hochwasser, Gewässer und Wasserrecht','whg','Räumliche Treffer, Gewässerrandstreifen, Verbote, erforderliche Ausnahmen und Genehmigungen prüfen.'),
 ('nature','Natur-, Arten-, Baum- und Bodenschutz','bnatschg','Schutzgebiete, Artenprüfung, Baumschutz, Pflanzgebote, Ausgleich und Baufeldfreimachung prüfen.'),
 ('heritage','Denkmal- und archäologischer Schutz','baubehoerden','Aktuelle Betroffenheit, Umgebungsschutz und notwendige denkmalrechtliche Freigaben prüfen.'),
 ('contamination','Altlasten und frühere Bodennutzungen','baubehoerden','Aktuelle grundstücksbezogene Bodenauskunft/Gutachten; alte Begründung ersetzt keine aktuelle Auskunft.'),
 ('local_statutes','Weitere kommunale Satzungen','baugb','Gestaltung, Erhaltung, Sanierung, Veränderungssperre, Baumschutz und sonstige örtliche Satzungen prüfen.'),
 ('technical','Technische Baubestimmungen und Bauprodukte','bautechnik','Anwendbare H-VV TB, Produkt-/Bauartnachweise und technische Anforderungen fachlich prüfen.'),
 ('procedure','Verfahren, Bauvorlagen und Fachgenehmigungen','bauvorlagen','Verfahrensart, Entwurfsverfasser, Unterschriften, Bauvorlagen und sonstige notwendige Entscheidungen prüfen.'),
 ('other_law','Weitere fallbezogene Rechtsbereiche','baubehoerden','Je Lage/Nutzung z. B. Straßen-, Forst-, Luftverkehrs-, Berg-, Arbeitsstätten- oder Sonderbaurecht gesondert abklären.'),
]
TOPIC_IDS={x[0] for x in TOPICS}
PARCEL_TOPICS={'easements','contamination','plan_scope'}
GEO_TOPICS={
    'flood':({'hq100'}, {'hq100'}),
    'nature':({'nsg','nationalpark','naturmonument','ffh','vsg','lsg','biosphaere','naturpark'}, {'schutzgebiete'}),
    'heritage':({'denkmal','archaeologie'}, {'denkmal'}),
}


def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def assess(*,meta,assessment,pack,planning,sources,spec,checks,records,site_signature,model_signature,inputs_signature):
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds');today=date.today()
    muni=(assessment.land_value.gemeinde if assessment.land_value else None) or meta.get('gemeinde')
    entry=hessen_sources.municipality_entry(muni,sources)
    land=assessment.parcel.land if assessment.parcel else None
    rows=[]
    plan_current=not planning.get('stale_geometry') and planning.get('state')=='done'
    plans=planning.get('plans',[]) if plan_current else []
    docs=planning.get('documents',[]) if plan_current else []
    counts={'planfassungen':len(plans),'dokumente':len(docs),'fundstellen':len(planning.get('evidence',[])) if plan_current else 0}
    links={x['id']:x for x in sources.get('sources',[])}
    active=[];invalid=[]
    superseded={r['supersedes'] for r in records if r.get('supersedes')}
    for rec in records:
        why='Durch späteren Nachweis ersetzt.' if rec['id'] in superseded else None
        if rec['site_signature']!=site_signature:why='Andere Flurstücksauswahl.'
        elif rec['scope']=='parcel' and rec['topic'] not in PARCEL_TOPICS:why='Dieser Prüfbereich erfordert einen Gebäudebezug.'
        elif rec['scope']=='model' and (not model_signature or not rec.get('model_signature')):why='Gebäudebezug fehlt.'
        elif rec.get('model_signature') and rec['model_signature']!=model_signature:why='Anderer Gebäudestand.'
        elif rec.get('inputs_signature') and rec['inputs_signature']!=inputs_signature:why='Planunterlagen, Gelände oder Prüfgrundlagen geändert.'
        elif date.fromisoformat(rec['valid_until'])<today:why='Gültigkeitsdatum überschritten.'
        (invalid if why else active).append({**rec,**({'invalid_reason':why} if why else {})})
    for key,title,source_id,need in TOPICS:
        applicable=[r for r in active if r['topic']==key]
        evidence_state='MISSING';finding='Kein ausreichender projektbezogener Nachweis dokumentiert.'
        if key=='plan_scope':
            finding=f"{len(plans)} räumlich zugeordnete/zugehörige Planfassungen. Teilgebiet und Rechtswirkung sind nicht automatisch bestätigt." if plans else 'Keine aktuell anwendbare Planfassung bestätigt; kein Treffer bedeutet nicht Planfreiheit.'
        elif key=='setbacks':finding='Grundformel aus HBO-Primärtext belegt; Modell-Gelände, Ausnahmen und Grenzbauten erfordern projektbezogene Prüfung.'
        elif key in GEO_TOPICS:
            kinds,_=GEO_TOPICS[key]
            hits=[x for x in assessment.protections if x.kind in kinds]
            finding=f'{len(hits)} Hinweise aus angebundenen Geodaten. Weder Treffer noch fehlender Treffer entscheiden allein die rechtliche Zulässigkeit.'
        if applicable:
            evidence_state='CONFLICT' if any(r['outcome']=='conflict' for r in applicable) else 'DOCUMENTED'
            finding='Widerspruch in dokumentierter Fachprüfung.' if evidence_state=='CONFLICT' else 'Projektbezogene Aussage dokumentiert; externe Fachprüfung, kein automatischer Rechtsnachweis.'
        geo=None
        if key in GEO_TOPICS:
            kinds,source_ids=GEO_TOPICS[key]
            geo={'hits':[x.model_dump(mode='json') for x in assessment.protections if x.kind in kinds],
                 'sources':[{'id':sid,'status':next((s.status for s in assessment.data_status if s.source_id==sid),'NOT_CONNECTED'),
                   'detail':next((s.detail for s in assessment.data_status if s.source_id==sid),None),
                   'cached':next((s.cached for s in assessment.data_status if s.source_id==sid),False),
                   'reference':next((s.model_dump(mode='json') for s in assessment.sources if s.id==sid),None)} for sid in sorted(source_ids)],
                 'scope_notice':'Treffer beziehen sich auf die ursprüngliche Grundstücksanalyse, nicht automatisch auf später ergänzte Flurstücke. Schutzgebiete werden nur am Punkt abgefragt. Fehlende Treffer und Dienstausfälle sind kein Negativnachweis; bei Cache ist das tatsächliche Datenalter nicht bekannt.'}
        rows.append({'id':key,'title':title,'status':evidence_state,'finding':finding,'required_evidence':need,'geodata':geo,
            'automation':'document_scope_and_numbers' if key in ('plan_scope','grz','gfz','heights','roof','envelope') else 'geometry_approximation' if key=='setbacks' else 'geodata_indications' if key in ('flood','nature','heritage') else 'expert_evidence_required',
            'source':links.get(source_id,{'id':source_id,**hessen_sources.SOURCE_DEFS[source_id],'status':'NOT_RETRIEVED'}),
            'evidence':applicable})
    for c in checks:
        c['meaning']='Rechen-/Geometrieprüfung am vereinfachten Baukörpermodell, keine vollständige Rechtsprüfung.'
        if c['id'] in ('GRZ2','GFZ','STOREYS','HEIGHT','EAVE','ENVELOPE','HBO_ABSTAND','ROOF','PITCH'):
            c['legal_status']='REVIEW_REQUIRED'
    failed=[c for c in checks if c['status']=='FAIL']
    missing=[r for r in rows if r['status']=='MISSING']
    conflicts=[r for r in rows if r['status']=='CONFLICT']
    # Even a fully documented checklist is not an approval or completeness proof for every legal field.
    overall='OUT_OF_SCOPE' if land not in (None,'06') else 'CONFLICTS_FOUND' if failed or conflicts else 'REVIEW_INCOMPLETE' if missing else 'EXPERT_REVIEW_DOCUMENTED'
    return {'hbo_rule_source':{'url':HBO_PDF+'#page=16','sha256':HBO_SHA256,'verified_on':'2026-11-02','scope':'Nur Grundformel und Dachanrechnung § 6 Abs. 4–5 visuell gegen den Primärtext geprüft; keine vollständige Projektauslegung.'},'schema':'archaitect.hessen-legal-review/1','generated_at':stamp,'project_id':meta['id'],
        'jurisdiction':'Hessen' if land=='06' else 'nicht amtlich bestätigt','scope':'Vorprüfung eines Wohngebäudevorhabens; Sonder- und weitere fallbezogene Vorschriften separat prüfen.',
        'overall':overall,'legally_complete':False,'permit_issued':False,'automatic_legal_approval':False,
        'municipality':muni,'municipal_entry':entry,'directory_entries':len(sources.get('municipalities',[])),
        'directory_state':sources.get('state','missing'),'plan_data':counts,'source_receipts':sources.get('sources',[]),
        'site_signature':site_signature,'model_signature':model_signature,'inputs_signature':inputs_signature,
        'model_present':bool(spec),'calculated_checks':checks,'review_topics':rows,'invalidated_evidence':invalid,
        'summary':{'topics':len(rows),'documented':len(rows)-len(missing)-len(conflicts),'missing':len(missing),'evidence_conflicts':len(conflicts),'calculation_conflicts':len(failed)},
        'next_actions':[{'topic':r['id'],'title':r['title'],'action':r['required_evidence']} for r in rows if r['status']=='MISSING'],
        'limitations':['Kein Ersatz für bauvorlageberechtigte Planung, technische Nachweise oder behördliche Entscheidungen.',
          'Quellenabruf und eine Liste kommunaler Links belegen keine vollständige Plan-/Satzungserfassung oder aktuellen Rechtsstand.',
          'Baukörpermodell bildet insbesondere Vollgeschoss-/GFZ-Sonderregeln, Anlagen, reale Baugrenzen und Höhenbezug nicht vollständig rechtssicher ab.',
          'Dokumentierte Nachweise sind zugeschriebene Aussagen der genannten prüfenden Person; ihre Identität und fachliche Berechtigung werden nicht automatisch verifiziert.']}
