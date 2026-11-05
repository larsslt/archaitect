import {redirect} from 'next/navigation';
export default async function LegacyStudio({searchParams}:{searchParams:Promise<{p?:string}>}) {
  const {p}=await searchParams;
  redirect(p && /^p_[a-f0-9]{12}$/.test(p) ? `/entwurf?p=${p}` : '/');
}
