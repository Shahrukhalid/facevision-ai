import { Lock } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useApp } from '../lib/store';

export default function AuthNotice({ what = 'use face recognition' }: { what?: string }) {
  const { auth } = useApp();
  if (!auth || auth.signed_in) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-info/30 bg-info/10 px-4 py-3 text-sm">
      <Lock className="h-4 w-4 text-info" />
      <span className="flex-1 text-fog-100">
        {auth.configured ? `Sign in to ${what}.` : `Set an access passphrase to ${what}. It protects enrolled faces, which are stored encrypted.`}
      </span>
      <Link to="/settings#access" className="rounded-lg bg-info/20 px-3 py-1.5 text-info hover:bg-info/30">
        {auth.configured ? 'Sign in' : 'Set up access'}
      </Link>
    </div>
  );
}
